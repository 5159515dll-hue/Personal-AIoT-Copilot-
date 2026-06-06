from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.database import insert_sensor_readings_idempotent
from app.device_connections import record_ingest_connection
from app.ingestion import readings_from_request
from app.models import SensorIngestRequest, SensorIngestResponse

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/sensor-readings", response_model=SensorIngestResponse)
def ingest_sensor_readings(request: SensorIngestRequest) -> SensorIngestResponse:
    readings = readings_from_request(request)
    try:
        stored = insert_sensor_readings_idempotent(
            readings,
            source=request.source,
            device_id=request.device_id,
            message_id=request.message_id,
            sequence=request.sequence,
            protocol_version=request.protocol_version,
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
            "message_id": request.message_id,
            "sequence": request.sequence,
            "accepted": len(readings),
            "stored": stored,
        },
    )
    message = "传感器读数已写入时间序列数据库。"
    if request.message_id and stored == 0:
        message = "该入站消息已处理过，未重复写入时间序列数据库。"
    return SensorIngestResponse(
        accepted=len(readings),
        stored=stored,
        source=request.source,
        message=message,
    )
