from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.model_providers import get_catalog, get_public_config, import_api_key, save_config, select_active_model, test_connection
from app.models import (
    ModelConfigRequest,
    ModelConnectionTestRequest,
    ModelConnectionTestResponse,
    ModelKeyImportRequest,
    ModelProviderCatalog,
    ModelSelectionRequest,
    PublicModelConfig,
)

router = APIRouter(prefix="/api/model-providers", tags=["model-providers"])


@router.get("", response_model=ModelProviderCatalog)
def list_model_providers() -> ModelProviderCatalog:
    return get_catalog()


@router.get("/active", response_model=PublicModelConfig | None)
def active_model_config() -> PublicModelConfig | None:
    return get_public_config()


@router.post("/active", response_model=PublicModelConfig)
def update_model_config(request: ModelConfigRequest) -> PublicModelConfig:
    try:
        saved = save_config(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        actor="user",
        action="update_model_provider",
        result="success",
        details="模型厂商配置已更新，接口密钥不会在接口响应中回显。",
        parameters={
            "provider_id": saved.provider_id,
            "endpoint_id": saved.endpoint_id,
            "protocol": saved.protocol,
            "base_url": saved.base_url,
            "model": saved.model,
            "api_key_set": saved.api_key_set,
        },
    )
    return saved


@router.post("/keys", response_model=PublicModelConfig)
def import_model_provider_key(request: ModelKeyImportRequest) -> PublicModelConfig:
    try:
        saved = import_api_key(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        actor="user",
        action="import_model_provider_key",
        result="success",
        details="模型厂商接口密钥已导入或覆盖，接口响应不会回显明文密钥。",
        parameters={
            "provider_id": saved.provider_id,
            "endpoint_id": saved.endpoint_id,
            "protocol": saved.protocol,
            "base_url": saved.base_url,
            "api_key_set": saved.api_key_set,
        },
    )
    return saved


@router.post("/selection", response_model=PublicModelConfig)
def switch_active_model(request: ModelSelectionRequest) -> PublicModelConfig:
    try:
        saved = select_active_model(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        actor="user",
        action="switch_active_model",
        result="success",
        details="智能体当前模型已切换，未接收或保存新的接口密钥。",
        parameters={
            "provider_id": saved.provider_id,
            "endpoint_id": saved.endpoint_id,
            "protocol": saved.protocol,
            "base_url": saved.base_url,
            "model": saved.model,
            "api_key_set": saved.api_key_set,
        },
    )
    return saved


@router.post("/test", response_model=ModelConnectionTestResponse)
async def test_model_provider(request: ModelConnectionTestRequest) -> ModelConnectionTestResponse:
    result = await test_connection(request)
    record_audit(
        actor="user",
        action="test_model_provider",
        result="success" if result.ok else "failed",
        details=result.message,
        parameters={
            "provider_id": result.provider_id,
            "protocol": result.protocol,
            "base_url": result.base_url,
            "model": result.model,
            "status_code": result.status_code,
        },
    )
    return result
