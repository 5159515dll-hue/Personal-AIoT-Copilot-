"""服务器侧三模态情绪推理骨架（声明式可插拔）。

架构（plan §2）：v0 三模态推理放服务器，边缘只做廉价门控采集，原始音视频过境即弃。

- infer_text：**真推理**（语言相关模态）。v0 用确定性关键词词典做中/英情感，蒙语见 M4。
- detect_language：脚本启发式（蒙文/西里尔→mn，CJK→zh，否则 en）。
- infer_face / infer_voice：v0 **可插拔桩**——真实 FER/SER 模型未接入，直接采用调用方/边缘
  给出的分布。接真实模型时只替换这两个函数体，调用方与融合层不变。

所有出口统一为 EmotionModalityInput（7 类分布 + 置信度），喂给 emotion_fusion。
"""
from __future__ import annotations

from app.models import EMOTION_LABELS, EmotionModalityInput

# 关键词情感词典（v0 确定性桩，可替换为真实文本情感模型）。
_LEXICON: dict[str, dict[str, tuple[str, ...]]] = {
    "zh": {
        "happy": ("开心", "高兴", "快乐", "太好了", "幸福", "愉快", "喜欢", "满足", "棒", "好开心"),
        "sad": ("累", "难过", "伤心", "沮丧", "委屈", "想哭", "失落", "疲惫", "孤独", "难受", "压力"),
        "angry": ("生气", "愤怒", "烦", "讨厌", "气死", "恼火", "崩溃"),
        "fear": ("害怕", "担心", "紧张", "焦虑", "不安", "恐惧", "怕"),
        "surprise": ("惊讶", "没想到", "居然", "竟然", "震惊"),
        "disgust": ("恶心", "反感", "厌恶"),
    },
    "en": {
        "happy": ("happy", "glad", "great", "joy", "love", "wonderful", "awesome", "good"),
        "sad": ("tired", "sad", "down", "depressed", "lonely", "exhausted", "unhappy", "cry", "stressed"),
        "angry": ("angry", "mad", "annoyed", "furious", "hate"),
        "fear": ("afraid", "scared", "worried", "anxious", "nervous", "fear"),
        "surprise": ("surprised", "wow", "unexpected", "shocked"),
        "disgust": ("disgust", "gross", "sick"),
    },
}


def detect_language(text: str) -> str:
    """脚本启发式语种识别：传统蒙文/西里尔→mn，CJK→zh，否则 en。"""
    for ch in text:
        if "᠀" <= ch <= "᢯" or "Ѐ" <= ch <= "ӿ":
            return "mn"
    for ch in text:
        if "一" <= ch <= "鿿":
            return "zh"
    return "en"


def infer_text(transcript: str, language: str) -> EmotionModalityInput | None:
    """文本情感推理（真推理）。中/英用关键词词典；蒙语 v0 暂不可用（见 M4）。"""
    transcript = (transcript or "").strip()
    if not transcript:
        return None
    if language == "mn":
        return _infer_text_mongolian(transcript)
    lexicon = _LEXICON.get(language)
    if lexicon is None:
        return None
    lowered = transcript.lower()
    scores = {label: 0.0 for label in EMOTION_LABELS}
    for emotion, words in lexicon.items():
        for word in words:
            if word in lowered:
                scores[emotion] += 1.0
    hits = sum(scores.values())
    if hits <= 0:
        # 无情感词命中 → 中性为主、低置信。
        scores["neutral"] = 1.0
        return EmotionModalityInput(distribution=scores, confidence=0.2, transcript_lang=language)
    # 命中越多置信越高（封顶 0.9）。
    confidence = min(0.9, 0.5 + 0.1 * hits)
    return EmotionModalityInput(distribution=scores, confidence=confidence, transcript_lang=language)


def _infer_text_mongolian(transcript: str) -> EmotionModalityInput | None:
    """蒙古语文本情感（M4 务实降级 / M7 升级点）。

    决策（§7）：v0 仅识别支持蒙语、回应先中/英；数据两步走——先公开资源/零样本，再按需自建。
    当前无可用蒙语文本情感模型 → 返回 None（文本模态 unavailable），由视觉+韵律两模态兜底，
    事件 language 仍标 'mn'，蒙语作为感知侧特色成立。接入真实蒙语情感模型时只替换本函数体。
    """
    return None


def infer_face(reading: EmotionModalityInput | None) -> EmotionModalityInput | None:
    """视觉表情情绪（v0 可插拔桩）。

    真实 FER 模型尚未接入：直接采用调用方/边缘给出的分布。接真实模型时替换此函数体
    （输入改为帧/特征，输出仍为 EmotionModalityInput）。
    """
    return reading


def infer_voice(reading: EmotionModalityInput | None) -> EmotionModalityInput | None:
    """语音韵律情绪（v0 可插拔桩）。同 infer_face，待接真实 SER 模型。"""
    return reading
