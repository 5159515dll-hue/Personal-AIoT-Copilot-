import type { TelemetrySource } from "./types";

export function normalizeTelemetrySource(value: string | string[] | undefined): TelemetrySource {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "database" ? "database" : "mock";
}

export function telemetrySourceLabel(source: TelemetrySource): string {
  return source === "database" ? "数据库遥测" : "模拟数据";
}
