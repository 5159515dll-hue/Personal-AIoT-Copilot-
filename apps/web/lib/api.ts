import type {
  AgentDataSource,
  AgentChatResponse,
  AgentConversationDeleteResponse,
  AgentConversationEntry,
  AgentSafetyEvaluationReport,
  AnomalyEvent,
  AuditLog,
  AuditLogQuery,
  AutomationRule,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  ControlDeviceResponse,
  Device,
  DeviceBatchManagementItem,
  DeviceBatchManagementResponse,
  DeviceManagementCreate,
  DeviceManagementDeleteResponse,
  DeviceManagementResponse,
  DeviceManagementUpdate,
  ManagedDevice,
  MetricName,
  ModelConfigRequest,
  ModelConnectionTestResponse,
  ModelKeyImportRequest,
  ModelProviderCatalog,
  ModelSelectionRequest,
  PublicModelConfig,
  RuleEvaluation,
  RoomState,
  SensorHealth,
  SensorReading,
  TelemetryStatus,
  TelemetrySource
} from "./types";

function configured(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed.replace(/\/$/, "") : null;
}

function apiBaseUrl(): string {
  const publicBaseUrl = configured(process.env.NEXT_PUBLIC_API_BASE_URL);
  if (typeof window !== "undefined") {
    // Browser requests stay same-origin and are forwarded by the Next.js API proxy.
    // This avoids production pages trying to fetch the viewer's own 127.0.0.1.
    return "";
  }
  return configured(process.env.API_BASE_URL) ?? publicBaseUrl ?? "http://localhost:8000";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const internalToken = process.env.AIOT_INTERNAL_API_TOKEN;
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(internalToken ? { "X-AIoT-Internal-Token": internalToken } : {}),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(errorMessageFromBody(body) || `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

function errorMessageFromBody(body: string): string {
  if (!body) {
    return "";
  }
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    if (parsed.detail && typeof parsed.detail === "object" && "message" in parsed.detail) {
      const message = (parsed.detail as { message?: unknown }).message;
      return typeof message === "string" ? message : body;
    }
  } catch {
    return body;
  }
  return body;
}

export async function getRoomState(source: TelemetrySource = "mock"): Promise<RoomState> {
  const params = source === "database" ? "?source=database" : "";
  return request<RoomState>(`/api/room/current${params}`);
}

export async function getAnomalyEvents(source: TelemetrySource = "mock", window = "24h"): Promise<AnomalyEvent[]> {
  const params = new URLSearchParams({ source, window });
  return request<AnomalyEvent[]>(`/api/anomalies?${params.toString()}`);
}

export async function getSensorHistory(
  metric: MetricName,
  bucket = "15m",
  days?: number,
  source: TelemetrySource = "mock"
): Promise<SensorReading[]> {
  const params = new URLSearchParams({ metric, bucket });
  if (source === "database") {
    params.set("source", "database");
  }
  const windowDays = days ?? (source === "database" ? 1 : undefined);
  if (windowDays) {
    const from = new Date(Date.now() - windowDays * 24 * 60 * 60 * 1000).toISOString();
    params.set("from", from);
  }
  return request<SensorReading[]>(`/api/sensors/history?${params.toString()}`);
}

export async function getSensorHealth(source: TelemetrySource = "mock"): Promise<SensorHealth[]> {
  const params = source === "database" ? "?source=database" : "";
  return request<SensorHealth[]>(`/api/sensors/health${params}`);
}

export async function getTelemetryStatus(): Promise<TelemetryStatus> {
  return request<TelemetryStatus>("/api/telemetry/status");
}

export async function getDevices(): Promise<Device[]> {
  return request<Device[]>("/api/devices");
}

export async function getManagedDevices(): Promise<ManagedDevice[]> {
  return request<ManagedDevice[]>("/api/devices/management");
}

export async function createDeviceManagement(payload: DeviceManagementCreate): Promise<DeviceManagementResponse> {
  return request<DeviceManagementResponse>("/api/devices/management", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateDeviceManagement(
  id: string,
  payload: DeviceManagementUpdate
): Promise<DeviceManagementResponse> {
  return request<DeviceManagementResponse>(`/api/devices/${id}/management`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteDeviceManagement(id: string): Promise<DeviceManagementDeleteResponse> {
  return request<DeviceManagementDeleteResponse>(`/api/devices/${id}/management`, {
    method: "DELETE"
  });
}

export async function markDeviceOffline(id: string, reason: string): Promise<DeviceManagementResponse> {
  return request<DeviceManagementResponse>(`/api/devices/${id}/offline`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export async function batchUpdateDeviceManagement(
  items: DeviceBatchManagementItem[]
): Promise<DeviceBatchManagementResponse> {
  return request<DeviceBatchManagementResponse>("/api/devices/batch-management", {
    method: "POST",
    body: JSON.stringify({ items })
  });
}

export async function controlDevice(
  id: string,
  state: "on" | "off",
  confirmed = false
): Promise<ControlDeviceResponse> {
  return request<ControlDeviceResponse>(`/api/devices/${id}/control`, {
    method: "POST",
    body: JSON.stringify({ state, confirmed, reason: "dashboard mock control" })
  });
}

export async function getRules(): Promise<AutomationRule[]> {
  return request<AutomationRule[]>("/api/rules");
}

export async function createRule(payload: AutomationRuleCreate): Promise<AutomationRule> {
  return request<AutomationRule>("/api/rules", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateRule(id: string, payload: AutomationRuleUpdate): Promise<AutomationRule> {
  return request<AutomationRule>(`/api/rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function evaluateRules(source: TelemetrySource = "mock"): Promise<RuleEvaluation[]> {
  const params = source === "database" ? "?source=database" : "";
  return request<RuleEvaluation[]>(`/api/rules/evaluate${params}`, {
    method: "POST"
  });
}

export async function chat(message: string, sessionId?: string, dataSource: AgentDataSource = "mock"): Promise<AgentChatResponse> {
  return request<AgentChatResponse>("/api/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId, data_source: dataSource })
  });
}

export async function getAgentHistory(limit = 12, sessionId?: string): Promise<AgentConversationEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  return request<AgentConversationEntry[]>(`/api/agent/history?${params.toString()}`);
}

export async function deleteAgentHistoryEntry(id: string): Promise<AgentConversationDeleteResponse> {
  return request<AgentConversationDeleteResponse>(`/api/agent/history/${id}`, {
    method: "DELETE"
  });
}

export async function getAuditLogs(query: AuditLogQuery = {}): Promise<AuditLog[]> {
  const params = new URLSearchParams();
  if (query.limit) {
    params.set("limit", String(query.limit));
  }
  if (query.actor) {
    params.set("actor", query.actor);
  }
  if (query.action) {
    params.set("action", query.action);
  }
  if (query.result) {
    params.set("result", query.result);
  }
  if (query.policy_result) {
    params.set("policy_result", query.policy_result);
  }
  if (query.risk_level) {
    params.set("risk_level", query.risk_level);
  }
  const keyword = query.q?.trim();
  if (keyword) {
    params.set("q", keyword);
  }
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<AuditLog[]>(`/api/audit-logs${suffix}`);
}

export async function getModelProviderCatalog(): Promise<ModelProviderCatalog> {
  return request<ModelProviderCatalog>("/api/model-providers");
}

export async function saveModelConfig(payload: ModelConfigRequest): Promise<PublicModelConfig> {
  return request<PublicModelConfig>("/api/model-providers/active", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function importModelProviderKey(payload: ModelKeyImportRequest): Promise<PublicModelConfig> {
  return request<PublicModelConfig>("/api/model-providers/keys", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function switchActiveModel(payload: ModelSelectionRequest): Promise<PublicModelConfig> {
  return request<PublicModelConfig>("/api/model-providers/selection", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function testModelConnection(payload: ModelConfigRequest): Promise<ModelConnectionTestResponse> {
  return request<ModelConnectionTestResponse>("/api/model-providers/test", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getAgentSafetyEvaluation(): Promise<AgentSafetyEvaluationReport> {
  return request<AgentSafetyEvaluationReport>("/api/evaluations/agent-safety");
}
