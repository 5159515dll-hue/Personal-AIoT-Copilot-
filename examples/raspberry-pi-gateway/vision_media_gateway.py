#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE_URL = os.getenv("AIOT_API_BASE_URL", "http://82.157.148.249").rstrip("/")
DEVICE_ID = os.getenv("AIOT_DEVICE_ID", "raspi_cam_01")
DEVICE_TOKEN = os.getenv("AIOT_DEVICE_TOKEN", "")
SPACE_ID = os.getenv("AIOT_SPACE_ID", "space_study_001")
ZONE = os.getenv("AIOT_ZONE", "门口")
SNAPSHOT_PATH = Path(os.getenv("AIOT_SNAPSHOT_PATH", "snapshot.jpg"))


def main() -> None:
    if not DEVICE_TOKEN:
        raise SystemExit("缺少 AIOT_DEVICE_TOKEN，请先在设备页生成设备令牌。")
    session = requests.Session()
    session.trust_env = False
    headers = {"X-AIoT-Device-Token": DEVICE_TOKEN}
    event = upload_presence_event(session, headers)
    if SNAPSHOT_PATH.exists():
        upload_snapshot(session, headers, event["id"])
    print("边缘事件已上报。RTSP 推流可单独运行 start_rtsp_stream()。")


def upload_presence_event(session: requests.Session, headers: dict[str, str]) -> dict:
    payload = {
        "event_type": "presence_detected",
        "severity": "info",
        "confidence": 0.91,
        "space_id": SPACE_ID,
        "zone": ZONE,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "attributes": {
            "person_count": 1,
            "edge_model": "local-yolo-lite",
            "identity_mode": "anonymous",
        },
    }
    response = session.post(
        f"{API_BASE_URL}/api/device-connections/{DEVICE_ID}/events",
        json=payload,
        headers=headers,
        timeout=8,
    )
    response.raise_for_status()
    return response.json()["event"]


def upload_snapshot(session: requests.Session, headers: dict[str, str], event_id: str) -> None:
    with SNAPSHOT_PATH.open("rb") as image:
        response = session.post(
            f"{API_BASE_URL}/api/device-connections/{DEVICE_ID}/media",
            headers=headers,
            data={"space_id": SPACE_ID, "zone": ZONE, "event_id": event_id},
            files={"file": (SNAPSHOT_PATH.name, image, "image/jpeg")},
            timeout=20,
        )
    response.raise_for_status()
    print(response.json())


def start_rtsp_stream() -> None:
    command = (
        "libcamera-vid -t 0 --inline --width 1280 --height 720 --framerate 15 -o - "
        f"| ffmpeg -re -i - -c:v copy -f rtsp rtsp://82.157.148.249:8554/{DEVICE_ID}"
    )
    subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    main()
