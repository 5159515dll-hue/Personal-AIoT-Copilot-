from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.mock_data import get_device, get_device_catalog
from app.models import (
    ControlDeviceRequest,
    ControlDeviceResponse,
    Device,
    PolicyResult,
)
from app.policy import assess_device_control

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[Device])
def list_devices() -> list[Device]:
    return get_device_catalog()


@router.post("/{device_id}/control", response_model=ControlDeviceResponse)
def control_device(device_id: str, request: ControlDeviceRequest) -> ControlDeviceResponse:
    device = get_device(device_id)
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
        device.current_state["power"] = request.state
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
