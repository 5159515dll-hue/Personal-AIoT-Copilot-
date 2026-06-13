"""M2 感知骨架单测（纯逻辑）：语种识别 + 文本情感（真推理）+ 视觉/语音桩。"""
from __future__ import annotations

from app.emotion_perception import detect_language, infer_face, infer_text, infer_voice
from app.models import EmotionModalityInput


def test_detect_language_heuristic() -> None:
    assert detect_language("我今天有点累") == "zh"
    assert detect_language("I am so tired today") == "en"
    # 西里尔蒙文
    assert detect_language("Би өнөөдөр ядарч байна") == "mn"


def test_infer_text_zh_detects_sadness() -> None:
    reading = infer_text("我今天好累，有点难过", "zh")
    assert reading is not None
    assert max(reading.distribution, key=reading.distribution.get) == "sad"
    assert reading.confidence > 0.5
    assert reading.transcript_lang == "zh"


def test_infer_text_en_detects_happiness() -> None:
    reading = infer_text("I feel great and happy today", "en")
    assert reading is not None
    assert max(reading.distribution, key=reading.distribution.get) == "happy"


def test_infer_text_no_keywords_is_low_confidence_neutral() -> None:
    reading = infer_text("今天星期三", "zh")
    assert reading is not None
    assert max(reading.distribution, key=reading.distribution.get) == "neutral"
    assert reading.confidence <= 0.3


def test_infer_text_mongolian_unavailable_in_v0() -> None:
    # M4 决策：v0 蒙语文本情感不可用，靠视觉+韵律兜底。
    assert infer_text("Би ядарч байна", "mn") is None


def test_infer_text_empty_returns_none() -> None:
    assert infer_text("", "zh") is None
    assert infer_text("   ", "en") is None


def test_infer_face_and_voice_are_passthrough_stubs() -> None:
    reading = EmotionModalityInput(distribution={"happy": 1.0}, confidence=0.8)
    assert infer_face(reading) is reading
    assert infer_voice(reading) is reading
    assert infer_face(None) is None
    assert infer_voice(None) is None
