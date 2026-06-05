from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.anomaly_events import list_anomaly_events
from app.models import AnomalyEvent
from app.room_state import clean_database_error_text

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("", response_model=list[AnomalyEvent])
def get_anomalies(
    source: Literal["mock", "database"] = Query("mock"),
    window: Literal["24h", "7d"] = Query("24h"),
) -> list[AnomalyEvent]:
    try:
        return list_anomaly_events(source=source, window=window)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=clean_database_error_text(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="异常事件生成失败，请检查数据源、数据库连接和历史曲线。") from exc
