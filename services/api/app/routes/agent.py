from fastapi import APIRouter

from app.agent_tools import handle_chat
from app.models import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def chat(request: AgentChatRequest) -> AgentChatResponse:
    return await handle_chat(request)
