from __future__ import annotations

from app.database import (
    get_device_registry_db,
    list_device_connections_db,
    record_device_heartbeat_db,
    upsert_device_connection_db,
    upsert_device_registry_db,
)
from app.models import (
    Device,
    DeviceConnectionRecord,
    DeviceHeartbeatRequest,
    DeviceRegistrationRequest,
    DeviceState,
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
