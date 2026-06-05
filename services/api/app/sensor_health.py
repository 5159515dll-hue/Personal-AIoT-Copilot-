from __future__ import annotations

from datetime import timedelta
from typing import Literal

from app.models import Metric, SensorHealth, SensorReading
from app.time_utils import ensure_tz, now

STALE_AFTER_MINUTES = 30


def evaluate_sensor_health(
    readings: dict[Metric, SensorReading],
    *,
    source: Literal["mock", "database"],
    reference_time=None,
) -> list[SensorHealth]:
    reference = ensure_tz(reference_time or now())
    return [_health_for_metric(metric, readings.get(metric), source=source, reference_time=reference) for metric in Metric]


def _health_for_metric(
    metric: Metric,
    reading: SensorReading | None,
    *,
    source: Literal["mock", "database"],
    reference_time,
) -> SensorHealth:
    if reading is None:
        return SensorHealth(
            metric=metric,
            status="offline",
            source=source,
            message=f"{_metric_label(metric)}暂无最新读数，按离线处理。",
        )

    timestamp = ensure_tz(reading.timestamp)
    age = max(0, round((reference_time - timestamp).total_seconds() / 60, 1))
    if reading.quality == "anomaly":
        status: Literal["ok", "stale", "anomaly", "offline", "unavailable"] = "anomaly"
        message = f"{_metric_label(metric)}最新读数被标记为异常，需要复核传感器或环境状态。"
    elif reading.quality == "stale" or timestamp < reference_time - timedelta(minutes=STALE_AFTER_MINUTES):
        status = "stale"
        message = f"{_metric_label(metric)}最新读数距今 {age:g} 分钟，已超过 {STALE_AFTER_MINUTES} 分钟健康阈值。"
    else:
        status = "ok"
        message = f"{_metric_label(metric)}上报正常，最新读数距今 {age:g} 分钟。"

    return SensorHealth(
        metric=metric,
        status=status,
        source=source,
        device_id=reading.device_id,
        last_seen_at=timestamp,
        age_minutes=age,
        quality=reading.quality,
        value=reading.value,
        unit=reading.unit,
        message=message,
    )


def unavailable_sensor_health(source: Literal["database"], message: str) -> list[SensorHealth]:
    return [
        SensorHealth(
            metric=metric,
            status="unavailable",
            source=source,
            message=message,
        )
        for metric in Metric
    ]


def _metric_label(metric: Metric) -> str:
    labels = {
        Metric.temperature: "温度",
        Metric.humidity: "湿度",
        Metric.co2: "二氧化碳",
        Metric.light: "光照",
        Metric.presence: "有人状态",
        Metric.noise: "噪声",
    }
    return labels[metric]
