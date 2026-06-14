"""实时画面（MJPEG 中继直播）的服务端最新帧缓冲。

机器人在内网(NAT)后无法被服务器直接拉流，所以由机器人侧 agent 把本地
`open_vision_stream` 产生的 MJPEG 逐帧**出站**推送到
`POST /api/device-connections/{id}/vision-live`；这里只在内存里保留每个空间的
「最新一帧」，浏览器用 `<img>` 快速轮询 `GET /api/companion/vision/live/frame`
取最新帧 → 近实时预览（~1s 延迟）。

内存缓冲（不落库、不保留）：直播是瞬时预览，符合空间「本地优先/最小留存」原则；
进程重启即清空。超过 TTL 没有新帧则视为已停止（浏览器收到 404）。
"""
from __future__ import annotations

import threading
import time

# 超过该秒数没有新帧则视为直播已停止（浏览器轮询会收到 404，前端据此提示）。
LIVE_FRAME_TTL_SECONDS = 8.0

_LOCK = threading.Lock()
_FRAMES: dict[str, tuple[bytes, float]] = {}


def set_frame(space_id: str, data: bytes) -> None:
    """记录某空间的最新一帧（覆盖旧帧）。空数据忽略。"""
    if not data:
        return
    with _LOCK:
        _FRAMES[space_id] = (data, time.monotonic())


def get_frame(space_id: str) -> bytes | None:
    """取某空间的最新一帧；无帧或已超过 TTL 返回 None。"""
    with _LOCK:
        item = _FRAMES.get(space_id)
    if item is None:
        return None
    data, ts = item
    if time.monotonic() - ts > LIVE_FRAME_TTL_SECONDS:
        return None
    return data


def is_live(space_id: str) -> bool:
    return get_frame(space_id) is not None


def clear(space_id: str) -> None:
    """停止直播时清掉缓冲帧。"""
    with _LOCK:
        _FRAMES.pop(space_id, None)
