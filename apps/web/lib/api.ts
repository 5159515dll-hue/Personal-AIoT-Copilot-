import type {
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
  RoomState,
  SensorReading
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getRoomState(): Promise<RoomState> {
  return request<RoomState>("/api/room/current");
}

export async function getSensorHistory(
  metric: MetricName,
  bucket = "15m",
  days?: number
): Promise<SensorReading[]> {
  const params = new URLSearchParams({ metric, bucket });
  if (days) {
    const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
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

export async function chat(message: string, sessionId?: string): Promise<AgentChatResponse> {
  return request<AgentChatResponse>("/api/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId })
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
