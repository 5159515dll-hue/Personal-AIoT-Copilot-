#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]


class MqttSmokeFailure(AssertionError):
    pass


def main() -> int:
    disable_proxy_env()
    env_file_values = read_dashboard_env()
    parser = argparse.ArgumentParser(description="运行 Personal AIoT Copilot MQTT 遥测入站烟测。")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("AIOT_INTERNAL_API_TOKEN") or env_file_values.get("AIOT_INTERNAL_API_TOKEN", ""))
    parser.add_argument("--broker-host", default=os.getenv("MQTT_BROKER_HOST") or env_file_values.get("MQTT_BROKER_HOST", "127.0.0.1"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("MQTT_BROKER_PORT") or env_file_values.get("MQTT_BROKER_PORT", "1883")))
    parser.add_argument("--topic", default=os.getenv("MQTT_SMOKE_TOPIC", "aiot/room/mqtt-smoke/telemetry"))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME") or env_file_values.get("MQTT_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD") or env_file_values.get("MQTT_PASSWORD", ""))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("MQTT_SMOKE_TIMEOUT", "30")))
    args = parser.parse_args()

    token = args.token.strip()
    if not token:
        print("失败：缺少 AIOT_INTERNAL_API_TOKEN。请通过环境变量或 .dashboard-env 提供内部服务令牌。", file=sys.stderr)
        return 1

    api_base_url = args.api_base_url.rstrip("/")
    device_id = f"room_node_mqtt_smoke_{int(time.time())}"
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    payload = build_payload(device_id, timestamp)

    print(f"开始 MQTT 遥测入站烟测：broker={args.broker_host}:{args.broker_port} topic={args.topic} API={api_base_url}")
    started = time.time()
    try:
        publish_payload(
            host=args.broker_host,
            port=args.broker_port,
            topic=args.topic,
            payload=payload,
            username=args.username.strip() or None,
            password=args.password.strip() or None,
            timeout=args.timeout,
        )
        print(f"通过：已发布 MQTT 遥测 device_id={device_id}")

        status = wait_for_database_ingest(api_base_url, token, device_id, timeout=args.timeout)
        print("通过：数据库遥测状态已出现本次 MQTT 设备")

        latest_co2 = status.get("latest_metrics", {}).get("co2", {})
        assert_equal(latest_co2.get("device_id"), device_id, "最新二氧化碳读数不是本次 MQTT 设备")
        assert_close(float(latest_co2.get("value", -1)), 965.0, "最新二氧化碳读数值不符合烟测 payload")
        print("通过：最新二氧化碳读数来自 MQTT 入站 payload")

        assert_mqtt_source(status)
        print("通过：遥测来源统计包含 MQTT")
    except Exception as exc:  # noqa: BLE001 - CLI should return a concise failure for deployment scripts.
        print(f"失败：MQTT 遥测入站烟测未通过：{exc}", file=sys.stderr)
        return 1

    elapsed = round(time.time() - started, 1)
    print(f"MQTT 遥测入站烟测完成，用时 {elapsed} 秒。")
    return 0


def disable_proxy_env() -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(name, None)


def read_dashboard_env() -> dict[str, str]:
    env_file = ROOT_DIR / ".dashboard-env"
    values: dict[str, str] = {}
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def build_payload(device_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "readings": [
            {"metric": "temperature", "value": 25.8, "unit": "℃"},
            {"metric": "humidity", "value": 46.5, "unit": "%"},
            {"metric": "co2", "value": 965, "unit": "ppm", "quality": "ok"},
            {"metric": "light", "value": 640, "unit": "lux"},
            {"metric": "presence", "value": 1, "unit": "occupied"},
            {"metric": "noise", "value": 47.2, "unit": "dB"},
        ],
    }


def publish_payload(
    *,
    host: str,
    port: int,
    topic: str,
    payload: dict[str, Any],
    username: str | None,
    password: str | None,
    timeout: float,
) -> None:
    try:
        from paho.mqtt import client as mqtt
    except ModuleNotFoundError as exc:
        raise MqttSmokeFailure("缺少 paho-mqtt。请先安装 services/mqtt-ingestor/requirements.txt。") from exc

    connected = Event()
    errors: list[str] = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"aiot-mqtt-smoke-{int(time.time())}")
    if username:
        client.username_pw_set(username, password)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        if mqtt_reason_code_succeeded(reason_code):
            connected.set()
        else:
            errors.append(f"MQTT 连接失败：{reason_code}")
            connected.set()

    client.on_connect = on_connect
    client.connect(host, port, keepalive=20)
    client.loop_start()
    try:
        if not connected.wait(timeout):
            raise MqttSmokeFailure("连接 MQTT broker 超时")
        if errors:
            raise MqttSmokeFailure(errors[0])
        info = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        info.wait_for_publish(timeout=timeout)
        if not info.is_published():
            raise MqttSmokeFailure("发布 MQTT 消息超时")
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MqttSmokeFailure(f"发布 MQTT 消息失败：rc={info.rc}")
    finally:
        client.disconnect()
        client.loop_stop()


def mqtt_reason_code_succeeded(reason_code: Any) -> bool:
    is_failure = getattr(reason_code, "is_failure", None)
    if callable(is_failure):
        return not is_failure()
    if isinstance(is_failure, bool):
        return not is_failure
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return str(reason_code).lower() in {"0", "success"}


def wait_for_database_ingest(api_base_url: str, token: str, device_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_status: dict[str, Any] | None = None
    while time.time() < deadline:
        status = api_request(api_base_url, "/api/telemetry/status", token, timeout=timeout)
        last_status = status
        devices = status.get("devices", [])
        latest_co2 = status.get("latest_metrics", {}).get("co2", {})
        if any(item.get("device_id") == device_id for item in devices) and latest_co2.get("device_id") == device_id:
            return status
        time.sleep(1)
    summary = json.dumps(last_status or {}, ensure_ascii=False, default=str)[:500]
    raise MqttSmokeFailure(f"等待 MQTT 入库超时，最后遥测状态：{summary}")


def assert_mqtt_source(status: dict[str, Any]) -> None:
    sources = status.get("sources", [])
    matching = [item for item in sources if item.get("source") == "mqtt"]
    assert_true(bool(matching), "遥测状态缺少 mqtt 来源")
    assert_true(int(matching[0].get("total_readings") or 0) >= 6, "mqtt 来源读数数量不足")


def api_request(api_base_url: str, path: str, token: str, *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{api_base_url}{path}",
        method="GET",
        headers={"X-AIoT-Internal-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise MqttSmokeFailure(f"HTTP 状态异常：{response.status}")
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise MqttSmokeFailure(f"HTTP {exc.code}：{detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise MqttSmokeFailure(f"无法访问 API：{exc}") from exc


def assert_close(actual: float, expected: float, message: str) -> None:
    if abs(actual - expected) > 0.01:
        raise MqttSmokeFailure(f"{message}，期望 {expected!r}，实际 {actual!r}")


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise MqttSmokeFailure(f"{message}，期望 {expected!r}，实际 {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise MqttSmokeFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
