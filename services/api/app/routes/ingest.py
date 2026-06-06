from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.database import insert_sensor_readings
from app.device_connections import record_ingest_connection
from app.ingestion import readings_from_request
from app.models import SensorIngestRequest, SensorIngestResponse

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/sensor-readings", response_model=SensorIngestResponse)
def ingest_sensor_readings(request: SensorIngestRequest) -> SensorIngestResponse:
    readings = readings_from_request(request)
    try:
        stored = insert_sensor_readings(
            readings,
            source=request.source,
            ensure_schema=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库连接或写入失败，请检查 DATABASE_URL、网络和数据库服务状态。") from exc
    try:
        record_ingest_connection(request, transport=request.source)
    except Exception:
        pass

    record_audit(
        actor="system",
        action="ingest_sensor_readings",
        result="success",
        details=f"已写入 {stored} 条传感器读数。",
        parameters={
            "device_id": request.device_id,
            "source": request.source,
            "accepted": len(readings),
            "stored": stored,
        },
    )
    return SensorIngestResponse(
        accepted=len(readings),
        stored=stored,
        source=request.source,
        message="传感器读数已写入时间序列数据库。",
    )
