from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Metric(str, Enum):
    temperature = "temperature"
    humidity = "humidity"
    co2 = "co2"
    light = "light"
    presence = "presence"


class RiskLevel(str, Enum):
    read_only = "read_only"
    low = "low"
    medium = "medium"
    high = "high"
    forbidden = "forbidden"


class PolicyResult(str, Enum):
    allowed = "allowed"
    requires_confirmation = "requires_confirmation"
    denied = "denied"


class DeviceState(str, Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"


class SensorReading(BaseModel):
    metric: Metric
    value: float
    unit: str
    timestamp: datetime
    device_id: str = "room_node_01"
    quality: Literal["ok", "stale", "anomaly"] = "ok"


class SensorValueInput(BaseModel):
    metric: Metric
    value: float
    unit: str | None = None
    timestamp: datetime | None = None
    quality: Literal["ok", "stale", "anomaly"] = "ok"


class SensorIngestRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    readings: list[SensorValueInput] = Field(min_length=1, max_length=64)
    source: Literal["http", "mqtt", "test"] = "http"


class SensorIngestResponse(BaseModel):
    accepted: int
    stored: int
    source: str
    message: str


class TelemetryStatus(BaseModel):
    source: Literal["database"] = "database"
    configured: bool
    connected: bool
    sensor_table_exists: bool = False
    timescale_available: bool = False
    timescale_enabled: bool = False
    hypertable: bool = False
    total_readings: int = 0
    device_count: int = 0
    metric_count: int = 0
    latest_reading_at: datetime | None = None
    latest_received_at: datetime | None = None
    latest_metrics: dict[Metric, SensorReading] = Field(default_factory=dict)
    status: Literal["ok", "empty", "unavailable"]
    message: str


class RoomState(BaseModel):
    timestamp: datetime
    health_score: int = Field(ge=0, le=100)
    status: Literal["good", "watch", "poor"]
    summary: str
    metrics: dict[Metric, SensorReading]
    anomalies: list[str]
    recommendation: str


class Device(BaseModel):
    id: str
    name: str
    type: str
    location: str
    risk_level: RiskLevel
    controllable: bool
    requires_confirmation: bool
    online_state: DeviceState
    current_state: dict[str, Any]
    connected_appliance: str | None = None
    max_active_duration_minutes: int | None = None


class PolicyDecision(BaseModel):
    result: PolicyResult
    risk_level: RiskLevel
    requires_confirmation: bool
    reason: str
    constraints: list[str] = Field(default_factory=list)


class ControlDeviceRequest(BaseModel):
    state: Literal["on", "off"]
    confirmed: bool = False
    reason: str = "user request"


class ControlDeviceResponse(BaseModel):
    policy: PolicyDecision
    execution_result: Literal["success", "blocked", "requires_confirmation", "failed"]
    audit_log_id: str
    device: Device | None = None


class AutomationRuleCreate(BaseModel):
    condition: str = Field(min_length=3, max_length=240)
    action: str = Field(min_length=3, max_length=240)
    enabled: bool = True
    confirmed: bool = False


class AutomationRuleUpdate(BaseModel):
    enabled: bool


class AutomationRule(BaseModel):
    id: str = Field(default_factory=lambda: f"rule_{uuid4().hex[:10]}")
    condition: str
    action: str
    enabled: bool = True
    created_by: Literal["user", "agent"] = "user"
    created_at: datetime


class RuleEvaluation(BaseModel):
    rule_id: str
    condition: str
    action: str
    matched: bool
    status: Literal["triggered", "not_matched", "disabled", "unsupported"]
    reason: str
    evaluated_at: datetime
    observed: dict[str, Any] = Field(default_factory=dict)
    audit_log_id: str | None = None


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    data_source: Literal["mock", "database"] = "mock"


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: f"tool_{uuid4().hex[:10]}")
    name: str
    parameters: dict[str, Any]
    result: dict[str, Any]
    policy: PolicyDecision | None = None
    created_at: datetime


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AgentModelUsage(BaseModel):
    provider_id: str | None = None
    provider_label: str | None = None
    model: str | None = None
    protocol: str | None = None
    status: Literal["not_configured", "used", "fallback", "blocked"]
    used: bool
    reason: str


class AgentChatResponse(BaseModel):
    session_id: str
    message: AgentMessage
    used_data: list[str]
    tool_calls: list[ToolCall]
    needs_confirmation: bool
    model_usage: AgentModelUsage
    policy: PolicyDecision | None = None
    rule_draft: AutomationRuleCreate | None = None


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: f"audit_{uuid4().hex[:12]}")
    timestamp: datetime
    actor: Literal["user", "agent", "system"]
    action: str
    policy_result: PolicyResult | None = None
    risk_level: RiskLevel | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: str
    details: str


class ProviderProtocol(str, Enum):
    openai = "openai"
    anthropic = "anthropic"


class ProviderEndpoint(BaseModel):
    id: str
    label: str
    protocol: ProviderProtocol
    base_url: str
    description: str


class ModelProviderDefinition(BaseModel):
    id: str
    label: str
    description: str
    docs_url: str
    endpoints: list[ProviderEndpoint]
    models: list[str]
    default_model: str


class ModelConfigRequest(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    api_key: str | None = Field(default=None, max_length=4096)


class ModelConfig(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    api_key: str | None = None
    updated_at: datetime


class ModelKeyImportRequest(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    api_key: str = Field(min_length=1, max_length=4096)


class ModelSelectionRequest(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str


class ActiveModelSelection(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    updated_at: datetime


class PublicModelConfig(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    api_key_set: bool
    api_key_preview: str | None = None
    updated_at: datetime | None = None


class ModelProviderCatalog(BaseModel):
    providers: list[ModelProviderDefinition]
    active_config: PublicModelConfig | None
    saved_configs: list[PublicModelConfig] = Field(default_factory=list)


class ModelConnectionTestRequest(BaseModel):
    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    api_key: str | None = Field(default=None, max_length=4096)


class ModelConnectionTestResponse(BaseModel):
    ok: bool
    provider_id: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    message: str
    status_code: int | None = None
