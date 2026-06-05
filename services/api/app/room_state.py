from typing import Literal

from app.database import latest_sensor_readings_db
from app.models import Metric, RoomState, SensorReading
from app.time_utils import now


def current_database_room_state() -> RoomState:
    return database_room_state_from_readings(latest_sensor_readings_db())


def database_room_state_from_readings(readings: dict[Metric, SensorReading]) -> RoomState:
    timestamp = now()
    if not readings:
        return RoomState(
            timestamp=timestamp,
            health_score=0,
            status="watch",
            summary="数据库暂无当前房间遥测。",
            metrics={},
            anomalies=["数据库暂无当前房间遥测。"],
            recommendation="请确认 MQTT 入站服务和 TimescaleDB 写入链路已经启动。",
        )

    co2 = readings.get(Metric.co2)
    temperature = readings.get(Metric.temperature)
    humidity = readings.get(Metric.humidity)
    noise = readings.get(Metric.noise)
    anomalies: list[str] = []

    if co2 and co2.value > 1200:
        status: Literal["good", "watch", "poor"] = "poor"
        health = 58
        anomalies.append("数据库最新二氧化碳读数高于专注阈值。")
        recommendation = "建议优先通风，并继续观察数据库趋势是否回落。"
    elif co2 and co2.value > 900:
        status = "watch"
        health = 76
        recommendation = "空气质量正在变差，建议未来 20 分钟内安排通风。"
    elif co2:
        status = "good"
        health = 88
        recommendation = "数据库最新读数处于可接受范围，可以保持当前环境。"
    else:
        status = "watch"
        health = 68
        anomalies.append("数据库当前缺少二氧化碳读数。")
        recommendation = "请检查 MQTT payload 是否包含 co2 指标。"

    if temperature and temperature.value > 28:
        anomalies.append("数据库最新温度对长时间专注学习偏高。")
    if humidity and (humidity.value < 35 or humidity.value > 65):
        anomalies.append("数据库最新湿度不在舒适区间。")
    if noise and noise.value > 65:
        anomalies.append("数据库最新噪声等级偏高，可能影响专注学习。")
        if status == "good":
            status = "watch"
            health = min(health, 74)
            recommendation = "噪声等级偏高，建议降低环境噪声或调整学习节奏。"

    summary = "数据库最新读数：" + "，".join(
        f"{reading.metric.value} {reading.value:g} {reading.unit}"
        for reading in readings.values()
    )
    return RoomState(
        timestamp=timestamp,
        health_score=health,
        status=status,
        summary=summary,
        metrics=readings,
        anomalies=anomalies,
        recommendation=recommendation,
    )


def clean_database_error_text(exc: Exception) -> str:
    return str(exc).strip().rstrip("。.") + "。"
