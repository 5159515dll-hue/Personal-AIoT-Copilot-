from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.audit import record_audit
from app.device_adapter import (
    DeviceRegistryUnavailable,
    execute_device_control,
    get_device,
    list_devices as list_registered_devices,
)
from app.device_connections import (
    create_managed_device,
    delete_managed_device,
    list_managed_devices,
    mark_managed_device_offline,
    update_managed_device,
)
from app.device_credentials import get_device_credential, issue_device_token, list_device_credentials
from app.device_rate_limit import assess_device_control_rate_limit, record_device_control_execution
from app.models import (
    ControlDeviceRequest,
    ControlDeviceResponse,
    DeviceBatchManagementFailure,
    DeviceBatchManagementRequest,
    DeviceBatchManagementResponse,
    Device,
    DeviceCredentialIssueResponse,
    DeviceCredentialPublic,
    DeviceManagementCreate,
    DeviceManagementDeleteResponse,
    DeviceManagementResponse,
    DeviceManagementUpdate,
    DeviceOfflineRequest,
    ManagedDevice,
    PolicyResult,
)
from app.policy import assess_device_control

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[Device])
def list_devices(source: Literal["auto", "mock", "database"] = Query("auto")) -> list[Device]:
    try:
        return list_registered_devices(source)
    except DeviceRegistryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/management", response_model=list[ManagedDevice])
def get_device_management(limit: int = Query(500, ge=1, le=1000)) -> list[ManagedDevice]:
    try:
        return list_managed_devices(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备管理后台查询失败，请检查 DATABASE_URL 和数据库服务状态。") from exc


@router.get("/credentials", response_model=list[DeviceCredentialPublic])
def get_device_credentials() -> list[DeviceCredentialPublic]:
    return list_device_credentials()


@router.post("/{device_id}/credentials", response_model=DeviceCredentialIssueResponse)
def issue_device_credentials(device_id: str) -> DeviceCredentialIssueResponse:
    credential, token = issue_device_token(device_id)
    audit = record_audit(
        actor="user",
        action="issue_device_credential",
        result="success",
        details=f"设备令牌已生成或轮换：{device_id}。",
        parameters={"device_id": device_id, "token_preview": credential.token_preview},
    )
    public_credential = get_device_credential(device_id)
    if public_credential is None:
        raise HTTPException(status_code=500, detail="设备令牌生成后读取失败。")
    return DeviceCredentialIssueResponse(
        credential=public_credential,
        token=token,
        audit_log_id=audit.id,
    )


@router.post("/management", response_model=DeviceManagementResponse)
def create_device_management(request: DeviceManagementCreate) -> DeviceManagementResponse:
    try:
        item = create_managed_device(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备创建失败，请检查 DATABASE_URL 和数据库服务状态。") from exc

    audit = record_audit(
        actor="user",
        action="create_device_management",
        result="success",
        details=f"设备后台档案已创建：{item.device.id}。",
        parameters={
            "device_id": item.device.id,
            "binding_status": item.binding_status,
            "risk_level": item.device.risk_level.value,
            "controllable": item.device.controllable,
            "load_mark": item.load_mark,
        },
    )
    return DeviceManagementResponse(item=item, audit_log_id=audit.id)


@router.patch("/{device_id}/management", response_model=DeviceManagementResponse)
def update_device_management(device_id: str, request: DeviceManagementUpdate) -> DeviceManagementResponse:
    try:
        item = update_managed_device(device_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备管理更新失败，请检查 DATABASE_URL 和数据库服务状态。") from exc

    audit = record_audit(
        actor="user",
        action="update_device_management",
        result="success",
        details=f"设备后台配置已更新：{item.device.id}。",
        parameters={
            "device_id": item.device.id,
            "binding_status": item.binding_status,
            "risk_level": item.device.risk_level.value,
            "controllable": item.device.controllable,
            "connected_appliance": item.device.connected_appliance,
            "load_mark": item.load_mark,
        },
    )
    return DeviceManagementResponse(item=item, audit_log_id=audit.id)


@router.delete("/{device_id}/management", response_model=DeviceManagementDeleteResponse)
def delete_device_management(device_id: str) -> DeviceManagementDeleteResponse:
    try:
        item = delete_managed_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备删除失败，请检查 DATABASE_URL 和数据库服务状态。") from exc

    audit = record_audit(
        actor="user",
        action="delete_device_management",
        result="success",
        details=f"设备后台档案已删除：{item.device.id}。历史遥测数据保留，硬件重新上报后会以只读档案重新进入后台。",
        parameters={
            "device_id": item.device.id,
            "binding_status": item.binding_status,
            "connection_removed": item.connection is not None,
        },
    )
    return DeviceManagementDeleteResponse(deleted=True, device_id=item.device.id, audit_log_id=audit.id)


@router.post("/{device_id}/offline", response_model=DeviceManagementResponse)
def offline_device(device_id: str, request: DeviceOfflineRequest) -> DeviceManagementResponse:
    try:
        item = mark_managed_device_offline(device_id, request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备下线失败，请检查 DATABASE_URL 和数据库服务状态。") from exc

    audit = record_audit(
        actor="user",
        action="offline_device",
        result="success",
        details=f"设备已由后台手动下线：{item.device.id}。",
        parameters={"device_id": item.device.id, "reason": request.reason},
    )
    return DeviceManagementResponse(item=item, audit_log_id=audit.id)


@router.post("/batch-management", response_model=DeviceBatchManagementResponse)
def batch_update_device_management(request: DeviceBatchManagementRequest) -> DeviceBatchManagementResponse:
    updated: list[ManagedDevice] = []
    failed: list[DeviceBatchManagementFailure] = []
    for item in request.items:
        try:
            if item.offline:
                managed = mark_managed_device_offline(item.device_id, item.offline_reason or "批量设备管理下线")
            else:
                managed = update_managed_device(item.device_id, item)
            updated.append(managed)
        except Exception as exc:
            failed.append(DeviceBatchManagementFailure(device_id=item.device_id, error=str(exc).strip("'")))
    audit = record_audit(
        actor="user",
        action="batch_update_device_management",
        result="success" if not failed else "failed",
        details=f"批量设备管理完成：成功 {len(updated)} 个，失败 {len(failed)} 个。",
        parameters={
            "updated": [item.device.id for item in updated],
            "failed": [item.model_dump() for item in failed],
        },
    )
    for managed in updated:
        managed.management_flags.append(f"批量审计编号：{audit.id}")
    return DeviceBatchManagementResponse(updated=updated, failed=failed)


@router.post("/{device_id}/control", response_model=ControlDeviceResponse)
def control_device(
    device_id: str,
    request: ControlDeviceRequest,
    source: Literal["auto", "mock", "database"] = Query("auto"),
) -> ControlDeviceResponse:
    try:
        device = get_device(device_id, source)
    except DeviceRegistryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if device is None:
        policy = assess_device_control(
            device=None,
            requested_state=request.state,
            confirmed=request.confirmed,
            intent=request.reason,
        )
        audit = record_audit(
            actor="user",
            action="control_device",
            result="blocked",
            details=policy.reason,
            parameters={"device_id": device_id, **request.model_dump()},
            policy=policy,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "message": "设备不存在",
                "policy": policy.model_dump(mode="json"),
                "audit_log_id": audit.id,
            },
        )

    policy = assess_device_control(
        device=device,
        requested_state=request.state,
        confirmed=request.confirmed,
        intent=request.reason,
    )
    if policy.result == PolicyResult.allowed:
        policy = assess_device_control_rate_limit(device) or policy
    if policy.result == PolicyResult.allowed:
        if device.requires_confirmation and request.confirmed:
            record_audit(
                actor="user",
                action="confirm_device_control",
                result="success",
                details=f"用户已确认控制中风险设备：{device.name} -> {request.state}。",
                parameters={"device_id": device_id, **request.model_dump()},
                policy=policy,
            )
        device = execute_device_control(device, request.state, source)
        record_device_control_execution(device.id, "user")
        result = "success"
        details = "模拟设备状态已更新。"
    elif policy.result == PolicyResult.requires_confirmation:
        result = "requires_confirmation"
        details = policy.reason
    else:
        result = "blocked"
        details = policy.reason

    audit = record_audit(
        actor="user",
        action="control_device",
        result=result,
        details=details,
        parameters={"device_id": device_id, **request.model_dump()},
        policy=policy,
    )
    return ControlDeviceResponse(
        policy=policy,
        execution_result=result,  # type: ignore[arg-type]
        audit_log_id=audit.id,
        device=device if result == "success" else None,
    )
