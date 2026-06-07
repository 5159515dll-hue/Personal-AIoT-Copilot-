#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

API_BASE_URL = os.getenv("AIOT_API_BASE_URL", "http://82.157.148.249").rstrip("/")
INTERNAL_TOKEN = os.getenv("AIOT_INTERNAL_API_TOKEN", "")
DEVICE_ID = os.getenv("AIOT_DEVICE_ID", "raspi_gateway_01")
DEVICE_NAME = os.getenv("AIOT_DEVICE_NAME", "树莓派网关")
FIRMWARE_VERSION = os.getenv("AIOT_GATEWAY_VERSION", "0.1.0")


def main() -> None:
    session = requests.Session()
    session.trust_env = False
    headers = {"Content-Type": "application/json"}
    if INTERNAL_TOKEN:
        headers["X-AIoT-Internal-Token"] = INTERNAL_TOKEN

    register(session, headers)
    sequence = 1
    last_heartbeat = 0.0
    last_telemetry = 0.0
    while True:
        now_ts = time.time()
        if now_ts - last_heartbeat >= 30:
            heartbeat(session, headers, sequence)
            sequence += 1
            last_heartbeat = now_ts
        if now_ts - last_telemetry >= 60:
            telemetry(session, headers, sequence)
            sequence += 1
            last_telemetry = now_ts
        time.sleep(1)


def register(session: requests.Session, headers: dict[str, str]) -> None:
    payload = {
        "device_id": DEVICE_ID,
        "display_name": DEVICE_NAME,
        "device_type": "raspberry_pi",
        "transport": "http",
        "protocol_version": "aiot.v1",
        "firmware_version": FIRMWARE_VERSION,
        "hardware_revision": "raspberry-pi",
        "location": "gateway",
        "capabilities": [
            {
                "kind": "gateway",
                "metrics": ["temperature", "humidity", "co2", "light", "presence", "noise"],
                "description": "树莓派环境网关",
            }
        ],
        "metadata": {"python": True, "direct_ip": True},
    }
    post_json(session, "/api/device-connections/register", payload, headers)


def heartbeat(session: requests.Session, headers: dict[str, str], sequence: int) -> None:
    payload = {
        "status": "online",
        "transport": "http",
        "protocol_version": "aiot.v1",
        "firmware_version": FIRMWARE_VERSION,
        "uptime_seconds": int(time.monotonic()),
        "message_id": f"{DEVICE_ID}-hb-{sequence}",
        "sequence": sequence,
        "sent_at": utc_now(),
        "metrics": {"process": "aiot_gateway"},
    }
    post_json(session, f"/api/device-connections/{DEVICE_ID}/heartbeat", payload, headers)


def telemetry(session: requests.Session, headers: dict[str, str], sequence: int) -> None:
    snapshot = read_sensor_snapshot()
    payload = {
        "protocol_version": "aiot.v1",
        "message_id": f"{DEVICE_ID}-tel-{sequence}",
        "sequence": sequence,
        "sent_at": utc_now(),
        "firmware_version": FIRMWARE_VERSION,
        "readings": [
            {"metric": metric, "value": value, "unit": unit, "quality": "ok"}
            for metric, (value, unit) in snapshot.items()
        ],
        "metadata": {"sample_id": uuid.uuid4().hex[:10]},
    }
    post_json(session, f"/api/device-connections/{DEVICE_ID}/telemetry", payload, headers)


def read_sensor_snapshot() -> dict[str, tuple[float, str]]:
    return {
        "temperature": (25.0, "℃"),
        "humidity": (48.0, "%"),
        "co2": (930.0, "ppm"),
        "light": (420.0, "lux"),
        "presence": (1.0, "occupied"),
        "noise": (48.5, "dB"),
    }


def post_json(session: requests.Session, path: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
    response = session.post(f"{API_BASE_URL}{path}", json=payload, headers=headers, timeout=8)
    response.raise_for_status()
    print(response.json())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
