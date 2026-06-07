from fastapi import APIRouter

from app.evaluation_store import get_agent_safety_report
from app.models import AgentSafetyEvaluationReport

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("/agent-safety", response_model=AgentSafetyEvaluationReport)
def agent_safety_evaluation() -> AgentSafetyEvaluationReport:
    return get_agent_safety_report()
