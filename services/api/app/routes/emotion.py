"""情绪感知摄取路由（plan §2 / M2）。

POST /api/emotion/ingest：边缘/采集端上报三模态结果，服务器推理(文本)+融合+平滑→
  可选记录 emotion_detected 事件。**不接收也不落任何原始音视频**；文本原文用完即弃、不入库。
GET  /api/emotion/state：读当前平滑情绪状态（供前端/agent 只读工具）。

鉴权复用设备令牌（与事件上报一致）；空间需开启情绪识别双门控才处理（隐私优先）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.audit import record_audit
from app.emotion_fusion import (
    fuse_and_smooth,
    get_last_state,
    set_last_state,
    to_device_event,
)
from app.emotion_perception import detect_language, infer_face, infer_text, infer_voice
from app.media_store import ensure_event_allowed, record_device_event
from app.models import EmotionIngestRequest, EmotionIngestResponse, EmotionState
from app.routes.device_connections import _require_device_ingest_auth

router = APIRouter(prefix="/api/emotion", tags=["emotion"])

# v0 推理来源标识：文本真推理 + FER/SER 可插拔桩。接真实模型后更新。
INFERENCE_LABEL = "infer_text+stub_fer_ser"


@router.post("/ingest", response_model=EmotionIngestResponse)
def ingest_emotion(payload: EmotionIngestRequest, request: Request) -> EmotionIngestResponse:
    _require_device_ingest_auth(request, payload.device_id or "")

    # 隐私门控：空间未开情绪识别（双门控 camera + emotion_recognition）→ 不处理、不返回情绪。
    try:
        ensure_event_allowed(payload.space_id, "emotion_detected")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        audit = record_audit(
            actor="system",
            action="ingest_emotion",
            result="blocked",
            details=str(exc),
            parameters={"space_id": payload.space_id, "device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=403, detail={"message": str(exc), "audit_log_id": audit.id}
        ) from exc

    # 文本：服务器真推理（语言相关）。转写原文仅用于推理、用完即弃，不入库、不写日志。
    language = payload.language
    text_reading = None
    if payload.transcript:
        language = language or detect_language(payload.transcript)
        text_reading = infer_text(payload.transcript, language)
    language = language or "zh"

    state = fuse_and_smooth(
        key=payload.space_id,
        face=infer_face(payload.face),
        voice=infer_voice(payload.voice),
        text=text_reading,
        language=language,
    )
    set_last_state(payload.space_id, state)

    event_id: str | None = None
    recorded = False
    detail: str | None = None
    if payload.record_event:
        event = record_device_event(
            payload.device_id or "emotion_engine",
            to_device_event(
                state,
                space_id=payload.space_id,
                zone=payload.zone,
                inference_model=INFERENCE_LABEL,
            ),
        )
        event_id = event.id
        recorded = True
        record_audit(
            actor="system",
            action="ingest_emotion",
            result="success",
            details=f"情绪事件已记录：{state.primary_emotion}（{language}）。",
            parameters={
                "event_id": event.id,
                "space_id": payload.space_id,
                "device_id": payload.device_id,
                "primary_emotion": state.primary_emotion,
                "language": language,
            },
        )
    else:
        detail = "已计算情绪状态但未记录事件（record_event=false）。"

    return EmotionIngestResponse(
        state=state, event_recorded=recorded, event_id=event_id, detail=detail
    )


@router.get("/state", response_model=EmotionState)
def current_emotion_state(space_id: str = Query(..., min_length=1, max_length=80)) -> EmotionState:
    state = get_last_state(space_id)
    if state is None:
        raise HTTPException(status_code=404, detail="该空间暂无情绪状态。")
    return state
