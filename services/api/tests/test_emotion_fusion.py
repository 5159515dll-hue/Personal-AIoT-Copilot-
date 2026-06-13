"""M1 融合引擎单测：只验融合/平滑的逻辑正确性（不验情绪准确性，无标注数据）。"""
from __future__ import annotations

from app.emotion_fusion import (
    EmotionSmoother,
    fuse,
    fuse_and_smooth,
    fuse_distribution,
    to_device_event,
)
from app.models import DeviceEventCreate, EmotionModalityInput


def _reading(emotion: str, confidence: float, lang: str | None = None) -> EmotionModalityInput:
    return EmotionModalityInput(distribution={emotion: 1.0}, confidence=confidence, transcript_lang=lang)


def test_single_modality_drives_primary_and_marks_others_unavailable() -> None:
    state = fuse(face=_reading("happy", 0.9))
    assert state.primary_emotion == "happy"
    assert state.modalities["face"].status == "ok"
    assert state.modalities["face"].emotion == "happy"
    assert state.modalities["voice"].status == "unavailable"
    assert state.modalities["text"].status == "unavailable"
    assert state.valence > 0  # happy -> 正向 valence
    assert 0.0 <= state.confidence <= 1.0


def test_missing_text_modality_still_produces_valid_state() -> None:
    state = fuse(face=_reading("sad", 0.8), voice=_reading("sad", 0.7))
    assert state.primary_emotion == "sad"
    assert state.modalities["text"].status == "unavailable"
    assert state.valence < 0  # sad -> 负向 valence
    # 两模态一致时置信度取参与模态均值
    assert abs(state.confidence - 0.75) < 1e-6


def test_all_modalities_missing_falls_back_to_neutral_zero_confidence() -> None:
    state = fuse()
    assert state.primary_emotion == "neutral"
    assert state.confidence == 0.0
    assert all(m.status == "unavailable" for m in state.modalities.values())


def test_higher_confidence_modality_wins_on_conflict() -> None:
    # face 说 happy(高置信)，voice 说 angry(低置信) → 融合偏 happy
    state = fuse(face=_reading("happy", 0.9), voice=_reading("angry", 0.2))
    assert state.primary_emotion == "happy"


def test_zero_confidence_modality_is_ignored() -> None:
    dist, conf = fuse_distribution(
        face=_reading("happy", 0.0), voice=_reading("sad", 0.8)
    )
    # 零置信的 face 不参与，结果由 voice 决定
    assert max(dist, key=dist.get) == "sad"
    assert abs(conf - 0.8) < 1e-6


def test_hysteresis_suppresses_single_frame_jitter() -> None:
    smoother = EmotionSmoother(window=5, hysteresis=0.15)
    key = "space_x"
    # 先连续若干帧 sad，建立稳定 primary
    for _ in range(4):
        state = fuse_and_smooth(key=key, face=_reading("sad", 0.9), smoother=smoother)
    assert state.primary_emotion == "sad"
    # 单帧抖到 happy，但窗口平均下不足以越过滞回阈值 → 仍 sad
    jitter = fuse_and_smooth(key=key, face=_reading("happy", 0.9), smoother=smoother)
    assert jitter.primary_emotion == "sad"
    assert jitter.smoothed is True


def test_smoother_switches_primary_on_sustained_change() -> None:
    smoother = EmotionSmoother(window=3, hysteresis=0.15)
    key = "space_y"
    for _ in range(3):
        fuse_and_smooth(key=key, face=_reading("sad", 0.9), smoother=smoother)
    # 持续多帧 happy 后，窗口被 happy 占满 → 切换
    last = None
    for _ in range(3):
        last = fuse_and_smooth(key=key, face=_reading("happy", 0.95), smoother=smoother)
    assert last is not None and last.primary_emotion == "happy"


def test_smoother_isolates_keys() -> None:
    smoother = EmotionSmoother(window=3, hysteresis=0.15)
    fuse_and_smooth(key="a", face=_reading("happy", 0.9), smoother=smoother)
    state_b = fuse_and_smooth(key="b", face=_reading("sad", 0.9), smoother=smoother)
    # b 的历史不受 a 影响
    assert state_b.primary_emotion == "sad"


def test_to_device_event_serializes_to_valid_emotion_event() -> None:
    state = fuse(
        face=_reading("sad", 0.78),
        voice=_reading("sad", 0.71),
        language="mn",
    )
    event = to_device_event(
        state, space_id="space_living_001", zone="沙发", inference_model="ser+fer"
    )
    assert isinstance(event, DeviceEventCreate)
    assert event.event_type == "emotion_detected"
    assert event.space_id == "space_living_001"
    assert event.attributes["primary_emotion"] == "sad"
    assert event.attributes["language"] == "mn"
    assert event.attributes["modalities"]["text"]["status"] == "unavailable"
    assert event.attributes["modalities"]["face"]["emotion"] == "sad"
    assert event.attributes["inference_model"] == "ser+fer"
    # confidence 在 [0,1]
    assert event.confidence is not None and 0.0 <= event.confidence <= 1.0
