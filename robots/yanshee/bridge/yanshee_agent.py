#!/usr/bin/env python3
"""Yanshee → AIoT Copilot 平台桥接（只读设备）。

在机器人内置树莓派上运行。用 yanapi 读取机器人真实状态（电量、姿态、IMU），
按平台 aiot.v1 协议注册 / 心跳 / 上报遥测，让机器人作为一个【只读设备】
出现在平台 /devices。

设计参照 examples/raspberry-pi-gateway/aiot_gateway.py，刻意【不包含任何运动控制】：
机器人是物理执行器，控制能力必须由服务端人工配置并经 policy.py 策略引擎确认，
不能由设备自注册获得。这一阶段机器人只上报、不接受控制，零物理风险。

用法（在机器人上）：
    AIOT_INTERNAL_API_TOKEN="<服务器内部令牌>" python yanshee_agent.py

未安装 yanapi 时仍可运行：会以"无硬件读数"降级上报，便于单独验证平台推送链路。
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

# 让 `import config` 找到 robots/yanshee/config.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
except ModuleNotFoundError:
    sys.exit("未找到 config.py，请先在 robots/yanshee/ 下执行: cp config.example.py config.py")

API_BASE_URL = config.AIOT_API_BASE_URL.rstrip("/")
INTERNAL_TOKEN = config.AIOT_INTERNAL_API_TOKEN
DEVICE_ID = config.DEVICE_ID
DEVICE_NAME = config.DEVICE_NAME
ROBOT_IP = config.ROBOT_IP
FIRMWARE_VERSION = os.getenv("YANSHEE_AGENT_VERSION", "0.1.0")

HEARTBEAT_INTERVAL = 30
TELEMETRY_INTERVAL = 60

# yanapi 是可选的：装了就读真实数据，没装就降级上报（仍保持设备在线）。
try:
    import YanAPI  # type: ignore

    YanAPI.yan_api_init(ROBOT_IP)
    _YANAPI = True
except Exception as exc:  # noqa: BLE001
    print(f"[warn] yanapi 不可用（{exc!r}）：以无硬件读数降级运行。")
    YanAPI = None  # type: ignore
    _YANAPI = False


def main() -> None:
    if not INTERNAL_TOKEN:
        print("[warn] 未设置 AIOT_INTERNAL_API_TOKEN，私有 API 会返回 401。"
              "请用环境变量注入服务器 .dashboard-env 里的内部令牌。")

    session = requests.Session()
    session.trust_env = False  # 关键：不走系统代理，直连平台（避免 HTTP_PROXY 干扰）
    headers = {"Content-Type": "application/json"}
    if INTERNAL_TOKEN:
        headers["X-AIoT-Internal-Token"] = INTERNAL_TOKEN

    register(session, headers)
    sequence = 1
    last_heartbeat = 0.0
    last_telemetry = 0.0
    while True:
        now_ts = time.time()
        if now_ts - last_heartbeat >= HEARTBEAT_INTERVAL:
            heartbeat(session, headers, sequence)
            sequence += 1
            last_heartbeat = now_ts
        if now_ts - last_telemetry >= TELEMETRY_INTERVAL:
            telemetry(session, headers, sequence)
            sequence += 1
            last_telemetry = now_ts
        time.sleep(1)


def register(session: requests.Session, headers: dict[str, str]) -> None:
    payload = {
        "device_id": DEVICE_ID,
        "display_name": DEVICE_NAME,
        # device_type 是封闭 Literal（无 robot/humanoid 值）；Yanshee 内置树莓派，
        # 用合法的 "raspberry_pi"，"humanoid_robot" 标记见下方 metadata。
        "device_type": "raspberry_pi",
        "transport": "http",
        "protocol_version": "aiot.v1",
        "firmware_version": FIRMWARE_VERSION,
        "hardware_revision": "raspberry-pi-3b",
        "location": "robot",
        # DeviceCapability.kind 是封闭 Literal：telemetry/control/gateway/diagnostic/media/vision/stream。
        # 机器人状态(电量/姿态)不在 Metric 6 个环境量里，故用 diagnostic + 空 metrics；电量走心跳字段。
        "capabilities": [
            {
                "kind": "diagnostic",
                "metrics": [],
                "description": "Yanshee 机器人状态（电量/姿态，只读）",
            },
            {
                "kind": "vision",
                "metrics": [],
                "description": "摄像头边缘识别事件（需先在 /spaces 启用本地媒体策略）",
            },
        ],
        # 明确声明：这是物理执行器，控制能力须服务端配置 + 策略确认，不在此自注册。
        "metadata": {"python": True, "humanoid_robot": True, "actuator": True, "control": "server_gated"},
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
        "metrics": {"yanapi": _YANAPI},
    }
    battery = read_battery_percent()
    if battery is not None:
        payload["battery_percent"] = battery
    post_json(session, f"/api/device-connections/{DEVICE_ID}/heartbeat", payload, headers)


def telemetry(session: requests.Session, headers: dict[str, str], sequence: int) -> None:
    readings = build_readings()
    if not readings:
        return  # 没有任何可上报读数时跳过，避免发空遥测
    payload = {
        "protocol_version": "aiot.v1",
        "message_id": f"{DEVICE_ID}-tel-{sequence}",
        "sequence": sequence,
        "sent_at": utc_now(),
        "firmware_version": FIRMWARE_VERSION,
        "readings": readings,
        "metadata": {"sample_id": uuid.uuid4().hex[:10]},
    }
    post_json(session, f"/api/device-connections/{DEVICE_ID}/telemetry", payload, headers)


def build_readings() -> list[dict[str, Any]]:
    # Metric 枚举只含 6 个环境量(temperature/humidity/co2/light/presence/noise)，机器人没有这些读数：
    # 电量经心跳 battery_percent 字段上报；姿态/IMU 需扩展 Metric 枚举或改用设备事件，v0 不经 telemetry。
    # 故返回空，telemetry() 会自动跳过。日后给机器人挂真实环境传感器时，在此按合法 Metric 组装 readings。
    return []


def read_battery_percent() -> float | None:
    if not _YANAPI:
        return None
    info = _safe_call("get_robot_battery_info")
    # yanapi 返回结构各版本不一，尽量从常见字段里取百分比。
    if isinstance(info, dict):
        data = info.get("data", info)
        if isinstance(data, dict):
            for key in ("battery", "percent", "percentage", "value"):
                val = data.get(key)
                if isinstance(val, (int, float)):
                    return float(val)
    return None


def _safe_call(func_name: str):
    func = getattr(YanAPI, func_name, None)
    if func is None or not callable(func):
        return None
    try:
        return func()
    except Exception:  # noqa: BLE001
        return None


def post_json(session: requests.Session, path: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
    try:
        response = session.post(f"{API_BASE_URL}{path}", json=payload, headers=headers, timeout=8)
        response.raise_for_status()
        print(f"{path} -> {response.json()}")
    except requests.RequestException as exc:
        print(f"[error] POST {path} 失败：{exc!r}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
