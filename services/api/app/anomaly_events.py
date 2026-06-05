from __future__ import annotations

from datetime import timedelta
from typing import Literal

from app.database import latest_sensor_readings_db, query_sensor_history_db
from app.mock_data import current_room_state, query_history
from app.models import AnomalyEvent, Metric, SensorHealth, SensorReading
from app.sensor_health import evaluate_sensor_health
from app.time_utils import now

AnomalyWindow = Literal["24h", "7d"]
TelemetrySource = Literal["mock", "database"]


def list_anomaly_events(*, source: TelemetrySource = "mock", window: AnomalyWindow = "24h") -> list[AnomalyEvent]:
    reference = now()
    start = reference - (timedelta(days=7) if window == "7d" else timedelta(hours=24))
    bucket = "1h" if window == "7d" else "15m"

    if source == "database":
        latest = latest_sensor_readings_db()
        histories = {
            metric: query_sensor_history_db(metric, start, reference, bucket=bucket)
            for metric in (Metric.co2, Metric.noise, Metric.temperature, Metric.humidity)
        }
    else:
        room = current_room_state()
        latest = room.metrics
        histories = {
            metric: query_history(metric, start, reference, bucket)
            for metric in (Metric.co2, Metric.noise, Metric.temperature, Metric.humidity)
        }

    health = evaluate_sensor_health(latest, source=source, reference_time=reference)
    return build_anomaly_events(
        source=source,
        latest=latest,
        histories=histories,
        sensor_health=health,
        window=window,
    )


def build_anomaly_events(
    *,
    source: TelemetrySource,
    latest: dict[Metric, SensorReading],
    histories: dict[Metric, list[SensorReading]],
    sensor_health: list[SensorHealth],
    window: AnomalyWindow = "24h",
) -> list[AnomalyEvent]:
    events = [
        *_environment_events(source=source, histories=histories, latest=latest, window=window),
        *_sensor_health_events(source=source, health=sensor_health, reference_time=now()),
    ]
    return sorted(events, key=lambda item: (_severity_rank(item.severity), item.timestamp), reverse=True)[:12]


def _environment_events(
    *,
    source: TelemetrySource,
    histories: dict[Metric, list[SensorReading]],
    latest: dict[Metric, SensorReading],
    window: AnomalyWindow,
) -> list[AnomalyEvent]:
    events: list[AnomalyEvent] = []

    co2_peak = _peak_reading(histories.get(Metric.co2, []))
    if co2_peak and co2_peak.value > 900:
        severity: Literal["warning", "critical"] = "critical" if co2_peak.value > 1200 else "warning"
        latest_co2 = latest.get(Metric.co2)
        active = bool(latest_co2 and latest_co2.value > 900)
        events.append(
            _event(
                source=source,
                metric=Metric.co2,
                timestamp=co2_peak.timestamp,
                severity=severity,
                title="二氧化碳峰值偏高" if severity == "warning" else "二氧化碳峰值过高",
                detail=f"{_window_label(window)}内二氧化碳最高达到 {co2_peak.value:g} {co2_peak.unit}。",
                recommendation="安排通风并观察曲线是否回落；如果人在房间内，优先降低连续停留时间。",
                status="active" if active else "observed",
                evidence={"peak": co2_peak.model_dump(mode="json"), "latest": latest_co2.model_dump(mode="json") if latest_co2 else None},
            )
        )

    noise_peak = _peak_reading(histories.get(Metric.noise, []))
    if noise_peak and noise_peak.value > 65:
        latest_noise = latest.get(Metric.noise)
        events.append(
            _event(
                source=source,
                metric=Metric.noise,
                timestamp=noise_peak.timestamp,
                severity="warning",
                title="噪声峰值偏高",
                detail=f"{_window_label(window)}内噪声最高达到 {noise_peak.value:g} {noise_peak.unit}。",
                recommendation="降低环境噪声，或把智能体建议切换为提醒模式而不是设备动作。",
                status="active" if latest_noise and latest_noise.value > 65 else "observed",
                evidence={"peak": noise_peak.model_dump(mode="json"), "latest": latest_noise.model_dump(mode="json") if latest_noise else None},
            )
        )

    temperature_peak = _peak_reading(histories.get(Metric.temperature, []))
    if temperature_peak and temperature_peak.value > 28:
        latest_temperature = latest.get(Metric.temperature)
        events.append(
            _event(
                source=source,
                metric=Metric.temperature,
                timestamp=temperature_peak.timestamp,
                severity="warning",
                title="温度高于舒适区",
                detail=f"{_window_label(window)}内温度最高达到 {temperature_peak.value:g} {temperature_peak.unit}。",
                recommendation="优先采用人工通风、调整空调或降低设备发热，不由智能体直接控制高风险设备。",
                status="active" if latest_temperature and latest_temperature.value > 28 else "observed",
                evidence={
                    "peak": temperature_peak.model_dump(mode="json"),
                    "latest": latest_temperature.model_dump(mode="json") if latest_temperature else None,
                },
            )
        )

    humidity_readings = histories.get(Metric.humidity, [])
    humidity_low = _min_reading(humidity_readings)
    humidity_high = _peak_reading(humidity_readings)
    if humidity_low and humidity_low.value < 35:
        latest_humidity = latest.get(Metric.humidity)
        events.append(
            _event(
                source=source,
                metric=Metric.humidity,
                timestamp=humidity_low.timestamp,
                severity="warning",
                title="湿度低于舒适区",
                detail=f"{_window_label(window)}内湿度最低为 {humidity_low.value:g}{humidity_low.unit}。",
                recommendation="补水或增加空气湿度，并继续观察趋势。",
                status="active" if latest_humidity and latest_humidity.value < 35 else "observed",
                evidence={"min": humidity_low.model_dump(mode="json"), "latest": latest_humidity.model_dump(mode="json") if latest_humidity else None},
            )
        )
    elif humidity_high and humidity_high.value > 65:
        latest_humidity = latest.get(Metric.humidity)
        events.append(
            _event(
                source=source,
                metric=Metric.humidity,
                timestamp=humidity_high.timestamp,
                severity="warning",
                title="湿度高于舒适区",
                detail=f"{_window_label(window)}内湿度最高为 {humidity_high.value:g}{humidity_high.unit}。",
                recommendation="检查通风和除湿条件，避免长时间闷湿。",
                status="active" if latest_humidity and latest_humidity.value > 65 else "observed",
                evidence={"peak": humidity_high.model_dump(mode="json"), "latest": latest_humidity.model_dump(mode="json") if latest_humidity else None},
            )
        )

    return events


def _sensor_health_events(
    *,
    source: TelemetrySource,
    health: list[SensorHealth],
    reference_time,
) -> list[AnomalyEvent]:
    events: list[AnomalyEvent] = []
    for item in health:
        if item.status == "ok":
            continue
        severity: Literal["info", "warning", "critical"] = "critical" if item.status == "anomaly" else "warning"
        events.append(
            _event(
                source=source,
                metric=item.metric,
                timestamp=item.last_seen_at or reference_time,
                severity=severity,
                category="sensor_health",
                title=f"{_metric_label(item.metric)}传感器{_health_status_label(item.status)}",
                detail=item.message,
                recommendation="检查传感器供电、网络、payload 字段和入库链路；不要把异常读数直接用于自动控制。",
                status="active",
                evidence=item.model_dump(mode="json"),
            )
        )
    return events


def _event(
    *,
    source: TelemetrySource,
    metric: Metric | None,
    timestamp,
    severity: Literal["info", "warning", "critical"],
    title: str,
    detail: str,
    recommendation: str,
    status: Literal["active", "observed", "resolved"],
    evidence: dict,
    category: Literal["environment", "sensor_health"] = "environment",
) -> AnomalyEvent:
    metric_part = metric.value if metric else "room"
    return AnomalyEvent(
        id=f"{source}_{category}_{metric_part}_{int(timestamp.timestamp())}",
        timestamp=timestamp,
        source=source,
        severity=severity,
        category=category,
        metric=metric,
        title=title,
        detail=detail,
        recommendation=recommendation,
        status=status,
        evidence=evidence,
    )


def _peak_reading(readings: list[SensorReading]) -> SensorReading | None:
    return max(readings, key=lambda item: item.value, default=None)


def _min_reading(readings: list[SensorReading]) -> SensorReading | None:
    return min(readings, key=lambda item: item.value, default=None)


def _severity_rank(severity: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(severity, 0)


def _window_label(window: AnomalyWindow) -> str:
    return "最近 7 天" if window == "7d" else "最近 24 小时"


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


def _health_status_label(status: str) -> str:
    labels = {
        "stale": "过期",
        "anomaly": "异常",
        "offline": "离线",
        "unavailable": "不可用",
    }
    return labels.get(status, status)
