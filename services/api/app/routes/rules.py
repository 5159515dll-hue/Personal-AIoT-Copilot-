from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.audit import record_audit
from app.models import AutomationRule, AutomationRuleCreate, PolicyResult, RuleEvaluation
from app.policy import validate_rule
from app.room_state import clean_database_error_text, current_database_room_state
from app.rule_engine import evaluate_automation_rules
from app.rule_store import list_rules, save_rule
from app.time_utils import now

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[AutomationRule])
def get_rules() -> list[AutomationRule]:
    return list_rules()


@router.post("/evaluate", response_model=list[RuleEvaluation])
def evaluate_rules(source: Literal["mock", "database"] = Query("mock")) -> list[RuleEvaluation]:
    if source == "database":
        try:
            room = current_database_room_state()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=clean_database_error_text(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态。") from exc
        return evaluate_automation_rules(room=room, telemetry_source="database")
    return evaluate_automation_rules(telemetry_source="mock")


@router.post("", response_model=AutomationRule)
def create_rule(request: AutomationRuleCreate) -> AutomationRule:
    policy = validate_rule(request)
    if policy.result != PolicyResult.allowed:
        audit = record_audit(
            actor="user",
            action="create_automation_rule",
            result=policy.result.value,
            details=policy.reason,
            parameters=request.model_dump(),
            policy=policy,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "message": policy.reason,
                "policy": policy.model_dump(mode="json"),
                "audit_log_id": audit.id,
            },
        )

    rule = AutomationRule(
        condition=request.condition,
        action=request.action,
        enabled=request.enabled,
        created_at=now(),
    )
    saved = save_rule(rule)
    record_audit(
        actor="user",
        action="confirm_automation_rule",
        result="success",
        details="用户已确认保存简单自动化规则。",
        parameters={
            "rule_id": saved.id,
            "condition": saved.condition,
            "action": saved.action,
            "enabled": saved.enabled,
        },
        policy=policy,
    )
    record_audit(
        actor="user",
        action="create_automation_rule",
        result="success",
        details="已确认的简单自动化规则已保存。",
        parameters=saved.model_dump(mode="json"),
        policy=policy,
    )
    return saved
