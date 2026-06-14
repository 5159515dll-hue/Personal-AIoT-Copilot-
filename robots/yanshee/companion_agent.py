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
    action = data.get("action")
    if action == "capture":
        print("收到拍照指令 space=%s" % data.get("space_id"), flush=True)
        _capture_and_upload(data.get("space_id"), data.get("zone", ""))
        return
    if action == "live_start":
        print("收到直播开始 space=%s" % data.get("space_id"), flush=True)
        _live_start(data.get("space_id"))
        return
    if action == "live_stop":
        print("收到直播停止", flush=True)
        _live_stop()
        return
    gesture = data.get("gesture")
    text = data.get("text") or ""
    print("收到指令 gesture=%s text=%s" % (gesture, text[:50]), flush=True)
    # Step 2：先异步开始朗读（start_voice_tts 立即返回），再播手势 → 说话与动作并行。
    if text:
        _speak(text)
    if gesture:
        try:
            play_gesture(gesture)
        except Exception as exc:
            print("play_gesture 出错：%s" % exc, flush=True)


def _speak(text):
    """朗读陪伴回复（Step 2）。start_voice_tts 异步：立即返回，与手势同时进行；interrupt=True 让新回复打断旧的。"""
    try:
        import YanAPI
        YanAPI.yan_api_init(getattr(config, "ROBOT_IP", "127.0.0.1"))
        YanAPI.start_voice_tts(text[:300], True)
    except Exception as exc:
        print("tts 出错：%s" % exc, flush=True)


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


def _upload_media(path, space_id, zone, base, token, device_id):
    """把本地照片以 multipart 上传到 /api/device-connections/{id}/media（device token）。3.5 手写 multipart。"""
    boundary = "----aiotyanshee7e3b9c"
    with open(path, "rb") as fh:
        img = fh.read()
    fname = os.path.basename(path)

    def _field(name, value):
        return ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, name, value)).encode("utf-8")

    body = _field("space_id", space_id)
    if zone:
        body += _field("zone", zone)
    body += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: image/jpeg\r\n\r\n" % (boundary, fname)).encode("utf-8")
    body += img + b"\r\n" + ("--%s--\r\n" % boundary).encode("utf-8")
    url = base.rstrip("/") + "/api/device-connections/" + device_id + "/media"
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary, "X-AIoT-Device-Token": token},
    )
    urllib.request.urlopen(req, timeout=30).read()


def _capture_and_upload(space_id, zone):
    """拍一张照片并上传到服务器媒体库（出现在 /vision）。"""
    base = getattr(config, "AIOT_API_BASE_URL", "")
    token = getattr(config, "DEVICE_TOKEN", "")
    device_id = getattr(config, "DEVICE_ID", "yanshee_robot_01")
    if not (base and token and space_id):
        print("capture: 缺少 base/token/space_id，跳过", flush=True)
        return
    try:
        import YanAPI
        YanAPI.yan_api_init(getattr(config, "ROBOT_IP", "127.0.0.1"))
        res = YanAPI.take_vision_photo(getattr(config, "PHOTO_RESOLUTION", "640x480"))
        name = (res or {}).get("data", {}).get("name")
        if not name:
            print("capture: take_vision_photo 无 name：%s" % res, flush=True)
            return
        YanAPI.get_vision_photo(name, "/tmp/")
    except Exception as exc:
        print("capture: 拍照失败 %s" % exc, flush=True)
        return
    try:
        _upload_media("/tmp/" + name, space_id, zone, base, token, device_id)
        print("capture: 已上传照片 %s" % name, flush=True)
    except Exception as exc:
        print("capture: 上传失败 %s" % exc, flush=True)


# ---- 实时画面（MJPEG 中继直播）：收到 live_start 后把本地 open_vision_stream 的
# MJPEG 逐帧出站推到服务器 vision-live；浏览器轮询最新帧。看门狗：浏览器停发 keepalive
# （关页面）则 LIVE_IDLE_TIMEOUT 秒后自动停，避免摄像头一直开着。----
_LIVE_LOCK = threading.Lock()
_LIVE = {"thread": None, "stop": None, "space_id": None, "last_keepalive": 0.0}


def _post_frame(url, token, frame):
    req = urllib.request.Request(
        url, data=frame, method="POST",
        headers={"Content-Type": "image/jpeg", "X-AIoT-Device-Token": token},
    )
    urllib.request.urlopen(req, timeout=10).read()


def _live_loop(space_id, stop_event):
    base = getattr(config, "AIOT_API_BASE_URL", "")
    token = getattr(config, "DEVICE_TOKEN", "")
    device_id = getattr(config, "DEVICE_ID", "yanshee_robot_01")
    mjpeg_url = getattr(config, "LIVE_LOCAL_MJPEG_URL", "http://127.0.0.1:8000/stream.mjpg")
    resolution = getattr(config, "LIVE_RESOLUTION", "640x480")
    target_fps = float(getattr(config, "LIVE_TARGET_FPS", 5))
    idle_timeout = float(getattr(config, "LIVE_IDLE_TIMEOUT", 60))
    min_interval = (1.0 / target_fps) if target_fps > 0 else 0.2
    ingest_url = base.rstrip("/") + "/api/device-connections/" + device_id + "/vision-live?space_id=" + space_id

    # YanAPI 内部用 asyncio；在工作线程里 get_event_loop 会报「no current event loop」，
    # 故先给本线程建一个事件循环（主线程的回调路径不需要，这里是独立线程）。
    try:
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception as exc:
        print("live: 建事件循环失败 %s" % exc, flush=True)

    try:
        import YanAPI
        YanAPI.yan_api_init(getattr(config, "ROBOT_IP", "127.0.0.1"))
        YanAPI.open_vision_stream(resolution)
    except Exception as exc:
        print("live: open_vision_stream 失败 %s" % exc, flush=True)

    last_post = 0.0
    print("live: 开始中继 space=%s -> %s" % (space_id, ingest_url), flush=True)
    while not stop_event.is_set():
        with _LIVE_LOCK:
            last_ka = _LIVE["last_keepalive"]
        if time.time() - last_ka > idle_timeout:
            print("live: 看门狗超时，自动停止", flush=True)
            break
        try:
            stream = urllib.request.urlopen(mjpeg_url, timeout=8)
        except Exception as exc:
            print("live: 打开本地 MJPEG 失败 %s（2s 后重试）" % exc, flush=True)
            time.sleep(2)
            continue
        buf = b""
        try:
            while not stop_event.is_set():
                with _LIVE_LOCK:
                    last_ka = _LIVE["last_keepalive"]
                if time.time() - last_ka > idle_timeout:
                    print("live: 看门狗超时，自动停止", flush=True)
                    stop_event.set()
                    break
                chunk = stream.read(8192)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 4 * 1024 * 1024:   # 找不到完整帧时避免无限增长
                    buf = buf[-1024 * 1024:]
                while True:
                    soi = buf.find(b"\xff\xd8")
                    if soi < 0:
                        break
                    eoi = buf.find(b"\xff\xd9", soi + 2)
                    if eoi < 0:
                        if soi > 0:
                            buf = buf[soi:]
                        break
                    frame = buf[soi:eoi + 2]
                    buf = buf[eoi + 2:]
                    now_t = time.time()
                    if now_t - last_post < min_interval:
                        continue   # 限速丢帧
                    last_post = now_t
                    try:
                        _post_frame(ingest_url, token, frame)
                    except Exception as exc:
                        print("live: 推帧失败 %s" % exc, flush=True)
        except Exception as exc:
            print("live: 读流出错 %s" % exc, flush=True)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    try:
        import YanAPI
        YanAPI.close_vision_stream()
    except Exception as exc:
        print("live: close_vision_stream %s" % exc, flush=True)
    print("live: 中继已停止 space=%s" % space_id, flush=True)


def _live_start(space_id):
    if not space_id:
        return
    with _LIVE_LOCK:
        _LIVE["last_keepalive"] = time.time()
        running = _LIVE["thread"] is not None and _LIVE["thread"].is_alive()
        if running and _LIVE["space_id"] == space_id:
            return   # 已在直播该空间：仅刷新 keepalive（浏览器心跳）
        if running and _LIVE["stop"] is not None:
            _LIVE["stop"].set()   # 切换空间：先停旧的
        stop_event = threading.Event()
        t = threading.Thread(target=_live_loop, args=(space_id, stop_event))
        t.daemon = True
        _LIVE["thread"] = t
        _LIVE["stop"] = stop_event
        _LIVE["space_id"] = space_id
        t.start()


def _live_stop():
    with _LIVE_LOCK:
        if _LIVE["stop"] is not None:
            _LIVE["stop"].set()
        _LIVE["space_id"] = None


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
