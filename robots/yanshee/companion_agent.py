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

# 机器人正在说话的截止时间戳：语音输入循环据此避免听到机器人自己的 TTS（防回声）。
_speaking_until = 0.0


def _note_speaking(text):
    global _speaking_until
    _speaking_until = time.time() + min(20.0, 1.2 + len(text or "") * 0.22)


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
    # 手势与朗读并行：手势独立线程播，朗读在本线程流式播放。
    if gesture:
        _play_gesture_async(gesture)
    if text:
        _speak(text)


def _play_audio_stream(path, body_dict, timeout=40):
    """POST 到服务器流式 TTS 端点，把返回的 MP3 边收边喂给 mpg123 播放。返回是否播到音频。"""
    import subprocess
    base = getattr(config, "AIOT_API_BASE_URL", "")
    token = getattr(config, "DEVICE_TOKEN", "")
    device_id = getattr(config, "DEVICE_ID", "yanshee_robot_01")
    if not (base and token):
        return False
    url = base.rstrip("/") + path.replace("{id}", device_id)
    req = urllib.request.Request(
        url, data=json.dumps(body_dict).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-AIoT-Device-Token": token},
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    player = subprocess.Popen(["mpg123", "-q", "-"], stdin=subprocess.PIPE)
    got = False
    try:
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            got = True
            player.stdin.write(chunk)
    finally:
        try:
            player.stdin.close()
            player.wait()
        except Exception:
            pass
    return got


def _speak(text):
    """朗读陪伴回复：服务器火山 TTS 合成自然语音（可在服务器切换音色），流式播放；失败回退本机机械 TTS。"""
    _note_speaking(text)
    try:
        if _play_audio_stream("/api/device-connections/{id}/tts-stream", {"text": text[:600]}, timeout=30):
            return
        print("say: 服务器 TTS 无音频，回退本机", flush=True)
    except Exception as exc:
        print("say: 服务器 TTS 失败，回退本机 %s" % exc, flush=True)
    try:
        import YanAPI
        YanAPI.yan_api_init(getattr(config, "ROBOT_IP", "127.0.0.1"))
        YanAPI.start_voice_tts(text[:300], True)
    except Exception as exc:
        print("say: 本机 tts 失败 %s" % exc, flush=True)


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


# ---- 实时画面（真·MJPEG 流式中继）：收到 live_start 后用 raspivid 直驱 CSI 摄像头(30fps)，
# 把 MJPEG 逐帧包成 multipart，经一条长连接 chunked POST 出站推到服务器 vision-live-stream；
# 服务端扇出给浏览器 <img> 直接渲染（满帧率、单连接、不轮询）。看门狗：浏览器停发 keepalive
# 后 LIVE_IDLE_TIMEOUT 秒自动停。注意：直播期间 raspivid 独占摄像头（YanAPI 拍照/人脸暂不可
# 同时用），停播即 terminate 释放。----
_LIVE_LOCK = threading.Lock()
_LIVE = {"thread": None, "stop": None, "space_id": None, "last_keepalive": 0.0}

_LIVE_BOUNDARY = b"aiotmjpegframe"


def _live_loop(space_id, stop_event):
    import subprocess
    import http.client
    from urllib.parse import urlparse

    base = getattr(config, "AIOT_API_BASE_URL", "")
    token = getattr(config, "DEVICE_TOKEN", "")
    device_id = getattr(config, "DEVICE_ID", "yanshee_robot_01")
    width = int(getattr(config, "LIVE_WIDTH", 640))
    height = int(getattr(config, "LIVE_HEIGHT", 480))
    fps = int(getattr(config, "LIVE_FPS", 30))
    idle_timeout = float(getattr(config, "LIVE_IDLE_TIMEOUT", 60))

    u = urlparse(base)
    host = u.hostname or "127.0.0.1"
    port = u.port or 80
    path = "/api/device-connections/" + device_id + "/vision-live-stream?space_id=" + space_id

    print("live: raspivid %dx%d@%dfps -> 流式推送 space=%s" % (width, height, fps, space_id), flush=True)
    while not stop_event.is_set():
        with _LIVE_LOCK:
            last_ka = _LIVE["last_keepalive"]
        if time.time() - last_ka > idle_timeout:
            print("live: 看门狗超时，自动停止", flush=True)
            break
        proc = None
        conn = None
        try:
            cmd = ["raspivid", "-t", "0", "-w", str(width), "-h", str(height),
                   "-fps", str(fps), "-cd", "MJPEG", "-n", "-fl", "-o", "-"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            conn = http.client.HTTPConnection(host, port, timeout=15)
            conn.putrequest("POST", path, skip_accept_encoding=True)
            conn.putheader("X-AIoT-Device-Token", token)
            conn.putheader("Content-Type", "multipart/x-mixed-replace; boundary=aiotmjpegframe")
            conn.putheader("Transfer-Encoding", "chunked")
            conn.endheaders()
            sock = conn.sock
            buf = b""
            while not stop_event.is_set():
                with _LIVE_LOCK:
                    last_ka = _LIVE["last_keepalive"]
                if time.time() - last_ka > idle_timeout:
                    print("live: 看门狗超时，自动停止", flush=True)
                    stop_event.set()
                    break
                chunk = proc.stdout.read(16384)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 4 * 1024 * 1024:
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
                    part = (b"--" + _LIVE_BOUNDARY + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(frame)).encode("ascii") + b"\r\n\r\n" + frame + b"\r\n")
                    sock.sendall(("%X\r\n" % len(part)).encode("ascii") + part + b"\r\n")
        except Exception as exc:
            print("live: 推流出错 %s（2s 后重试）" % exc, flush=True)
            time.sleep(2)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            try:
                if proc is not None:
                    proc.terminate()
                    proc.wait()
            except Exception:
                pass
        if not stop_event.is_set():
            time.sleep(0.5)   # raspivid 异常退出时避免忙重启
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


# ---- 语音对话（Step 3，唤醒触发）：喊两次"小暖"唤醒 → 听写 → 服务器流式回复
# （大模型流式 → 逐句火山 TTS）→ mpg123 边收边播（≤3s 开口）。浏览器输入路径照常保留。
# 唤醒用离线命令词 ASR（喊名字）。识别结果结构未知 → 宽松解析 + 打日志便于调参。----
def _play_gesture_async(gesture):
    """在独立线程播手势（带自己的事件循环），与朗读并行。"""
    def run():
        try:
            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
        try:
            play_gesture(gesture)
        except Exception as exc:
            print("voice: play_gesture 出错 %s" % exc, flush=True)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()


def _setup_wake_grammar(yanapi, wake_words):
    try:
        grammar = {
            "grammar": "wake",
            "rule": [{"name": "name", "value": "|".join(wake_words)}],
            "slot": [{"name": "name"}],
            "start": "wakeStart",
            "startinfo": "<name>",
        }
        yanapi.create_voice_asr_offline_syntax(grammar)
    except Exception as exc:
        print("voice: 注册唤醒词失败 %s" % exc, flush=True)


def _asr_text(data):
    """从语义识别结果里尽量抠出识别文本（结构未知，宽松解析 + 兜底 stringify）。"""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("text", "result", "content", "answer", "question", "nlu"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(data, ensure_ascii=False)
    return ""


def _is_wake(text, wake_words):
    cleaned = (text or "").replace(" ", "")
    return any(w in cleaned for w in wake_words) or "小暖" in cleaned


def _wait_for_wake(yanapi, wake_words):
    """单次识别循环监听唤醒词（continuous 模式引擎会立刻 idle，故用单次反复）。
    窗口内喊到 WAKE_HITS 次唤醒词才触发（降误唤醒）。返回 True 表示已唤醒。"""
    need = int(getattr(config, "WAKE_HITS", 2))
    window = float(getattr(config, "WAKE_WINDOW", 8.0))
    hits = []
    while True:
        try:
            res = yanapi.sync_do_voice_asr_value()
        except Exception as exc:
            print("voice: 唤醒识别出错 %s" % exc, flush=True)
            time.sleep(1)
            continue
        heard = ((res.get("question") if isinstance(res, dict) else res) or "").strip()
        if not heard:
            continue
        if _is_wake(heard, wake_words):
            now = time.time()
            hits = [h for h in hits if now - h < window] + [now]
            print("voice: 唤醒命中 %d/%d（听到「%s」）" % (len(hits), need, heard[:20]), flush=True)
            if len(hits) >= need:
                return True
        else:
            print("voice: 听到「%s」（非唤醒词，忽略）" % heard[:20], flush=True)


def _converse(yanapi, space_id):
    """已唤醒：听用户说话 → 服务器流式回复并播放。
    CONV_IDLE_TIMEOUT 秒内没有有效声音则自动退出，回到待唤醒（避免醒着空耗+一直滴）。
    每说成功一句就把空闲计时续上。"""
    idle_timeout = float(getattr(config, "CONV_IDLE_TIMEOUT", 10.0))
    max_turns = int(getattr(config, "MAX_CONV_TURNS", 5))
    print("voice: 已唤醒，请说…（%.0fs 内没说话就自动退出）" % idle_timeout, flush=True)
    deadline = time.time() + idle_timeout
    turns = 0
    while time.time() < deadline and turns < max_turns:
        try:
            text = (yanapi.sync_do_voice_iat_value() or "").strip()
        except Exception as exc:
            print("voice: 听写出错 %s" % exc, flush=True)
            break
        if len(text) < 2:
            if time.time() >= deadline:
                break
            continue   # 本轮没听清，但还没到空闲上限，再听一次
        turns += 1
        print("voice: 你说「%s」" % text, flush=True)
        try:
            if not _play_audio_stream(
                "/api/device-connections/{id}/companion-voice-stream",
                {"space_id": space_id, "message": text}, timeout=45,
            ):
                print("voice: 无回复音频", flush=True)
        except Exception as exc:
            print("voice: 回复出错 %s" % exc, flush=True)
        deadline = time.time() + idle_timeout   # 有有效对话 → 续 10s
    print("voice: 空闲超时/结束，回到待唤醒", flush=True)


def _voice_loop():
    # 喊名字唤醒（用户已确认接受待唤醒时的周期"滴"声——本机任何在听的识别都会响，无法关）。
    if not getattr(config, "VOICE_INPUT_ENABLED", True):
        print("voice: 语音输入已关闭（VOICE_INPUT_ENABLED=False）", flush=True)
        return
    space_id = getattr(config, "SPACE_ID", "space_study_001")
    wake_words = getattr(config, "WAKE_WORDS", ["小暖", "小暖小暖", "你好小暖", "小暖在吗"])
    try:
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception as exc:
        print("voice: 建事件循环失败 %s" % exc, flush=True)
    import YanAPI
    YanAPI.yan_api_init(getattr(config, "ROBOT_IP", "127.0.0.1"))
    _setup_wake_grammar(YanAPI, wake_words)
    print("voice: 待唤醒——喊两次「%s」开始对话" % wake_words[0], flush=True)
    while True:
        try:
            if _wait_for_wake(YanAPI, wake_words):
                _converse(YanAPI, space_id)
        except Exception as exc:
            print("voice: 循环出错 %s" % exc, flush=True)
            time.sleep(2)


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
    # 语音输入线程（Step 3）：守护线程，独立聆听 → 生成回复 → 本机朗读+手势。
    vc = threading.Thread(target=_voice_loop)
    vc.daemon = True
    vc.start()
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
