"""长期记忆模块 v0（plan companion-v2 §2）。

两层（按 character_id 分，记忆跟角色走）：
- 情节记忆 episodic（按事件+时间）：显著互动条目。
- 画像记忆 profile（按事实）：用户稳定偏好/重要的人/备注。

v0 用规则抽取写入 + 结构化检索（recency + 话题重叠），进阶可换 LLM 抽取 + 向量检索。
容错：记忆任一步失败都不应中断对话——调用方用 safe_* 包裹（见 companion.py）。
隐私：本地存、保留期裁剪、用户可查看/遗忘（routes/companion 的 /memory）。
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from urllib.parse import urljoin

import httpx

from app.models import EmotionState, MemoryEpisode, MemorySnapshot, UserProfile
from app.storage import JsonListStore
from app.time_utils import now

episode_store: JsonListStore[MemoryEpisode] = JsonListStore("memory_episodes.json", MemoryEpisode)
profile_store: JsonListStore[UserProfile] = JsonListStore("memory_profile.json", UserProfile)

SALIENCE_WRITE_THRESHOLD = 0.5
RECENT_EPISODES = 3
RELEVANT_EPISODES = 2

# 情节保留期 + 上限裁剪（带滞回，复用事件裁剪模式）。
EPISODE_RETENTION_DAYS = 60
EPISODE_TARGET = 400
EPISODE_TRIGGER = 500

_RELATION_WORDS = (
    "奶奶", "爷爷", "外婆", "外公", "妈妈", "爸爸", "母亲", "父亲", "老婆", "老公",
    "妻子", "丈夫", "儿子", "女儿", "孩子", "朋友", "同事", "老师", "对象", "男朋友", "女朋友",
    "猫", "狗",
)
_STOP_TAIL = "，。！？、；,.!?；\n "


def _clean_tail(text: str, limit: int = 24) -> str:
    text = text.strip(_STOP_TAIL)
    for ch in _STOP_TAIL:
        idx = text.find(ch)
        if idx > 0:
            text = text[:idx]
    return text.strip()[:limit]


def _extract_profile_updates(message: str) -> tuple[dict[str, str | None], list[str]]:
    """从用户消息里规则抽取画像更新 + 命中话题。返回(更新dict, topics)。"""
    updates: dict[str, str | None] = {"preferences": [], "important_people": [], "notes": [], "display_name": None}
    topics: list[str] = []

    for marker in ("我喜欢", "我爱", "我很喜欢", "喜欢"):
        if marker in message:
            pref = _clean_tail(message.split(marker, 1)[1])
            if pref:
                updates["preferences"].append(pref)
                topics.append(pref)
            break
    for marker in ("我讨厌", "我不喜欢", "我害怕", "我担心"):
        if marker in message:
            dislike = _clean_tail(message.split(marker, 1)[1])
            if dislike:
                updates["notes"].append(f"{marker.lstrip('我')}{dislike}")
                topics.append(dislike)
            break
    for word in _RELATION_WORDS:
        if word in message:
            updates["important_people"].append(word)
            topics.append(word)
    for marker in ("记住", "记得"):
        if marker in message:
            note = _clean_tail(message.split(marker, 1)[1].lstrip("：:，, "), limit=60)
            if note:
                updates["notes"].append(note)
                topics.append(note[:8])
            break
    for marker in ("我叫", "我的名字叫", "我的名字是", "叫我"):
        if marker in message:
            name = _clean_tail(message.split(marker, 1)[1], limit=20)
            if name:
                updates["display_name"] = name
            break
    return updates, topics


def _salience(message: str, state: EmotionState | None, has_fact: bool) -> float:
    score = 0.3
    if state is not None:
        score += 0.4 * max(abs(state.valence), state.arousal)
    if any(marker in message for marker in ("记住", "记得")):
        score += 0.3
    if has_fact:
        score += 0.2
    return min(1.0, round(score, 3))


def get_profile(character_id: str, subject_id: str = "user_default") -> UserProfile:
    for item in profile_store.list():
        if item.character_id == character_id and item.subject_id == subject_id:
            return item
    return UserProfile(character_id=character_id, subject_id=subject_id, updated_at=now())


def _save_profile(profile: UserProfile) -> None:
    others = [
        item
        for item in profile_store.list()
        if not (item.character_id == profile.character_id and item.subject_id == profile.subject_id)
    ]
    profile_store.replace_all(others + [profile])


def _merge_list(existing: list[str], additions: list[str], cap: int) -> list[str]:
    merged = list(existing)
    for item in additions:
        if item and item not in merged:
            merged.append(item)
    return merged[-cap:]


def _as_str_list(value: object) -> list[str]:
    """把 LLM 输出的任意值规整成去重字符串列表。"""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text[:40])
    return out[:20]


def write_memory(
    character_id: str,
    subject_id: str,
    user_message: str,
    reply: str,
    emotion_state: EmotionState | None,
    extraction: dict | None = None,
) -> None:
    """写入记忆：更新画像事实 + 显著时写情节。

    extraction（来自 LLM 抽取）存在时优先用它；否则回退规则抽取（容错：LLM 失败不影响）。
    """
    message = (user_message or "").strip()
    if not message:
        return

    if extraction is not None:
        updates = {
            "display_name": extraction.get("display_name") or None,
            "preferences": _as_str_list(extraction.get("preferences")),
            "important_people": _as_str_list(extraction.get("important_people")),
            "notes": _as_str_list(extraction.get("notes")),
        }
        topics = updates["preferences"] + updates["important_people"]
        summary = str(extraction.get("episode_summary") or message)[:280]
        explicit_salience = extraction.get("salience")
    else:
        updates, topics = _extract_profile_updates(message)
        summary = message[:280]
        explicit_salience = None

    has_fact = bool(
        updates["preferences"] or updates["important_people"] or updates["notes"] or updates["display_name"]
    )
    if has_fact:
        profile = get_profile(character_id, subject_id)
        profile = profile.model_copy(
            update={
                "display_name": updates["display_name"] or profile.display_name,
                "preferences": _merge_list(profile.preferences, updates["preferences"], 40),
                "important_people": _merge_list(profile.important_people, updates["important_people"], 40),
                "notes": _merge_list(profile.notes, updates["notes"], 40),
                "updated_at": now(),
            }
        )
        _save_profile(profile)

    if isinstance(explicit_salience, (int, float)):
        salience = min(1.0, max(0.0, float(explicit_salience)))
    else:
        salience = _salience(message, emotion_state, has_fact)
    if salience >= SALIENCE_WRITE_THRESHOLD:
        episode = MemoryEpisode(
            character_id=character_id,
            subject_id=subject_id,
            created_at=now(),
            summary=summary,
            emotion=emotion_state.primary_emotion if emotion_state else None,
            valence=emotion_state.valence if emotion_state else 0.0,
            salience=salience,
            topics=topics[:12],
        )
        episode_store.append(episode)
        _enforce_episode_retention(character_id)


def _parse_extraction_json(content: str) -> dict | None:
    """从模型输出里提取 JSON 对象（容忍代码围栏/多余文字）。"""
    text = (content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


async def llm_extract(message: str, reply: str) -> dict | None:
    """用当前大模型（豆包，关思考）抽取长期记忆 JSON。无模型/失败返回 None（回退规则抽取）。"""
    from app.model_providers import (
        _agent_model_timeout_seconds,
        _openai_headers,
        apply_speed_params,
        get_active_config,
    )
    from app.models import ProviderProtocol

    message = (message or "").strip()
    if not message:
        return None
    config = get_active_config()
    if not config or not config.api_key or config.protocol != ProviderProtocol.openai:
        return None

    instruction = (
        "你是记忆抽取器。从下面这轮对话里抽取关于【用户】的长期记忆，"
        "只输出一个 JSON 对象，不要任何额外文字。字段：\n"
        "preferences(用户明确喜欢的事物,字符串数组)、important_people(用户在意的人,字符串数组)、"
        "notes(其他值得长期记住的事实,字符串数组)、display_name(用户希望被怎么称呼,没有则 null)、"
        "episode_summary(这轮的一句话客观摘要)、salience(0~1 之间，这轮对长期记忆的重要程度)。\n"
        "区分清楚：宠物/喜好归 preferences，人才归 important_people。\n"
        f"用户：{message}\n回应：{reply or ''}"
    )
    payload = apply_speed_params(
        {"model": config.model, "messages": [{"role": "user", "content": instruction}], "max_completion_tokens": 300},
        config.provider_id,
    )
    try:
        async with httpx.AsyncClient(timeout=_agent_model_timeout_seconds()) as client:
            resp = await client.post(
                urljoin(f"{config.base_url.rstrip('/')}/", "chat/completions"),
                headers=_openai_headers(config.provider_id, config.api_key or ""),
                json=payload,
            )
        if resp.status_code < 200 or resp.status_code >= 300:
            return None
        content = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        return _parse_extraction_json(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        return None


def _enforce_episode_retention(character_id: str) -> None:
    episodes = episode_store.list()
    same = [item for item in episodes if item.character_id == character_id]
    if len(same) <= EPISODE_TRIGGER:
        return
    cutoff = now() - timedelta(days=EPISODE_RETENTION_DAYS)
    fresh = [item for item in same if item.created_at >= cutoff]
    # 优先保留高显著度 + 近期：按 (salience, time) 排序取前 TARGET。
    fresh.sort(key=lambda item: (item.salience, item.created_at))
    kept = fresh[-EPISODE_TARGET:]
    others = [item for item in episodes if item.character_id != character_id]
    episode_store.replace_all(others + kept)


def _episodes_for(character_id: str, subject_id: str) -> list[MemoryEpisode]:
    return [
        item
        for item in episode_store.list()
        if item.character_id == character_id and item.subject_id == subject_id
    ]


def retrieve_memory_context(character_id: str, subject_id: str, current_message: str) -> str:
    """组装紧凑"记忆摘要"注入提示。无记忆返回空串。"""
    parts: list[str] = []
    profile = get_profile(character_id, subject_id)
    facts: list[str] = []
    if profile.display_name:
        facts.append(f"名字{profile.display_name}")
    if profile.preferences:
        facts.append("喜欢" + "、".join(profile.preferences[-5:]))
    if profile.important_people:
        facts.append("在意的人：" + "、".join(profile.important_people[-5:]))
    if profile.notes:
        facts.append("备注：" + "；".join(profile.notes[-3:]))
    if facts:
        parts.append("关于Ta：" + "；".join(facts) + "。")

    episodes = _episodes_for(character_id, subject_id)
    episodes.sort(key=lambda item: item.created_at)
    recent = episodes[-RECENT_EPISODES:]
    recent_ids = {item.id for item in recent}

    keywords = [token for token in re.split(r"[\s，。、,.!?；]+", current_message or "") if len(token) >= 2]
    relevant = [
        item
        for item in episodes
        if item.id not in recent_ids and any(topic and topic in (current_message or "") for topic in item.topics)
    ]
    relevant = relevant[-RELEVANT_EPISODES:]

    def fmt(item: MemoryEpisode) -> str:
        return f"{item.summary[:60]}（{item.created_at.strftime('%m-%d')}）"

    if recent:
        parts.append("最近：" + "；".join(fmt(item) for item in recent) + "。")
    if relevant:
        parts.append("相关：" + "；".join(fmt(item) for item in relevant) + "。")

    _ = keywords  # 预留：进阶按关键词做向量/倒排检索
    return " ".join(parts)


def memory_snapshot(character_id: str, subject_id: str = "user_default", limit: int = 50) -> MemorySnapshot:
    episodes = _episodes_for(character_id, subject_id)
    episodes.sort(key=lambda item: item.created_at, reverse=True)
    profile = get_profile(character_id, subject_id)
    has_profile = bool(
        profile.display_name or profile.preferences or profile.important_people or profile.notes
    )
    return MemorySnapshot(profile=profile if has_profile else None, episodes=episodes[:limit])


def clear_memory(character_id: str, subject_id: str = "user_default") -> tuple[int, bool]:
    episodes = episode_store.list()
    keep = [
        item
        for item in episodes
        if not (item.character_id == character_id and item.subject_id == subject_id)
    ]
    cleared_episodes = len(episodes) - len(keep)
    episode_store.replace_all(keep)

    profiles = profile_store.list()
    keep_profiles = [
        item
        for item in profiles
        if not (item.character_id == character_id and item.subject_id == subject_id)
    ]
    cleared_profile = len(keep_profiles) != len(profiles)
    profile_store.replace_all(keep_profiles)

    return cleared_episodes, cleared_profile
