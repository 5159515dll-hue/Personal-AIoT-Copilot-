from __future__ import annotations

from fastapi import APIRouter, Query

from app.media_store import list_device_events
from app.models import DeviceEvent

router = APIRouter(prefix="/api/device-events", tags=["device-events"])


@router.get("", response_model=list[DeviceEvent])
def get_device_events(
    limit: int = Query(100, ge=1, le=500),
    device_id: str | None = None,
    space_id: str | None = None,
    event_type: str | None = None,
) -> list[DeviceEvent]:
    return list_device_events(limit=limit, device_id=device_id, space_id=space_id, event_type=event_type)
