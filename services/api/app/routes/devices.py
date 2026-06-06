from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.audit import record_audit
from app.device_adapter import (
    DeviceRegistryUnavailable,
    execute_device_control,
    get_device,
    list_devices as list_registered_devices,
)
from app.device_rate_limit import assess_device_control_rate_limit, record_device_control_execution
from app.models import (
    ControlDeviceRequest,
    ControlDeviceResponse,
    Device,
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
