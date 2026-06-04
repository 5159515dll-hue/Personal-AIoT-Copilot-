from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.mock_data import query_history
from app.models import Metric, SensorReading

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("/history", response_model=list[SensorReading])
def get_sensor_history(
    metric: Metric = Query(...),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    bucket: str = Query("15m"),
) -> list[SensorReading]:
    try:
        return query_history(metric, from_ts, to_ts, bucket)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

