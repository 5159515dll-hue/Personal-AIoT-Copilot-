import type { TelemetrySource } from "./types";

export function normalizeTelemetrySource(value: string | string[] | undefined): TelemetrySource {
  const raw = Array.isArray(value) ? value[0] : value;
  // Real (database) is the default now; mock is explicit opt-in (labeled demo mode).
  return raw === "mock" ? "mock" : "database";
}

export function telemetrySourceLabel(source: TelemetrySource): string {
  return source === "database" ? "数据库遥测" : "模拟数据";
}
