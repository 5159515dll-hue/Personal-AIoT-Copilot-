from fastapi import APIRouter

from app.mock_data import current_room_state
from app.models import RoomState

router = APIRouter(prefix="/api/room", tags=["room"])


@router.get("/current", response_model=RoomState)
def get_current_room() -> RoomState:
    return current_room_state()

