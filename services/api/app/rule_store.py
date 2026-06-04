from __future__ import annotations

from app.models import AutomationRule
from app.storage import JsonListStore

rule_store = JsonListStore("automation_rules.json", AutomationRule)


def list_rules() -> list[AutomationRule]:
    return sorted(rule_store.list(), key=lambda item: item.created_at, reverse=True)


def save_rule(rule: AutomationRule) -> AutomationRule:
    return rule_store.append(rule)

