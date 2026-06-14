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
import threading
import time
import urllib.request

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


def _heartbeat_once():
    """向服务器发一次心跳：让机器人出现在设备界面并保持在线。断网失败下次重试。"""
    base = getattr(config, "AIOT_API_BASE_URL", "")
    token = getattr(config, "DEVICE_TOKEN", "")
    device_id = getattr(config, "DEVICE_ID", "yanshee_robot_01")
    if not base or not token:
        return
    url = base.rstrip("/") + "/api/device-connections/" + device_id + "/heartbeat"
    data = json.dumps({"status": "online", "transport": "mqtt"}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "X-AIoT-Device-Token": token},
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        print("heartbeat failed: %s" % exc, flush=True)


def _heartbeat_loop():
    interval = getattr(config, "HEARTBEAT_INTERVAL", 45)
    while True:
        _heartbeat_once()
        time.sleep(max(10, interval))


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
    # 设备心跳线程：守护线程，独立于 MQTT，保证设备界面在线状态。
    hb = threading.Thread(target=_heartbeat_loop)
    hb.daemon = True
    hb.start()
    print("连接 %s:%s ..." % (config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT), flush=True)
    # connect_async + loop_forever：开机网络未就绪或断线都会自动重连（重启后只要联网就恢复）。
    try:
        client.reconnect_delay_set(min_delay=1, max_delay=30)
    except Exception:
        pass
    client.connect_async(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, 30)
    client.loop_forever()


if __name__ == "__main__":
    main()
