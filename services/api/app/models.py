from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Metric(str, Enum):
    temperature = "temperature"
    humidity = "humidity"
    co2 = "co2"
    light = "light"
    presence = "presence"
    noise = "noise"


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


class SensorHealth(BaseModel):
    metric: Metric
    status: Literal["ok", "stale", "anomaly", "offline", "unavailable"]
    source: Literal["mock", "database"]
    device_id: str | None = None
    last_seen_at: datetime | None = None
    age_minutes: float | None = None
    quality: Literal["ok", "stale", "anomaly"] | None = None
    value: float | None = None
    unit: str | None = None
    message: str


class SensorValueInput(BaseModel):
    metric: Metric
    value: float
    unit: str | None = None
    timestamp: datetime | None = None
    quality: Literal["ok", "stale", "anomaly"] = "ok"


class DeviceCapability(BaseModel):
    kind: Literal["telemetry", "control", "gateway", "diagnostic"] = "telemetry"
    metrics: list[Metric] = Field(default_factory=list, max_length=16)
    description: str | None = Field(default=None, max_length=160)


class SensorIngestRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    readings: list[SensorValueInput] = Field(min_length=1, max_length=64)
    source: Literal["http", "mqtt", "test"] = "http"
    protocol_version: str = Field(default="aiot.v1", max_length=32)
    message_id: str | None = Field(default=None, max_length=120)
    sequence: int | None = Field(default=None, ge=0)
    sent_at: datetime | None = None
    device_type: str | None = Field(default=None, max_length=40)
    firmware_version: str | None = Field(default=None, max_length=80)
    hardware_revision: str | None = Field(default=None, max_length=80)
    capabilities: list[DeviceCapability] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SensorIngestResponse(BaseModel):
    accepted: int
    stored: int
    source: str
    message: str


class DeviceRegistrationRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    display_name: str | None = Field(default=None, max_length=120)
    device_type: Literal["esp32", "stm32", "raspberry_pi", "linux_gateway", "sensor_node", "other"] = "other"
    transport: Literal["mqtt", "http", "serial_gateway", "edge_gateway"] = "mqtt"
    protocol_version: str = Field(default="aiot.v1", max_length=32)
    firmware_version: str | None = Field(default=None, max_length=80)
    hardware_revision: str | None = Field(default=None, max_length=80)
    location: str = Field(default="unknown", max_length=80)
    capabilities: list[DeviceCapability] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceHeartbeatRequest(BaseModel):
    status: Literal["online", "degraded", "offline"] = "online"
    transport: Literal["mqtt", "http", "serial_gateway", "edge_gateway"] = "http"
    protocol_version: str = Field(default="aiot.v1", max_length=32)
    firmware_version: str | None = Field(default=None, max_length=80)
    uptime_seconds: int | None = Field(default=None, ge=0)
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    rssi_dbm: float | None = None
    message_id: str | None = Field(default=None, max_length=120)
    sequence: int | None = Field(default=None, ge=0)
    sent_at: datetime | None = None
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)


class DeviceTelemetryRequest(BaseModel):
    protocol_version: str = Field(default="aiot.v1", max_length=32)
    message_id: str | None = Field(default=None, max_length=120)
    sequence: int | None = Field(default=None, ge=0)
    sent_at: datetime | None = None
    readings: list[SensorValueInput] = Field(min_length=1, max_length=64)
    firmware_version: str | None = Field(default=None, max_length=80)
    capabilities: list[DeviceCapability] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceTelemetryResponse(BaseModel):
    device_id: str
    accepted: int
    stored: int
    source: Literal["http", "mqtt", "test"]
    message_id: str | None = None
    received_at: datetime
    message: str


class DeviceConnectionRecord(BaseModel):
    device_id: str
    display_name: str
    device_type: str
    transport: str
    protocol_version: str
    firmware_version: str | None = None
    hardware_revision: str | None = None
    location: str
    capabilities: list[DeviceCapability] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    online_state: DeviceState = DeviceState.unknown
    last_seen_at: datetime | None = None
    last_message_id: str | None = None
    last_sequence: int | None = None
    updated_at: datetime


class DeviceHeartbeatResponse(BaseModel):
    device_id: str
    online_state: DeviceState
    last_seen_at: datetime
    message: str


class TelemetrySourceSummary(BaseModel):
    source: str
    total_readings: int
    device_count: int
    latest_reading_at: datetime | None = None
    latest_received_at: datetime | None = None


class TelemetryDeviceSummary(BaseModel):
    device_id: str
    total_readings: int
    metric_count: int
    latest_reading_at: datetime | None = None
    latest_received_at: datetime | None = None


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
    sources: list[TelemetrySourceSummary] = Field(default_factory=list)
    devices: list[TelemetryDeviceSummary] = Field(default_factory=list)
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


class AnomalyEvent(BaseModel):
    id: str
    timestamp: datetime
    source: Literal["mock", "database"]
    severity: Literal["info", "warning", "critical"]
    category: Literal["environment", "sensor_health"]
    metric: Metric | None = None
    title: str
    detail: str
    recommendation: str
    status: Literal["active", "observed", "resolved"]
    evidence: dict[str, Any] = Field(default_factory=dict)


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


class DeviceControlRateEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"rate_{uuid4().hex[:10]}")
    device_id: str
    actor: Literal["user", "agent"]
    timestamp: datetime


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
    trigger_count: int = 0
    last_triggered_at: datetime | None = None


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


class AgentConversationEntry(BaseModel):
    id: str = Field(default_factory=lambda: f"agent_history_{uuid4().hex[:12]}")
    session_id: str
    data_source: Literal["mock", "database"]
    user_message: AgentMessage
    assistant_message: AgentMessage
    used_data: list[str]
    tool_calls: list[ToolCall]
    needs_confirmation: bool
    model_usage: AgentModelUsage
    policy: PolicyDecision | None = None
    rule_draft: AutomationRuleCreate | None = None
    created_at: datetime


class AgentConversationDeleteResponse(BaseModel):
    deleted: bool
    id: str
    audit_log_id: str | None = None


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
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    endpoint_id: str
    protocol: ProviderProtocol
    base_url: str
    api_key: str = Field(min_length=1, max_length=4096)


class ModelSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
