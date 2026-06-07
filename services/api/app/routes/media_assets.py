from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.audit import record_audit
from app.media_store import delete_media_asset, get_media_asset, list_media_assets, media_asset_path
from app.models import MediaAsset, MediaAssetDeleteResponse

router = APIRouter(prefix="/api/media-assets", tags=["media-assets"])


@router.get("", response_model=list[MediaAsset])
def get_media_assets(
    limit: int = Query(100, ge=1, le=500),
    device_id: str | None = None,
    space_id: str | None = None,
    media_type: str | None = None,
) -> list[MediaAsset]:
    return list_media_assets(limit=limit, device_id=device_id, space_id=space_id, media_type=media_type)


@router.get("/{media_id}", response_model=MediaAsset)
def get_media_asset_detail(media_id: str) -> MediaAsset:
    asset = get_media_asset(media_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="媒体文件不存在。")
    return asset


@router.get("/{media_id}/content")
def get_media_asset_content(media_id: str) -> FileResponse:
    asset = get_media_asset(media_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="媒体文件不存在。")
    path = media_asset_path(asset)
    if not path.exists():
        raise HTTPException(status_code=404, detail="媒体文件索引存在，但本机文件已丢失。")
    return FileResponse(path, media_type=asset.content_type, filename=asset.file_name)


@router.delete("/{media_id}", response_model=MediaAssetDeleteResponse)
def delete_media_asset_route(media_id: str) -> MediaAssetDeleteResponse:
    try:
        asset = delete_media_asset(media_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    audit = record_audit(
        actor="user",
        action="delete_media_asset",
        result="success",
        details=f"媒体文件已删除：{media_id}。",
        parameters={
            "media_id": media_id,
            "device_id": asset.device_id,
            "space_id": asset.space_id,
            "media_type": asset.media_type,
        },
    )
    return MediaAssetDeleteResponse(deleted=True, media_id=media_id, audit_log_id=audit.id)
