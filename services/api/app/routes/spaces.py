from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.models import RoomSpace, RoomSpaceCreate, RoomSpaceDeleteResponse, RoomSpaceMutationResponse, RoomSpaceUpdate
from app.space_store import activate_space, create_space, current_space, delete_space, list_spaces, update_space

router = APIRouter(prefix="/api/spaces", tags=["spaces"])


@router.get("", response_model=list[RoomSpace])
def get_spaces() -> list[RoomSpace]:
    return list_spaces()


@router.get("/current", response_model=RoomSpace)
def get_current_space() -> RoomSpace:
    return current_space()


@router.post("", response_model=RoomSpaceMutationResponse)
def post_space(request: RoomSpaceCreate) -> RoomSpaceMutationResponse:
    try:
        space = create_space(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit = record_audit(
        actor="user",
        action="create_space",
        result="success",
        details=f"空间已创建：{space.name}。",
        parameters={
            "space_id": space.id,
            "space_type": space.space_type,
            "perception": space.perception.model_dump(mode="json"),
        },
    )
    return RoomSpaceMutationResponse(space=space, audit_log_id=audit.id)


@router.patch("/{space_id}", response_model=RoomSpaceMutationResponse)
def patch_space(space_id: str, request: RoomSpaceUpdate) -> RoomSpaceMutationResponse:
    try:
        space = update_space(space_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    audit = record_audit(
        actor="user",
        action="update_space",
        result="success",
        details=f"空间设置已更新：{space.name}。",
        parameters={
            "space_id": space.id,
            "space_type": space.space_type,
            "device_ids": space.device_ids,
            "zones": space.zones,
            "perception": space.perception.model_dump(mode="json"),
        },
    )
    return RoomSpaceMutationResponse(space=space, audit_log_id=audit.id)


@router.post("/{space_id}/activate", response_model=RoomSpaceMutationResponse)
def activate_room_space(space_id: str) -> RoomSpaceMutationResponse:
    try:
        space = activate_space(space_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    audit = record_audit(
        actor="user",
        action="activate_space",
        result="success",
        details=f"当前空间已切换为：{space.name}。",
        parameters={"space_id": space.id, "space_type": space.space_type},
    )
    return RoomSpaceMutationResponse(space=space, audit_log_id=audit.id)


@router.delete("/{space_id}", response_model=RoomSpaceDeleteResponse)
def delete_room_space(space_id: str) -> RoomSpaceDeleteResponse:
    try:
        space = delete_space(space_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit = record_audit(
        actor="user",
        action="delete_space",
        result="success",
        details=f"空间已删除：{space.name}。",
        parameters={"space_id": space.id, "space_type": space.space_type},
    )
    return RoomSpaceDeleteResponse(deleted=True, space_id=space.id, audit_log_id=audit.id)
