from __future__ import annotations

from datetime import datetime

from app.database import database_url, list_rules_db, record_rule_trigger_db, save_rule_db, update_rule_enabled_db
from app.models import AutomationRule
from app.storage import JsonListStore

rule_store = JsonListStore("automation_rules.json", AutomationRule)


def list_rules() -> list[AutomationRule]:
    if database_url():
        try:
            return list_rules_db()
        except Exception:
            pass
    return sorted(rule_store.list(), key=lambda item: item.created_at, reverse=True)


def save_rule(rule: AutomationRule) -> AutomationRule:
    if database_url():
        try:
            return save_rule_db(rule)
        except Exception:
            pass
    return rule_store.append(rule)


def update_rule_enabled(rule_id: str, enabled: bool) -> AutomationRule | None:
    if database_url():
        try:
            return update_rule_enabled_db(rule_id, enabled)
        except Exception:
            pass
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
    if database_url():
        try:
            return record_rule_trigger_db(rule_id, triggered_at)
        except Exception:
            pass
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
