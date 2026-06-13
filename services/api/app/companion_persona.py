"""情感陪伴机器人人格存储（plan §7 / B6）。

单条人格记录，存在 .local/companion_persona.json。默认温柔治愈型「小暖」。
companion.py 用它注入共情提示；用户可在前端修改名字/语气/陪伴对象。
"""
from __future__ import annotations

from app.models import CompanionPersona, CompanionPersonaUpdate
from app.storage import JsonListStore

persona_store: JsonListStore[CompanionPersona] = JsonListStore("companion_persona.json", CompanionPersona)


def get_persona() -> CompanionPersona:
    items = persona_store.list()
    return items[0] if items else CompanionPersona()


def get_active_character() -> CompanionPersona:
    """当前入驻机器人的角色（= 当前人格）。记忆按其 id 分；角色↔躯体解耦的入口。

    单角色阶段等价于 get_persona()；多机器人时改为按 device→character 绑定解析。
    """
    return get_persona()


def update_persona(request: CompanionPersonaUpdate) -> CompanionPersona:
    current = get_persona()
    patch = request.model_dump(exclude_none=True)
    persona = current.model_copy(update=patch)
    persona_store.replace_all([persona])
    return persona
