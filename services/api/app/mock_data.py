from __future__ import annotations

import math
from datetime import datetime, timedelta

from app.models import Device, DeviceState, Metric, RiskLevel, RoomState, SensorReading
from app.time_utils import ensure_tz, now

UNITS = {
    Metric.temperature: "℃",
    Metric.humidity: "%",
    Metric.co2: "ppm",
    Metric.light: "lux",
    Metric.presence: "occupied",
}


def _round_bucket(value: datetime, minutes: int = 5) -> datetime:
    value = ensure_tz(value)
    bucket_minute = value.minute - (value.minute % minutes)
    return value.replace(minute=bucket_minute, second=0, microsecond=0)


def _daily_phase(timestamp: datetime) -> float:
    return (timestamp.hour * 60 + timestamp.minute) / 1440


def _presence(timestamp: datetime) -> float:
    hour = timestamp.hour
    if 8 <= hour < 12 or 14 <= hour < 18 or 20 <= hour < 23:
        return 1.0
    return 0.0


def reading_value(metric: Metric, timestamp: datetime) -> tuple[float, str]:
    timestamp = ensure_tz(timestamp)
    phase = _daily_phase(timestamp)
    presence = _presence(timestamp)
    day_wave = math.sin(2 * math.pi * phase)
    focus_wave = math.sin(2 * math.pi * ((timestamp.hour * 4 + timestamp.minute // 15) / 96))

    if metric == Metric.temperature:
        value = 24.2 + 2.1 * day_wave + 0.4 * focus_wave
        return round(value, 1), "ok"
    if metric == Metric.humidity:
        value = 48 - 6 * day_wave + 1.8 * focus_wave
        return round(value, 1), "ok"
    if metric == Metric.co2:
        base = 520 + 90 * math.sin(2 * math.pi * phase + 1.4)
        occupied_gain = 360 * presence
        afternoon_spike = 420 if 14 <= timestamp.hour < 16 and presence else 0
        evening_spike = 520 if 21 <= timestamp.hour < 23 and presence else 0
        value = base + occupied_gain + afternoon_spike + evening_spike
        quality = "anomaly" if value > 1200 else "ok"
        return round(value), quality
    if metric == Metric.light:
        daylight = max(0, math.sin(math.pi * ((timestamp.hour + timestamp.minute / 60) - 6) / 14))
        desk_light = 180 if 20 <= timestamp.hour < 23 and presence else 0
        value = 60 + 760 * daylight + desk_light
        return round(value), "ok"
    if metric == Metric.presence:
        return presence, "ok"
    raise ValueError(f"Unsupported metric: {metric}")


def get_reading(metric: Metric, timestamp: datetime | None = None) -> SensorReading:
    ts = _round_bucket(timestamp or now())
    value, quality = reading_value(metric, ts)
    return SensorReading(
        metric=metric,
        value=value,
        unit=UNITS[metric],
        timestamp=ts,
        quality=quality,
    )


def query_history(
    metric: Metric,
    start: datetime | None,
    end: datetime | None,
    bucket: str,
) -> list[SensorReading]:
    end_ts = _round_bucket(end or now())
    if start is None:
        start_ts = end_ts - timedelta(hours=24)
    else:
        start_ts = _round_bucket(start)
    step = _bucket_to_delta(bucket)
    if start_ts >= end_ts:
        raise ValueError("from must be before to")

    readings: list[SensorReading] = []
    cursor = start_ts
    while cursor <= end_ts:
        readings.append(get_reading(metric, cursor))
        cursor += step
    return readings


def summarize_metric(metric: Metric, hours: int = 24) -> dict[str, float | int]:
    end_ts = now()
    readings = query_history(metric, end_ts - timedelta(hours=hours), end_ts, "15m")
    values = [reading.value for reading in readings]
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 1),
        "samples": len(values),
    }


def current_room_state() -> RoomState:
    metrics = {metric: get_reading(metric) for metric in Metric}
    co2 = metrics[Metric.co2].value
    temperature = metrics[Metric.temperature].value
    humidity = metrics[Metric.humidity].value
    presence = metrics[Metric.presence].value

    anomalies: list[str] = []
    if co2 > 1200:
        anomalies.append("二氧化碳在当前时间窗口内持续高于专注阈值。")
    if temperature > 28:
        anomalies.append("当前温度对长时间专注学习偏高。")
    if humidity < 35 or humidity > 65:
        anomalies.append("当前湿度不在舒适区间。")
    if get_device_catalog()[0].online_state == DeviceState.offline:
        anomalies.append("主房间传感器已离线。")

    if co2 > 1200:
        status = "poor"
        health = 58
        recommendation = "建议开窗或短时通风后再继续深度学习。"
    elif co2 > 900:
        status = "watch"
        health = 76
        recommendation = "空气质量正在变差，建议未来 20 分钟内安排通风。"
    elif presence:
        status = "good"
        health = 88
        recommendation = "当前环境适合专注学习，可以保持现有光照。"
    else:
        status = "good"
        health = 92
        recommendation = "当前未检测到有人，自动化建议保持提醒模式。"

    return RoomState(
        timestamp=now(),
        health_score=health,
        status=status,
        summary=f"二氧化碳 {co2:.0f} ppm，温度 {temperature:.1f} C，湿度 {humidity:.1f}%。",
        metrics=metrics,
        anomalies=anomalies,
        recommendation=recommendation,
    )


def get_device_catalog() -> list[Device]:
    return [
        Device(
            id="room_node_01",
            name="房间传感器节点",
            type="esp32_sensor_node",
            location="desk",
            risk_level=RiskLevel.read_only,
            controllable=False,
            requires_confirmation=False,
            online_state=DeviceState.online,
            current_state={"sampling_interval_seconds": 60, "battery": 93},
        ),
        Device(
            id="desk_lamp_01",
            name="桌面台灯",
            type="smart_light",
            location="desk",
            risk_level=RiskLevel.low,
            controllable=True,
            requires_confirmation=False,
            online_state=DeviceState.online,
            current_state={"power": "off", "brightness": 62},
            connected_appliance="led_lamp",
            max_active_duration_minutes=240,
        ),
        Device(
            id="ambient_light_01",
            name="氛围灯",
            type="smart_light",
            location="shelf",
            risk_level=RiskLevel.low,
            controllable=True,
            requires_confirmation=False,
            online_state=DeviceState.online,
            current_state={"power": "on", "brightness": 38},
            connected_appliance="led_strip",
            max_active_duration_minutes=360,
        ),
        Device(
            id="fan_ir_01",
            name="红外风扇控制器",
            type="ir_remote",
            location="floor",
            risk_level=RiskLevel.medium,
            controllable=True,
            requires_confirmation=True,
            online_state=DeviceState.online,
            current_state={"power": "off", "mode": "natural"},
            connected_appliance="fan",
            max_active_duration_minutes=60,
        ),
        Device(
            id="smart_plug_01",
            name="未知负载智能插座",
            type="smart_plug",
            location="wall",
            risk_level=RiskLevel.high,
            controllable=False,
            requires_confirmation=True,
            online_state=DeviceState.online,
            current_state={"power": "off"},
            connected_appliance="未知",
        ),
        Device(
            id="smoke_alarm_01",
            name="烟雾报警器",
            type="safety_alarm",
            location="ceiling",
            risk_level=RiskLevel.forbidden,
            controllable=False,
            requires_confirmation=True,
            online_state=DeviceState.online,
            current_state={"muted": False, "self_test": "ok"},
        ),
    ]


def get_device(device_id: str) -> Device | None:
    return next((device for device in get_device_catalog() if device.id == device_id), None)


def _bucket_to_delta(bucket: str) -> timedelta:
    mapping = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
    }
    if bucket not in mapping:
        raise ValueError("bucket 必须是 5m、15m、1h 或 1d")
    return mapping[bucket]
