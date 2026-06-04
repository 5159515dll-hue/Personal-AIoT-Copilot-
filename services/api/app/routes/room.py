from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.mock_data import current_room_state
from app.models import RoomState
from app.room_state import clean_database_error_text, current_database_room_state

router = APIRouter(prefix="/api/room", tags=["room"])


@router.get("/current", response_model=RoomState)
def get_current_room(source: Literal["mock", "database"] = Query("mock")) -> RoomState:
    if source == "database":
        try:
            return current_database_room_state()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=clean_database_error_text(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态。") from exc
    return current_room_state()
