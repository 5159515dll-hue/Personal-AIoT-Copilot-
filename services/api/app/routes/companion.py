"""情感陪伴回应路由（plan §5 / M3）。

POST /api/companion/reply：情绪 → 共情回应。默认返回 JSON；stream=true 时返回 SSE 流
（先发 meta 帧含情绪/手势/语言，再逐块发正文 delta，最后 [DONE]）。
情绪默认取空间最近平滑状态，也可用 primary_emotion 显式覆盖。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.companion import (
    generate_companion_reply,
    reply_language,
    response_strategy,
    stream_companion_reply,
)
from app.audit import record_audit
from app.companion_persona import get_persona, update_persona
from app.emotion_fusion import get_last_state
from app.models import (
    CompanionGestureRequest,
    CompanionGestureResponse,
    CompanionPersona,
    CompanionPersonaUpdate,
    CompanionReplyRequest,
    CompanionReplyResponse,
    EmotionState,
    PolicyResult,
)
from app.yanshee_control import plan_companion_gesture

router = APIRouter(prefix="/api/companion", tags=["companion"])


def _resolve_state(payload: CompanionReplyRequest) -> EmotionState:
    if payload.primary_emotion:
        return EmotionState(
            primary_emotion=payload.primary_emotion,
            valence=0.0,
            arousal=0.3,
            confidence=0.5,
            language=payload.language or "zh",
        )
    state = get_last_state(payload.space_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="该空间暂无情绪状态，请先上报情绪或显式提供 primary_emotion。",
        )
    return state


@router.post("/reply")
async def companion_reply(payload: CompanionReplyRequest):
    state = _resolve_state(payload)

    if payload.stream:
        async def event_stream():
            strat = response_strategy(state.primary_emotion)
            lang = reply_language(payload.language or state.language)
            meta = {
                "primary_emotion": state.primary_emotion,
                "gesture": strat["gesture"],
                "tone": strat["tone"],
                "language": lang,
            }
            yield f"data: {json.dumps({'meta': meta}, ensure_ascii=False)}\n\n"
            async for delta in stream_companion_reply(state, payload.language, payload.message):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    reply, usage, meta = await generate_companion_reply(state, payload.language, payload.message)
    return CompanionReplyResponse(
        reply=reply,
        primary_emotion=state.primary_emotion,
        language=meta["language"],
        tone=meta["tone"],
        gesture=meta["gesture"],
        model_used=usage.used,
        model_status=usage.status,
    )


@router.post("/gesture", response_model=CompanionGestureResponse)
def companion_gesture(payload: CompanionGestureRequest) -> CompanionGestureResponse:
    """情绪驱动的原地手势：经 policy 门控 + 审计。平台下发抽象手势，具体 YanAPI 运动名
    由机器人侧用 get_motion_list() 解析后 sync_play_motion 播放；v0 不接真机，executed=False。"""
    decision = plan_companion_gesture(
        gesture=payload.gesture, intent=payload.intent or "", confirmed=payload.confirmed
    )
    allowed = decision.result == PolicyResult.allowed
    audit = record_audit(
        actor="agent",
        action="companion_gesture",
        result="success" if allowed else "blocked",
        details=decision.reason,
        parameters={
            "gesture": payload.gesture,
            "device_id": payload.device_id,
            "confirmed": payload.confirmed,
        },
        policy=decision,
    )
    return CompanionGestureResponse(
        gesture=payload.gesture,
        allowed=allowed,
        executed=False,  # v0 不接真机；真机执行待机器人侧控制适配器联调
        reason=decision.reason,
        audit_log_id=audit.id,
    )


@router.get("/persona", response_model=CompanionPersona)
def companion_persona() -> CompanionPersona:
    return get_persona()


@router.post("/persona", response_model=CompanionPersona)
def set_companion_persona(payload: CompanionPersonaUpdate) -> CompanionPersona:
    persona = update_persona(payload)
    record_audit(
        actor="user",
        action="update_companion_persona",
        result="success",
        details=f"陪伴人格已更新：{persona.name}（{persona.archetype}）。",
        parameters=persona.model_dump(mode="json"),
    )
    return persona
