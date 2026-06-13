#!/usr/bin/env python3
"""边缘情绪采集（在机器人内置树莓派上运行）。plan §2 / M2 机器人侧。

职责（边缘只做廉价门控采集，推理在服务器）：
  1) 廉价门控：只在"检测到人/被唤醒"且"有语音活动(VAD)"时才采样，不逐帧、不常开；
  2) 采一个 1–2s 窗口：摄像头取帧、麦克风取音频、（可选）本地 ASR 转写；
  3) POST 到 /api/emotion/ingest，由服务器做三模态推理 + 融合；
  4) **绝不落盘、绝不发 /media**，原始帧/音频用完即弃。

隐私：本脚本不写任何文件、不缓存原始音视频。

⚠️ 未硬件实测：FER/SER/ASR 与门控均为可插拔桩（标 TODO）。在真机上接 yanapi/真实模型后替换。
无 yanapi 环境下可用桩数据跑通上报链路（沿用 bridge 的"无硬件降级"思路）。
"""
from __future__ import annotations

import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
except ModuleNotFoundError:
    sys.exit("未找到 config.py，请先在 robots/yanshee/ 下执行: cp config.example.py config.py")

API_BASE_URL = config.AIOT_API_BASE_URL.rstrip("/")
DEVICE_ID = config.DEVICE_ID
SPACE_ID = getattr(config, "SPACE_ID", os.getenv("AIOT_SPACE_ID", "space_study_001"))
DEVICE_TOKEN = getattr(config, "DEVICE_TOKEN", os.getenv("AIOT_DEVICE_TOKEN", ""))
INTERNAL_TOKEN = config.AIOT_INTERNAL_API_TOKEN
SAMPLE_INTERVAL = float(os.getenv("AIOT_EMOTION_SAMPLE_INTERVAL", "2.0"))

try:
    import YanAPI  # type: ignore

    YanAPI.yan_api_init(config.ROBOT_IP)
    _YANAPI = True
except Exception as exc:  # noqa: BLE001
    print(f"[warn] yanapi 不可用（{exc!r}）：以桩数据跑通上报链路。")
    YanAPI = None  # type: ignore
    _YANAPI = False


def main() -> None:
    session = requests.Session()
    session.trust_env = False  # 不走系统代理，直连平台
    headers = {"Content-Type": "application/json"}
    if DEVICE_TOKEN:
        headers["X-AIoT-Device-Token"] = DEVICE_TOKEN
    elif INTERNAL_TOKEN:
        headers["X-AIoT-Internal-Token"] = INTERNAL_TOKEN
    else:
        print("[warn] 既无设备令牌也无内部令牌，/api/emotion/ingest 会返回 401。")

    print(f"边缘情绪采集启动：space={SPACE_ID} device={DEVICE_ID} -> {API_BASE_URL}")
    while True:
        if person_present() and voice_active():
            payload = capture_window()
            post_ingest(session, headers, payload)
        time.sleep(SAMPLE_INTERVAL)


# ── 廉价门控（TODO：接真实人脸存在检测 / VAD）────────────────────────
def person_present() -> bool:
    """检测画面里是否有人。v0 桩：恒为 True。真机用轻量人脸存在/运动/亮度触发替换。"""
    # TODO: 用 yanapi 取一帧 + 轻量人脸存在检测，或运动/亮度变化触发。
    return True


def voice_active() -> bool:
    """语音活动检测(VAD)。v0 桩：恒为 True。真机用能量阈值/WebRTC VAD 替换。"""
    # TODO: 取短音频窗做能量/VAD 判断，避免静默时无谓采样。
    return True


# ── 采样一个窗口（不落盘）────────────────────────────────────────────
def capture_window() -> dict:
    """采 1–2s 窗口，产出上报 payload；原始帧/音频用完即弃，不写文件。"""
    transcript = capture_transcript()  # 本地 ASR（桩）
    payload: dict = {"space_id": SPACE_ID, "device_id": DEVICE_ID}
    if transcript:
        payload["transcript"] = transcript
    face = capture_face_reading()
    if face is not None:
        payload["face"] = face
    voice = capture_voice_reading()
    if voice is not None:
        payload["voice"] = voice
    return payload


def capture_transcript() -> str | None:
    """本地 ASR 听写：官方 YanAPI `sync_do_voice_iat_value()`（中/英；蒙语 ASR 见 M4/M7）。
    原文只过境服务器、不落盘。无 yanapi 或静默时返回 None。"""
    if not _YANAPI:
        return None
    try:
        result = YanAPI.sync_do_voice_iat_value()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 听写失败：{exc!r}")
        return None
    # 官方返回可能是 str 或 {'data': {'text': ...}}；函数名确定，仅对返回结构做轻量容错。
    if isinstance(result, str):
        return result.strip() or None
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            text = str(data.get("text") or data.get("iat") or "").strip()
            return text or None
    return None


def capture_face_reading() -> dict | None:
    """视觉表情情绪(FER) → 7 类分布。v0 桩返回 None。Yanshee 无内置情绪 API：
    用 YanAPI.get_vision_photo() 取一帧，再交外部 FER 模型；产出 {"distribution": {...}, "confidence": x}。"""
    # TODO: frame = YanAPI.get_vision_photo(); 外部 FER → 分布。原始帧不落盘。
    return None


def capture_voice_reading() -> dict | None:
    """语音韵律情绪(SER) → 7 类分布。v0 桩返回 None。Yanshee 无内置 SER：
    取音频窗（IAT 同源音频）→ 外部韵律/SER 模型 → 分布。"""
    # TODO: 取音频窗 → 外部 SER → {"distribution": {...}, "confidence": x}。原始音频不落盘。
    return None


def post_ingest(session: requests.Session, headers: dict, payload: dict) -> None:
    # 没有任何模态信号就不上报，避免无意义请求。
    if not any(k in payload for k in ("transcript", "face", "voice")):
        return
    try:
        resp = session.post(
            f"{API_BASE_URL}/api/emotion/ingest", json=payload, headers=headers, timeout=8
        )
        resp.raise_for_status()
        body = resp.json()
        print(f"ingest -> {body['state']['primary_emotion']} (recorded={body['event_recorded']})")
    except requests.RequestException as exc:
        print(f"[error] /api/emotion/ingest 失败：{exc!r}")


if __name__ == "__main__":
    main()
