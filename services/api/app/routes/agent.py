from fastapi import APIRouter

from app.agent_tools import handle_chat
from app.models import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat(request: AgentChatRequest) -> AgentChatResponse:
    return handle_chat(request)

