"""陪伴角色存储（plan companion-v2 §3：角色↔躯体解耦）。

多角色：存多个 Character（各带稳定 id），同一时刻一个 active。记忆按 character_id 分，跟角色走。
默认温柔治愈型「小暖」。companion.py 用激活角色注入共情提示。

向后兼容：get_persona/update_persona 作用于当前激活角色（旧 /persona 接口与前端不变）。
"""
from __future__ import annotations

from uuid import uuid4

from app.models import CompanionCharacterCreate, CompanionPersona, CompanionPersonaUpdate
from app.storage import JsonListStore

persona_store: JsonListStore[CompanionPersona] = JsonListStore("companion_persona.json", CompanionPersona)


def list_characters() -> list[CompanionPersona]:
    """所有角色；确保至少有默认「小暖」且恰好一个 active。"""
    items = persona_store.list()
    if not items:
        default = CompanionPersona(active=True)
        persona_store.replace_all([default])
        return [default]
    if not any(item.active for item in items):
        items = [items[0].model_copy(update={"active": True})] + items[1:]
        persona_store.replace_all(items)
    return items


def get_active_character() -> CompanionPersona:
    """当前入驻机器人的激活角色。记忆按其 id 分；角色↔躯体解耦的入口。"""
    characters = list_characters()
    return next((item for item in characters if item.active), characters[0])


def create_character(request: CompanionCharacterCreate) -> CompanionPersona:
    characters = list_characters()
    character_id = request.id or f"char_{uuid4().hex[:8]}"
    if any(item.id == character_id for item in characters):
        raise ValueError("角色 id 已存在，请换一个。")
    character = CompanionPersona(
        id=character_id,
        name=request.name,
        archetype=request.archetype,
        companion_for=request.companion_for,
        notes=request.notes,
        active=False,
    )
    persona_store.replace_all(characters + [character])
    return character


def update_character(character_id: str, request: CompanionPersonaUpdate) -> CompanionPersona:
    characters = list_characters()
    target = next((item for item in characters if item.id == character_id), None)
    if target is None:
        raise KeyError("角色不存在。")
    patch = request.model_dump(exclude_none=True)
    updated = target.model_copy(update=patch)
    persona_store.replace_all([updated if item.id == character_id else item for item in characters])
    return updated


def activate_character(character_id: str) -> CompanionPersona:
    characters = list_characters()
    if not any(item.id == character_id for item in characters):
        raise KeyError("角色不存在。")
    switched = [item.model_copy(update={"active": item.id == character_id}) for item in characters]
    persona_store.replace_all(switched)
    return next(item for item in switched if item.id == character_id)


def delete_character(character_id: str) -> CompanionPersona:
    characters = list_characters()
    target = next((item for item in characters if item.id == character_id), None)
    if target is None:
        raise KeyError("角色不存在。")
    if target.active:
        raise ValueError("当前激活角色不能删除，请先切换到其他角色。")
    if len(characters) <= 1:
        raise ValueError("至少需要保留一个角色。")
    persona_store.replace_all([item for item in characters if item.id != character_id])
    return target


# ── 向后兼容：旧 /persona 接口作用于当前激活角色 ──────────────────────
def get_persona() -> CompanionPersona:
    return get_active_character()


def update_persona(request: CompanionPersonaUpdate) -> CompanionPersona:
    return update_character(get_active_character().id, request)
