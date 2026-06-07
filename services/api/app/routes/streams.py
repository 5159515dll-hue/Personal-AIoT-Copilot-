from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.audit import record_audit
from app.media_store import create_stream_source, delete_stream_source, get_stream_source, list_stream_sources, stream_hls_file_path, update_stream_source
from app.models import StreamSource, StreamSourceCreate, StreamSourceDeleteResponse, StreamSourceMutationResponse, StreamSourceUpdate

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.get("", response_model=list[StreamSource])
def get_streams(space_id: str | None = None, device_id: str | None = None) -> list[StreamSource]:
    return list_stream_sources(space_id=space_id, device_id=device_id)


@router.post("", response_model=StreamSourceMutationResponse)
def create_stream(request: StreamSourceCreate) -> StreamSourceMutationResponse:
    try:
        stream = create_stream_source(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    audit = record_audit(
        actor="user",
        action="create_stream_source",
        result="success",
        details=f"实时流已创建：{stream.name}。",
        parameters={
            "stream_id": stream.id,
            "device_id": stream.device_id,
            "space_id": stream.space_id,
            "stream_key": stream.stream_key,
        },
    )
    return StreamSourceMutationResponse(stream=stream, audit_log_id=audit.id)


@router.patch("/{stream_id}", response_model=StreamSourceMutationResponse)
def update_stream(stream_id: str, request: StreamSourceUpdate) -> StreamSourceMutationResponse:
    try:
        stream = update_stream_source(stream_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    audit = record_audit(
        actor="user",
        action="update_stream_source",
        result="success",
        details=f"实时流已更新：{stream.name}。",
        parameters={"stream_id": stream.id, "status": stream.status, "enabled": stream.enabled},
    )
    return StreamSourceMutationResponse(stream=stream, audit_log_id=audit.id)


@router.delete("/{stream_id}", response_model=StreamSourceDeleteResponse)
def delete_stream(stream_id: str) -> StreamSourceDeleteResponse:
    try:
        stream = delete_stream_source(stream_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    audit = record_audit(
        actor="user",
        action="delete_stream_source",
        result="success",
        details=f"实时流已删除：{stream.name}。",
        parameters={"stream_id": stream.id, "device_id": stream.device_id, "space_id": stream.space_id},
    )
    return StreamSourceDeleteResponse(deleted=True, stream_id=stream.id, audit_log_id=audit.id)


@router.get("/{stream_id}/hls/{file_path:path}")
def get_stream_hls_file(stream_id: str, file_path: str):
    stream = get_stream_source(stream_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="实时流不存在。")
    local_hls_base = os.getenv("MEDIAMTX_HLS_BASE_URL", "").strip().rstrip("/")
    if local_hls_base:
        url = f"{local_hls_base}/{stream.stream_key}/{file_path}"
        try:
            response = httpx.get(url, timeout=5)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="HLS 本地代理读取失败。") from exc
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail="HLS 文件暂不可用。")
        content_type = response.headers.get("content-type") or _hls_content_type(file_path)
        return Response(content=response.content, media_type=content_type)
    try:
        path = stream_hls_file_path(stream, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="HLS 文件暂不可用，请确认 MediaMTX 已启动并收到推流。")
    return FileResponse(path, media_type=_hls_content_type(file_path))


def _hls_content_type(file_path: str) -> str:
    if file_path.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if file_path.endswith(".ts"):
        return "video/mp2t"
    return "application/octet-stream"
