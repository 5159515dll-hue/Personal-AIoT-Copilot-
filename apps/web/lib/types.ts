export type MetricName = "temperature" | "humidity" | "co2" | "light" | "presence" | "noise";

export type SensorReading = {
  metric: MetricName;
  value: number;
  unit: string;
  timestamp: string;
  device_id: string;
  quality: "ok" | "stale" | "anomaly";
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
  status: "ok" | "empty" | "unavailable";
  message: string;
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
  status: "triggered" | "not_matched" | "disabled" | "unsupported";
  reason: string;
  evaluated_at: string;
  observed: Record<string, unknown>;
  audit_log_id: string | null;
};

export type ToolCall = {
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  result: Record<string, unknown>;
  policy: PolicyDecision | null;
  created_at: string;
};

export type AgentChatResponse = {
  session_id: string;
  message: {
    role: "user" | "assistant";
    content: string;
    created_at: string;
  };
  used_data: string[];
  tool_calls: ToolCall[];
  needs_confirmation: boolean;
  model_usage: {
    provider_id: string | null;
    provider_label: string | null;
    model: string | null;
    protocol: string | null;
    status: "not_configured" | "used" | "fallback" | "blocked";
    used: boolean;
    reason: string;
  };
  policy: PolicyDecision | null;
  rule_draft: AutomationRuleCreate | null;
};

export type TelemetrySource = "mock" | "database";
export type AgentDataSource = TelemetrySource;

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

export type ProviderProtocol = "openai" | "anthropic";

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
