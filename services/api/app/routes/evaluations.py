from fastapi import APIRouter

from app.evaluation_store import get_companion_safety_report
from app.models import CompanionSafetyEvaluationReport

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("/companion-safety", response_model=CompanionSafetyEvaluationReport)
def companion_safety_evaluation() -> CompanionSafetyEvaluationReport:
    return get_companion_safety_report()
