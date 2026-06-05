from fastapi import APIRouter, HTTPException, Query

from app.agent_history import delete_agent_history_entry, list_agent_history
from app.audit import record_audit
from app.agent_tools import handle_chat
from app.models import AgentChatRequest, AgentChatResponse, AgentConversationDeleteResponse, AgentConversationEntry

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def chat(request: AgentChatRequest) -> AgentChatResponse:
    return await handle_chat(request)


@router.get("/history", response_model=list[AgentConversationEntry])
def get_history(
    limit: int = Query(30, ge=1, le=100),
    session_id: str | None = Query(default=None, min_length=1, max_length=128),
) -> list[AgentConversationEntry]:
    return list_agent_history(limit=limit, session_id=session_id)


@router.delete("/history/{entry_id}", response_model=AgentConversationDeleteResponse)
def delete_history_entry(entry_id: str) -> AgentConversationDeleteResponse:
    deleted = delete_agent_history_entry(entry_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="未找到该智能体对话记录。")
    audit = record_audit(
        actor="user",
        action="delete_agent_history",
        result="success",
        details="用户手动删除了一条智能体对话记录。",
        parameters={"entry_id": entry_id, "session_id": deleted.session_id},
    )
    return AgentConversationDeleteResponse(deleted=True, id=entry_id, audit_log_id=audit.id)
