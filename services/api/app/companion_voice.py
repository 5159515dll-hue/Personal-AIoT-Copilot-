"""陪伴朗读音色设置（用户在服务器切换音色）。

存的是火山 TTS 的 voice_type；机器人朗读时按此合成。单值，用 JsonListStore 存一条。
"""
from __future__ import annotations

from app.models import CompanionVoiceSetting
from app.storage import JsonListStore
from app.volc_tts import DEFAULT_VOICE, valid_voice

voice_store: JsonListStore[CompanionVoiceSetting] = JsonListStore("companion_voice.json", CompanionVoiceSetting)


def get_voice() -> str:
    items = voice_store.list()
    return valid_voice(items[0].voice) if items else DEFAULT_VOICE


def set_voice(voice: str) -> str:
    chosen = valid_voice(voice)
    voice_store.replace_all([CompanionVoiceSetting(voice=chosen)])
    return chosen
