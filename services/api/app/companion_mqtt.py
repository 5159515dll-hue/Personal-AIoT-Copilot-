"""陪伴/视觉指令 MQTT 下发（companion-v2）。

聊天生成回应后把手势(+文本)发布到命令主题；前端拍照按钮发布拍照指令。机器人侧 agent
（robots/yanshee/companion_agent.py）订阅后用 YanAPI 执行（播手势 / 拍照上传）。机器人在
LAN/NAT 后，MQTT 出站订阅是最稳的下发通道（复用已部署的鉴权 broker）。

容错隔离：发布失败只记录日志，绝不影响对话/请求。
"""
from __future__ import annotations

import json
import logging
import os

from paho.mqtt import publish as mqtt_publish

LOGGER = logging.getLogger("aiot.companion_mqtt")


def command_topic() -> str:
    return os.getenv("COMPANION_COMMAND_TOPIC", "aiot/companion/command")


def _publish(payload: dict) -> bool:
    host = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    username = os.getenv("MQTT_USERNAME")
    auth = {"username": username, "password": os.getenv("MQTT_PASSWORD", "")} if username else None
    try:
        mqtt_publish.single(
            command_topic(),
            payload=json.dumps(payload, ensure_ascii=False),
            qos=1,
            hostname=host,
            port=port,
            client_id="aiot-companion-publisher",
            auth=auth,
            keepalive=15,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - 下发失败不能影响主流程
        LOGGER.warning("陪伴指令发布失败：%s", exc)
        return False


def publish_companion_command(
    *,
    gesture: str | None,
    text: str | None = None,
    language: str | None = None,
    emotion: str | None = None,
) -> bool:
    """聊天回应后下发手势指令（Step1 手势；Step2 起含 text 做 TTS）。"""
    if not gesture and not text:
        return False
    return _publish({"gesture": gesture, "text": text, "language": language, "emotion": emotion})


def publish_vision_capture(*, space_id: str, zone: str | None = None) -> bool:
    """下发拍照指令：机器人收到后 take_vision_photo + 上传到媒体库（出现在 /vision）。"""
    return _publish({"action": "capture", "space_id": space_id, "zone": zone})


def publish_vision_live(*, space_id: str, action: str) -> bool:
    """下发直播开关：action 为 'live_start' / 'live_stop'，机器人侧开/关 MJPEG 出站中继。"""
    return _publish({"action": action, "space_id": space_id})
