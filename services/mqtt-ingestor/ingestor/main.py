from __future__ import annotations

import logging
import os
import signal
import sys

from paho.mqtt import client as mqtt

from app.database import init_db, insert_sensor_readings
from app.ingestion import readings_from_request, safe_parse_mqtt_payload

LOGGER = logging.getLogger("aiot.mqtt_ingestor")


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    topic = os.getenv("MQTT_TOPIC", "aiot/room/+/telemetry")
    host = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    client_id = os.getenv("MQTT_CLIENT_ID", "aiot-copilot-ingestor")

    init_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    if username:
        client.username_pw_set(username, password)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        if mqtt_reason_code_succeeded(reason_code):
            LOGGER.info("已连接 MQTT broker %s:%s，订阅 %s", host, port, topic)
            client.subscribe(topic, qos=1)
        else:
            LOGGER.error("MQTT 连接失败：%s", reason_code)

    def on_message(client, userdata, message) -> None:
        request, error = safe_parse_mqtt_payload(message.payload)
        if error or request is None:
            LOGGER.warning("丢弃非法 MQTT 消息 topic=%s error=%s", message.topic, error)
            return
        readings = readings_from_request(request)
        stored = insert_sensor_readings(readings, source="mqtt")
        LOGGER.info(
            "已写入 MQTT 遥测 topic=%s device_id=%s stored=%s",
            message.topic,
            request.device_id,
            stored,
        )

    def stop(signum, frame) -> None:
        LOGGER.info("收到停止信号，断开 MQTT 连接。")
        client.disconnect()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=60)
    client.loop_forever(retry_first_connection=True)
    return 0


def mqtt_reason_code_succeeded(reason_code) -> bool:
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


if __name__ == "__main__":
    sys.exit(main())
