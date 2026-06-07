import hmac

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from app.audit import record_audit
from app.auth import INTERNAL_API_TOKEN_HEADER, internal_api_token
from app.database import insert_sensor_readings_idempotent
from app.device_credentials import DEVICE_TOKEN_HEADER, verify_device_token
from app.device_connections import (
    list_connections,
    record_heartbeat,
    record_ingest_connection,
    register_device_connection,
)
from app.ingestion import readings_from_request
from app.media_store import record_device_event, save_media_asset
from app.models import (
    DeviceEventCreate,
    DeviceEventIngestResponse,
    DeviceConnectionRecord,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceRegistrationRequest,
    DeviceTelemetryRequest,
    DeviceTelemetryResponse,
    MediaAssetUploadResponse,
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


@router.post("/{device_id}/events", response_model=DeviceEventIngestResponse)
def ingest_device_event(device_id: str, payload: DeviceEventCreate, request: Request) -> DeviceEventIngestResponse:
    _require_device_ingest_auth(request, device_id)
    try:
        event = record_device_event(device_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        audit = record_audit(
            actor="system",
            action="ingest_device_event",
            result="blocked",
            details=str(exc),
            parameters={"device_id": device_id, **payload.model_dump(mode="json")},
        )
        raise HTTPException(status_code=403, detail={"message": str(exc), "audit_log_id": audit.id}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit = record_audit(
        actor="system",
        action="ingest_device_event",
        result="success",
        details=f"设备边缘事件已记录：{event.event_type}。",
        parameters={
            "event_id": event.id,
            "device_id": device_id,
            "space_id": event.space_id,
            "event_type": event.event_type,
            "severity": event.severity,
        },
    )
    return DeviceEventIngestResponse(event=event, audit_log_id=audit.id)


@router.post("/{device_id}/media", response_model=MediaAssetUploadResponse)
async def upload_device_media(
    device_id: str,
    request: Request,
    file: UploadFile = File(...),
    space_id: str = Form(...),
    zone: str | None = Form(default=None),
    event_id: str | None = Form(default=None),
    captured_at: str | None = Form(default=None),
) -> MediaAssetUploadResponse:
    _require_device_ingest_auth(request, device_id)
    content = await file.read()
    try:
        asset = save_media_asset(
            device_id=device_id,
            space_id=space_id,
            file_name=file.filename or "upload",
            content_type=file.content_type or "",
            content=content,
            zone=zone,
            event_id=event_id,
            captured_at=captured_at,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except PermissionError as exc:
        audit = record_audit(
            actor="system",
            action="upload_device_media",
            result="blocked",
            details=str(exc),
            parameters={"device_id": device_id, "space_id": space_id, "content_type": file.content_type},
        )
        raise HTTPException(status_code=403, detail={"message": str(exc), "audit_log_id": audit.id}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit = record_audit(
        actor="system",
        action="upload_device_media",
        result="success",
        details=f"设备媒体已保存：{asset.id}。",
        parameters={
            "media_id": asset.id,
            "device_id": device_id,
            "space_id": space_id,
            "media_type": asset.media_type,
            "file_size_bytes": asset.file_size_bytes,
            "sha256": asset.sha256,
        },
    )
    return MediaAssetUploadResponse(asset=asset, audit_log_id=audit.id)


def _require_device_ingest_auth(request: Request, device_id: str) -> None:
    configured_internal_token = internal_api_token()
    submitted_internal_token = request.headers.get(INTERNAL_API_TOKEN_HEADER)
    if (
        configured_internal_token
        and submitted_internal_token
        and hmac.compare_digest(submitted_internal_token, configured_internal_token)
    ):
        return
    submitted_device_token = request.headers.get(DEVICE_TOKEN_HEADER)
    if verify_device_token(device_id, submitted_device_token):
        return
    raise HTTPException(status_code=401, detail="设备上报需要有效的设备令牌。")
