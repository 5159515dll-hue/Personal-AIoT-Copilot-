import type {
  CompanionSafetyEvaluationReport,
  AnomalyEvent,
  NodeSummary,
  AuditLog,
  AuditLogQuery,
  AutomationRule,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  ControlDeviceResponse,
  Device,
  DeviceBatchManagementItem,
  DeviceBatchManagementResponse,
  DeviceCredentialIssueResponse,
  DeviceCredentialPublic,
  DeviceEvent,
  DeviceManagementCreate,
  DeviceManagementDeleteResponse,
  DeviceManagementResponse,
  DeviceManagementUpdate,
  MediaAsset,
  ManagedDevice,
  MetricName,
  ModelConfigRequest,
  ModelConnectionTestResponse,
  ModelKeyImportRequest,
  ModelProviderCatalog,
  ModelSelectionRequest,
  PublicModelConfig,
  RuleEvaluation,
  RoomSpace,
  RoomSpaceCreate,
  RoomSpaceDeleteResponse,
  RoomSpaceMutationResponse,
  RoomSpaceUpdate,
  RoomState,
  SensorHealth,
  SensorReading,
  StreamSource,
  StreamSourceCreate,
  StreamSourceDeleteResponse,
  StreamSourceMutationResponse,
  StreamSourceUpdate,
  TelemetryStatus,
  TelemetrySource,
  CompanionPersona,
  CompanionPersonaUpdate,
  CompanionCharacterCreate,
  CompanionReplyResponse,
  MemorySnapshot,
  MemoryClearResponse,
  EmotionLabel,
  EmotionLanguage,
  EmotionState
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

export async function getSpaces(): Promise<RoomSpace[]> {
  return request<RoomSpace[]>("/api/spaces");
}

export async function getCurrentSpace(): Promise<RoomSpace> {
  return request<RoomSpace>("/api/spaces/current");
}

export async function createSpace(payload: RoomSpaceCreate): Promise<RoomSpaceMutationResponse> {
  return request<RoomSpaceMutationResponse>("/api/spaces", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateSpace(id: string, payload: RoomSpaceUpdate): Promise<RoomSpaceMutationResponse> {
  return request<RoomSpaceMutationResponse>(`/api/spaces/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function activateSpace(id: string): Promise<RoomSpaceMutationResponse> {
  return request<RoomSpaceMutationResponse>(`/api/spaces/${id}/activate`, {
    method: "POST"
  });
}

export async function deleteSpace(id: string): Promise<RoomSpaceDeleteResponse> {
  return request<RoomSpaceDeleteResponse>(`/api/spaces/${id}`, {
    method: "DELETE"
  });
}

export async function getDevices(): Promise<Device[]> {
  return request<Device[]>("/api/devices");
}

export async function getManagedDevices(): Promise<ManagedDevice[]> {
  return request<ManagedDevice[]>("/api/devices/management");
}

export async function getNodes(): Promise<NodeSummary[]> {
  return request<NodeSummary[]>("/api/nodes");
}

export async function captureCompanionPhoto(spaceId: string, zone?: string): Promise<{ requested: boolean }> {
  return request<{ requested: boolean }>("/api/companion/vision/capture", {
    method: "POST",
    body: JSON.stringify({ space_id: spaceId, zone: zone || null })
  });
}

export async function startCompanionLive(spaceId: string): Promise<{ requested: boolean }> {
  return request<{ requested: boolean }>("/api/companion/vision/live/start", {
    method: "POST",
    body: JSON.stringify({ space_id: spaceId })
  });
}

export async function stopCompanionLive(spaceId: string): Promise<{ requested: boolean }> {
  return request<{ requested: boolean }>("/api/companion/vision/live/stop", {
    method: "POST",
    body: JSON.stringify({ space_id: spaceId })
  });
}

// 直播单帧快照（轮询兜底/缩略），不走 request()。
export function companionLiveFrameUrl(spaceId: string): string {
  return `/api/companion/vision/live/frame?space_id=${encodeURIComponent(spaceId)}`;
}

// 实时画面：浏览器 <img> 直连的 MJPEG 流（multipart/x-mixed-replace），满帧率、单连接。
export function companionLiveStreamUrl(spaceId: string): string {
  return `/api/companion/vision/live/stream?space_id=${encodeURIComponent(spaceId)}`;
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

export async function getDeviceCredentials(): Promise<DeviceCredentialPublic[]> {
  return request<DeviceCredentialPublic[]>("/api/devices/credentials");
}

export async function issueDeviceCredential(id: string): Promise<DeviceCredentialIssueResponse> {
  return request<DeviceCredentialIssueResponse>(`/api/devices/${id}/credentials`, {
    method: "POST"
  });
}

export async function getDeviceEvents(params?: {
  device_id?: string;
  space_id?: string;
  event_type?: string;
  limit?: number;
}): Promise<DeviceEvent[]> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.space_id) query.set("space_id", params.space_id);
  if (params?.event_type) query.set("event_type", params.event_type);
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<DeviceEvent[]>(`/api/device-events${suffix}`);
}

export async function getMediaAssets(params?: {
  device_id?: string;
  space_id?: string;
  media_type?: string;
  limit?: number;
}): Promise<MediaAsset[]> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.space_id) query.set("space_id", params.space_id);
  if (params?.media_type) query.set("media_type", params.media_type);
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<MediaAsset[]>(`/api/media-assets${suffix}`);
}

export async function deleteMediaAsset(id: string): Promise<{ deleted: boolean; media_id: string; audit_log_id: string }> {
  return request<{ deleted: boolean; media_id: string; audit_log_id: string }>(`/api/media-assets/${id}`, {
    method: "DELETE"
  });
}

export async function getStreams(params?: { space_id?: string; device_id?: string }): Promise<StreamSource[]> {
  const query = new URLSearchParams();
  if (params?.space_id) query.set("space_id", params.space_id);
  if (params?.device_id) query.set("device_id", params.device_id);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<StreamSource[]>(`/api/streams${suffix}`);
}

export async function createStream(payload: StreamSourceCreate): Promise<StreamSourceMutationResponse> {
  return request<StreamSourceMutationResponse>("/api/streams", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateStream(id: string, payload: StreamSourceUpdate): Promise<StreamSourceMutationResponse> {
  return request<StreamSourceMutationResponse>(`/api/streams/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteStream(id: string): Promise<StreamSourceDeleteResponse> {
  return request<StreamSourceDeleteResponse>(`/api/streams/${id}`, {
    method: "DELETE"
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

export async function getCompanionSafetyEvaluation(): Promise<CompanionSafetyEvaluationReport> {
  return request<CompanionSafetyEvaluationReport>("/api/evaluations/companion-safety");
}

export async function getEmotionState(spaceId: string): Promise<EmotionState | null> {
  try {
    return await request<EmotionState>(`/api/emotion/state?space_id=${encodeURIComponent(spaceId)}`);
  } catch {
    // 404 = 该空间暂无情绪状态
    return null;
  }
}

export async function postCompanionReply(body: {
  space_id: string;
  message?: string;
  primary_emotion?: EmotionLabel;
  language?: EmotionLanguage;
}): Promise<CompanionReplyResponse> {
  return request<CompanionReplyResponse>("/api/companion/reply", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export async function getCompanionPersona(): Promise<CompanionPersona> {
  return request<CompanionPersona>("/api/companion/persona");
}

export async function postCompanionPersona(body: CompanionPersonaUpdate): Promise<CompanionPersona> {
  return request<CompanionPersona>("/api/companion/persona", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export async function getCompanionMemory(): Promise<MemorySnapshot> {
  return request<MemorySnapshot>("/api/companion/memory");
}

export async function clearCompanionMemory(): Promise<MemoryClearResponse> {
  return request<MemoryClearResponse>("/api/companion/memory", { method: "DELETE" });
}

export async function listCompanionCharacters(): Promise<CompanionPersona[]> {
  return request<CompanionPersona[]>("/api/companion/characters");
}

export async function createCompanionCharacter(body: CompanionCharacterCreate): Promise<CompanionPersona> {
  return request<CompanionPersona>("/api/companion/characters", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export async function updateCompanionCharacter(id: string, body: CompanionPersonaUpdate): Promise<CompanionPersona> {
  return request<CompanionPersona>(`/api/companion/characters/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
}

export async function activateCompanionCharacter(id: string): Promise<CompanionPersona> {
  return request<CompanionPersona>(`/api/companion/characters/${id}/activate`, { method: "POST" });
}

export async function deleteCompanionCharacter(id: string): Promise<CompanionPersona> {
  return request<CompanionPersona>(`/api/companion/characters/${id}`, { method: "DELETE" });
}
