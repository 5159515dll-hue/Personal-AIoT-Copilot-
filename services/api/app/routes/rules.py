from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.models import AutomationRule, AutomationRuleCreate, PolicyResult, RuleEvaluation
from app.policy import validate_rule
from app.rule_engine import evaluate_automation_rules
from app.rule_store import list_rules, save_rule
from app.time_utils import now

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[AutomationRule])
def get_rules() -> list[AutomationRule]:
    return list_rules()


@router.post("/evaluate", response_model=list[RuleEvaluation])
def evaluate_rules() -> list[RuleEvaluation]:
    return evaluate_automation_rules()


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
        action="create_automation_rule",
        result="success",
        details="已确认的简单自动化规则已保存。",
        parameters=saved.model_dump(mode="json"),
        policy=policy,
    )
    return saved
