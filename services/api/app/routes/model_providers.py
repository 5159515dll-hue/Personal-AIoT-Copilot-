from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.model_providers import get_catalog, get_public_config, save_config, test_connection
from app.models import (
    ModelConfigRequest,
    ModelConnectionTestRequest,
    ModelConnectionTestResponse,
    ModelProviderCatalog,
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
