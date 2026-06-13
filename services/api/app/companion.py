"""情感陪伴共情回应（plan §5 / M3）。

回路：情绪状态 → 确定性回应策略（温柔治愈基调）→ 豆包生成共情话语（流式可选）。
工具优先/策略优先：情绪判定与手势选择是确定性的，LLM 只负责"把话说自然"。
未配置模型或调用失败时回退到温柔治愈模板，保证始终有得体回应。

决策（§7）：宠物人格=温柔治愈型；v0 仅识别支持蒙语、回应先中/英（mn→zh 兜底，蒙语回应见 M7）。
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from urllib.parse import urljoin

import httpx

from app.companion_persona import get_active_character
from app.policy import SAFE_COMPANION_GESTURES
from app.model_providers import (
    _agent_model_timeout_seconds,
    _openai_headers,
    apply_speed_params,
    get_active_config,
)
from app.models import AgentModelUsage, CompanionPersona, EmotionState, ProviderProtocol

# 人格基调（archetype → 中/英语气）。默认 gentle_healing 温柔治愈（§7 决策）。
_ARCHETYPE_TONE: dict[str, tuple[str, str]] = {
    "gentle_healing": ("轻声、共情、温柔安抚", "soft-spoken, empathetic, gently comforting"),
    "lively_playful": ("活泼、俏皮、有活力但不吵闹", "lively, playful, energetic but not noisy"),
    "quiet_companion": ("安静、低打扰，只在需要时温柔回应", "quiet and unobtrusive, gently responding only when needed"),
}

_RULES_ZH = (
    "规则：\n"
    "1. 用 2-3 句温柔、口语化的中文回应，简短贴心，不说教、不评判、不下命令。\n"
    "2. 先接住对方的情绪，再给一点点轻轻的陪伴或建议，绝不强迫。\n"
    "3. 不要输出 Markdown、列表或标题，直接像朋友一样说话。\n"
    "4. 绝不利用对方的情绪进行诱导、推销或操控。"
)
_RULES_EN = (
    "Rules:\n"
    "1. Reply in 2-3 short, warm, spoken-style English sentences. Never lecture or judge.\n"
    "2. Acknowledge the feeling first, then offer light companionship, never pushy.\n"
    "3. No Markdown, lists, or headings — just talk like a friend.\n"
    "4. Never exploit the person's emotion to persuade, sell, or manipulate."
)


def _build_system_prompt(language: str, persona: CompanionPersona) -> str:
    tone_zh, tone_en = _ARCHETYPE_TONE.get(persona.archetype, _ARCHETYPE_TONE["gentle_healing"])
    if language == "en":
        who = f"You are {persona.name}, a desktop emotional-companion robot"
        if persona.companion_for:
            who += f" mainly accompanying {persona.companion_for}"
        return f"{who} — a warm little friend, not an assistant. Tone: {tone_en}.\n{_RULES_EN}"
    who = f"你是「{persona.name}」，一只桌面情感陪伴机器人"
    if persona.companion_for:
        who += f"，主要陪伴{persona.companion_for}"
    return f"{who}，像一个温暖的小伙伴，不是助手或客服。语气：{tone_zh}。\n{_RULES_ZH}"

# 情绪 → 回应策略（确定性，温柔治愈基调）。gesture 对齐 M6 安全手势集。
_STRATEGY: dict[str, dict[str, str]] = {
    "sad": {"tone": "安抚陪伴", "gesture": "tilt_head"},
    "happy": {"tone": "共情欢喜", "gesture": "nod"},
    "angry": {"tone": "平静倾听", "gesture": "lean_back"},
    "fear": {"tone": "稳定安抚", "gesture": "reach_out"},
    "surprise": {"tone": "温和回应", "gesture": "nod"},
    "disgust": {"tone": "理解接纳", "gesture": "tilt_head"},
    "neutral": {"tone": "轻轻陪伴", "gesture": "idle_nod"},
}

_TEMPLATE_ZH: dict[str, str] = {
    "sad": "辛苦啦，今天一定累坏了吧。别硬撑，先靠着歇一会儿，我就在这儿陪着你。",
    "happy": "看到你开心，我也跟着高兴呢！这份好心情要好好收着呀。",
    "angry": "我在听着呢，慢慢说，气一会儿没关系，我都陪着你。",
    "fear": "别怕，有我在呢。我们一点一点来，会没事的。",
    "surprise": "哇，是发生什么啦？我都好奇起来了，慢慢跟我说呀。",
    "disgust": "嗯，那种感觉确实不太舒服，我懂的，先放一放吧。",
    "neutral": "我在呢，想聊点什么都可以，我一直都在。",
}

_TEMPLATE_EN: dict[str, str] = {
    "sad": "You've worked so hard today. Don't push yourself — lean back and rest a little, I'm right here with you.",
    "happy": "Seeing you happy makes me happy too! Hold on to this lovely feeling.",
    "angry": "I'm listening. Take your time — it's okay to be upset, I'm here with you.",
    "fear": "Don't be afraid, I'm right here. We'll take it one little step at a time.",
    "surprise": "Oh, what happened? I'm curious now — tell me slowly.",
    "disgust": "Yeah, that feeling really isn't pleasant. I get it — let's set it aside for now.",
    "neutral": "I'm here. We can talk about anything you like, I'm always around.",
}


def response_strategy(emotion: str) -> dict[str, str]:
    return _STRATEGY.get(emotion, _STRATEGY["neutral"])


def reply_language(language: str | None) -> str:
    """v0：仅识别支持蒙语、回应先中/英；mn→zh 兜底（蒙语回应见 M7）。"""
    return "en" if language == "en" else "zh"


def _template_reply(emotion: str, language: str) -> str:
    table = _TEMPLATE_EN if language == "en" else _TEMPLATE_ZH
    return table.get(emotion, table["neutral"])


# 解析模型在回应末尾标注的动作行：「动作: nod」/「action: nod」。
_GESTURE_TAG_RE = re.compile(r"[\n\r]+\s*(?:动作|action)\s*[:：]\s*([A-Za-z_]+)\s*$", re.IGNORECASE)


def _split_gesture(content: str) -> tuple[str, str | None]:
    """从回应末尾切出动作标签，返回 (纯回应文本, 建议手势|None)。"""
    match = _GESTURE_TAG_RE.search(content)
    if not match:
        return content, None
    gesture = match.group(1).strip().lower()
    clean = content[: match.start()].rstrip()
    return (clean or content), gesture


def _messages(
    state: EmotionState,
    language: str,
    message: str | None,
    persona: CompanionPersona,
    memory_context: str = "",
    tool_context: str = "",
) -> list[dict[str, str]]:
    system = _build_system_prompt(language, persona)
    if memory_context:
        system += f"\n\n你对Ta已有的记忆（自然融入，别生硬复述）：{memory_context}"
    context = [
        f"用户当前情绪：{state.primary_emotion}"
        f"（valence={state.valence}, arousal={state.arousal}, 置信度={state.confidence}）。",
        f"回应基调：{response_strategy(state.primary_emotion)['tone']}。",
    ]
    if message:
        context.append(f"用户刚说的话：{message}")
    if tool_context:
        context.append(f"【传感器实时数据】{tool_context}。请基于这些真实数据回答相关问题，不要编造数值。")
    context.append("请按你的人格风格，用 2-3 句温柔的话回应。")
    context.append(
        "回应之后另起一行，用「动作: X」标注一个最贴合的肢体动作，"
        "X 只能从 nod、tilt_head、reach_out、wave、lean_back、idle_nod 里选一个。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(context)},
    ]


def _payload(config, messages: list[dict[str, str]], *, stream: bool) -> dict:
    payload: dict = {
        "model": config.model,
        "messages": messages,
        "max_completion_tokens": 400,
        "stream": stream,
    }
    return apply_speed_params(payload, config.provider_id, temperature=0.6)


def _usable_openai_config():
    config = get_active_config()
    if not config or not config.api_key or config.protocol != ProviderProtocol.openai:
        return None
    return config


SUBJECT_DEFAULT = "user_default"  # 单用户阶段；多用户时按用户身份分


def _safe_retrieve_memory(character_id: str, message: str | None) -> str:
    """检索记忆上下文；失败降级为空（记忆故障不影响对话，容错隔离）。"""
    try:
        from app.memory import retrieve_memory_context

        return retrieve_memory_context(character_id, SUBJECT_DEFAULT, message or "")
    except Exception:  # noqa: BLE001
        return ""


def _safe_write_memory(character_id: str, message: str | None, reply: str, state: EmotionState) -> None:
    """回应后写记忆；失败静默降级（不影响已生成的回应）。"""
    try:
        from app.memory import write_memory

        write_memory(character_id, SUBJECT_DEFAULT, message or "", reply, state)
    except Exception:  # noqa: BLE001
        pass


def _safe_tool_context(message: str | None) -> str:
    """按意图拉取真实传感器上下文注入提示；失败降级为空（工具故障不影响对话）。"""
    try:
        from app.companion_tools import gather_tool_context

        return gather_tool_context(message or "")
    except Exception:  # noqa: BLE001
        return ""


async def generate_companion_reply(
    state: EmotionState,
    language: str | None = None,
    message: str | None = None,
) -> tuple[str, AgentModelUsage, dict[str, str]]:
    lang = reply_language(language or state.language)
    strat = response_strategy(state.primary_emotion)
    meta = {"language": lang, "tone": strat["tone"], "gesture": strat["gesture"]}
    character = get_active_character()
    memory_context = _safe_retrieve_memory(character.id, message)
    tool_context = _safe_tool_context(message)

    config = _usable_openai_config()
    if config is None:
        reply = _template_reply(state.primary_emotion, lang)
        _safe_write_memory(character.id, message, reply, state)
        return (
            reply,
            AgentModelUsage(status="not_configured", used=False, reason="未配置可用 OpenAI 兼容模型，已用温柔治愈模板回应。"),
            meta,
        )
    try:
        async with httpx.AsyncClient(timeout=_agent_model_timeout_seconds()) as client:
            response = await client.post(
                urljoin(f"{config.base_url.rstrip('/')}/", "chat/completions"),
                headers=_openai_headers(config.provider_id, config.api_key or ""),
                json=_payload(config, _messages(state, lang, message, character, memory_context, tool_context), stream=False),
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise ValueError(f"服务返回 {response.status_code}：{response.text[:200]}")
        content = (response.json()["choices"][0]["message"].get("content") or "").strip()
        if not content:
            raise ValueError("模型返回空内容")
        content, proposed = _split_gesture(content)
        if proposed in SAFE_COMPANION_GESTURES:
            meta["gesture"] = proposed  # 内容驱动：模型在安全集内选的手势，贴合本句回应
        _safe_write_memory(character.id, message, content, state)
        return content, AgentModelUsage(status="used", used=True, reason="已用当前大模型生成共情回应。"), meta
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        reply = _template_reply(state.primary_emotion, lang)
        _safe_write_memory(character.id, message, reply, state)
        return (
            reply,
            AgentModelUsage(status="fallback", used=False, reason=f"模型调用失败，已回退温柔治愈模板：{exc}"),
            meta,
        )


def extract_sse_content_delta(line: str) -> str | None:
    """从一行 OpenAI 兼容 SSE 中取 content 增量；跳过 reasoning_content、[DONE] 与非数据行。"""
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:"):].strip()
    if not data or data == "[DONE]":
        return None
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return None
    choices = obj.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")  # 忽略 reasoning_content（思考），只取正文
    return content if isinstance(content, str) and content else None


async def stream_companion_reply(
    state: EmotionState,
    language: str | None = None,
    message: str | None = None,
) -> AsyncIterator[str]:
    """流式生成共情回应，逐块产出正文文本。无模型/失败时一次性产出模板。"""
    lang = reply_language(language or state.language)
    character = get_active_character()
    memory_context = _safe_retrieve_memory(character.id, message)
    tool_context = _safe_tool_context(message)
    config = _usable_openai_config()
    if config is None:
        yield _template_reply(state.primary_emotion, lang)
        return
    try:
        async with httpx.AsyncClient(timeout=_agent_model_timeout_seconds()) as client:
            async with client.stream(
                "POST",
                urljoin(f"{config.base_url.rstrip('/')}/", "chat/completions"),
                headers=_openai_headers(config.provider_id, config.api_key or ""),
                json=_payload(config, _messages(state, lang, message, character, memory_context, tool_context), stream=True),
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    yield _template_reply(state.primary_emotion, lang)
                    return
                emitted = False
                async for line in response.aiter_lines():
                    delta = extract_sse_content_delta(line)
                    if delta:
                        emitted = True
                        yield delta
                if not emitted:
                    yield _template_reply(state.primary_emotion, lang)
    except httpx.HTTPError:
        yield _template_reply(state.primary_emotion, lang)
