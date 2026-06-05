from __future__ import annotations

from datetime import datetime

from app.models import AutomationRule
from app.storage import JsonListStore

rule_store = JsonListStore("automation_rules.json", AutomationRule)


def list_rules() -> list[AutomationRule]:
    return sorted(rule_store.list(), key=lambda item: item.created_at, reverse=True)


def save_rule(rule: AutomationRule) -> AutomationRule:
    return rule_store.append(rule)


def update_rule_enabled(rule_id: str, enabled: bool) -> AutomationRule | None:
    rules = rule_store.list()
    updated: AutomationRule | None = None
    next_rules: list[AutomationRule] = []
    for rule in rules:
        if rule.id == rule_id:
            updated = rule.model_copy(update={"enabled": enabled})
            next_rules.append(updated)
        else:
            next_rules.append(rule)
    if updated is None:
        return None
    rule_store.replace_all(next_rules)
    return updated


def record_rule_trigger(rule_id: str, triggered_at: datetime) -> AutomationRule | None:
    rules = rule_store.list()
    updated: AutomationRule | None = None
    next_rules: list[AutomationRule] = []
    for rule in rules:
        if rule.id == rule_id:
            updated = rule.model_copy(
                update={
                    "trigger_count": rule.trigger_count + 1,
                    "last_triggered_at": triggered_at,
                }
            )
            next_rules.append(updated)
        else:
            next_rules.append(rule)
    if updated is None:
        return None
    rule_store.replace_all(next_rules)
    return updated
