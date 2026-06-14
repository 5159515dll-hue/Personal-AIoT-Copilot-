#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器人侧陪伴 agent（companion-v2 Step 1）。**Python 3.5 兼容**。

订阅 MQTT 陪伴指令主题 → 用 YanAPI 播放对应手势（经 companion_gesture.play_gesture，
内部用 get_motion_list() 校验真实动作名后 sync_play_motion）。
Step 2 会在收到指令时同时做 TTS（start_voice_tts）；Step 3 会加机器人侧语音输入。
安全：手势已在平台经 policy 门控；本机只播原地安全动作。**运行前清空机器人周围、远离桌沿。**

用法（在机器人树莓派上）：
    cp config.example.py config.py    # 填 ROBOT_IP=127.0.0.1 与 MQTT_PASSWORD
    python3 companion_agent.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from companion_gesture import play_gesture
from paho.mqtt import client as mqtt

TOPIC = getattr(config, "COMMAND_TOPIC", "aiot/companion/command")
CLIENT_ID = getattr(config, "MQTT_CLIENT_ID", "yanshee-companion-agent")


def on_connect(client, userdata, flags, rc, *args):
    print("MQTT connected rc=%s; 订阅 %s" % (rc, TOPIC), flush=True)
    client.subscribe(TOPIC, qos=1)


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
    except Exception as exc:
        print("非法消息：%s" % exc, flush=True)
        return
    gesture = data.get("gesture")
    text = (data.get("text") or "")[:50]
    print("收到指令 gesture=%s text=%s" % (gesture, text), flush=True)
    if not gesture:
        return
    try:
        play_gesture(gesture)
    except Exception as exc:
        print("play_gesture 出错：%s" % exc, flush=True)


def _make_client():
    # 兼容 paho v2（需 CallbackAPIVersion）与 v1（树莓派 3.5 上为 1.6.x）。
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=CLIENT_ID)
    except (AttributeError, TypeError):
        return mqtt.Client(client_id=CLIENT_ID)


def main():
    client = _make_client()
    if getattr(config, "MQTT_USERNAME", None):
        client.username_pw_set(config.MQTT_USERNAME, getattr(config, "MQTT_PASSWORD", ""))
    client.on_connect = on_connect
    client.on_message = on_message
    print("连接 %s:%s ..." % (config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT), flush=True)
    client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, 30)
    client.loop_forever()


if __name__ == "__main__":
    main()
