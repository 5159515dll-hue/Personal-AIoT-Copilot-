from __future__ import annotations

from app.database import (
    database_url,
    delete_device_connection_db,
    delete_device_registry_device_db,
    get_device_registry_db,
    list_device_registry_db,
    list_device_connections_db,
    record_device_heartbeat_db,
    upsert_device_connection_db,
    upsert_device_registry_device_db,
    upsert_device_registry_db,
)
from app.models import (
    Device,
    DeviceConnectionRecord,
    DeviceManagementCreate,
    DeviceManagementUpdate,
    DeviceHeartbeatRequest,
    DeviceRegistrationRequest,
    DeviceState,
    ManagedDevice,
    RiskLevel,
    SensorIngestRequest,
)
from app.time_utils import now


def register_device_connection(request: DeviceRegistrationRequest) -> DeviceConnectionRecord:
    timestamp = now()
    record = DeviceConnectionRecord(
        device_id=request.device_id,
        display_name=request.display_name or request.device_id,
        device_type=request.device_type,
        transport=request.transport,
        protocol_version=request.protocol_version,
        firmware_version=request.firmware_version,
        hardware_revision=request.hardware_revision,
        location=request.location,
        capabilities=request.capabilities,
        metadata=request.metadata,
        online_state=DeviceState.online,
        last_seen_at=timestamp,
        last_message_id=None,
        last_sequence=None,
        updated_at=timestamp,
    )
    saved = upsert_device_connection_db(record)
    ensure_read_only_registry_device(saved)
    return saved


def record_heartbeat(device_id: str, request: DeviceHeartbeatRequest) -> DeviceConnectionRecord:
    record = record_device_heartbeat_db(
        device_id,
        transport=request.transport,
        protocol_version=request.protocol_version,
        firmware_version=request.firmware_version,
        status=request.status,
        last_seen_at=request.sent_at or now(),
        message_id=request.message_id,
        sequence=request.sequence,
        metrics={
            "uptime_seconds": request.uptime_seconds,
            "battery_percent": request.battery_percent,
            "rssi_dbm": request.rssi_dbm,
            **request.metrics,
        },
    )
    ensure_read_only_registry_device(record)
    return record


def record_ingest_connection(request: SensorIngestRequest, *, transport: str) -> DeviceConnectionRecord:
    timestamp = request.sent_at or now()
    capabilities = request.capabilities or _capabilities_from_ingest(request)
    record = DeviceConnectionRecord(
        device_id=request.device_id,
        display_name=request.device_id,
        device_type=request.device_type or "sensor_node",
        transport=transport,
        protocol_version=request.protocol_version,
        firmware_version=request.firmware_version,
        hardware_revision=request.hardware_revision,
        location="unknown",
        capabilities=capabilities,
        metadata=request.metadata,
        online_state=DeviceState.online,
        last_seen_at=timestamp,
        last_message_id=request.message_id,
        last_sequence=request.sequence,
        updated_at=timestamp,
    )
    saved = upsert_device_connection_db(record)
    ensure_read_only_registry_device(saved)
    return saved


def list_connections(limit: int = 500) -> list[DeviceConnectionRecord]:
    return list_device_connections_db(limit=limit)


def list_managed_devices(limit: int = 500) -> list[ManagedDevice]:
    if not database_url():
        raise RuntimeError("未配置 DATABASE_URL，无法访问设备管理后台。")
    devices = list_device_registry_db(seed_devices=[])
    connections = list_device_connections_db(limit=limit)
    by_device_id = {device.id: device for device in devices}
    by_connection_id = {connection.device_id: connection for connection in connections}
    ids = sorted(set(by_device_id) | set(by_connection_id))
    items: list[ManagedDevice] = []
    for device_id in ids:
        device = by_device_id.get(device_id)
        connection = by_connection_id.get(device_id)
        if device is None and connection is not None:
            ensure_read_only_registry_device(connection)
            device = get_device_registry_db(device_id)
        if device is None:
            continue
        items.append(_managed_device(device, connection))
    return items


def create_managed_device(request: DeviceManagementCreate) -> ManagedDevice:
    if not database_url():
        raise RuntimeError("未配置 DATABASE_URL，无法访问设备管理后台。")

    connection = _get_connection(request.device_id)
    if get_device_registry_db(request.device_id) is not None:
        raise ValueError("设备已存在，请使用编辑功能更新。")

    timestamp = now().isoformat()
    device = Device(
        id=request.device_id,
        name=request.name,
        type=request.device_type,
        location=request.location,
        risk_level=RiskLevel.read_only,
        controllable=False,
        requires_confirmation=False,
        online_state=connection.online_state if connection else DeviceState.unknown,
        current_state={
            "transport": request.transport,
            "protocol_version": request.protocol_version,
            "precreated": connection is None,
            "hardware_binding": {
                "bound": connection is not None,
                "updated_at": timestamp,
                "source": "device_management_ui",
            },
        },
    )
    update_request = _create_as_update(request)
    saved_device = upsert_device_registry_device_db(_apply_management_update(device, update_request))

    if connection is not None:
        updated_connection = _apply_connection_update(connection, update_request, saved_device)
        connection = upsert_device_connection_db(
            updated_connection.model_copy(update={"protocol_version": request.protocol_version})
        )
    return _managed_device(saved_device, connection)


def update_managed_device(device_id: str, request: DeviceManagementUpdate) -> ManagedDevice:
    if not database_url():
        raise RuntimeError("未配置 DATABASE_URL，无法访问设备管理后台。")

    connection = _get_connection(device_id)
    device = get_device_registry_db(device_id)
    if device is None and connection is not None:
        ensure_read_only_registry_device(connection)
        device = get_device_registry_db(device_id)
    if device is None:
        raise KeyError("设备不存在，必须先通过注册、心跳或遥测接口建立设备记录。")

    updated_device = _apply_management_update(device, request)
    saved_device = upsert_device_registry_device_db(updated_device)

    if connection is not None:
        updated_connection = _apply_connection_update(connection, request, saved_device)
        connection = upsert_device_connection_db(updated_connection)
    return _managed_device(saved_device, connection)


def delete_managed_device(device_id: str) -> ManagedDevice:
    if not database_url():
        raise RuntimeError("未配置 DATABASE_URL，无法访问设备管理后台。")

    connection = _get_connection(device_id)
    device = get_device_registry_db(device_id)
    if device is None and connection is not None:
        ensure_read_only_registry_device(connection)
        device = get_device_registry_db(device_id)
    if device is None:
        raise KeyError("设备不存在，无法删除。")

    snapshot = _managed_device(device, connection)
    registry_deleted = delete_device_registry_device_db(device_id)
    connection_deleted = delete_device_connection_db(device_id)
    if not registry_deleted and not connection_deleted:
        raise KeyError("设备不存在，无法删除。")
    return snapshot


def mark_managed_device_offline(device_id: str, reason: str) -> ManagedDevice:
    if not database_url():
        raise RuntimeError("未配置 DATABASE_URL，无法访问设备管理后台。")

    timestamp = now()
    connection = _get_connection(device_id)
    device = get_device_registry_db(device_id)
    if device is None and connection is not None:
        ensure_read_only_registry_device(connection)
        device = get_device_registry_db(device_id)
    if device is None:
        raise KeyError("设备不存在，无法下线。")

    state = {
        **device.current_state,
        "admin_offline": {
            "reason": reason,
            "updated_at": timestamp.isoformat(),
        },
    }
    saved_device = upsert_device_registry_device_db(
        device.model_copy(update={"online_state": DeviceState.offline, "current_state": state})
    )

    if connection is not None:
        connection = upsert_device_connection_db(
            connection.model_copy(
                deep=True,
                update={
                    "online_state": DeviceState.offline,
                    "metadata": {
                        **connection.metadata,
                        "admin_offline": {
                            "reason": reason,
                            "updated_at": timestamp.isoformat(),
                        },
                    },
                    "updated_at": timestamp,
                    "last_sequence": None,
                },
            )
        )
    return _managed_device(saved_device, connection)


def ensure_read_only_registry_device(record: DeviceConnectionRecord) -> None:
    if get_device_registry_db(record.device_id) is not None:
        return
    upsert_device_registry_db(
        [
            Device(
                id=record.device_id,
                name=record.display_name,
                type=record.device_type,
                location=record.location,
                risk_level=RiskLevel.read_only,
                controllable=False,
                requires_confirmation=False,
                online_state=record.online_state,
                current_state={
                    "transport": record.transport,
                    "protocol_version": record.protocol_version,
                    "firmware_version": record.firmware_version,
                    "capability_count": len(record.capabilities),
                },
            )
        ]
    )


def _capabilities_from_ingest(request: SensorIngestRequest):
    from app.models import DeviceCapability

    metrics = sorted({item.metric for item in request.readings}, key=lambda item: item.value)
    return [DeviceCapability(kind="telemetry", metrics=metrics, description="遥测指标上报")]


def _create_as_update(request: DeviceManagementCreate) -> DeviceManagementUpdate:
    payload = request.model_dump(exclude={"device_id", "protocol_version"})
    return DeviceManagementUpdate(**payload)


def _get_connection(device_id: str) -> DeviceConnectionRecord | None:
    matches = [connection for connection in list_device_connections_db(limit=1000) if connection.device_id == device_id]
    return matches[0] if matches else None


def _apply_management_update(device: Device, request: DeviceManagementUpdate) -> Device:
    current_state = dict(device.current_state)
    timestamp = now().isoformat()
    load = dict(current_state.get("load") if isinstance(current_state.get("load"), dict) else {})
    if request.load_type is not None:
        load["type"] = request.load_type
    if request.load_label is not None:
        load["label"] = request.load_label
    if request.load_power_watts is not None:
        load["power_watts"] = request.load_power_watts
    if load:
        load["updated_at"] = timestamp
        current_state["load"] = load
    if request.management_note is not None:
        current_state["management_note"] = request.management_note
    if request.tags:
        current_state["tags"] = request.tags
    if request.metadata:
        current_state["management_metadata"] = {**_state_dict(current_state.get("management_metadata")), **request.metadata}
    current_state["hardware_binding"] = {
        "bound": True,
        "updated_at": timestamp,
        "source": "device_management_ui",
    }

    risk_level = request.risk_level or device.risk_level
    controllable = request.controllable if request.controllable is not None else device.controllable
    requires_confirmation = (
        request.requires_confirmation
        if request.requires_confirmation is not None
        else device.requires_confirmation
    )
    if risk_level in {RiskLevel.read_only, RiskLevel.high, RiskLevel.forbidden}:
        controllable = False
        requires_confirmation = False
    if risk_level == RiskLevel.medium and controllable:
        requires_confirmation = True

    return device.model_copy(
        deep=True,
        update={
            "name": request.name or request.display_name or device.name,
            "type": request.device_type or device.type,
            "location": request.location or device.location,
            "risk_level": risk_level,
            "controllable": controllable,
            "requires_confirmation": requires_confirmation,
            "current_state": current_state,
            "connected_appliance": request.connected_appliance if request.connected_appliance is not None else device.connected_appliance,
            "max_active_duration_minutes": (
                request.max_active_duration_minutes
                if request.max_active_duration_minutes is not None
                else device.max_active_duration_minutes
            ),
        },
    )


def _apply_connection_update(
    connection: DeviceConnectionRecord,
    request: DeviceManagementUpdate,
    saved_device: Device,
) -> DeviceConnectionRecord:
    timestamp = now()
    metadata = dict(connection.metadata)
    metadata["registry_binding"] = {
        "risk_level": saved_device.risk_level.value,
        "controllable": saved_device.controllable,
        "requires_confirmation": saved_device.requires_confirmation,
        "updated_at": timestamp.isoformat(),
    }
    if request.metadata:
        metadata["management_metadata"] = {
            **_state_dict(metadata.get("management_metadata")),
            **request.metadata,
        }
    return connection.model_copy(
        deep=True,
        update={
            "display_name": request.display_name or request.name or saved_device.name,
            "device_type": request.device_type or connection.device_type,
            "transport": request.transport or connection.transport,
            "firmware_version": request.firmware_version if request.firmware_version is not None else connection.firmware_version,
            "hardware_revision": request.hardware_revision if request.hardware_revision is not None else connection.hardware_revision,
            "location": request.location or saved_device.location,
            "metadata": metadata,
            "updated_at": timestamp,
            "last_sequence": None,
        },
    )


def _managed_device(device: Device, connection: DeviceConnectionRecord | None) -> ManagedDevice:
    if connection is None:
        binding_status = "registry_only"
    elif device.id == connection.device_id:
        binding_status = "bound"
    else:
        binding_status = "connection_only"

    load_mark = _state_dict(device.current_state.get("load"))
    flags: list[str] = []
    if connection is None:
        flags.append("未见真实连接")
    if device.risk_level in {RiskLevel.read_only, RiskLevel.high, RiskLevel.forbidden} and device.controllable:
        flags.append("风险等级与可控状态不一致")
    if device.risk_level == RiskLevel.low and not load_mark:
        flags.append("低风险设备缺少负载标记")
    if device.online_state == DeviceState.offline:
        flags.append("已下线")
    return ManagedDevice(
        device=device,
        connection=connection,
        binding_status=binding_status,  # type: ignore[arg-type]
        load_mark=load_mark,
        management_flags=flags,
    )


def _state_dict(value) -> dict:
    return value if isinstance(value, dict) else {}
