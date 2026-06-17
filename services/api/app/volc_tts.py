"""火山引擎豆包语音合成 2.0 (SeedTTS 2.0) —— 服务端合成自然语音供机器人播放。

机器人自带 TTS 只有一个机械音色且不可换；这里在服务器用火山大模型 TTS 合成 MP3，
机器人用 mpg123 播放 → 可切换音色 + 自然声音。为压低延迟（用户要求"说完话 3s 内回话"），
按句合成、流式下发：调用方逐句 synthesize() 并把 MP3 立刻推给机器人，边生成边播。

接口：V3 单向流式 HTTP，NDJSON 响应（每行 {"code":0,"data":"<base64 mp3>"}）。
凭证从环境变量读：VOLC_TTS_APPID / VOLC_TTS_ACCESS_KEY（存服务器 .dashboard-env，不入 Git）。
容错：合成失败抛异常或返回空，调用方降级（机器人侧回退本机 TTS）。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.request
import uuid

LOGGER = logging.getLogger("aiot.volc_tts")

ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
RESOURCE_ID = "seed-tts-2.0"

# 试用已授权音色（已逐个 probe 确认可用）。voice_type -> 展示名。
VOICE_CATALOG = [
    {"voice_type": "zh_female_vv_uranus_bigtts", "name": "Vivi · 温柔女声"},
    {"voice_type": "zh_female_cancan_uranus_bigtts", "name": "灿灿 · 活泼女声"},
    {"voice_type": "zh_male_liufei_uranus_bigtts", "name": "刘飞 · 磁性男声"},
    {"voice_type": "zh_male_m191_uranus_bigtts", "name": "云舟 · 沉稳男声"},
]
DEFAULT_VOICE = "zh_female_vv_uranus_bigtts"
_VALID_VOICES = {v["voice_type"] for v in VOICE_CATALOG}

# 按句切分（让首句尽快合成播放）：中文句末标点 + 换行。
_SENTENCE_END = re.compile(r"[。！？!?\n；;]")


def is_configured() -> bool:
    return bool(os.getenv("VOLC_TTS_APPID") and os.getenv("VOLC_TTS_ACCESS_KEY"))


def valid_voice(voice: str | None) -> str:
    return voice if voice in _VALID_VOICES else DEFAULT_VOICE


def split_sentences(text: str):
    """把文本切成短句，便于"出一句合成一句"降低首音延迟。"""
    out, buf = [], ""
    for ch in text:
        buf += ch
        if _SENTENCE_END.search(ch):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def synthesize(text: str, voice: str | None = None, sample_rate: int = 24000) -> bytes:
    """合成一段文本 → MP3 字节。未配置/空文本返回 b""；网络或接口错误抛异常由调用方降级。"""
    appid = os.getenv("VOLC_TTS_APPID", "").strip()
    token = os.getenv("VOLC_TTS_ACCESS_KEY", "").strip()
    if not (appid and token and text and text.strip()):
        return b""
    body = {
        "user": {"uid": "aiot-companion"},
        "req_params": {
            "text": text,
            "speaker": valid_voice(voice),
            "audio_params": {"format": "mp3", "sample_rate": sample_rate},
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Api-App-Id": appid,
            "X-Api-Access-Key": token,
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-Request-Id": str(uuid.uuid4()),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    out = bytearray()
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line.decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        data = obj.get("data")
        if isinstance(data, str) and data:
            try:
                out += base64.b64decode(data)
            except Exception:  # noqa: BLE001
                pass
    return bytes(out)
