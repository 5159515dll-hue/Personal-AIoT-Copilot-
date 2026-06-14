"""陪伴指令 MQTT 下发（companion-v2 Step 1）。

聊天生成回应后，把"该做的手势(+回应文本)"发布到 MQTT 命令主题；机器人侧 agent
（robots/yanshee/companion_agent.py）订阅后用 YanAPI 执行。机器人在 LAN/NAT 后，
MQTT 出站订阅是最稳的下发通道（复用已部署的鉴权 broker）。

容错隔离：发布失败只记录日志，绝不影响对话回复。
"""
from __future__ import annotations

import json
import logging
import os

from paho.mqtt import publish as mqtt_publish

LOGGER = logging.getLogger("aiot.companion_mqtt")


def command_topic() -> str:
    return os.getenv("COMPANION_COMMAND_TOPIC", "aiot/companion/command")


def publish_companion_command(
    *,
    gesture: str | None,
    text: str | None = None,
    language: str | None = None,
    emotion: str | None = None,
) -> bool:
    """发布一条陪伴指令到 MQTT。失败返回 False（已吞异常，不影响对话）。"""
    if not gesture and not text:
        return False
    host = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    username = os.getenv("MQTT_USERNAME")
    auth = {"username": username, "password": os.getenv("MQTT_PASSWORD", "")} if username else None
    payload = json.dumps(
        {"gesture": gesture, "text": text, "language": language, "emotion": emotion},
        ensure_ascii=False,
    )
    try:
        mqtt_publish.single(
            command_topic(),
            payload=payload,
            qos=1,
            hostname=host,
            port=port,
            client_id="aiot-companion-publisher",
            auth=auth,
            keepalive=15,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - 下发失败不能影响对话
        LOGGER.warning("陪伴指令发布失败：%s", exc)
        return False
