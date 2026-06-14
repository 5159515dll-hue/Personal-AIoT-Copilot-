"""情感陪伴回应路由（plan §5 / M3）。

POST /api/companion/reply：情绪 → 共情回应。默认返回 JSON；stream=true 时返回 SSE 流
（先发 meta 帧含情绪/手势/语言，再逐块发正文 delta，最后 [DONE]）。
情绪默认取空间最近平滑状态，也可用 primary_emotion 显式覆盖。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.companion import (
    generate_companion_reply,
    reply_language,
    response_strategy,
    stream_companion_reply,
)
from app.audit import record_audit
from app.companion_persona import (
    activate_character,
    create_character,
    delete_character,
    get_active_character,
    get_persona,
    list_characters,
    update_character,
    update_persona,
)
from app.emotion_fusion import get_last_state
from app.memory import clear_memory, memory_snapshot
from app.models import (
    CompanionCharacterCreate,
    CompanionGestureRequest,
    CompanionGestureResponse,
    CompanionPersona,
    CompanionPersonaUpdate,
    CompanionReplyRequest,
    CompanionReplyResponse,
    CompanionVisionCaptureRequest,
    EmotionState,
    MemoryClearResponse,
    MemorySnapshot,
    PolicyResult,
)
from app.yanshee_control import plan_companion_gesture
from app.companion_mqtt import publish_companion_command, publish_vision_capture, publish_vision_live
from app import live_stream
from app.live_stream import clear as clear_live_frames, get_frame as get_live_frame
from app.media_store import _assert_space_allows_stream
from app.companion_voice import get_voice, set_voice
from app.volc_tts import VOICE_CATALOG, is_configured as tts_configured
from app.chat_log import clear as clear_chat, delete_message as delete_chat_message, list_messages as list_chat, record_turn
from app.models import ChatClearResponse, ChatMessage, CompanionVoiceUpdate
import asyncio

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
    # 下发陪伴指令到机器人（Step 1：手势；Step 2 起含 text 做 TTS）。容错，不影响回复。
    publish_companion_command(
        gesture=meta.get("gesture"),
        text=reply,
        language=meta.get("language"),
        emotion=state.primary_emotion,
    )
    try:
        record_turn(payload.message, reply, source="browser", gesture=meta.get("gesture"))
    except Exception:  # noqa: BLE001 - 记录失败不影响对话
        pass
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


@router.post("/vision/capture")
def companion_vision_capture(payload: CompanionVisionCaptureRequest) -> dict:
    """请求机器人拍一张照片并上传到媒体库（出现在 /vision）。"""
    requested = publish_vision_capture(space_id=payload.space_id, zone=payload.zone)
    record_audit(
        actor="user",
        action="companion_vision_capture",
        result="success" if requested else "blocked",
        details=f"已请求机器人拍照（空间 {payload.space_id}）。",
        parameters=payload.model_dump(mode="json"),
    )
    return {"requested": requested}


@router.post("/vision/live/start")
def companion_vision_live_start(payload: CompanionVisionCaptureRequest) -> dict:
    """开始实时画面：校验空间允许实时流后，下发直播开始指令；浏览器随后轮询 live/frame。"""
    try:
        _assert_space_allows_stream(payload.space_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    requested = publish_vision_live(space_id=payload.space_id, action="live_start")
    record_audit(
        actor="user",
        action="companion_vision_live_start",
        result="success" if requested else "blocked",
        details=f"已请求机器人开始实时画面（空间 {payload.space_id}）。",
        parameters=payload.model_dump(mode="json"),
    )
    return {"requested": requested}


@router.post("/vision/live/stop")
def companion_vision_live_stop(payload: CompanionVisionCaptureRequest) -> dict:
    """停止实时画面：下发停止指令并清空服务端缓冲帧。"""
    requested = publish_vision_live(space_id=payload.space_id, action="live_stop")
    clear_live_frames(payload.space_id)
    record_audit(
        actor="user",
        action="companion_vision_live_stop",
        result="success",
        details=f"已请求机器人停止实时画面（空间 {payload.space_id}）。",
        parameters=payload.model_dump(mode="json"),
    )
    return {"requested": requested}


@router.get("/vision/live/frame")
def companion_vision_live_frame(space_id: str) -> Response:
    """返回该空间最新一帧 JPEG（浏览器 <img> 轮询）。无帧或已超时返回 404。"""
    frame = get_live_frame(space_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="暂无实时画面（机器人未在推流或已超时）。")
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/vision/live/status")
def companion_vision_live_status(space_id: str) -> dict:
    """前端用来判断是否已有画面（区分"未推流/正在连接"）。"""
    return {"live": get_live_frame(space_id) is not None}


@router.get("/vision/live/stream")
async def companion_vision_live_stream(space_id: str):
    """浏览器 <img> 直连的 MJPEG 流（multipart/x-mixed-replace）：满帧率、单连接、不轮询。

    X-Accel-Buffering: no → nginx 不缓冲该响应（无需为响应侧改 nginx 配置）。
    连续 STREAM_IDLE_TIMEOUT 秒无新数据（机器人停推/离线）则结束，浏览器连接随之关闭。
    """
    queue = live_stream.subscribe(space_id)

    async def gen():
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=live_stream.STREAM_IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    break
                if chunk is None:
                    break
                yield chunk
        finally:
            live_stream.unsubscribe(space_id, queue)

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=" + live_stream.LIVE_BOUNDARY,
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/voice")
def companion_voice_options() -> dict:
    """可选音色列表 + 当前音色（用户在前端切换）。"""
    return {"current": get_voice(), "configured": tts_configured(), "voices": VOICE_CATALOG}


@router.post("/voice")
def update_companion_voice(payload: CompanionVoiceUpdate) -> dict:
    """切换机器人朗读音色（服务端火山 TTS voice_type）。"""
    voice = set_voice(payload.voice)
    record_audit(
        actor="user",
        action="set_companion_voice",
        result="success",
        details=f"切换机器人音色为 {voice}。",
        parameters={"voice": voice},
    )
    return {"current": voice}


@router.get("/chat", response_model=list[ChatMessage])
def companion_chat_history(limit: int = 200) -> list[ChatMessage]:
    """当前角色的聊天记录（浏览器 + 语音对话，按时间正序）。"""
    return list_chat(limit=limit)


@router.delete("/chat", response_model=ChatClearResponse)
def clear_companion_chat() -> ChatClearResponse:
    """清空当前角色的全部聊天记录。"""
    removed = clear_chat()
    record_audit(
        actor="user",
        action="clear_companion_chat",
        result="success",
        details=f"清空聊天记录 {removed} 条。",
        parameters={"removed": removed},
    )
    return ChatClearResponse(cleared=removed)


@router.delete("/chat/{message_id}")
def delete_companion_chat_message(message_id: str) -> dict:
    """删除单条聊天记录。"""
    if not delete_chat_message(message_id):
        raise HTTPException(status_code=404, detail="聊天记录不存在。")
    record_audit(
        actor="user",
        action="delete_companion_chat_message",
        result="success",
        details=f"删除聊天记录 {message_id}。",
        parameters={"message_id": message_id},
    )
    return {"deleted": message_id}


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


@router.get("/memory", response_model=MemorySnapshot)
def companion_memory() -> MemorySnapshot:
    """查看当前角色的记忆（画像 + 最近情节）。记忆是敏感数据，用户可查看。"""
    return memory_snapshot(get_active_character().id)


@router.delete("/memory", response_model=MemoryClearResponse)
def clear_companion_memory() -> MemoryClearResponse:
    """遗忘当前角色的全部记忆（用户的被遗忘权）。"""
    character = get_active_character()
    cleared_episodes, cleared_profile = clear_memory(character.id)
    audit = record_audit(
        actor="user",
        action="clear_companion_memory",
        result="success",
        details=f"已清除角色 {character.id} 的记忆：情节 {cleared_episodes} 条，画像{'已清' if cleared_profile else '无'}。",
        parameters={"character_id": character.id, "cleared_episodes": cleared_episodes, "cleared_profile": cleared_profile},
    )
    return MemoryClearResponse(
        character_id=character.id,
        cleared_episodes=cleared_episodes,
        cleared_profile=cleared_profile,
        audit_log_id=audit.id,
    )


@router.get("/characters", response_model=list[CompanionPersona])
def companion_characters() -> list[CompanionPersona]:
    return list_characters()


@router.post("/characters", response_model=CompanionPersona)
def create_companion_character(payload: CompanionCharacterCreate) -> CompanionPersona:
    try:
        character = create_character(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor="user",
        action="create_companion_character",
        result="success",
        details=f"新建陪伴角色：{character.name}（{character.id}）。",
        parameters=character.model_dump(mode="json"),
    )
    return character


@router.patch("/characters/{character_id}", response_model=CompanionPersona)
def update_companion_character(character_id: str, payload: CompanionPersonaUpdate) -> CompanionPersona:
    try:
        character = update_character(character_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    record_audit(
        actor="user",
        action="update_companion_character",
        result="success",
        details=f"更新角色：{character.name}（{character.id}）。",
        parameters=character.model_dump(mode="json"),
    )
    return character


@router.post("/characters/{character_id}/activate", response_model=CompanionPersona)
def activate_companion_character(character_id: str) -> CompanionPersona:
    try:
        character = activate_character(character_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    record_audit(
        actor="user",
        action="activate_companion_character",
        result="success",
        details=f"切换当前角色为：{character.name}（{character.id}）。",
        parameters={"character_id": character.id},
    )
    return character


@router.delete("/characters/{character_id}", response_model=CompanionPersona)
def delete_companion_character(character_id: str) -> CompanionPersona:
    try:
        character = delete_character(character_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor="user",
        action="delete_companion_character",
        result="success",
        details=f"删除角色：{character.name}（{character.id}）。",
        parameters={"character_id": character.id},
    )
    return character
