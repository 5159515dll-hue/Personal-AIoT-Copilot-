from fastapi import APIRouter

from app.database import telemetry_status_db
from app.models import TelemetryStatus

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("/status", response_model=TelemetryStatus)
def get_telemetry_status() -> TelemetryStatus:
    return telemetry_status_db()
