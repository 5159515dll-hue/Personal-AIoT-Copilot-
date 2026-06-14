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
    kind: Literal["telemetry", "control", "gateway", "diagnostic", "media", "vision", "stream"] = "telemetry"
    metrics: list[Metric] = Field(default_factory=list, max_length=16)
    description: str | None = Field(default=None, max_length=160)


class NodeSensor(BaseModel):
    """节点上的单个传感器（按 metric 聚合最新读数）。status: fresh=最近上报 / stale=读数过旧 / silent=声明过但当前无读数。"""

    metric: Metric
    value: float | None = None
    unit: str | None = None
    quality: Literal["ok", "stale", "anomaly"] | None = None
    last_reading_at: datetime | None = None
    age_seconds: float | None = None
    status: Literal["fresh", "stale", "silent"] = "silent"


class NodeSummary(BaseModel):
    """一个真实接入节点（如 ESP32）及其传感器一览，用于前端节点视图。"""

    device_id: str
    display_name: str
    device_type: str
    transport: str
    online: bool = False
    online_state: DeviceState = DeviceState.unknown
    last_seen_at: datetime | None = None
    age_seconds: float | None = None
    firmware_version: str | None = None
    location: str | None = None
    sensor_count: int = 0
    reporting_count: int = 0
    sensors: list[NodeSensor] = Field(default_factory=list)


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


class DeviceManagementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    device_type: Literal["esp32", "stm32", "raspberry_pi", "linux_gateway", "sensor_node", "smart_light", "ir_remote", "smart_plug", "safety_alarm", "other"] | None = None
    transport: Literal["mqtt", "http", "serial_gateway", "edge_gateway"] | None = None
    firmware_version: str | None = Field(default=None, max_length=80)
    hardware_revision: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, min_length=1, max_length=80)
    risk_level: RiskLevel | None = None
    controllable: bool | None = None
    requires_confirmation: bool | None = None
    connected_appliance: str | None = Field(default=None, max_length=120)
    max_active_duration_minutes: int | None = Field(default=None, ge=1, le=240)
    load_type: Literal[
        "none",
        "low_voltage_light",
        "usb_fan",
        "indicator",
        "relay_unknown",
        "high_power",
        "safety_critical",
        "other",
    ] | None = None
    load_label: str | None = Field(default=None, max_length=120)
    load_power_watts: float | None = Field(default=None, ge=0, le=5000)
    management_note: str | None = Field(default=None, max_length=240)
    tags: list[str] = Field(default_factory=list, max_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceManagementCreate(DeviceManagementUpdate):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=120)
    device_type: Literal["esp32", "stm32", "raspberry_pi", "linux_gateway", "sensor_node", "smart_light", "ir_remote", "smart_plug", "safety_alarm", "other"] = "sensor_node"
    transport: Literal["mqtt", "http", "serial_gateway", "edge_gateway"] = "mqtt"
    protocol_version: str = Field(default="aiot.v1", min_length=1, max_length=40)
    location: str = Field(default="unknown", min_length=1, max_length=80)
    risk_level: RiskLevel = RiskLevel.read_only
    controllable: bool = False
    requires_confirmation: bool = False


class DeviceOfflineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="后台手动下线", min_length=1, max_length=160)


class DeviceBatchManagementItem(DeviceManagementUpdate):
    device_id: str = Field(min_length=1, max_length=80)
    offline: bool = False
    offline_reason: str | None = Field(default=None, max_length=160)


class DeviceBatchManagementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DeviceBatchManagementItem] = Field(min_length=1, max_length=100)


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


class SpaceMediaPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_realtime_stream: bool = False
    allow_event_media: bool = False
    media_retention_days: int = Field(default=7, ge=1, le=30)
    event_retention_days: int = Field(default=30, ge=1, le=180)


class SpacePerceptionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: Literal["disabled", "planned", "local_only"] = "disabled"
    face_recognition: Literal["disabled", "planned", "local_only"] = "disabled"
    emotion_recognition: Literal["disabled", "planned", "local_only"] = "disabled"
    location_tracking: Literal["disabled", "planned", "local_only"] = "disabled"
    image_retention: Literal["none", "metadata_only", "event_media"] = "none"
    privacy_mode: Literal["strict", "local_only"] = "strict"
    media_policy: SpaceMediaPolicy = Field(default_factory=SpaceMediaPolicy)
    notes: str | None = Field(default=None, max_length=240)


class RoomSpace(BaseModel):
    id: str
    name: str
    space_type: Literal["study", "bedroom", "living_room", "lab", "balcony", "kitchen", "other"]
    location_label: str
    floor: str | None = None
    timezone: str = "Asia/Shanghai"
    is_active: bool = False
    device_ids: list[str] = Field(default_factory=list, max_length=100)
    zones: list[str] = Field(default_factory=list, max_length=50)
    perception: SpacePerceptionSettings = Field(default_factory=SpacePerceptionSettings)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RoomSpaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=120)
    space_type: Literal["study", "bedroom", "living_room", "lab", "balcony", "kitchen", "other"] = "study"
    location_label: str = Field(default="书房", min_length=1, max_length=120)
    floor: str | None = Field(default=None, max_length=80)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    device_ids: list[str] = Field(default_factory=list, max_length=100)
    zones: list[str] = Field(default_factory=list, max_length=50)
    perception: SpacePerceptionSettings = Field(default_factory=SpacePerceptionSettings)
    notes: str | None = Field(default=None, max_length=240)


class RoomSpaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    space_type: Literal["study", "bedroom", "living_room", "lab", "balcony", "kitchen", "other"] | None = None
    location_label: str | None = Field(default=None, min_length=1, max_length=120)
    floor: str | None = Field(default=None, max_length=80)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    device_ids: list[str] | None = Field(default=None, max_length=100)
    zones: list[str] | None = Field(default=None, max_length=50)
    perception: SpacePerceptionSettings | None = None
    notes: str | None = Field(default=None, max_length=240)


class RoomSpaceMutationResponse(BaseModel):
    space: RoomSpace
    audit_log_id: str


class RoomSpaceDeleteResponse(BaseModel):
    deleted: bool
    space_id: str
    audit_log_id: str


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


class ManagedDevice(BaseModel):
    device: Device
    connection: DeviceConnectionRecord | None = None
    binding_status: Literal["bound", "registry_only", "connection_only"]
    load_mark: dict[str, Any] = Field(default_factory=dict)
    management_flags: list[str] = Field(default_factory=list)


class DeviceManagementResponse(BaseModel):
    item: ManagedDevice
    audit_log_id: str


class DeviceManagementDeleteResponse(BaseModel):
    deleted: bool
    device_id: str
    audit_log_id: str


class DeviceBatchManagementFailure(BaseModel):
    device_id: str
    error: str


class DeviceBatchManagementResponse(BaseModel):
    updated: list[ManagedDevice]
    failed: list[DeviceBatchManagementFailure] = Field(default_factory=list)


class DeviceCredentialPublic(BaseModel):
    device_id: str
    issued_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    token_preview: str


class DeviceCredentialIssueResponse(BaseModel):
    credential: DeviceCredentialPublic
    token: str
    audit_log_id: str


class DeviceCredentialRecord(BaseModel):
    device_id: str
    token_hash: str
    token_preview: str
    issued_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None


DeviceEventType = Literal[
    "presence_detected",
    "motion_detected",
    "face_detected",
    "emotion_detected",
    "location_update",
    "safety_alert",
    "custom",
]


class DeviceEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: str = Field(default="aiot.v1", max_length=32)
    message_id: str | None = Field(default=None, max_length=120)
    sequence: int | None = Field(default=None, ge=0)
    event_type: DeviceEventType
    severity: Literal["info", "warning", "critical"] = "info"
    confidence: float | None = Field(default=None, ge=0, le=1)
    space_id: str = Field(min_length=1, max_length=80)
    zone: str | None = Field(default=None, max_length=80)
    captured_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    media_ids: list[str] = Field(default_factory=list, max_length=16)


class DeviceEvent(DeviceEventCreate):
    id: str = Field(default_factory=lambda: f"event_{uuid4().hex[:12]}")
    device_id: str
    received_at: datetime


class DeviceEventIngestResponse(BaseModel):
    event: DeviceEvent
    audit_log_id: str


# ── 多模态情感感知（情感陪伴）────────────────────────────────────────
EMOTION_LABELS: tuple[str, ...] = (
    "happy",
    "sad",
    "angry",
    "surprise",
    "fear",
    "disgust",
    "neutral",
)
EmotionLabel = Literal["happy", "sad", "angry", "surprise", "fear", "disgust", "neutral"]
EmotionLanguage = Literal["zh", "en", "mn"]


class EmotionModalityInput(BaseModel):
    """单模态推理结果：7 类情绪上的分布 + 置信度。喂给融合引擎。

    distribution 的键应是 EMOTION_LABELS 子集；融合时会归一化，缺失类按 0 处理。
    """

    model_config = ConfigDict(extra="forbid")

    distribution: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0, le=1)
    transcript_lang: str | None = Field(default=None, max_length=16)


class EmotionModalitySummary(BaseModel):
    """落到情绪事件 attributes 里的单模态摘要。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unavailable"] = "ok"
    emotion: EmotionLabel | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    transcript_lang: str | None = Field(default=None, max_length=16)


class EmotionState(BaseModel):
    """融合 + 时序平滑后的统一情绪状态。"""

    model_config = ConfigDict(extra="forbid")

    primary_emotion: EmotionLabel
    valence: float = Field(ge=-1, le=1)
    arousal: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    language: EmotionLanguage = "zh"
    modalities: dict[str, EmotionModalitySummary] = Field(default_factory=dict)
    fusion: str = "late_weighted"
    smoothed: bool = False


class EmotionIngestRequest(BaseModel):
    """边缘/采集端上报到 /api/emotion/ingest 的三模态推理结果（不含原始音视频）。"""

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1, max_length=80)
    device_id: str | None = Field(default=None, max_length=80)
    zone: str | None = Field(default=None, max_length=80)
    language: EmotionLanguage | None = None
    # 视觉/语音：v0 由边缘/调用方给出分布（infer_face/infer_voice 为可插拔桩，待接真实 FER/SER）。
    face: EmotionModalityInput | None = None
    voice: EmotionModalityInput | None = None
    # 文本：传原文转写，服务器 infer_text 真推理（语言相关模态）；原文不入库，只留情绪结果。
    transcript: str | None = Field(default=None, max_length=2000)
    record_event: bool = True


class EmotionIngestResponse(BaseModel):
    state: EmotionState
    event_recorded: bool = False
    event_id: str | None = None
    detail: str | None = None


class CompanionReplyRequest(BaseModel):
    """请求情感陪伴共情回应。情绪默认取空间最近状态，也可显式覆盖。"""

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1, max_length=80)
    message: str | None = Field(default=None, max_length=2000)
    primary_emotion: EmotionLabel | None = None
    language: EmotionLanguage | None = None
    stream: bool = False


class CompanionReplyResponse(BaseModel):
    reply: str
    primary_emotion: EmotionLabel
    language: EmotionLanguage
    tone: str
    gesture: str
    model_used: bool
    model_status: str


class CompanionVisionCaptureRequest(BaseModel):
    space_id: str = Field(min_length=1, max_length=80)
    zone: str | None = Field(default=None, max_length=40)


class DeviceCompanionVoiceRequest(BaseModel):
    """机器人侧语音输入（Step 3）：识别出的文本送来生成陪伴回复，由机器人本机朗读，不经 MQTT 广播。"""

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    language: str | None = Field(default=None, max_length=8)


class CompanionVoiceSetting(BaseModel):
    """陪伴朗读音色设置（服务端火山 TTS 的 voice_type）。"""

    voice: str = Field(default="zh_female_vv_uranus_bigtts", max_length=80)


class CompanionVoiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice: str = Field(min_length=1, max_length=80)


class DeviceTtsRequest(BaseModel):
    """机器人请求把一段文本合成为语音（设备令牌鉴权，返回流式 MP3）。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=600)
    voice: str | None = Field(default=None, max_length=80)


class CompanionGestureRequest(BaseModel):
    """请求执行一个情绪驱动的原地手势（经策略门控）。"""

    model_config = ConfigDict(extra="forbid")

    gesture: str = Field(min_length=1, max_length=40)
    device_id: str = Field(default="yanshee_robot_01", max_length=80)
    intent: str | None = Field(default=None, max_length=400)
    confirmed: bool = True


class CompanionGestureResponse(BaseModel):
    gesture: str
    allowed: bool
    executed: bool
    reason: str
    audit_log_id: str


CompanionArchetype = Literal["gentle_healing", "lively_playful", "quiet_companion"]


class CompanionPersona(BaseModel):
    """情感陪伴角色设定（注入共情提示）。默认温柔治愈型「小暖」（§7 决策）。

    id 是稳定的角色身份（记忆按它分；角色↔躯体解耦，记忆跟角色走，不跟机器人走）。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="xiaonuan", min_length=1, max_length=40)
    name: str = Field(default="小暖", min_length=1, max_length=40)
    archetype: CompanionArchetype = "gentle_healing"
    companion_for: str = Field(default="", max_length=80)
    notes: str | None = Field(default=None, max_length=240)
    active: bool = True


class CompanionPersonaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=40)
    archetype: CompanionArchetype | None = None
    companion_for: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=240)


class CompanionCharacterCreate(BaseModel):
    """新建一个陪伴角色（多角色）。id 不传则服务端生成。"""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=40)
    archetype: CompanionArchetype = "gentle_healing"
    companion_for: str = Field(default="", max_length=80)
    notes: str | None = Field(default=None, max_length=240)


# ── 长期记忆（plan companion-v2 §2）────────────────────────────────────
class MemoryEpisode(BaseModel):
    """情节记忆：按事件 + 时间的一条显著互动。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"ep_{uuid4().hex[:12]}")
    character_id: str = Field(min_length=1, max_length=40)
    subject_id: str = Field(default="user_default", max_length=64)
    created_at: datetime
    summary: str = Field(min_length=1, max_length=300)
    emotion: EmotionLabel | None = None
    valence: float = Field(default=0.0, ge=-1, le=1)
    salience: float = Field(default=0.5, ge=0, le=1)
    topics: list[str] = Field(default_factory=list, max_length=12)


class UserProfile(BaseModel):
    """画像记忆：关于用户的稳定事实（按事实），让陪伴"懂你"。"""

    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(min_length=1, max_length=40)
    subject_id: str = Field(default="user_default", max_length=64)
    display_name: str | None = Field(default=None, max_length=40)
    preferences: list[str] = Field(default_factory=list, max_length=40)
    important_people: list[str] = Field(default_factory=list, max_length=40)
    notes: list[str] = Field(default_factory=list, max_length=40)
    updated_at: datetime


class MemorySnapshot(BaseModel):
    profile: UserProfile | None = None
    episodes: list[MemoryEpisode] = Field(default_factory=list)


class MemoryClearResponse(BaseModel):
    character_id: str
    cleared_episodes: int
    cleared_profile: bool
    audit_log_id: str


class MediaAsset(BaseModel):
    id: str = Field(default_factory=lambda: f"media_{uuid4().hex[:12]}")
    device_id: str
    space_id: str
    zone: str | None = None
    media_type: Literal["image", "video"]
    content_type: Literal["image/jpeg", "image/png", "video/mp4"]
    file_name: str
    file_size_bytes: int = Field(ge=0)
    sha256: str
    storage_path: str
    content_url: str
    event_id: str | None = None
    captured_at: datetime
    received_at: datetime
    retention_policy: Literal["event_media", "metadata_only"]
    retention_days: int = Field(ge=1, le=30)
    privacy_level: Literal["space_local_only", "metadata_only"] = "space_local_only"
    analysis_status: Literal["not_requested", "edge_completed", "pending", "failed"] = "not_requested"


class MediaAssetUploadResponse(BaseModel):
    asset: MediaAsset
    audit_log_id: str


class MediaAssetDeleteResponse(BaseModel):
    deleted: bool
    media_id: str
    audit_log_id: str


class StreamSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=80)
    space_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    rtsp_url: str = Field(min_length=1, max_length=500)
    stream_key: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=80)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=240)


class StreamSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    rtsp_url: str | None = Field(default=None, min_length=1, max_length=500)
    stream_key: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    status: Literal["configured", "online", "offline", "error"] | None = None
    notes: str | None = Field(default=None, max_length=240)


class StreamSource(BaseModel):
    id: str = Field(default_factory=lambda: f"stream_{uuid4().hex[:12]}")
    device_id: str
    space_id: str
    name: str
    rtsp_url: str
    hls_url: str
    stream_key: str
    zone: str | None = None
    enabled: bool = True
    status: Literal["configured", "online", "offline", "error"] = "configured"
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class StreamSourceMutationResponse(BaseModel):
    stream: StreamSource
    audit_log_id: str


class StreamSourceDeleteResponse(BaseModel):
    deleted: bool
    stream_id: str
    audit_log_id: str


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
    status: Literal["triggered", "not_matched", "disabled", "unsupported", "blocked"]
    reason: str
    evaluated_at: datetime
    observed: dict[str, Any] = Field(default_factory=dict)
    audit_log_id: str | None = None


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: f"tool_{uuid4().hex[:10]}")
    name: str
    parameters: dict[str, Any]
    result: dict[str, Any]
    policy: PolicyDecision | None = None
    created_at: datetime


class AgentModelUsage(BaseModel):
    provider_id: str | None = None
    provider_label: str | None = None
    model: str | None = None
    protocol: str | None = None
    status: Literal["not_configured", "used", "fallback", "blocked"]
    used: bool
    reason: str


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


class ResearchEvaluationMetric(BaseModel):
    id: str
    label: str
    value: float
    unit: Literal["rate", "count"]
    status: Literal["pass", "watch", "fail", "missing"]
    description: str


class ResearchEvaluationCase(BaseModel):
    id: str
    name: str
    category: Literal["safety", "tool", "multi_turn", "policy"]
    status: Literal["passed", "failed"]
    message: str
    tool_names: list[str] = Field(default_factory=list)
    policy_result: str | None = None
    risk_level: str | None = None
    model_status: str | None = None
    failure: str | None = None


class CompanionSafetyEvaluationReport(BaseModel):
    generated_at: datetime
    source: Literal["report_file", "fallback"]
    total_cases: int
    passed_cases: int
    failed_cases: int
    misoperation_rate: float
    unauthorized_call_rate: float
    tool_success_rate: float
    multi_turn_consistency_rate: float
    metrics: list[ResearchEvaluationMetric]
    cases: list[ResearchEvaluationCase]
    summary: str
