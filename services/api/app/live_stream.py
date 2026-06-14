"""实时画面（真·MJPEG 流式中继）的服务端发布/订阅 + 最新帧缓冲。

机器人在 NAT 后无法被拉流，故机器人侧 agent 用 raspivid 直驱 CSI 摄像头（30fps），
把 MJPEG 逐帧包成 multipart 通过**一条长连接 chunked POST** 出站推到
`POST /api/device-connections/{id}/vision-live-stream`；服务端把字节**扇出**给所有浏览器
订阅者，浏览器 `<img>` 直接渲染 `multipart/x-mixed-replace` → 满帧率、单连接、不轮询。

同时顺手扫出最新一帧 JPEG（`_FRAMES`），供 `/frame` 快照与 `/status`。
内存缓冲，不落库；进程重启即清空。
"""
from __future__ import annotations

import asyncio
import threading
import time

LIVE_FRAME_TTL_SECONDS = 8.0          # 最新帧超过该秒数视为已停（/status、/frame）
STREAM_IDLE_TIMEOUT = 10.0            # serve 端连续多久没有新数据就结束（机器人停推/离线）
LIVE_BOUNDARY = "aiotmjpegframe"      # 与机器人侧 agent 构造的 multipart 边界一致
_QUEUE_MAX = 90                       # 每个观看者积压上限（约 3s@30fps），满了丢最旧

_LOCK = threading.Lock()             # 保护 _FRAMES / _SCAN_BUF（跨线程：发布在事件循环，/frame 在线程池）
_FRAMES = {}                         # space_id -> (jpeg_bytes, monotonic_ts)
_SCAN_BUF = {}                       # space_id -> bytes（帧扫描滚动缓冲）
_SUBS = {}                           # space_id -> set[asyncio.Queue]（仅事件循环内访问）


# ---- 最新帧（快照/状态；供 /frame、/status、测试）----
def set_frame(space_id: str, data: bytes) -> None:
    if not data:
        return
    with _LOCK:
        _FRAMES[space_id] = (data, time.monotonic())


def get_frame(space_id: str) -> bytes | None:
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
    with _LOCK:
        _FRAMES.pop(space_id, None)
        _SCAN_BUF.pop(space_id, None)


# ---- 流式发布/订阅（真·MJPEG 中继，均在事件循环内调用）----
def subscribe(space_id: str) -> "asyncio.Queue":
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
    _SUBS.setdefault(space_id, set()).add(q)
    return q


def unsubscribe(space_id: str, q: "asyncio.Queue") -> None:
    s = _SUBS.get(space_id)
    if s is not None:
        s.discard(q)
        if not s:
            _SUBS.pop(space_id, None)


def viewer_count(space_id: str) -> int:
    return len(_SUBS.get(space_id, ()))


def publish(space_id: str, data: bytes) -> None:
    """把机器人推来的字节扇出给所有浏览器订阅者，并顺手更新最新帧。"""
    if not data:
        return
    for q in list(_SUBS.get(space_id, ())):
        if q.full():
            try:
                q.get_nowait()          # 丢最旧，给慢消费者让路
            except Exception:
                pass
        try:
            q.put_nowait(data)
        except Exception:
            pass
    _scan_latest(space_id, data)


def _scan_latest(space_id: str, data: bytes) -> None:
    with _LOCK:
        buf = _SCAN_BUF.get(space_id, b"") + data
        if len(buf) > 3_000_000:        # 找不到完整帧时避免无限增长
            buf = buf[-1_000_000:]
        last = None
        start = 0
        while True:
            soi = buf.find(b"\xff\xd8", start)
            if soi < 0:
                break
            eoi = buf.find(b"\xff\xd9", soi + 2)
            if eoi < 0:
                break
            last = buf[soi:eoi + 2]
            start = eoi + 2
        if last is not None:
            _FRAMES[space_id] = (last, time.monotonic())
            buf = buf[start:]
        _SCAN_BUF[space_id] = buf
