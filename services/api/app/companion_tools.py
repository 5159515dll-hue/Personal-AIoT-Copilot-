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
_DEVICE_KEYWORDS = ("设备", "台灯", "灯", "插座", "风扇", "开着", "关了", "在线", "device", "lamp")
_ANOMALY_KEYWORDS = ("异常", "不对劲", "报警", "出问题", "正常吗", "有没有问题", "安全吗")

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


def device_summary() -> str:
    """设备在线/可控状态摘要（吸收自原 agent 的设备读取）。失败返回空。"""
    try:
        from app.device_adapter import list_devices

        devices = list_devices("mock")
    except Exception:  # noqa: BLE001
        return ""
    if not devices:
        return ""
    online = sum(1 for d in devices if getattr(d.online_state, "value", str(d.online_state)) == "online")
    names = "、".join(
        f"{d.name}({getattr(d.online_state, 'value', d.online_state)})" for d in devices[:6]
    )
    return f"设备（{online}/{len(devices)} 在线）：{names}"


def anomaly_summary() -> str:
    """近 24h 活跃异常摘要（吸收自原 agent 的异常读取）。失败返回空。"""
    try:
        from app.anomaly_events import list_anomaly_events

        events = list_anomaly_events(source="mock", window="24h")
    except Exception:  # noqa: BLE001
        return ""
    active = [event for event in events if event.status == "active"]
    if not active:
        return "近 24 小时无活跃异常"
    bits = "；".join(f"{event.title}({event.severity})" for event in active[:4])
    return f"活跃异常：{bits}"


def gather_tool_context(message: str) -> str:
    """按意图聚合可注入的真实传感器/设备/异常上下文。无相关意图返回空串。"""
    parts: list[str] = []
    if _mentions(message, _ENV_KEYWORDS):
        env = environment_summary()
        if env:
            parts.append(env)
    if _mentions(message, _DEVICE_KEYWORDS):
        dev = device_summary()
        if dev:
            parts.append(dev)
    if _mentions(message, _ANOMALY_KEYWORDS):
        parts.append(anomaly_summary())
    return " ".join(parts)
