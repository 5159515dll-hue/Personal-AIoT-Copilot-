from __future__ import annotations

from uuid import uuid4

from app.models import RoomSpace, RoomSpaceCreate, RoomSpaceUpdate, SpacePerceptionSettings
from app.storage import JsonListStore
from app.time_utils import now

space_store = JsonListStore("room_spaces.json", RoomSpace)


def list_spaces() -> list[RoomSpace]:
    return _ensure_spaces()


def current_space() -> RoomSpace:
    spaces = _ensure_spaces()
    active = next((space for space in spaces if space.is_active), None)
    if active is not None:
        return active
    default = spaces[0].model_copy(update={"is_active": True, "updated_at": now()})
    _replace_space(default)
    return default


def create_space(request: RoomSpaceCreate) -> RoomSpace:
    spaces = _ensure_spaces()
    space_id = request.id or f"space_{uuid4().hex[:10]}"
    if any(space.id == space_id for space in spaces):
        raise ValueError("空间编号已存在，请换一个编号。")
    timestamp = now()
    space = RoomSpace(
        id=space_id,
        name=request.name,
        space_type=request.space_type,
        location_label=request.location_label,
        floor=request.floor,
        timezone=request.timezone,
        is_active=False,
        device_ids=_clean_list(request.device_ids),
        zones=_clean_list(request.zones),
        perception=_sanitize_perception(request.perception),
        notes=request.notes,
        created_at=timestamp,
        updated_at=timestamp,
    )
    spaces.append(space)
    space_store.replace_all(spaces)
    return space


def update_space(space_id: str, request: RoomSpaceUpdate) -> RoomSpace:
    spaces = _ensure_spaces()
    existing = _find_space(spaces, space_id)
    if existing is None:
        raise KeyError("空间不存在。")
    update: dict = {"updated_at": now()}
    for field in ("name", "space_type", "location_label", "floor", "timezone", "notes"):
        value = getattr(request, field)
        if value is not None:
            update[field] = value
    if request.device_ids is not None:
        update["device_ids"] = _clean_list(request.device_ids)
    if request.zones is not None:
        update["zones"] = _clean_list(request.zones)
    if request.perception is not None:
        update["perception"] = _sanitize_perception(request.perception)
    updated = existing.model_copy(deep=True, update=update)
    _replace_space(updated, spaces)
    return updated


def activate_space(space_id: str) -> RoomSpace:
    spaces = _ensure_spaces()
    target = _find_space(spaces, space_id)
    if target is None:
        raise KeyError("空间不存在。")
    timestamp = now()
    updated_spaces = [
        space.model_copy(update={"is_active": space.id == space_id, "updated_at": timestamp if space.id == space_id else space.updated_at})
        for space in spaces
    ]
    space_store.replace_all(updated_spaces)
    return next(space for space in updated_spaces if space.id == space_id)


def delete_space(space_id: str) -> RoomSpace:
    spaces = _ensure_spaces()
    target = _find_space(spaces, space_id)
    if target is None:
        raise KeyError("空间不存在。")
    if target.is_active:
        raise ValueError("当前空间不能删除，请先切换到其他空间。")
    if len(spaces) <= 1:
        raise ValueError("至少需要保留一个空间。")
    space_store.replace_all([space for space in spaces if space.id != space_id])
    return target


def _ensure_spaces() -> list[RoomSpace]:
    spaces = space_store.list()
    if spaces:
        if not any(space.is_active for space in spaces):
            spaces[0] = spaces[0].model_copy(update={"is_active": True, "updated_at": now()})
            space_store.replace_all(spaces)
        return spaces
    default = _default_space()
    space_store.replace_all([default])
    return [default]


def _default_space() -> RoomSpace:
    timestamp = now()
    return RoomSpace(
        id="space_study_001",
        name="演示书房",
        space_type="study",
        location_label="书房",
        floor="默认楼层",
        timezone="Asia/Shanghai",
        is_active=True,
        device_ids=["room_node_01", "desk_lamp_01", "ambient_light_01"],
        zones=["书桌", "书架", "门口"],
        perception=SpacePerceptionSettings(
            camera="disabled",
            face_recognition="disabled",
            emotion_recognition="disabled",
            location_tracking="disabled",
            image_retention="none",
            privacy_mode="strict",
            notes="当前版本不接入摄像头、人脸、情绪或精确定位。",
        ),
        notes="默认作品集演示空间，可在房间设置中新增其他房间。",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _find_space(spaces: list[RoomSpace], space_id: str) -> RoomSpace | None:
    return next((space for space in spaces if space.id == space_id), None)


def _replace_space(updated: RoomSpace, spaces: list[RoomSpace] | None = None) -> None:
    current = spaces if spaces is not None else _ensure_spaces()
    space_store.replace_all([updated if space.id == updated.id else space for space in current])


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
    return cleaned


def _sanitize_perception(settings: SpacePerceptionSettings) -> SpacePerceptionSettings:
    if settings.image_retention != "none" and settings.camera == "disabled":
        return settings.model_copy(update={"image_retention": "none"})
    if settings.privacy_mode == "strict":
        return settings.model_copy(update={"image_retention": "none"})
    return settings
