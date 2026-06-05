from __future__ import annotations

from datetime import timedelta

from app.models import Device, DeviceControlRateEvent, PolicyDecision, PolicyResult
from app.storage import JsonListStore
from app.time_utils import now

CONTROL_RATE_LIMIT_WINDOW = timedelta(seconds=10)
CONTROL_RATE_LIMIT_MAX_EXECUTIONS = 2

device_control_rate_store = JsonListStore("device_control_rate_events.json", DeviceControlRateEvent)


def assess_device_control_rate_limit(device: Device | None) -> PolicyDecision | None:
    if device is None or not device.controllable:
        return None

    cutoff = now() - CONTROL_RATE_LIMIT_WINDOW
    recent = [
        event
        for event in device_control_rate_store.list()
        if event.device_id == device.id and event.timestamp >= cutoff
    ]
    if len(recent) < CONTROL_RATE_LIMIT_MAX_EXECUTIONS:
        return None

    window_seconds = int(CONTROL_RATE_LIMIT_WINDOW.total_seconds())
    return PolicyDecision(
        result=PolicyResult.denied,
        risk_level=device.risk_level,
        requires_confirmation=False,
        reason=f"{device.name} 控制请求过于频繁，已触发速率限制。",
        constraints=[
            f"{window_seconds} 秒内同一设备最多执行 {CONTROL_RATE_LIMIT_MAX_EXECUTIONS} 次模拟控制。",
            "请等待一段时间后再重试，避免连续误触或自动化循环。",
        ],
    )


def record_device_control_execution(device_id: str, actor: str) -> DeviceControlRateEvent:
    cutoff = now() - CONTROL_RATE_LIMIT_WINDOW
    retained = [event for event in device_control_rate_store.list() if event.timestamp >= cutoff]
    event = DeviceControlRateEvent(
        device_id=device_id,
        actor=actor,  # type: ignore[arg-type]
        timestamp=now(),
    )
    device_control_rate_store.replace_all([*retained, event])
    return event
