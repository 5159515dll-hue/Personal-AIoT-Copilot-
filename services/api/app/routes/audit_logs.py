from fastapi import APIRouter, Query

from app.audit import list_audit_logs
from app.models import AuditLog

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLog])
def get_audit_logs(limit: int = Query(100, ge=1, le=500)) -> list[AuditLog]:
    return list_audit_logs(limit=limit)

