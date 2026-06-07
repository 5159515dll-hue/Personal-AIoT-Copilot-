from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from collections.abc import Callable
from typing import Literal

from app.audit import record_audit
from app.media_store import list_device_events
from app.mock_data import current_room_state
from app.models import AutomationRule, Device, Metric, PolicyResult, RoomState, RuleEvaluation
from app.policy import assess_device_control
from app.rule_store import list_rules, record_rule_trigger
from app.time_utils import now

COMPARATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}

METRIC_ALIASES: tuple[tuple[Metric, tuple[str, ...]], ...] = (
    (Metric.co2, ("二氧化碳", "co2", "carbon dioxide")),
    (Metric.temperature, ("温度", "temperature", "temp")),
    (Metric.humidity, ("湿度", "humidity")),
    (Metric.light, ("光照", "照度", "light", "lux")),
    (Metric.presence, ("人体存在", "有人", "presence", "occupied")),
    (Metric.noise, ("噪声", "噪音", "分贝", "noise", "db", "decibel")),
)


@dataclass(frozen=True)
class MetricCondition:
    metric: Metric
    comparator: Callable[[float, float], bool]
    symbol: str
    threshold: float


@dataclass(frozen=True)
class TimeCondition:
    comparator: Callable[[float, float], bool]
    symbol: str
    minute_of_day: int


@dataclass(frozen=True)
class EventCondition:
    event_types: tuple[str, ...]


@dataclass(frozen=True)
class DeviceAction:
    device: Device
    state: Literal["on", "off"]


def evaluate_automation_rules(
    *,
    room: RoomState | None = None,
    rules: list[AutomationRule] | None = None,
    emit_audit: bool = True,
    telemetry_source: Literal["mock", "database"] = "mock",
) -> list[RuleEvaluation]:
    state = room or current_room_state()
    candidates = rules if rules is not None else list_rules()
    return [
        _evaluate_rule(rule, state, emit_audit=emit_audit, telemetry_source=telemetry_source)
        for rule in candidates
    ]


def _evaluate_rule(
    rule: AutomationRule,
    room: RoomState,
    *,
    emit_audit: bool,
    telemetry_source: Literal["mock", "database"],
) -> RuleEvaluation:
    evaluated_at = now()
    if not rule.enabled:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="disabled",
            reason="规则已暂停，本次未评估触发。",
            evaluated_at=evaluated_at,
        )

    condition = _parse_condition(rule.condition)
    if condition is None:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="unsupported",
            reason="当前版本只支持简单指标阈值、人体存在、时间提醒或边缘事件提醒条件。",
            evaluated_at=evaluated_at,
        )

    if isinstance(condition, TimeCondition):
        return _evaluate_time_rule(
            rule,
            condition,
            evaluated_at=evaluated_at,
            emit_audit=emit_audit,
            telemetry_source=telemetry_source,
        )

    if isinstance(condition, EventCondition):
        return _evaluate_event_rule(
            rule,
            condition,
            evaluated_at=evaluated_at,
            emit_audit=emit_audit,
            telemetry_source=telemetry_source,
        )

    metric = condition.metric
    reading = room.metrics.get(metric)
    if reading is None:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="unsupported",
            reason="当前房间状态缺少该指标，无法评估。",
            evaluated_at=evaluated_at,
        )

    matched = condition.comparator(reading.value, condition.threshold)
    observed = {
        "source": telemetry_source,
        "kind": "metric",
        "metric": metric.value,
        "value": reading.value,
        "unit": reading.unit,
        "threshold": condition.threshold,
        "comparator": condition.symbol,
        "timestamp": reading.timestamp.isoformat(),
    }
    if not matched:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="not_matched",
            reason="当前指标未满足规则条件。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    return _trigger_matched_rule(
        rule,
        observed,
        evaluated_at=evaluated_at,
        emit_audit=emit_audit,
        telemetry_source=telemetry_source,
        reminder_details=f"规则已触发提醒动作：{rule.action}",
        reminder_reason="规则条件已满足，提醒动作已写入审计日志。",
    )


def _evaluate_time_rule(
    rule: AutomationRule,
    condition: TimeCondition,
    *,
    evaluated_at,
    emit_audit: bool,
    telemetry_source: Literal["mock", "database"],
) -> RuleEvaluation:
    current_minutes = evaluated_at.hour * 60 + evaluated_at.minute
    matched = condition.comparator(current_minutes, condition.minute_of_day)
    observed = {
        "source": telemetry_source,
        "kind": "time",
        "current_time": _format_minutes(current_minutes),
        "current_minutes": current_minutes,
        "threshold_time": _format_minutes(condition.minute_of_day),
        "threshold_minutes": condition.minute_of_day,
        "comparator": condition.symbol,
        "timezone": "Asia/Shanghai",
    }
    if not matched:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="not_matched",
            reason="当前时间未满足规则条件。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    return _trigger_matched_rule(
        rule,
        observed,
        evaluated_at=evaluated_at,
        emit_audit=emit_audit,
        telemetry_source=telemetry_source,
        reminder_details=f"时间规则已触发提醒动作：{rule.action}",
        reminder_reason="时间条件已满足，提醒动作已写入审计日志。",
    )


def _evaluate_event_rule(
    rule: AutomationRule,
    condition: EventCondition,
    *,
    evaluated_at,
    emit_audit: bool,
    telemetry_source: Literal["mock", "database"],
) -> RuleEvaluation:
    events = list_device_events(limit=20)
    matched_events = [event for event in events if event.event_type in condition.event_types]
    observed = {
        "source": telemetry_source,
        "kind": "device_event",
        "event_types": list(condition.event_types),
        "matched_event_count": len(matched_events),
        "latest_event": matched_events[0].model_dump(mode="json") if matched_events else None,
    }
    if not matched_events:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=False,
            status="not_matched",
            reason="最近没有满足条件的边缘识别事件。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    if not _is_reminder_action(rule.action):
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=True,
            status="unsupported",
            reason="边缘事件规则第一版只支持提醒动作，不直接触发设备控制。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    return _trigger_matched_rule(
        rule,
        observed,
        evaluated_at=evaluated_at,
        emit_audit=emit_audit,
        telemetry_source=telemetry_source,
        reminder_details=f"边缘事件规则已触发提醒动作：{rule.action}",
        reminder_reason="边缘识别事件已满足规则条件，提醒动作已写入审计日志。",
    )


def _trigger_matched_rule(
    rule: AutomationRule,
    observed: dict,
    *,
    evaluated_at,
    emit_audit: bool,
    telemetry_source: Literal["mock", "database"],
    reminder_details: str,
    reminder_reason: str,
) -> RuleEvaluation:
    if _is_reminder_action(rule.action):
        audit_log_id = None
        if emit_audit:
            audit = record_audit(
                actor="system",
                action="trigger_automation_rule",
                result="success",
                details=reminder_details,
                parameters={
                    "rule_id": rule.id,
                    "condition": rule.condition,
                    "action": rule.action,
                    "observed": observed,
                },
            )
            audit_log_id = audit.id
            record_rule_trigger(rule.id, evaluated_at)

        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=True,
            status="triggered",
            reason=reminder_reason,
            evaluated_at=evaluated_at,
            observed=observed,
            audit_log_id=audit_log_id,
        )

    device_action = _parse_device_action(rule.action)
    if device_action is None:
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=True,
            status="unsupported",
            reason="当前只支持提醒动作，或明确指向单个已登记低风险设备的打开/关闭动作。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    return _trigger_device_action(
        rule,
        device_action,
        observed,
        evaluated_at=evaluated_at,
        emit_audit=emit_audit,
        telemetry_source=telemetry_source,
    )


def _trigger_device_action(
    rule: AutomationRule,
    device_action: DeviceAction,
    observed: dict,
    *,
    evaluated_at,
    emit_audit: bool,
    telemetry_source: Literal["mock", "database"],
) -> RuleEvaluation:
    from app.device_adapter import execute_device_control
    from app.device_rate_limit import assess_device_control_rate_limit, record_device_control_execution

    device = device_action.device
    state = device_action.state
    policy = assess_device_control(
        device=device,
        requested_state=state,
        confirmed=False,
        intent=f"自动化规则：{rule.condition} -> {rule.action}",
    )
    if policy.result == PolicyResult.allowed:
        policy = assess_device_control_rate_limit(device) or policy

    action_observed = {
        **observed,
        "action_kind": "device_control",
        "device_id": device.id,
        "device_name": device.name,
        "requested_state": state,
        "risk_level": device.risk_level.value,
        "policy": policy.model_dump(mode="json"),
    }
    result = "blocked"
    audit_log_id = None
    reason = policy.reason
    if policy.result == PolicyResult.allowed:
        source = "database" if telemetry_source == "database" else "auto"
        updated = execute_device_control(device, state, source)  # type: ignore[arg-type]
        record_device_control_execution(updated.id, "agent")
        action_observed["device_state"] = updated.model_dump(mode="json")
        result = "success"
        reason = "规则条件已满足，低风险设备动作已通过策略检查并写入审计日志。"
    elif policy.result == PolicyResult.requires_confirmation:
        result = "requires_confirmation"
        reason = "规则触发了需要确认的设备动作，系统已阻止自动执行。"

    if emit_audit:
        audit = record_audit(
            actor="system",
            action="trigger_automation_rule_control",
            result=result,
            details=reason,
            parameters={
                "rule_id": rule.id,
                "condition": rule.condition,
                "action": rule.action,
                "observed": action_observed,
            },
            policy=policy,
        )
        audit_log_id = audit.id
        if result == "success":
            record_rule_trigger(rule.id, evaluated_at)

    return RuleEvaluation(
        rule_id=rule.id,
        condition=rule.condition,
        action=rule.action,
        matched=True,
        status="triggered" if result == "success" else "blocked",
        reason=reason,
        evaluated_at=evaluated_at,
        observed=action_observed,
        audit_log_id=audit_log_id,
    )


def _parse_condition(condition: str) -> MetricCondition | TimeCondition | EventCondition | None:
    lowered = condition.lower()
    time_condition = _parse_time_condition(lowered)
    if time_condition is not None:
        return time_condition

    event_condition = _parse_event_condition(lowered)
    if event_condition is not None:
        return event_condition

    metric = _match_metric(lowered)
    if metric is None:
        return None

    if metric == Metric.presence and any(token in lowered for token in ("有人", "occupied", "presence")):
        return MetricCondition(metric=metric, comparator=operator.gt, symbol=">", threshold=0)

    match = re.search(r"(>=|<=|>|<)\s*([0-9]+(?:\.[0-9]+)?)", lowered)
    if not match:
        return None
    comparator = COMPARATORS[match.group(1)]
    threshold = float(match.group(2))
    return MetricCondition(metric=metric, comparator=comparator, symbol=match.group(1), threshold=threshold)


def _parse_event_condition(text: str) -> EventCondition | None:
    if any(token in text for token in ("检测到人", "人体检测", "人体存在事件", "有人事件", "presence_detected")):
        return EventCondition(event_types=("presence_detected", "motion_detected"))
    if any(token in text for token in ("移动侦测", "移动事件", "motion_detected")):
        return EventCondition(event_types=("motion_detected",))
    if any(token in text for token in ("人脸", "face_detected")):
        return EventCondition(event_types=("face_detected",))
    if any(token in text for token in ("情绪", "emotion_detected")):
        return EventCondition(event_types=("emotion_detected",))
    if any(token in text for token in ("视觉事件", "边缘事件", "摄像头事件")):
        return EventCondition(event_types=("presence_detected", "motion_detected", "face_detected", "emotion_detected"))
    return None


def _parse_time_condition(text: str) -> TimeCondition | None:
    hour_compare_match = re.search(r"(?:hour|小时|时间)\s*(>=|<=|>|<)\s*([0-9]{1,2})(?:[:：]([0-5][0-9]))?", text)
    if hour_compare_match:
        return _time_condition_from_parts(
            hour=int(hour_compare_match.group(2)),
            minute=int(hour_compare_match.group(3) or 0),
            symbol=hour_compare_match.group(1),
        )

    english_match = re.search(r"\b(after|before)\s+([0-9]{1,2})(?:[:：]([0-5][0-9]))?\b", text)
    if english_match:
        return _time_condition_from_parts(
            hour=int(english_match.group(2)),
            minute=int(english_match.group(3) or 0),
            symbol=">=" if english_match.group(1) == "after" else "<=",
        )

    clock_match = re.search(r"([01]?[0-9]|2[0-3])\s*[:：]\s*([0-5][0-9])\s*(后|以后|之后|前|以前|之前)?", text)
    if clock_match and any(token in text for token in ("时间", "提醒", "后", "前", "after", "before")):
        return _time_condition_from_parts(
            hour=int(clock_match.group(1)),
            minute=int(clock_match.group(2)),
            symbol=_time_suffix_to_symbol(clock_match.group(3)),
        )

    chinese_match = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|夜间|晚间)?\s*([0-9]{1,2})\s*点\s*(半|[0-5]?[0-9]\s*分?)?\s*(后|以后|之后|前|以前|之前)?",
        text,
    )
    if chinese_match and any(token in text for token in ("时间", "提醒", "点后", "点前", "晚上", "下午", "早上", "上午", "休息")):
        period = chinese_match.group(1) or ""
        hour = _normalize_chinese_hour(period, int(chinese_match.group(2)))
        minute_text = chinese_match.group(3) or ""
        minute = 30 if "半" in minute_text else int(re.sub(r"\D", "", minute_text) or 0)
        return _time_condition_from_parts(
            hour=hour,
            minute=minute,
            symbol=_time_suffix_to_symbol(chinese_match.group(4)),
        )

    return None


def _time_condition_from_parts(*, hour: int, minute: int, symbol: str) -> TimeCondition | None:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    comparator = COMPARATORS.get(symbol)
    if comparator is None:
        return None
    return TimeCondition(comparator=comparator, symbol=symbol, minute_of_day=hour * 60 + minute)


def _time_suffix_to_symbol(suffix: str | None) -> str:
    if suffix in {"前", "以前", "之前"}:
        return "<="
    return ">="


def _normalize_chinese_hour(period: str, hour: int) -> int:
    if period in {"下午", "晚上", "夜间", "晚间"} and 1 <= hour <= 11:
        return hour + 12
    if period == "中午" and hour < 11:
        return hour + 12
    if hour == 24:
        return 0
    return hour


def _format_minutes(minute_of_day: int) -> str:
    hour, minute = divmod(minute_of_day, 60)
    return f"{hour:02d}:{minute:02d}"


def _match_metric(text: str) -> Metric | None:
    for metric, aliases in METRIC_ALIASES:
        if any(alias in text for alias in aliases):
            return metric
    return None


def _is_reminder_action(action: str) -> bool:
    lowered = action.lower()
    return any(token in lowered for token in ("提醒", "通知", "alert", "notify", "message"))


def _parse_device_action(action: str) -> DeviceAction | None:
    lowered = action.lower()
    state = _parse_action_state(lowered)
    if state is None:
        return None

    try:
        from app.device_adapter import list_devices

        devices = list_devices("auto")
    except Exception:
        devices = []

    if not devices:
        return None

    alias_target = _device_alias_target(lowered)
    for device in devices:
        names = {
            device.id.lower(),
            device.name.lower(),
            str(device.connected_appliance or "").lower(),
        }
        if alias_target:
            names.add(alias_target)
        if any(name and name in lowered for name in names) or (alias_target and device.id == alias_target):
            return DeviceAction(device=device, state=state)
    return None


def _parse_action_state(text: str) -> Literal["on", "off"] | None:
    off_tokens = ("关闭", "关掉", "断开", "turn off", "power off", " off")
    on_tokens = ("打开", "开启", "启动", "turn on", "power on", " on")
    if any(token in text for token in off_tokens):
        return "off"
    if any(token in text for token in on_tokens):
        return "on"
    return None


def _device_alias_target(text: str) -> str | None:
    aliases = (
        ("未知负载智能插座", "smart_plug_01"),
        ("未知插座", "smart_plug_01"),
        ("智能插座", "smart_plug_01"),
        ("烟雾报警器", "smoke_alarm_01"),
        ("报警器", "smoke_alarm_01"),
        ("氛围灯", "ambient_light_01"),
        ("台灯", "desk_lamp_01"),
        ("灯带", "ambient_light_01"),
        ("风扇", "fan_ir_01"),
    )
    for keyword, device_id in aliases:
        if keyword in text:
            return device_id
    return None
