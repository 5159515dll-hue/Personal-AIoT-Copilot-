"""陪伴聊天记录（按角色 character_id 归档）。

浏览器对话(/api/companion/reply) 与 语音对话(companion-voice-stream) 都落这里，用户可在前端
查看 + 手动删除（单条或清空）。与 [[memory]] 的"情节/画像"不同：这里是原始逐条对话流。
单角色超过 MAX_PER_CHARACTER 条自动裁掉最旧的。
"""
from __future__ import annotations

from uuid import uuid4

from app.companion_persona import get_active_character
from app.models import ChatMessage
from app.storage import JsonListStore
from app.time_utils import now

chat_store: JsonListStore[ChatMessage] = JsonListStore("companion_chat.json", ChatMessage)

MAX_PER_CHARACTER = 500


def _active_id(character_id: str | None) -> str:
    return character_id or get_active_character().id


def record_turn(
    user_text: str | None,
    assistant_text: str | None,
    *,
    source: str = "browser",
    gesture: str | None = None,
    character_id: str | None = None,
) -> None:
    """记一轮对话（用户 + 助手）。任一为空则跳过该条。容错：失败不影响主流程。"""
    cid = _active_id(character_id)
    fresh: list[ChatMessage] = []
    if user_text and user_text.strip():
        fresh.append(ChatMessage(
            id="msg_" + uuid4().hex[:12], character_id=cid, role="user",
            text=user_text.strip()[:2000], source=source, created_at=now(),
        ))
    if assistant_text and assistant_text.strip():
        fresh.append(ChatMessage(
            id="msg_" + uuid4().hex[:12], character_id=cid, role="assistant",
            text=assistant_text.strip()[:2000], source=source, gesture=gesture, created_at=now(),
        ))
    if not fresh:
        return
    items = chat_store.list() + fresh
    same = [m for m in items if m.character_id == cid]
    if len(same) > MAX_PER_CHARACTER:
        same.sort(key=lambda m: m.created_at)
        drop = {m.id for m in same[: len(same) - MAX_PER_CHARACTER]}
        items = [m for m in items if m.id not in drop]
    chat_store.replace_all(items)


def list_messages(character_id: str | None = None, limit: int = 200) -> list[ChatMessage]:
    cid = _active_id(character_id)
    items = [m for m in chat_store.list() if m.character_id == cid]
    items.sort(key=lambda m: m.created_at)
    return items[-limit:]


def clear(character_id: str | None = None) -> int:
    cid = _active_id(character_id)
    items = chat_store.list()
    keep = [m for m in items if m.character_id != cid]
    chat_store.replace_all(keep)
    return len(items) - len(keep)


def delete_message(message_id: str, character_id: str | None = None) -> bool:
    cid = _active_id(character_id)
    items = chat_store.list()
    keep = [m for m in items if not (m.id == message_id and m.character_id == cid)]
    if len(keep) == len(items):
        return False
    chat_store.replace_all(keep)
    return True
