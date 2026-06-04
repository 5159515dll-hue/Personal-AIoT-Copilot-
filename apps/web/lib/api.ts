import type {
  AgentDataSource,
  AgentChatResponse,
  AuditLog,
  AutomationRule,
  AutomationRuleCreate,
  ControlDeviceResponse,
  Device,
  MetricName,
  ModelConfigRequest,
  ModelConnectionTestResponse,
  ModelProviderCatalog,
  RuleEvaluation,
  RoomState,
  SensorReading,
  TelemetrySource
} from "./types";

function configured(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed.replace(/\/$/, "") : null;
}

function apiBaseUrl(): string {
  const publicBaseUrl = configured(process.env.NEXT_PUBLIC_API_BASE_URL);
  if (typeof window !== "undefined") {
    if (publicBaseUrl) {
      return publicBaseUrl;
    }
    if (window.location.hostname === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }
    if (window.location.hostname === "localhost") {
      return "http://localhost:8000";
    }
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

export async function getDevices(): Promise<Device[]> {
  return request<Device[]>("/api/devices");
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

export async function evaluateRules(): Promise<RuleEvaluation[]> {
  return request<RuleEvaluation[]>("/api/rules/evaluate", {
    method: "POST"
  });
}

export async function chat(message: string, sessionId?: string, dataSource: AgentDataSource = "mock"): Promise<AgentChatResponse> {
  return request<AgentChatResponse>("/api/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId, data_source: dataSource })
  });
}

export async function getAuditLogs(): Promise<AuditLog[]> {
  return request<AuditLog[]>("/api/audit-logs");
}

export async function getModelProviderCatalog(): Promise<ModelProviderCatalog> {
  return request<ModelProviderCatalog>("/api/model-providers");
}

export async function saveModelConfig(payload: ModelConfigRequest): Promise<ModelProviderCatalog["active_config"]> {
  return request<ModelProviderCatalog["active_config"]>("/api/model-providers/active", {
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
