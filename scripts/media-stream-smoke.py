#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    disable_proxy_env()
    parser = argparse.ArgumentParser(description="运行媒体、边缘事件和实时流 API 烟测。")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("AIOT_INTERNAL_API_TOKEN") or read_internal_token())
    args = parser.parse_args()
    if not args.token:
        print("失败：缺少 AIOT_INTERNAL_API_TOKEN。请通过环境变量或 .dashboard-env 提供内部服务令牌。", file=sys.stderr)
        return 1

    api = args.api_base_url.rstrip("/")
    run_id = str(int(time.time()))
    space_id = f"space_media_smoke_{run_id}"
    device_id = f"raspi_media_smoke_{run_id}"
    headers = {"X-AIoT-Internal-Token": args.token}
    media_id: str | None = None
    stream_id: str | None = None

    try:
        print(f"开始媒体与实时流烟测：API={api}")
        create_space(api, headers, space_id, device_id)
        credential = request_json(api, f"/api/devices/{device_id}/credentials", method="POST", headers=headers)
        device_headers = {"X-AIoT-Device-Token": credential["token"]}
        event = request_json(
            api,
            f"/api/device-connections/{device_id}/events",
            method="POST",
            headers=device_headers,
            payload={
                "event_type": "presence_detected",
                "severity": "info",
                "confidence": 0.93,
                "space_id": space_id,
                "zone": "门口",
                "attributes": {"person_count": 1, "smoke_run": run_id},
            },
        )["event"]
        print("通过：设备令牌可上报边缘事件")

        asset = upload_media(api, device_headers, device_id, space_id, event["id"])
        media_id = asset["id"]
        assert asset["media_type"] == "image"
        print("通过：设备令牌可上传事件图片")

        content = request_bytes(api, f"/api/media-assets/{media_id}/content", headers=headers)
        assert content.startswith(b"\xff\xd8")
        print("通过：媒体内容可通过受保护接口读取")

        stream = request_json(
            api,
            "/api/streams",
            method="POST",
            headers=headers,
            payload={
                "device_id": device_id,
                "space_id": space_id,
                "name": "媒体烟测实时流",
                "rtsp_url": f"rtsp://82.157.148.249:8554/{device_id}",
                "zone": "门口",
            },
        )["stream"]
        stream_id = stream["id"]
        assert stream["hls_url"].endswith("/index.m3u8")
        print("通过：实时流配置可创建并返回 HLS 代理地址")

        status, _ = request_status(api, f"/api/streams/{stream_id}/hls/index.m3u8", headers=headers)
        assert status in {404, 502}
        print("通过：未推流时 HLS 代理返回明确不可用状态")

        request_json(api, f"/api/media-assets/{media_id}", method="DELETE", headers=headers)
        media_id = None
        request_json(api, f"/api/streams/{stream_id}", method="DELETE", headers=headers)
        stream_id = None
        request_json(api, f"/api/spaces/{space_id}", method="DELETE", headers=headers)
        print("通过：临时媒体、实时流和空间可清理")
        print("媒体与实时流烟测完成。")
        return 0
    finally:
        if media_id:
            request_status(api, f"/api/media-assets/{media_id}", method="DELETE", headers=headers, ignore_errors=True)
        if stream_id:
            request_status(api, f"/api/streams/{stream_id}", method="DELETE", headers=headers, ignore_errors=True)
        request_status(api, f"/api/spaces/{space_id}", method="DELETE", headers=headers, ignore_errors=True)


def create_space(api: str, headers: dict[str, str], space_id: str, device_id: str) -> None:
    request_json(
        api,
        "/api/spaces",
        method="POST",
        headers=headers,
        payload={
            "id": space_id,
            "name": "媒体烟测空间",
            "space_type": "lab",
            "location_label": "媒体烟测",
            "timezone": "Asia/Shanghai",
            "device_ids": [device_id],
            "zones": ["门口"],
            "perception": {
                "camera": "local_only",
                "face_recognition": "local_only",
                "emotion_recognition": "disabled",
                "location_tracking": "local_only",
                "image_retention": "event_media",
                "privacy_mode": "local_only",
                "media_policy": {
                    "allow_realtime_stream": True,
                    "allow_event_media": True,
                    "media_retention_days": 7,
                    "event_retention_days": 30,
                },
                "notes": "媒体烟测临时空间。",
            },
        },
    )
    print("通过：临时空间已启用本地视觉与媒体策略")


def upload_media(api: str, headers: dict[str, str], device_id: str, space_id: str, event_id: str) -> dict[str, Any]:
    boundary = f"----aiot-smoke-{int(time.time())}"
    image_bytes = b"\xff\xd8\xff\xdbaiot-smoke-image"
    fields = {
        "space_id": space_id,
        "zone": "门口",
        "event_id": event_id,
    }
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="file"; filename="snapshot.jpg"\r\n')
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(image_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    upload_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    return request_json(
        api,
        f"/api/device-connections/{device_id}/media",
        method="POST",
        headers=upload_headers,
        data=bytes(body),
    )["asset"]


def request_json(
    api: str,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: Any | None = None,
    data: bytes | None = None,
) -> Any:
    status, body = request_status(api, path, method=method, headers=headers, payload=payload, data=data)
    if status < 200 or status >= 300:
        raise AssertionError(f"{method} {path} 失败：HTTP {status} {body.decode('utf-8', errors='replace')}")
    return json.loads(body.decode("utf-8"))


def request_bytes(api: str, path: str, *, headers: dict[str, str] | None = None) -> bytes:
    status, body = request_status(api, path, headers=headers)
    if status != 200:
        raise AssertionError(f"GET {path} 失败：HTTP {status}")
    return body


def request_status(
    api: str,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: Any | None = None,
    data: bytes | None = None,
    ignore_errors: bool = False,
) -> tuple[int, bytes]:
    body = data
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(f"{api}{path}", data=body, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        content = exc.read()
        if ignore_errors:
            return exc.code, content
        return exc.code, content


def read_internal_token() -> str:
    env_file = ROOT_DIR / ".dashboard-env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("AIOT_INTERNAL_API_TOKEN="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def disable_proxy_env() -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(name, None)


if __name__ == "__main__":
    raise SystemExit(main())
