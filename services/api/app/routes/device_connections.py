from fastapi import APIRouter, HTTPException, Query

from app.audit import record_audit
from app.database import insert_sensor_readings_idempotent
from app.device_connections import (
    list_connections,
    record_heartbeat,
    record_ingest_connection,
    register_device_connection,
)
from app.ingestion import readings_from_request
from app.models import (
    DeviceConnectionRecord,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceRegistrationRequest,
    DeviceTelemetryRequest,
    DeviceTelemetryResponse,
    SensorIngestRequest,
)
from app.time_utils import now

router = APIRouter(prefix="/api/device-connections", tags=["device-connections"])


@router.get("", response_model=list[DeviceConnectionRecord])
def get_device_connections(limit: int = Query(100, ge=1, le=1000)) -> list[DeviceConnectionRecord]:
    try:
        return list_connections(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备连接表查询失败，请检查 DATABASE_URL 和数据库服务状态。") from exc


@router.post("/register", response_model=DeviceConnectionRecord)
def register_connection(request: DeviceRegistrationRequest) -> DeviceConnectionRecord:
    try:
        record = register_device_connection(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备注册失败，请检查 DATABASE_URL 和数据库服务状态。") from exc
    record_audit(
        actor="system",
        action="register_device_connection",
        result="success",
        details=f"设备连接已注册：{record.device_id}。",
        parameters={
            "device_id": record.device_id,
            "device_type": record.device_type,
            "transport": record.transport,
            "protocol_version": record.protocol_version,
            "capability_count": len(record.capabilities),
        },
    )
    return record


@router.post("/{device_id}/heartbeat", response_model=DeviceHeartbeatResponse)
def heartbeat(device_id: str, request: DeviceHeartbeatRequest) -> DeviceHeartbeatResponse:
    try:
        record = record_heartbeat(device_id, request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备心跳写入失败，请检查 DATABASE_URL 和数据库服务状态。") from exc
    record_audit(
        actor="system",
        action="device_heartbeat",
        result="success",
        details=f"设备心跳已更新：{device_id}。",
        parameters={
            "device_id": device_id,
            "status": request.status,
            "transport": request.transport,
            "sequence": request.sequence,
        },
    )
    return DeviceHeartbeatResponse(
        device_id=record.device_id,
        online_state=record.online_state,
        last_seen_at=record.last_seen_at or now(),
        message="设备心跳已记录。",
    )


@router.post("/{device_id}/telemetry", response_model=DeviceTelemetryResponse)
def ingest_device_telemetry(device_id: str, request: DeviceTelemetryRequest) -> DeviceTelemetryResponse:
    ingest = SensorIngestRequest(
        device_id=device_id,
        readings=request.readings,
        source="http",
        protocol_version=request.protocol_version,
        message_id=request.message_id,
        sequence=request.sequence,
        sent_at=request.sent_at,
        firmware_version=request.firmware_version,
        capabilities=request.capabilities,
        metadata=request.metadata,
    )
    readings = readings_from_request(ingest)
    try:
        stored = insert_sensor_readings_idempotent(
            readings,
            source="http",
            device_id=device_id,
            message_id=request.message_id,
            sequence=request.sequence,
            protocol_version=request.protocol_version,
            ensure_schema=True,
        )
        record_ingest_connection(ingest, transport="http")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="设备遥测写入失败，请检查 DATABASE_URL 和数据库服务状态。") from exc
    record_audit(
        actor="system",
        action="ingest_device_telemetry",
        result="success",
        details=f"已写入 {stored} 条设备遥测读数。",
        parameters={
            "device_id": device_id,
            "message_id": request.message_id,
            "sequence": request.sequence,
            "accepted": len(readings),
            "stored": stored,
        },
    )
    message = "设备遥测已写入时间序列数据库。"
    if request.message_id and stored == 0:
        message = "该设备遥测消息已处理过，未重复写入时间序列数据库。"
    return DeviceTelemetryResponse(
        device_id=device_id,
        accepted=len(readings),
        stored=stored,
        source="http",
        message_id=request.message_id,
        received_at=now(),
        message=message,
    )
