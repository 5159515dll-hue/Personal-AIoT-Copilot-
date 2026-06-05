from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.database import latest_sensor_readings_db, query_sensor_history_db
from app.mock_data import current_room_state, query_history
from app.models import Metric, SensorHealth, SensorReading
from app.sensor_health import evaluate_sensor_health
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


@router.get("/health", response_model=list[SensorHealth])
def get_sensor_health(source: Literal["mock", "database"] = Query("mock")) -> list[SensorHealth]:
    if source == "database":
        try:
            return evaluate_sensor_health(latest_sensor_readings_db(), source="database")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态。") from exc
    return evaluate_sensor_health(current_room_state().metrics, source="mock")
