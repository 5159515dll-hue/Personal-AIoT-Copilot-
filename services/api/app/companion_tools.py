"""陪伴工具上下文（plan companion-v2 §6 / V2.3）。

按确定性意图从传感器/事件拉取真实数据，组成紧凑文本注入提示——让陪伴模型**基于真实数据作答**
（工具优先：绝不编传感器数据）。这是"拉(on-demand)"的确定性版；全 LLM function-calling 留 V2.6。

吸收了原 agent 的设备/环境读取能力，但收口为"喂给陪伴模型的上下文"，而非独立问答 agent。
容错：任一读取失败降级为空，不影响对话。
"""
from __future__ import annotations

from app.mock_data import current_room_state

_ENV_KEYWORDS = (
    "房间", "屋里", "屋子", "空气", "闷", "温度", "几度", "湿度", "潮", "干燥",
    "二氧化碳", "co2", "光照", "亮", "暗", "噪音", "噪声", "吵", "安静吗", "环境", "凉", "热不热",
)
_EVENT_KEYWORDS = ("发生了什么", "刚才", "检测到", "有人吗", "动静", "事件")

_METRIC_LABEL: dict[str, str] = {
    "temperature": "温度",
    "humidity": "湿度",
    "co2": "二氧化碳",
    "light": "光照",
    "presence": "人体存在",
    "noise": "噪声",
}


def _mentions(message: str, keywords: tuple[str, ...]) -> bool:
    lowered = (message or "").lower()
    return any(keyword in lowered for keyword in keywords)


def environment_summary() -> str:
    """当前环境读数的紧凑摘要。失败返回空。"""
    try:
        state = current_room_state()
    except Exception:  # noqa: BLE001
        return ""
    bits: list[str] = []
    for metric, reading in state.metrics.items():
        key = getattr(metric, "value", str(metric))
        label = _METRIC_LABEL.get(key, key)
        unit = getattr(reading, "unit", None) or ""
        bits.append(f"{label}{reading.value}{unit}")
    if not bits:
        return ""
    return f"当前环境读数：{'、'.join(bits)}（状态：{state.status}；{state.summary}）"


def gather_tool_context(message: str) -> str:
    """按意图聚合可注入的真实传感器上下文。无相关意图返回空串。"""
    parts: list[str] = []
    if _mentions(message, _ENV_KEYWORDS):
        env = environment_summary()
        if env:
            parts.append(env)
    return " ".join(parts)
