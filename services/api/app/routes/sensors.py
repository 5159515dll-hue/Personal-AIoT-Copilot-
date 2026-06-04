from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.database import query_sensor_history_db
from app.mock_data import query_history
from app.models import Metric, SensorReading
from app.time_utils import now

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("/history", response_model=list[SensorReading])
def get_sensor_history(
    metric: Metric = Query(...),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    bucket: str = Query("15m"),
    source: Literal["mock", "database"] = Query("mock"),
) -> list[SensorReading]:
    if source == "database":
        end = to_ts or now()
        if from_ts is None:
            raise HTTPException(status_code=400, detail="使用 database 数据源时必须提供 from 参数。")
        try:
            return query_sensor_history_db(metric, from_ts, end, bucket=bucket)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return query_history(metric, from_ts, to_ts, bucket)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
