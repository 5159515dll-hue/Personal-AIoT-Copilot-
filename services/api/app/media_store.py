from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from app.models import (
    DeviceEvent,
    DeviceEventCreate,
    MediaAsset,
    StreamSource,
    StreamSourceCreate,
    StreamSourceUpdate,
)
from app.space_store import list_spaces
from app.storage import JsonListStore, data_dir
from app.time_utils import now

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "video/mp4"}
VISUAL_EVENT_TYPES = {"presence_detected", "motion_detected", "face_detected", "emotion_detected"}

event_store = JsonListStore("device_events.json", DeviceEvent)
media_asset_store = JsonListStore("media_assets.json", MediaAsset)
stream_store = JsonListStore("stream_sources.json", StreamSource)


def media_root() -> Path:
    configured = os.getenv("AIOT_MEDIA_ROOT", "").strip()
    return Path(configured) if configured else data_dir() / "media"


def stream_root() -> Path:
    configured = os.getenv("AIOT_STREAM_ROOT", "").strip()
    return Path(configured) if configured else data_dir() / "streams"


def record_device_event(device_id: str, request: DeviceEventCreate) -> DeviceEvent:
    _assert_space_allows_event(request.space_id, request.event_type)
    if request.message_id:
        existing = next(
            (
                item
                for item in event_store.list()
                if item.device_id == device_id and item.message_id == request.message_id
            ),
            None,
        )
        if existing is not None:
            return existing
    event = DeviceEvent(
        **request.model_dump(exclude={"captured_at"}),
        device_id=device_id,
        captured_at=request.captured_at or now(),
        received_at=now(),
    )
    event_store.append(event)
    return event


def list_device_events(
    *,
    limit: int = 100,
    device_id: str | None = None,
    space_id: str | None = None,
    event_type: str | None = None,
) -> list[DeviceEvent]:
    events = event_store.list()
    if device_id:
        events = [item for item in events if item.device_id == device_id]
    if space_id:
        events = [item for item in events if item.space_id == space_id]
    if event_type:
        events = [item for item in events if item.event_type == event_type]
    return sorted(events, key=lambda item: item.captured_at, reverse=True)[:limit]


def save_media_asset(
    *,
    device_id: str,
    space_id: str,
    file_name: str,
    content_type: str,
    content: bytes,
    zone: str | None = None,
    event_id: str | None = None,
    captured_at=None,
) -> MediaAsset:
    _assert_space_allows_media(space_id)
    content_type = content_type.lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("媒体类型不支持，只允许 JPEG、PNG 或 MP4。")
    media_type = "video" if content_type == "video/mp4" else "image"
    max_bytes = MAX_VIDEO_BYTES if media_type == "video" else MAX_IMAGE_BYTES
    if len(content) > max_bytes:
        limit_mb = max_bytes // 1024 // 1024
        raise ValueError(f"媒体文件过大，当前类型最大允许 {limit_mb}MB。")
    if not content:
        raise ValueError("媒体文件为空。")

    space = _space(space_id)
    retention_days = space.perception.media_policy.media_retention_days
    media_id = f"media_{uuid4().hex[:12]}"
    extension = _extension_for(content_type)
    relative_path = f"{space_id}/{media_id}{extension}"
    absolute_path = media_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    absolute_path.chmod(0o600)
    digest = hashlib.sha256(content).hexdigest()
    asset = MediaAsset(
        id=media_id,
        device_id=device_id,
        space_id=space_id,
        zone=zone,
        media_type=media_type,  # type: ignore[arg-type]
        content_type=content_type,  # type: ignore[arg-type]
        file_name=_safe_file_name(file_name) or f"{media_id}{extension}",
        file_size_bytes=len(content),
        sha256=digest,
        storage_path=relative_path,
        content_url=f"/api/media-assets/{media_id}/content",
        event_id=event_id,
        captured_at=captured_at or now(),
        received_at=now(),
        retention_policy="event_media",
        retention_days=retention_days,
        privacy_level="space_local_only",
        analysis_status="edge_completed" if event_id else "not_requested",
    )
    media_asset_store.append(asset)
    return asset


def list_media_assets(
    *,
    limit: int = 100,
    device_id: str | None = None,
    space_id: str | None = None,
    media_type: str | None = None,
) -> list[MediaAsset]:
    assets = media_asset_store.list()
    if device_id:
        assets = [item for item in assets if item.device_id == device_id]
    if space_id:
        assets = [item for item in assets if item.space_id == space_id]
    if media_type:
        assets = [item for item in assets if item.media_type == media_type]
    return sorted(assets, key=lambda item: item.received_at, reverse=True)[:limit]


def get_media_asset(media_id: str) -> MediaAsset | None:
    return next((item for item in media_asset_store.list() if item.id == media_id), None)


def media_asset_path(asset: MediaAsset) -> Path:
    return media_root() / asset.storage_path


def delete_media_asset(media_id: str) -> MediaAsset:
    asset = get_media_asset(media_id)
    if asset is None:
        raise KeyError("媒体文件不存在。")
    path = media_asset_path(asset)
    if path.exists():
        path.unlink()
    media_asset_store.replace_all([item for item in media_asset_store.list() if item.id != media_id])
    return asset


def create_stream_source(request: StreamSourceCreate) -> StreamSource:
    _assert_space_allows_stream(request.space_id)
    timestamp = now()
    stream_key = request.stream_key or f"{request.device_id}_{uuid4().hex[:8]}"
    stream = StreamSource(
        device_id=request.device_id,
        space_id=request.space_id,
        name=request.name,
        rtsp_url=request.rtsp_url,
        hls_url="",
        stream_key=stream_key,
        zone=request.zone,
        enabled=request.enabled,
        status="configured",
        notes=request.notes,
        created_at=timestamp,
        updated_at=timestamp,
    )
    stream = stream.model_copy(update={"hls_url": f"/api/streams/{stream.id}/hls/index.m3u8"})
    stream_store.append(stream)
    return stream


def list_stream_sources(*, space_id: str | None = None, device_id: str | None = None) -> list[StreamSource]:
    streams = stream_store.list()
    if space_id:
        streams = [item for item in streams if item.space_id == space_id]
    if device_id:
        streams = [item for item in streams if item.device_id == device_id]
    return sorted(streams, key=lambda item: item.updated_at, reverse=True)


def get_stream_source(stream_id: str) -> StreamSource | None:
    return next((item for item in stream_store.list() if item.id == stream_id), None)


def update_stream_source(stream_id: str, request: StreamSourceUpdate) -> StreamSource:
    existing = get_stream_source(stream_id)
    if existing is None:
        raise KeyError("实时流不存在。")
    update = request.model_dump(exclude_unset=True)
    if "rtsp_url" in update and update["rtsp_url"] is None:
        update.pop("rtsp_url")
    if "name" in update and update["name"] is None:
        update.pop("name")
    if "stream_key" in update and not update["stream_key"]:
        update.pop("stream_key")
    updated = existing.model_copy(update={**update, "updated_at": now()})
    if updated.enabled:
        _assert_space_allows_stream(updated.space_id)
    stream_store.replace_all([updated if item.id == stream_id else item for item in stream_store.list()])
    return updated


def delete_stream_source(stream_id: str) -> StreamSource:
    existing = get_stream_source(stream_id)
    if existing is None:
        raise KeyError("实时流不存在。")
    stream_store.replace_all([item for item in stream_store.list() if item.id != stream_id])
    return existing


def stream_hls_file_path(stream: StreamSource, file_path: str) -> Path:
    clean = Path(file_path)
    if clean.is_absolute() or ".." in clean.parts:
        raise ValueError("HLS 文件路径非法。")
    return stream_root() / stream.stream_key / clean


def _assert_space_allows_event(space_id: str, event_type: str) -> None:
    space = _space(space_id)
    perception = space.perception
    if event_type in VISUAL_EVENT_TYPES and perception.camera != "local_only":
        raise PermissionError("该空间未启用本地摄像头处理，不能接收视觉事件。")
    if event_type == "face_detected" and perception.face_recognition != "local_only":
        raise PermissionError("该空间未启用本地人脸识别，不能接收人脸事件。")
    if event_type == "emotion_detected" and perception.emotion_recognition != "local_only":
        raise PermissionError("该空间未启用本地情绪识别，不能接收情绪事件。")
    if event_type == "location_update" and perception.location_tracking != "local_only":
        raise PermissionError("该空间未启用本地位置能力，不能接收位置事件。")


def _assert_space_allows_media(space_id: str) -> None:
    space = _space(space_id)
    perception = space.perception
    if perception.camera != "local_only":
        raise PermissionError("该空间未启用本地摄像头处理，不能上传媒体。")
    if not perception.media_policy.allow_event_media or perception.image_retention != "event_media":
        raise PermissionError("该空间未允许保存事件媒体。")


def _assert_space_allows_stream(space_id: str) -> None:
    space = _space(space_id)
    perception = space.perception
    if perception.camera != "local_only":
        raise PermissionError("该空间未启用本地摄像头处理，不能配置实时流。")
    if not perception.media_policy.allow_realtime_stream:
        raise PermissionError("该空间未允许实时视频流。")


def _space(space_id: str):
    space = next((item for item in list_spaces() if item.id == space_id), None)
    if space is None:
        raise KeyError("空间不存在。")
    return space


def _extension_for(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    return ".mp4"


def _safe_file_name(value: str) -> str:
    return Path(value or "").name.replace("/", "").replace("\\", "")[:120]
