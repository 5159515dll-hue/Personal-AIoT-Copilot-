from __future__ import annotations

import operator
import re
from collections.abc import Callable

from app.audit import record_audit
from app.mock_data import current_room_state
from app.models import AutomationRule, Metric, RoomState, RuleEvaluation
from app.rule_store import list_rules
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
)


def evaluate_automation_rules(
    *,
    room: RoomState | None = None,
    rules: list[AutomationRule] | None = None,
    emit_audit: bool = True,
) -> list[RuleEvaluation]:
    state = room or current_room_state()
    candidates = rules if rules is not None else list_rules()
    return [_evaluate_rule(rule, state, emit_audit=emit_audit) for rule in candidates]


def _evaluate_rule(rule: AutomationRule, room: RoomState, *, emit_audit: bool) -> RuleEvaluation:
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
            reason="当前 V0 只支持简单指标阈值或人体存在条件。",
            evaluated_at=evaluated_at,
        )

    metric, comparator, threshold = condition
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

    matched = comparator(reading.value, threshold)
    observed = {
        "metric": metric.value,
        "value": reading.value,
        "unit": reading.unit,
        "threshold": threshold,
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

    if not _is_reminder_action(rule.action):
        return RuleEvaluation(
            rule_id=rule.id,
            condition=rule.condition,
            action=rule.action,
            matched=True,
            status="unsupported",
            reason="当前 V0 只触发提醒类动作，不执行设备控制。",
            evaluated_at=evaluated_at,
            observed=observed,
        )

    audit_log_id = None
    if emit_audit:
        audit = record_audit(
            actor="system",
            action="trigger_automation_rule",
            result="success",
            details=f"规则已触发提醒动作：{rule.action}",
            parameters={
                "rule_id": rule.id,
                "condition": rule.condition,
                "action": rule.action,
                "observed": observed,
            },
        )
        audit_log_id = audit.id

    return RuleEvaluation(
        rule_id=rule.id,
        condition=rule.condition,
        action=rule.action,
        matched=True,
        status="triggered",
        reason="规则条件已满足，提醒动作已写入审计日志。",
        evaluated_at=evaluated_at,
        observed=observed,
        audit_log_id=audit_log_id,
    )


def _parse_condition(condition: str) -> tuple[Metric, Callable[[float, float], bool], float] | None:
    lowered = condition.lower()
    metric = _match_metric(lowered)
    if metric is None:
        return None

    if metric == Metric.presence and any(token in lowered for token in ("有人", "occupied", "presence")):
        return metric, operator.gt, 0

    match = re.search(r"(>=|<=|>|<)\s*([0-9]+(?:\.[0-9]+)?)", lowered)
    if not match:
        return None
    comparator = COMPARATORS[match.group(1)]
    threshold = float(match.group(2))
    return metric, comparator, threshold


def _match_metric(text: str) -> Metric | None:
    for metric, aliases in METRIC_ALIASES:
        if any(alias in text for alias in aliases):
            return metric
    return None


def _is_reminder_action(action: str) -> bool:
    lowered = action.lower()
    return any(token in lowered for token in ("提醒", "通知", "alert", "notify", "message"))
