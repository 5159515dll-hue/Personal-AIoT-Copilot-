"""多模态情感晚融合 + 时序平滑。

设计要点（对齐 docs/companion-robot-plan.md M1）：
- 晚融合：每个模态给出 7 类情绪分布 + 置信度，按"置信度 × 模态先验"加权平均。
- 某模态缺失/零置信自动降级，不影响其余模态。
- 时序平滑：滚动窗口平均 + 对 primary_emotion 做滞回，避免逐帧跳变。
- 纯逻辑、确定性、无外部依赖，便于单测（只验逻辑正确性，不验情绪准确性）。
"""
from __future__ import annotations

from collections import deque
from threading import Lock

from app.models import (
    EMOTION_LABELS,
    DeviceEventCreate,
    EmotionModalityInput,
    EmotionModalitySummary,
    EmotionState,
)

# 7 类情绪 → (valence[-1,1], arousal[0,1]) 固定映射。
_VALENCE_AROUSAL: dict[str, tuple[float, float]] = {
    "happy": (0.80, 0.60),
    "sad": (-0.60, 0.35),
    "angry": (-0.60, 0.80),
    "surprise": (0.30, 0.75),
    "fear": (-0.50, 0.70),
    "disgust": (-0.55, 0.50),
    "neutral": (0.00, 0.25),
}

# 模态先验权重（在置信度之上再乘一层）。文本语义信息量略高，给稍大先验。
_MODALITY_PRIOR: dict[str, float] = {"face": 1.0, "voice": 1.0, "text": 1.2}

_MODALITY_ORDER = ("face", "voice", "text")


def _normalize(distribution: dict[str, float]) -> dict[str, float]:
    """把任意分布裁剪到 7 类并归一化；空/非正分布回退到均匀分布。"""
    clean = {label: max(0.0, float(distribution.get(label, 0.0))) for label in EMOTION_LABELS}
    total = sum(clean.values())
    if total <= 0:
        uniform = 1.0 / len(EMOTION_LABELS)
        return {label: uniform for label in EMOTION_LABELS}
    return {label: clean[label] / total for label in EMOTION_LABELS}


def _modality_summary(reading: EmotionModalityInput | None) -> EmotionModalitySummary:
    if reading is None:
        return EmotionModalitySummary(status="unavailable")
    dist = _normalize(reading.distribution)
    emotion = max(EMOTION_LABELS, key=lambda label: dist[label])
    return EmotionModalitySummary(
        status="ok",
        emotion=emotion,
        confidence=reading.confidence,
        transcript_lang=reading.transcript_lang,
    )


def fuse_distribution(
    *,
    face: EmotionModalityInput | None = None,
    voice: EmotionModalityInput | None = None,
    text: EmotionModalityInput | None = None,
) -> tuple[dict[str, float], float]:
    """晚融合三模态 → (融合分布, 总置信度)。"""
    readings = {"face": face, "voice": voice, "text": text}
    weighted = {label: 0.0 for label in EMOTION_LABELS}
    weight_total = 0.0
    confidences: list[float] = []
    for name, reading in readings.items():
        if reading is None or reading.confidence <= 0:
            continue
        weight = reading.confidence * _MODALITY_PRIOR.get(name, 1.0)
        dist = _normalize(reading.distribution)
        for label in EMOTION_LABELS:
            weighted[label] += weight * dist[label]
        weight_total += weight
        confidences.append(reading.confidence)

    if weight_total <= 0:
        # 全部缺失或零置信 → neutral 兜底，置信度 0。
        fused = {label: (1.0 if label == "neutral" else 0.0) for label in EMOTION_LABELS}
        return fused, 0.0

    fused = {label: weighted[label] / weight_total for label in EMOTION_LABELS}
    overall_confidence = sum(confidences) / len(confidences)
    return fused, overall_confidence


def _valence_arousal(distribution: dict[str, float]) -> tuple[float, float]:
    valence = sum(distribution[label] * _VALENCE_AROUSAL[label][0] for label in EMOTION_LABELS)
    arousal = sum(distribution[label] * _VALENCE_AROUSAL[label][1] for label in EMOTION_LABELS)
    return round(valence, 3), round(arousal, 3)


def fuse(
    *,
    face: EmotionModalityInput | None = None,
    voice: EmotionModalityInput | None = None,
    text: EmotionModalityInput | None = None,
    language: str = "zh",
) -> EmotionState:
    """无平滑的一次性融合（用于单帧或测试）。"""
    fused, confidence = fuse_distribution(face=face, voice=voice, text=text)
    primary = max(EMOTION_LABELS, key=lambda label: fused[label])
    valence, arousal = _valence_arousal(fused)
    return EmotionState(
        primary_emotion=primary,
        valence=valence,
        arousal=arousal,
        confidence=round(confidence, 3),
        language=language,  # type: ignore[arg-type]
        modalities={
            "face": _modality_summary(face),
            "voice": _modality_summary(voice),
            "text": _modality_summary(text),
        },
        fusion="late_weighted",
        smoothed=False,
    )


class EmotionSmoother:
    """按 key（如 space_id/device_id）维持滚动窗口，做时序平滑 + primary 滞回。

    - 窗口平均：抑制逐帧抖动。
    - 滞回：只有当新候选在平滑分布上领先当前 primary 达到阈值，才切换 primary。
    进程内线程安全（单 uvicorn 进程部署，与既有 JsonListStore 同假设）。
    """

    def __init__(self, window: int = 5, hysteresis: float = 0.15) -> None:
        self._window = max(1, window)
        self._hysteresis = max(0.0, hysteresis)
        self._history: dict[str, deque[dict[str, float]]] = {}
        self._primary: dict[str, str] = {}
        self._lock = Lock()

    def smooth(self, key: str, distribution: dict[str, float]) -> tuple[dict[str, float], str]:
        with self._lock:
            history = self._history.setdefault(key, deque(maxlen=self._window))
            history.append(dict(distribution))
            averaged = {
                label: sum(item.get(label, 0.0) for item in history) / len(history)
                for label in EMOTION_LABELS
            }
            candidate = max(EMOTION_LABELS, key=lambda label: averaged[label])
            current = self._primary.get(key)
            if current is None or current not in averaged:
                chosen = candidate
            elif candidate != current and (averaged[candidate] - averaged[current]) >= self._hysteresis:
                chosen = candidate
            else:
                chosen = current
            self._primary[key] = chosen
            return averaged, chosen

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._history.clear()
                self._primary.clear()
            else:
                self._history.pop(key, None)
                self._primary.pop(key, None)


# 模块级默认平滑器（被 /api/emotion/ingest 复用）。
default_smoother = EmotionSmoother()


def fuse_and_smooth(
    *,
    key: str,
    face: EmotionModalityInput | None = None,
    voice: EmotionModalityInput | None = None,
    text: EmotionModalityInput | None = None,
    language: str = "zh",
    smoother: EmotionSmoother | None = None,
) -> EmotionState:
    """融合 + 时序平滑，返回稳定的 EmotionState。"""
    smoother = smoother or default_smoother
    fused, confidence = fuse_distribution(face=face, voice=voice, text=text)
    averaged, primary = smoother.smooth(key, fused)
    valence, arousal = _valence_arousal(averaged)
    return EmotionState(
        primary_emotion=primary,  # type: ignore[arg-type]
        valence=valence,
        arousal=arousal,
        confidence=round(confidence, 3),
        language=language,  # type: ignore[arg-type]
        modalities={
            "face": _modality_summary(face),
            "voice": _modality_summary(voice),
            "text": _modality_summary(text),
        },
        fusion="late_weighted",
        smoothed=True,
    )


def to_device_event(
    state: EmotionState,
    *,
    space_id: str,
    zone: str | None = None,
    message_id: str | None = None,
    inference_model: str | None = None,
) -> DeviceEventCreate:
    """把 EmotionState 序列化成 emotion_detected 设备事件（落 device_events，不含原始音视频）。"""
    attributes: dict[str, object] = {
        "primary_emotion": state.primary_emotion,
        "valence": state.valence,
        "arousal": state.arousal,
        "language": state.language,
        "modalities": {
            name: summary.model_dump(exclude_none=True) for name, summary in state.modalities.items()
        },
        "fusion": state.fusion,
        "smoothed": state.smoothed,
    }
    if inference_model:
        attributes["inference_model"] = inference_model
    return DeviceEventCreate(
        event_type="emotion_detected",
        severity="info",
        confidence=state.confidence,
        space_id=space_id,
        zone=zone,
        message_id=message_id,
        attributes=attributes,
    )


# ── 最近情绪状态（供 GET /api/emotion/state 与 agent 只读工具）──────────
_last_state: dict[str, EmotionState] = {}
_last_state_lock = Lock()


def set_last_state(space_id: str, state: EmotionState) -> None:
    with _last_state_lock:
        _last_state[space_id] = state


def get_last_state(space_id: str) -> EmotionState | None:
    with _last_state_lock:
        return _last_state.get(space_id)


def reset_emotion_state() -> None:
    """清空进程内平滑器历史与最近状态（测试隔离用）。"""
    default_smoother.reset()
    with _last_state_lock:
        _last_state.clear()
