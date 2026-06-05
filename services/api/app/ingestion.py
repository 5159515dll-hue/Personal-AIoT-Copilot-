from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.models import Metric, SensorIngestRequest, SensorReading, SensorValueInput
from app.time_utils import now

DEFAULT_UNITS = {
    Metric.temperature: "℃",
    Metric.humidity: "%",
    Metric.co2: "ppm",
    Metric.light: "lux",
    Metric.presence: "occupied",
    Metric.noise: "dB",
}


def readings_from_request(request: SensorIngestRequest) -> list[SensorReading]:
    return [
        SensorReading(
            metric=item.metric,
            value=item.value,
            unit=item.unit or DEFAULT_UNITS[item.metric],
            timestamp=item.timestamp or now(),
            device_id=request.device_id,
            quality=item.quality,
        )
        for item in request.readings
    ]


def parse_mqtt_payload(payload: bytes | str) -> SensorIngestRequest:
    raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("MQTT 消息必须是 JSON object")

    if "readings" in data:
        timestamp = data.get("timestamp")
        readings = []
        for item in data["readings"]:
            if isinstance(item, dict):
                readings.append({**item, "timestamp": item.get("timestamp") or timestamp})
            else:
                readings.append(item)
        return SensorIngestRequest.model_validate({**data, "readings": readings, "source": "mqtt"})

    if "metric" in data and "value" in data:
        reading = SensorValueInput.model_validate(data)
        return SensorIngestRequest(
            device_id=str(data.get("device_id", "unknown_device")),
            readings=[reading],
            source="mqtt",
        )

    expanded = _expand_metric_map(data)
    if expanded:
        return SensorIngestRequest(
            device_id=str(data.get("device_id", "unknown_device")),
            readings=expanded,
            source="mqtt",
        )

    raise ValueError("MQTT 消息缺少 readings，或缺少 metric/value")


def _expand_metric_map(data: dict[str, Any]) -> list[SensorValueInput]:
    timestamp = _parse_timestamp(data.get("timestamp"))
    readings: list[SensorValueInput] = []
    for metric in Metric:
        if metric.value in data:
            readings.append(
                SensorValueInput(
                    metric=metric,
                    value=float(data[metric.value]),
                    timestamp=timestamp,
                )
            )
    return readings


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def safe_parse_mqtt_payload(payload: bytes | str) -> tuple[SensorIngestRequest | None, str | None]:
    try:
        return parse_mqtt_payload(payload), None
    except (ValueError, ValidationError, json.JSONDecodeError) as exc:
        return None, str(exc)
