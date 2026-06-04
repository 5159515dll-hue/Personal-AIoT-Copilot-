from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.models import (
    ModelConfig,
    ModelConfigRequest,
    ModelConnectionTestRequest,
    ModelConnectionTestResponse,
    ModelProviderCatalog,
    ModelProviderDefinition,
    ProviderEndpoint,
    ProviderProtocol,
    PublicModelConfig,
)
from app.storage import JsonListStore
from app.time_utils import now

config_store = JsonListStore("model_config.json", ModelConfig)

PROVIDERS: list[ModelProviderDefinition] = [
    ModelProviderDefinition(
        id="xiaomi_mimo",
        label="小米 MiMo",
        description="小米 MiMo 大模型，预置 Token Plan 中国集群入口，支持 OpenAI 与 Anthropic 兼容协议。",
        docs_url="https://platform.xiaomimimo.com/docs/zh-CN/tokenplan/quick-access",
        endpoints=[
            ProviderEndpoint(
                id="mimo_token_cn_openai",
                label="Token Plan 中国集群 · OpenAI 兼容",
                protocol=ProviderProtocol.openai,
                base_url="https://token-plan-cn.xiaomimimo.com/v1",
                description="订阅套餐专属入口，接口密钥通常为 tp- 开头。",
            ),
            ProviderEndpoint(
                id="mimo_token_cn_anthropic",
                label="Token Plan 中国集群 · Anthropic 兼容",
                protocol=ProviderProtocol.anthropic,
                base_url="https://token-plan-cn.xiaomimimo.com/anthropic",
                description="订阅套餐 Anthropic 兼容入口。",
            ),
        ],
        models=["mimo-v2.5-pro", "mimo-v2.5"],
        default_model="mimo-v2.5-pro",
    ),
    ModelProviderDefinition(
        id="kimi",
        label="Kimi（月之暗面）",
        description="Kimi 开放平台，预置中国区 OpenAI 兼容入口。",
        docs_url="https://platform.kimi.com/docs/api/overview",
        endpoints=[
            ProviderEndpoint(
                id="kimi_cn_openai",
                label="中国区 · OpenAI 兼容",
                protocol=ProviderProtocol.openai,
                base_url="https://api.moonshot.cn/v1",
                description="Kimi 中国区 OpenAI 兼容入口。",
            ),
        ],
        models=[
            "kimi-k2.6",
            "kimi-k2.5",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
            "moonshot-v1-8k-vision-preview",
        ],
        default_model="kimi-k2.6",
    ),
]


def get_catalog() -> ModelProviderCatalog:
    return ModelProviderCatalog(providers=PROVIDERS, active_config=get_public_config())


def get_active_config() -> ModelConfig | None:
    configs = config_store.list()
    if not configs:
        return None
    return sorted(configs, key=lambda item: item.updated_at, reverse=True)[0]


def get_public_config() -> PublicModelConfig | None:
    return redact_config(get_active_config())


def save_config(request: ModelConfigRequest) -> PublicModelConfig:
    existing = get_active_config()
    api_key = request.api_key if request.api_key else existing.api_key if existing else None
    config = ModelConfig(
        provider_id=request.provider_id,
        endpoint_id=request.endpoint_id,
        protocol=request.protocol,
        base_url=request.base_url.rstrip("/"),
        model=request.model,
        api_key=api_key,
        updated_at=now(),
    )
    config_store.replace_all([config])
    return redact_config(config)


async def test_connection(request: ModelConnectionTestRequest) -> ModelConnectionTestResponse:
    active = get_active_config()
    if request.api_key:
        api_key = request.api_key
    elif active:
        api_key = active.api_key
    else:
        api_key = None
    if not api_key:
        return ModelConnectionTestResponse(
            ok=False,
            provider_id=request.provider_id,
            protocol=request.protocol,
            base_url=request.base_url,
            model=request.model,
            message="未配置 API Key，无法测试连接。",
        )

    base_url = request.base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            if request.protocol == ProviderProtocol.openai:
                response = await client.post(
                    urljoin(f"{base_url}/", "chat/completions"),
                    headers=_openai_headers(request.provider_id, api_key),
                    json=_openai_test_payload(request.provider_id, request.model),
                )
            else:
                response = await client.post(
                    urljoin(f"{base_url}/", "v1/messages"),
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": request.model,
                        "max_tokens": 16,
                        "messages": [{"role": "user", "content": "请回复：连接正常"}],
                    },
                )
    except httpx.HTTPError as exc:
        return ModelConnectionTestResponse(
            ok=False,
            provider_id=request.provider_id,
            protocol=request.protocol,
            base_url=base_url,
            model=request.model,
            message=f"连接失败：{exc}",
        )

    ok = 200 <= response.status_code < 300
    if ok:
        message = "连接成功，当前 Base URL 与密钥可用。"
    else:
        body = response.text[:300]
        message = f"连接失败，服务返回 {response.status_code}：{body}"
    return ModelConnectionTestResponse(
        ok=ok,
        provider_id=request.provider_id,
        protocol=request.protocol,
        base_url=base_url,
        model=request.model,
        message=message,
        status_code=response.status_code,
    )


def redact_config(config: ModelConfig | None) -> PublicModelConfig | None:
    if config is None:
        return None
    return PublicModelConfig(
        provider_id=config.provider_id,
        endpoint_id=config.endpoint_id,
        protocol=config.protocol,
        base_url=config.base_url,
        model=config.model,
        api_key_set=bool(config.api_key),
        api_key_preview=_preview(config.api_key),
        updated_at=config.updated_at,
    )


def _preview(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 10:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _openai_headers(provider_id: str, api_key: str) -> dict[str, str]:
    if provider_id == "xiaomi_mimo":
        return {
            "api-key": api_key,
            "content-type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }


def _openai_test_payload(provider_id: str, model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复：连接正常"}],
    }
    if provider_id == "xiaomi_mimo":
        payload["max_completion_tokens"] = 16
    else:
        payload["max_tokens"] = 16
    return payload
