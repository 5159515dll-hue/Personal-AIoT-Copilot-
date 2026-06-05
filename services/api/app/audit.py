from __future__ import annotations

import json

from app.models import AuditLog, PolicyDecision
from app.storage import JsonListStore
from app.time_utils import now

audit_store = JsonListStore("audit_logs.json", AuditLog)


def record_audit(
    *,
    actor: str,
    action: str,
    result: str,
    details: str,
    parameters: dict,
    policy: PolicyDecision | None = None,
) -> AuditLog:
    log = AuditLog(
        timestamp=now(),
        actor=actor,  # type: ignore[arg-type]
        action=action,
        policy_result=policy.result if policy else None,
        risk_level=policy.risk_level if policy else None,
        parameters=parameters,
        result=result,
        details=details,
    )
    return audit_store.append(log)


def list_audit_logs(
    limit: int = 100,
    *,
    actor: str | None = None,
    action: str | None = None,
    result: str | None = None,
    policy_result: str | None = None,
    risk_level: str | None = None,
    q: str | None = None,
) -> list[AuditLog]:
    logs = audit_store.list()
    filtered = [
        log
        for log in logs
        if _matches_exact(log.actor, actor)
        and _matches_exact(log.action, action)
        and _matches_exact(log.result, result)
        and _matches_exact(log.policy_result, policy_result)
        and _matches_exact(log.risk_level, risk_level)
        and _matches_query(log, q)
    ]
    return sorted(filtered, key=lambda item: item.timestamp, reverse=True)[:limit]


def _matches_exact(value: object, expected: str | None) -> bool:
    if not expected:
        return True
    actual = getattr(value, "value", value)
    return str(actual) == expected


def _matches_query(log: AuditLog, q: str | None) -> bool:
    query = (q or "").strip().casefold()
    if not query:
        return True
    haystack = " ".join(
        [
            log.id,
            log.actor,
            log.action,
            str(log.policy_result.value if log.policy_result else ""),
            str(log.risk_level.value if log.risk_level else ""),
            log.result,
            log.details,
            json.dumps(log.parameters, ensure_ascii=False, default=str),
        ]
    ).casefold()
    return query in haystack
