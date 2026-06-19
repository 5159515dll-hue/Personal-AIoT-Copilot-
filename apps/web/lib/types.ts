export type MetricName = "temperature" | "humidity" | "co2" | "light" | "presence" | "noise";

export type SensorReading = {
  metric: MetricName;
  value: number;
  unit: string;
  timestamp: string;
  device_id: string;
  quality: "ok" | "stale" | "anomaly";
};

export type SensorHealth = {
  metric: MetricName;
  status: "ok" | "stale" | "anomaly" | "offline" | "unavailable";
  source: TelemetrySource;
  device_id: string | null;
  last_seen_at: string | null;
  age_minutes: number | null;
  quality: SensorReading["quality"] | null;
  value: number | null;
  unit: string | null;
  message: string;
};

export type RoomState = {
  timestamp: string;
  health_score: number;
  status: "good" | "watch" | "poor";
  summary: string;
  metrics: Record<MetricName, SensorReading>;
  anomalies: string[];
  recommendation: string;
};

export type AnomalyEvent = {
  id: string;
  timestamp: string;
  source: TelemetrySource;
  severity: "info" | "warning" | "critical";
  category: "environment" | "sensor_health";
  metric: MetricName | null;
  title: string;
  detail: string;
  recommendation: string;
  status: "active" | "observed" | "resolved";
  evidence: Record<string, unknown>;
};

export type TelemetryStatus = {
  source: "database";
  configured: boolean;
  connected: boolean;
  sensor_table_exists: boolean;
  timescale_available: boolean;
  timescale_enabled: boolean;
  hypertable: boolean;
  total_readings: number;
  device_count: number;
  metric_count: number;
  latest_reading_at: string | null;
  latest_received_at: string | null;
  latest_metrics: Partial<Record<MetricName, SensorReading>>;
  sources: TelemetrySourceSummary[];
  devices: TelemetryDeviceSummary[];
  status: "ok" | "empty" | "unavailable";
  message: string;
};

export type SpaceCapabilityStatus = "disabled" | "planned" | "local_only";

export type SpacePerceptionSettings = {
  camera: SpaceCapabilityStatus;
  face_recognition: SpaceCapabilityStatus;
  emotion_recognition: SpaceCapabilityStatus;
  location_tracking: SpaceCapabilityStatus;
  image_retention: "none" | "metadata_only" | "event_media";
  privacy_mode: "strict" | "local_only";
  media_policy: {
    allow_realtime_stream: boolean;
    allow_event_media: boolean;
    media_retention_days: number;
    event_retention_days: number;
  };
  notes: string | null;
};

export type RoomSpace = {
  id: string;
  name: string;
  space_type: "study" | "bedroom" | "living_room" | "lab" | "balcony" | "kitchen" | "other";
  location_label: string;
  floor: string | null;
  timezone: string;
  is_active: boolean;
  device_ids: string[];
  zones: string[];
  perception: SpacePerceptionSettings;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type RoomSpaceCreate = {
  id?: string | null;
  name: string;
  space_type: RoomSpace["space_type"];
  location_label: string;
  floor?: string | null;
  timezone: string;
  device_ids: string[];
  zones: string[];
  perception: SpacePerceptionSettings;
  notes?: string | null;
};

export type RoomSpaceUpdate = Partial<Omit<RoomSpaceCreate, "id">>;

export type RoomSpaceMutationResponse = {
  space: RoomSpace;
  audit_log_id: string;
};

export type RoomSpaceDeleteResponse = {
  deleted: boolean;
  space_id: string;
  audit_log_id: string;
};

export type TelemetrySourceSummary = {
  source: string;
  total_readings: number;
  device_count: number;
  latest_reading_at: string | null;
  latest_received_at: string | null;
};

export type TelemetryDeviceSummary = {
  device_id: string;
  total_readings: number;
  metric_count: number;
  latest_reading_at: string | null;
  latest_received_at: string | null;
};

export type Device = {
  id: string;
  name: string;
  type: string;
  location: string;
  risk_level: "read_only" | "low" | "medium" | "high" | "forbidden";
  controllable: boolean;
  requires_confirmation: boolean;
  online_state: "online" | "offline" | "unknown";
  current_state: Record<string, unknown>;
  connected_appliance?: string | null;
  max_active_duration_minutes?: number | null;
};

export type DeviceConnectionRecord = {
  device_id: string;
  display_name: string;
  device_type: string;
  transport: string;
  protocol_version: string;
  firmware_version: string | null;
  hardware_revision: string | null;
  location: string;
  capabilities: {
    kind: "telemetry" | "control" | "gateway" | "diagnostic" | "media" | "vision" | "stream";
    metrics: MetricName[];
    description: string | null;
  }[];
  metadata: Record<string, unknown>;
  online_state: Device["online_state"];
  last_seen_at: string | null;
  last_message_id: string | null;
  last_sequence: number | null;
  updated_at: string;
};

export type ManagedDevice = {
  device: Device;
  connection: DeviceConnectionRecord | null;
  binding_status: "bound" | "registry_only" | "connection_only";
  load_mark: Record<string, unknown>;
  management_flags: string[];
};

export type DeviceManagementUpdate = {
  name?: string | null;
  display_name?: string | null;
  device_type?: string | null;
  transport?: "mqtt" | "http" | "serial_gateway" | "edge_gateway" | null;
  firmware_version?: string | null;
  hardware_revision?: string | null;
  location?: string | null;
  risk_level?: Device["risk_level"] | null;
  controllable?: boolean | null;
  requires_confirmation?: boolean | null;
  connected_appliance?: string | null;
  max_active_duration_minutes?: number | null;
  load_type?: string | null;
  load_label?: string | null;
  load_power_watts?: number | null;
  management_note?: string | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
};

export type DeviceManagementCreate = DeviceManagementUpdate & {
  device_id: string;
  name: string;
  device_type: string;
  transport: "mqtt" | "http" | "serial_gateway" | "edge_gateway";
  protocol_version: string;
  location: string;
  risk_level: Device["risk_level"];
  controllable: boolean;
  requires_confirmation: boolean;
};

export type DeviceOfflineRequest = {
  reason: string;
};

export type DeviceManagementResponse = {
  item: ManagedDevice;
  audit_log_id: string;
};

export type DeviceManagementDeleteResponse = {
  deleted: boolean;
  device_id: string;
  audit_log_id: string;
};

export type DeviceBatchManagementItem = DeviceManagementUpdate & {
  device_id: string;
  offline?: boolean;
  offline_reason?: string | null;
};

export type DeviceBatchManagementResponse = {
  updated: ManagedDevice[];
  failed: { device_id: string; error: string }[];
};

export type DeviceCredentialPublic = {
  device_id: string;
  issued_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  token_preview: string;
};

export type DeviceCredentialIssueResponse = {
  credential: DeviceCredentialPublic;
  token: string;
  audit_log_id: string;
};

export type DeviceEventType =
  | "presence_detected"
  | "motion_detected"
  | "face_detected"
  | "emotion_detected"
  | "location_update"
  | "safety_alert"
  | "custom";

export type DeviceEvent = {
  id: string;
  device_id: string;
  protocol_version: string;
  message_id: string | null;
  sequence: number | null;
  event_type: DeviceEventType;
  severity: "info" | "warning" | "critical";
  confidence: number | null;
  space_id: string;
  zone: string | null;
  captured_at: string;
  received_at: string;
  attributes: Record<string, unknown>;
  media_ids: string[];
};

export type MediaAsset = {
  id: string;
  device_id: string;
  space_id: string;
  zone: string | null;
  media_type: "image" | "video";
  content_type: "image/jpeg" | "image/png" | "video/mp4";
  file_name: string;
  file_size_bytes: number;
  sha256: string;
  storage_path: string;
  content_url: string;
  event_id: string | null;
  captured_at: string;
  received_at: string;
  retention_policy: "event_media" | "metadata_only";
  retention_days: number;
  privacy_level: "space_local_only" | "metadata_only";
  analysis_status: "not_requested" | "edge_completed" | "pending" | "failed";
};

export type StreamSource = {
  id: string;
  device_id: string;
  space_id: string;
  name: string;
  rtsp_url: string;
  hls_url: string;
  stream_key: string;
  zone: string | null;
  enabled: boolean;
  status: "configured" | "online" | "offline" | "error";
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type StreamSourceCreate = {
  device_id: string;
  space_id: string;
  name: string;
  rtsp_url: string;
  stream_key?: string | null;
  zone?: string | null;
  enabled: boolean;
  notes?: string | null;
};

export type StreamSourceUpdate = Partial<Pick<StreamSource, "name" | "rtsp_url" | "stream_key" | "zone" | "enabled" | "status" | "notes">>;

export type StreamSourceMutationResponse = {
  stream: StreamSource;
  audit_log_id: string;
};

export type StreamSourceDeleteResponse = {
  deleted: boolean;
  stream_id: string;
  audit_log_id: string;
};

export type PolicyDecision = {
  result: "allowed" | "requires_confirmation" | "denied";
  risk_level: Device["risk_level"];
  requires_confirmation: boolean;
  reason: string;
  constraints: string[];
};

export type ControlDeviceResponse = {
  policy: PolicyDecision;
  execution_result: "success" | "blocked" | "requires_confirmation" | "failed";
  audit_log_id: string;
  device: Device | null;
};

export type AutomationRule = {
  id: string;
  condition: string;
  action: string;
  enabled: boolean;
  created_by: "user" | "agent";
  created_at: string;
  trigger_count: number;
  last_triggered_at: string | null;
};

export type AutomationRuleCreate = {
  condition: string;
  action: string;
  enabled: boolean;
  confirmed: boolean;
};

export type AutomationRuleUpdate = {
  enabled: boolean;
};

export type RuleEvaluation = {
  rule_id: string;
  condition: string;
  action: string;
  matched: boolean;
  status: "triggered" | "not_matched" | "disabled" | "unsupported" | "blocked";
  reason: string;
  evaluated_at: string;
  observed: Record<string, unknown>;
  audit_log_id: string | null;
};

export type TelemetrySource = "mock" | "database";

export type NodeSensor = {
  metric: string;
  value: number | null;
  unit: string | null;
  quality: "ok" | "stale" | "anomaly" | null;
  last_reading_at: string | null;
  age_seconds: number | null;
  status: "fresh" | "stale" | "silent";
};

export type NodeSummary = {
  device_id: string;
  display_name: string;
  device_type: string;
  transport: string;
  online: boolean;
  online_state: "online" | "offline" | "unknown";
  last_seen_at: string | null;
  age_seconds: number | null;
  firmware_version: string | null;
  location: string | null;
  sensor_count: number;
  reporting_count: number;
  sensors: NodeSensor[];
};

export type AuditLog = {
  id: string;
  timestamp: string;
  actor: "user" | "agent" | "system";
  action: string;
  policy_result: PolicyDecision["result"] | null;
  risk_level: Device["risk_level"] | null;
  parameters: Record<string, unknown>;
  result: string;
  details: string;
};

export type AuditLogQuery = {
  limit?: number;
  actor?: AuditLog["actor"] | "";
  action?: string;
  result?: string;
  policy_result?: AuditLog["policy_result"] | "";
  risk_level?: AuditLog["risk_level"] | "";
  q?: string;
};

export type ProviderProtocol = "openai" | "anthropic";

export type EmotionLabel = "happy" | "sad" | "angry" | "surprise" | "fear" | "disgust" | "neutral";
export type EmotionLanguage = "zh" | "en" | "mn";

export type EmotionModalitySummary = {
  status: "ok" | "unavailable";
  emotion?: EmotionLabel | null;
  confidence?: number;
  transcript_lang?: string | null;
};

export type EmotionState = {
  primary_emotion: EmotionLabel;
  valence: number;
  arousal: number;
  confidence: number;
  language: EmotionLanguage;
  modalities: Record<string, EmotionModalitySummary>;
  fusion: string;
  smoothed: boolean;
};

export type CompanionReplyResponse = {
  reply: string;
  primary_emotion: EmotionLabel;
  language: EmotionLanguage;
  tone: string;
  gesture: string;
  gesture_dispatched?: boolean;
  model_used: boolean;
  model_status: string;
};

export type ChatMessage = {
  id: string;
  character_id: string;
  role: "user" | "assistant";
  text: string;
  source: "browser" | "voice";
  gesture: string | null;
  created_at: string;
};

export type CompanionArchetype = "gentle_healing" | "lively_playful" | "quiet_companion";

export type CompanionPersona = {
  id: string;
  name: string;
  archetype: CompanionArchetype;
  companion_for: string;
  notes: string | null;
  active: boolean;
};

export type CompanionPersonaUpdate = {
  name?: string;
  archetype?: CompanionArchetype;
  companion_for?: string;
  notes?: string | null;
};

export type CompanionCharacterCreate = {
  id?: string;
  name: string;
  archetype?: CompanionArchetype;
  companion_for?: string;
  notes?: string | null;
};

export type MemoryEpisode = {
  id: string;
  character_id: string;
  subject_id: string;
  created_at: string;
  summary: string;
  emotion: EmotionLabel | null;
  valence: number;
  salience: number;
  topics: string[];
};

export type UserProfile = {
  character_id: string;
  subject_id: string;
  display_name: string | null;
  preferences: string[];
  important_people: string[];
  notes: string[];
  updated_at: string;
};

export type MemorySnapshot = {
  profile: UserProfile | null;
  episodes: MemoryEpisode[];
};

export type MemoryClearResponse = {
  character_id: string;
  cleared_episodes: number;
  cleared_profile: boolean;
  audit_log_id: string;
};

export type ProviderEndpoint = {
  id: string;
  label: string;
  protocol: ProviderProtocol;
  base_url: string;
  description: string;
};

export type ModelProviderDefinition = {
  id: string;
  label: string;
  description: string;
  docs_url: string;
  endpoints: ProviderEndpoint[];
  models: string[];
  default_model: string;
};

export type PublicModelConfig = {
  provider_id: string;
  endpoint_id: string;
  protocol: ProviderProtocol;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_preview: string | null;
  updated_at: string | null;
};

export type ModelProviderCatalog = {
  providers: ModelProviderDefinition[];
  active_config: PublicModelConfig | null;
  saved_configs: PublicModelConfig[];
};

export type ModelConfigRequest = {
  provider_id: string;
  endpoint_id: string;
  protocol: ProviderProtocol;
  base_url: string;
  model: string;
  api_key?: string | null;
};

export type ModelKeyImportRequest = {
  provider_id: string;
  endpoint_id: string;
  protocol: ProviderProtocol;
  base_url: string;
  api_key: string;
};

export type ModelSelectionRequest = {
  provider_id: string;
  endpoint_id: string;
  protocol: ProviderProtocol;
  base_url: string;
  model: string;
};

export type ModelConnectionTestResponse = {
  ok: boolean;
  provider_id: string;
  protocol: ProviderProtocol;
  base_url: string;
  model: string;
  message: string;
  status_code: number | null;
};

export type ResearchEvaluationMetric = {
  id: string;
  label: string;
  value: number;
  unit: "rate" | "count";
  status: "pass" | "watch" | "fail" | "missing";
  description: string;
};

export type ResearchEvaluationCase = {
  id: string;
  name: string;
  category: "safety" | "tool" | "multi_turn" | "policy";
  status: "passed" | "failed";
  message: string;
  tool_names: string[];
  policy_result: string | null;
  risk_level: string | null;
  model_status: string | null;
  failure: string | null;
};

export type CompanionSafetyEvaluationReport = {
  generated_at: string;
  source: "report_file" | "fallback";
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  misoperation_rate: number;
  unauthorized_call_rate: number;
  tool_success_rate: number;
  multi_turn_consistency_rate: number;
  metrics: ResearchEvaluationMetric[];
  cases: ResearchEvaluationCase[];
  summary: string;
};
