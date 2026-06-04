from __future__ import annotations

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


def list_audit_logs(limit: int = 100) -> list[AuditLog]:
    logs = audit_store.list()
    return sorted(logs, key=lambda item: item.timestamp, reverse=True)[:limit]

