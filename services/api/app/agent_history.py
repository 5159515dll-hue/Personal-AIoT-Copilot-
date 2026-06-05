from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Literal

from app.models import AgentChatResponse, AgentConversationEntry, AgentMessage, ToolCall
from app.storage import JsonListStore
from app.time_utils import now

history_store = JsonListStore("agent_conversations.json", AgentConversationEntry)
RETENTION_DAYS = 30

_SECRET_TEXT_PATTERNS = [
    re.compile(r"\b(sk|tp)-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|authorization|bearer|token|secret|password)\s*[:=]\s*[^\s,;]+"),
]
_SECRET_KEYS = ("api_key", "apikey", "authorization", "bearer", "token", "secret", "password", "密钥", "口令")


def record_agent_conversation(
    *,
    session_id: str,
    data_source: Literal["mock", "database"],
    user_message: str,
    response: AgentChatResponse,
) -> AgentConversationEntry:
    entry = AgentConversationEntry(
        session_id=session_id,
        data_source=data_source,
        user_message=AgentMessage(role="user", content=redact_sensitive_text(user_message), created_at=now()),
        assistant_message=response.message.model_copy(update={"content": redact_sensitive_text(response.message.content)}),
        used_data=list(response.used_data),
        tool_calls=[redact_tool_call(tool) for tool in response.tool_calls],
        needs_confirmation=response.needs_confirmation,
        model_usage=response.model_usage,
        policy=response.policy,
        rule_draft=response.rule_draft,
        created_at=now(),
    )
    retained = _retained(history_store.list())
    history_store.replace_all([*retained, entry])
    return entry


def list_agent_history(limit: int = 50, session_id: str | None = None) -> list[AgentConversationEntry]:
    current = history_store.list()
    retained = _retained(current)
    if len(retained) != len(current):
        history_store.replace_all(retained)
    entries = retained
    if session_id:
        entries = [entry for entry in entries if entry.session_id == session_id]
    return sorted(entries, key=lambda item: item.created_at, reverse=True)[:limit]


def delete_agent_history_entry(entry_id: str) -> AgentConversationEntry | None:
    entries = history_store.list()
    deleted = next((entry for entry in entries if entry.id == entry_id), None)
    if deleted is None:
        return None
    history_store.replace_all([entry for entry in entries if entry.id != entry_id])
    return deleted


def _retained(entries: list[AgentConversationEntry]) -> list[AgentConversationEntry]:
    cutoff = now() - timedelta(days=RETENTION_DAYS)
    return [entry for entry in entries if entry.created_at >= cutoff]


def redact_tool_call(tool: ToolCall) -> ToolCall:
    return tool.model_copy(
        deep=True,
        update={
            "parameters": redact_sensitive_value(tool.parameters),
            "result": redact_sensitive_value(tool.result),
        },
    )


def redact_sensitive_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in _SECRET_KEYS):
                redacted[key] = "已脱敏"
            else:
                redacted[key] = redact_sensitive_value(nested)
        return redacted
    return value


def redact_sensitive_text(text: str) -> str:
    redacted = text
    redacted = _SECRET_TEXT_PATTERNS[0].sub(lambda match: f"{match.group(1)}-已脱敏", redacted)
    redacted = _SECRET_TEXT_PATTERNS[1].sub(lambda match: f"{match.group(1)}=已脱敏", redacted)
    return redacted
