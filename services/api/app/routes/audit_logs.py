from fastapi import APIRouter, Query

from app.audit import list_audit_logs
from app.models import AuditLog, PolicyResult, RiskLevel

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLog])
def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    actor: str | None = Query(None, pattern="^(user|agent|system)$"),
    action: str | None = Query(None, min_length=1, max_length=80),
    result: str | None = Query(None, min_length=1, max_length=80),
    policy_result: PolicyResult | None = None,
    risk_level: RiskLevel | None = None,
    q: str | None = Query(None, min_length=1, max_length=120),
) -> list[AuditLog]:
    return list_audit_logs(
        limit=limit,
        actor=actor,
        action=action,
        result=result,
        policy_result=policy_result.value if policy_result else None,
        risk_level=risk_level.value if risk_level else None,
        q=q,
    )
