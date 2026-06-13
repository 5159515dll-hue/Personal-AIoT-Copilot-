from __future__ import annotations

import json
import os
from typing import Any, Literal
from urllib.parse import urljoin

import httpx

from app.models import (
    ActiveModelSelection,
    AgentModelUsage,
    AutomationRuleCreate,
    ModelConfig,
    ModelConfigRequest,
    ModelConnectionTestRequest,
    ModelConnectionTestResponse,
    ModelKeyImportRequest,
    ModelProviderCatalog,
    ModelProviderDefinition,
    ModelSelectionRequest,
    PolicyDecision,
    PolicyResult,
    ProviderEndpoint,
    ProviderProtocol,
    PublicModelConfig,
    ToolCall,
)
from app.storage import JsonListStore
from app.time_utils import now

config_store = JsonListStore("model_config.json", ModelConfig)
active_selection_store = JsonListStore("active_model_selection.json", ActiveModelSelection)
DEFAULT_AGENT_MODEL_TIMEOUT_SECONDS = 12.0

AGENT_SYSTEM_PROMPT = """你是“个人空间智能物联助手”的受约束分析层。你不能直接控制设备，也不能绕过策略引擎。

回复规则：
1. 只能基于工具结果、本地草案回复和策略判断进行解释，不要编造传感器数据、设备状态或审计结果。
2. 如果工具结果显示需要用户确认，必须明确说明保存或执行前需要确认。
3. 如果策略拒绝或阻止某事，必须维持拒绝，不要提供绕过办法。
4. 用中文回复，保持专业、简洁、可执行，适合产品演示场景。
5. 可以补充趋势判断、原因解释、风险提醒和下一步建议，但不要改变工具已经给出的结论。
6. 不要使用 Markdown 标题、粗体、代码块或表格，直接输出适合界面展示的纯文本短段落。"""

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
    ModelProviderDefinition(
        id="doubao",
        label="字节豆包",
        description="字节豆包大模型，火山引擎方舟 Ark，OpenAI 兼容入口，国内响应速度最快，用于情感陪伴共情对话。",
        docs_url="https://www.volcengine.com/docs/82379",
        endpoints=[
            ProviderEndpoint(
                id="doubao_ark_openai",
                label="火山方舟 Ark · OpenAI 兼容",
                protocol=ProviderProtocol.openai,
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                description="火山引擎方舟 Ark OpenAI 兼容入口；密钥为 ark- 开头，模型需先在 Ark 控制台开通。",
            ),
        ],
        models=["doubao-seed-2-0-lite-260215"],
        default_model="doubao-seed-2-0-lite-260215",
    ),
]


def get_catalog() -> ModelProviderCatalog:
    return ModelProviderCatalog(
        providers=PROVIDERS,
        active_config=get_public_config(),
        saved_configs=get_public_configs(),
    )


def get_active_config() -> ModelConfig | None:
    selection = get_active_selection()
    if selection is None:
        return None
    key_config = _provider_key_config(selection.provider_id)
    return ModelConfig(
        provider_id=selection.provider_id,
        endpoint_id=selection.endpoint_id,
        protocol=selection.protocol,
        base_url=selection.base_url,
        model=selection.model,
        api_key=key_config.api_key if key_config else None,
        updated_at=selection.updated_at,
    )


def get_active_selection() -> ActiveModelSelection | None:
    selections = active_selection_store.list()
    if selections:
        return sorted(selections, key=lambda item: item.updated_at, reverse=True)[0]
    if active_selection_store.path.exists():
        return None
    legacy_config = _latest_config()
    if legacy_config is None:
        return None
    return ActiveModelSelection(
        provider_id=legacy_config.provider_id,
        endpoint_id=legacy_config.endpoint_id,
        protocol=legacy_config.protocol,
        base_url=legacy_config.base_url,
        model=legacy_config.model,
        updated_at=legacy_config.updated_at,
    )


def get_public_config() -> PublicModelConfig | None:
    return redact_config(get_active_config())


def get_public_configs() -> list[PublicModelConfig]:
    latest_by_provider: dict[str, ModelConfig] = {}
    for config in sorted(config_store.list(), key=lambda item: item.updated_at, reverse=True):
        latest_by_provider.setdefault(config.provider_id, config)
    return [
        redacted
        for redacted in (
            redact_config(config)
            for config in latest_by_provider.values()
        )
        if redacted is not None
    ]


def save_config(request: ModelConfigRequest) -> PublicModelConfig:
    if request.api_key and request.api_key.strip():
        import_api_key(
            ModelKeyImportRequest(
                provider_id=request.provider_id,
                endpoint_id=request.endpoint_id,
                protocol=request.protocol,
                base_url=request.base_url,
                api_key=request.api_key,
            )
        )
    return select_active_model(
        ModelSelectionRequest(
            provider_id=request.provider_id,
            endpoint_id=request.endpoint_id,
            protocol=request.protocol,
            base_url=request.base_url,
            model=request.model,
        )
    )


def import_api_key(request: ModelKeyImportRequest) -> PublicModelConfig:
    provider, endpoint = validate_model_target(
        request.provider_id,
        request.endpoint_id,
        request.protocol,
        request.base_url,
    )
    base_url = endpoint.base_url.rstrip("/")
    configs = config_store.list()
    _ensure_active_selection_initialized(configs)
    api_key = request.api_key.strip()
    if not api_key:
        raise ValueError("接口密钥不能为空。")
    config = ModelConfig(
        provider_id=request.provider_id,
        endpoint_id=request.endpoint_id,
        protocol=request.protocol,
        base_url=base_url,
        model=provider.default_model,
        api_key=api_key,
        updated_at=now(),
    )
    config_store.replace_all([config, *[item for item in configs if item.provider_id != config.provider_id]])
    return redact_config(config)


def select_active_model(request: ModelSelectionRequest) -> PublicModelConfig:
    _, endpoint = validate_model_target(
        request.provider_id,
        request.endpoint_id,
        request.protocol,
        request.base_url,
    )
    key_config = _provider_key_config(request.provider_id)
    if not key_config or not key_config.api_key:
        raise ValueError("请先导入该厂商接口密钥，再切换当前模型。")
    selection = ActiveModelSelection(
        provider_id=request.provider_id,
        endpoint_id=request.endpoint_id,
        protocol=request.protocol,
        base_url=endpoint.base_url.rstrip("/"),
        model=request.model,
        updated_at=now(),
    )
    active_selection_store.replace_all([selection])
    return redact_config(
        ModelConfig(
            provider_id=selection.provider_id,
            endpoint_id=selection.endpoint_id,
            protocol=selection.protocol,
            base_url=selection.base_url,
            model=selection.model,
            api_key=key_config.api_key,
            updated_at=selection.updated_at,
        )
    )


async def test_connection(request: ModelConnectionTestRequest) -> ModelConnectionTestResponse:
    try:
        _, endpoint = validate_model_target(
            request.provider_id,
            request.endpoint_id,
            request.protocol,
            request.base_url,
        )
    except ValueError as exc:
        return ModelConnectionTestResponse(
            ok=False,
            provider_id=request.provider_id,
            protocol=request.protocol,
            base_url=request.base_url.rstrip("/"),
            model=request.model,
            message=str(exc),
        )

    base_url = endpoint.base_url.rstrip("/")
    requested_key = request.api_key.strip() if request.api_key and request.api_key.strip() else None
    if requested_key:
        api_key = requested_key
    else:
        saved_key = _provider_key_config(request.provider_id)
        api_key = saved_key.api_key if saved_key else None
    if not api_key:
        return ModelConnectionTestResponse(
            ok=False,
            provider_id=request.provider_id,
            protocol=request.protocol,
            base_url=base_url,
            model=request.model,
            message="当前选择未导入 API Key，无法测试连接。",
        )

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


def validate_model_target(
    provider_id: str,
    endpoint_id: str,
    protocol: ProviderProtocol,
    base_url: str,
) -> tuple[ModelProviderDefinition, ProviderEndpoint]:
    provider = next((item for item in PROVIDERS if item.id == provider_id), None)
    if not provider:
        raise ValueError("未知模型厂商。")
    endpoint = next((item for item in provider.endpoints if item.id == endpoint_id), None)
    if not endpoint:
        raise ValueError("未知模型接口入口。")
    if endpoint.protocol != protocol:
        raise ValueError("协议与所选接口入口不匹配。")
    if endpoint.base_url.rstrip("/") != base_url.rstrip("/"):
        raise ValueError("V0 只允许使用预置中国区 Base URL，避免密钥被发送到未知地址。")
    return provider, endpoint


async def generate_agent_reply(
    *,
    user_message: str,
    fallback_reply: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
    allow_model: bool,
) -> tuple[str, AgentModelUsage]:
    config = get_active_config()
    if not allow_model or (policy and policy.result == PolicyResult.denied):
        if config and config.api_key:
            usage = _usage_from_config(
                config,
                status="blocked",
                used=False,
                reason="安全策略已阻止该请求，本次未调用外部大模型。",
            )
        else:
            usage = AgentModelUsage(
                status="blocked",
                used=False,
                reason="安全策略已阻止该请求，本次未调用外部大模型。",
            )
        return fallback_reply, usage

    if not config or not config.api_key:
        return fallback_reply, AgentModelUsage(
            status="not_configured",
            used=False,
            reason="未配置当前大模型或密钥，已使用本地工具链回复。",
        )

    prompt = _agent_user_prompt(
        user_message=user_message,
        fallback_reply=fallback_reply,
        used_data=used_data,
        tool_calls=tool_calls,
        needs_confirmation=needs_confirmation,
        policy=policy,
        rule_draft=rule_draft,
    )
    try:
        content = await _call_agent_model(config, prompt)
        if not content.strip():
            content = await _call_agent_model(
                config,
                f"{prompt}\n\n上一次模型返回为空。请务必用 3 到 6 句中文给出最终分析，不要返回空内容。",
            )
    except (httpx.HTTPError, ValueError) as exc:
        return fallback_reply, _usage_from_config(
            config,
            status="fallback",
            used=False,
            reason=f"大模型调用失败，已回退到本地工具链回复：{_error_summary(exc)}",
        )

    content = _sanitize_model_reply(content)
    if not content:
        return fallback_reply, _usage_from_config(
            config,
            status="fallback",
            used=False,
            reason="大模型未返回可用文本，已回退到本地工具链回复。",
        )

    return content, _usage_from_config(
        config,
        status="used",
        used=True,
        reason="已在工具调用和策略判断之后使用当前大模型生成增强分析。",
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


def _latest_config() -> ModelConfig | None:
    configs = config_store.list()
    if not configs:
        return None
    return sorted(configs, key=lambda item: item.updated_at, reverse=True)[0]


def _provider_key_config(provider_id: str) -> ModelConfig | None:
    for config in sorted(config_store.list(), key=lambda item: item.updated_at, reverse=True):
        if config.provider_id == provider_id and config.api_key:
            return config
    return None


def _ensure_active_selection_initialized(configs: list[ModelConfig]) -> None:
    if active_selection_store.path.exists():
        return
    legacy_config = sorted(configs, key=lambda item: item.updated_at, reverse=True)[0] if configs else None
    if legacy_config is None:
        active_selection_store.replace_all([])
        return
    active_selection_store.replace_all(
        [
            ActiveModelSelection(
                provider_id=legacy_config.provider_id,
                endpoint_id=legacy_config.endpoint_id,
                protocol=legacy_config.protocol,
                base_url=legacy_config.base_url,
                model=legacy_config.model,
                updated_at=legacy_config.updated_at,
            )
        ]
    )


def _openai_headers(provider_id: str, api_key: str) -> dict[str, str]:
    if provider_id == "xiaomi_mimo":
        return {
            "api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }


def apply_speed_params(payload: dict[str, Any], provider_id: str, *, temperature: float = 0.2) -> dict[str, Any]:
    """统一的低延迟参数：豆包/Kimi 是推理模型，默认开思考很慢（豆包实测 14.6s→2.8s，
    且会超 12s 超时），情感陪伴对延迟敏感 → 关思考只取正文；其余厂商用 temperature。"""
    if provider_id in ("kimi", "doubao"):
        payload["thinking"] = {"type": "disabled"}
    else:
        payload["temperature"] = temperature
    return payload


def _openai_test_payload(provider_id: str, model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复：连接正常"}],
        "max_completion_tokens": 128,
    }
    return apply_speed_params(payload, provider_id)


async def _openai_agent_completion(client: httpx.AsyncClient, config: ModelConfig, prompt: str) -> str:
    response = await client.post(
        urljoin(f"{config.base_url.rstrip('/')}/", "chat/completions"),
        headers=_openai_headers(config.provider_id, config.api_key or ""),
        json=_openai_agent_payload(config.provider_id, config.model, prompt),
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError(f"服务返回 {response.status_code}：{response.text[:300]}")
    payload = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("响应缺少 choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    raise ValueError("响应缺少 message.content")


async def _anthropic_agent_completion(client: httpx.AsyncClient, config: ModelConfig, prompt: str) -> str:
    response = await client.post(
        urljoin(f"{config.base_url.rstrip('/')}/", "v1/messages"),
        headers={
            "x-api-key": config.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.model,
            "max_tokens": 1000,
            "system": AGENT_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError(f"服务返回 {response.status_code}：{response.text[:300]}")
    payload = response.json()
    parts = payload.get("content")
    if not isinstance(parts, list):
        raise ValueError("响应缺少 content")
    return "".join(str(item.get("text", "")) for item in parts if isinstance(item, dict) and item.get("type") == "text")


def _openai_agent_payload(provider_id: str, model: str, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 1200,
    }
    return apply_speed_params(payload, provider_id)


async def _call_agent_model(config: ModelConfig, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=_agent_model_timeout_seconds()) as client:
        if config.protocol == ProviderProtocol.openai:
            return await _openai_agent_completion(client, config, prompt)
        return await _anthropic_agent_completion(client, config, prompt)


def _agent_model_timeout_seconds() -> float:
    raw = os.getenv("AIOT_AGENT_MODEL_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return DEFAULT_AGENT_MODEL_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_AGENT_MODEL_TIMEOUT_SECONDS
    return max(1.0, timeout)


def _agent_user_prompt(
    *,
    user_message: str,
    fallback_reply: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> str:
    payload = {
        "用户问题": user_message,
        "本地工具链草案回复": fallback_reply,
        "使用的数据源": used_data,
        "是否需要确认": needs_confirmation,
        "策略判断": policy.model_dump(mode="json") if policy else None,
        "规则草案": rule_draft.model_dump(mode="json") if rule_draft else None,
        "工具调用": [
            _tool_call_for_prompt(tool)
            for tool in tool_calls
        ],
    }
    return (
        "请根据下面 JSON 生成智能体最终回复。不要输出 JSON，不要声称调用了不存在的工具。\n"
        f"{_compact_json(payload)}"
    )


def _compact_json(payload: Any, limit: int = 9000) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...已截断，仅展示关键工具证据。"


def _sanitize_model_reply(content: str) -> str:
    return "\n".join(
        line.lstrip("# ").replace("**", "").replace("__", "").rstrip()
        for line in content.strip().splitlines()
    ).strip()


def _tool_call_for_prompt(tool: ToolCall) -> dict[str, Any]:
    result = tool.result
    if tool.name == "get_current_room_state":
        result = {
            "status": tool.result.get("status"),
            "health_score": tool.result.get("health_score"),
            "summary": tool.result.get("summary"),
            "anomalies": tool.result.get("anomalies"),
            "recommendation": tool.result.get("recommendation"),
        }
    elif tool.name == "query_sensor_history":
        result = tool.result
    elif tool.name == "get_anomaly_events":
        events = tool.result.get("events") or []
        result = {
            "count": tool.result.get("count"),
            "events": [
                {
                    "severity": event.get("severity"),
                    "status": event.get("status"),
                    "metric": event.get("metric"),
                    "title": event.get("title"),
                    "detail": event.get("detail"),
                    "recommendation": event.get("recommendation"),
                }
                for event in events[:5]
                if isinstance(event, dict)
            ],
        }
    elif tool.name in {"create_automation_rule", "control_device", "policy_check"}:
        result = {
            "status": tool.result.get("status"),
            "execution_result": tool.result.get("execution_result"),
            "decision": tool.result.get("decision"),
            "policy": tool.result.get("policy"),
        }
    return {
        "name": tool.name,
        "parameters": tool.parameters,
        "result": result,
        "policy": tool.policy.model_dump(mode="json") if tool.policy else None,
    }


def _usage_from_config(
    config: ModelConfig,
    *,
    status: Literal["not_configured", "used", "fallback", "blocked"],
    used: bool,
    reason: str,
) -> AgentModelUsage:
    return AgentModelUsage(
        provider_id=config.provider_id,
        provider_label=_provider_label(config.provider_id),
        model=config.model,
        protocol=config.protocol.value,
        status=status,
        used=used,
        reason=reason,
    )


def _provider_label(provider_id: str) -> str:
    for provider in PROVIDERS:
        if provider.id == provider_id:
            return provider.label
    return provider_id


def _error_summary(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__
