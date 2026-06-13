import Link from "next/link";
import { AlertTriangle, ArrowRight, Database, FileClock, RadioTower, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { RiskPill } from "@/components/risk-pill";
import { TelemetrySourceSwitch } from "@/components/telemetry-source-switch";
import { TrendChart } from "@/components/trend-chart";
import { getAnomalyEvents, getAuditLogs, getDevices, getRoomState, getSensorHealth, getSensorHistory, getTelemetryStatus } from "@/lib/api";
import { formatDateTime, metricLabel, statusLabel } from "@/lib/format";
import { normalizeTelemetrySource, telemetrySourceLabel } from "@/lib/telemetry-source";
import type { AnomalyEvent, SensorHealth, SensorReading, TelemetryStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

type DashboardPageProps = {
  searchParams?: Promise<{ source?: string | string[] }>;
};

type DataResult<T> = {
  data: T | null;
  error: string | null;
};

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const params = await searchParams;
  const source = normalizeTelemetrySource(params?.source);
  const [roomResult, co2HistoryResult, anomalyResult, sensorHealthResult, telemetryResult, devices, auditLogs] = await Promise.all([
    readData(() => getRoomState(source)),
    readData(() => getSensorHistory("co2", "15m", undefined, source)),
    readData(() => getAnomalyEvents(source)),
    readData(() => getSensorHealth(source)),
    readData(getTelemetryStatus),
    getDevices(),
    getAuditLogs()
  ]);
  const room = roomResult.data;
  const co2History = co2HistoryResult.data ?? [];

  const riskyDevices = devices.filter((device) => ["medium", "high", "forbidden"].includes(device.risk_level));
  const metricReadings = room ? (Object.values(room.metrics).filter(Boolean) as SensorReading[]) : [];

  return (
    <AppShell>
      <PageHeader
        title="空间总览"
        description={`查看当前${telemetrySourceLabel(source)}、情感陪伴、安全状态和最近审计活动。`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <TelemetrySourceSwitch source={source} basePath="/dashboard" />
            <Link
              href="/emotion"
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white"
            >
              情感陪伴
              <ArrowRight size={16} aria-hidden />
            </Link>
          </div>
        }
      />

      {roomResult.error && <DataSourceNotice title="当前状态不可用" detail={roomResult.error} />}

      {metricReadings.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          {metricReadings.map((reading) => (
            <MetricCard key={reading.metric} reading={reading} />
          ))}
        </div>
      ) : !roomResult.error ? (
        <DataSourceNotice
          title="暂无当前指标"
          detail={source === "database" ? "数据库当前没有可展示的最新传感器读数。" : "模拟数据暂不可用。"}
        />
      ) : null}

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">二氧化碳最近 24 小时</h2>
              <p className="mt-1 text-sm text-muted">
                {source === "database" ? "来自 TimescaleDB 的最近 24 小时聚合曲线。" : "异常窗口会在下午和晚间有人时段模拟生成。"}
              </p>
            </div>
            {room && (
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                {statusLabel(room.status)}
              </span>
            )}
          </div>
          {co2HistoryResult.error && <p className="mt-3 text-sm leading-6 text-rose-700">{co2HistoryResult.error}</p>}
          <div className="mt-4">
            <TrendChart readings={co2History} />
          </div>
        </section>

        <aside className="space-y-5">
          <TelemetryStatusCard result={telemetryResult} />
          <SensorHealthCard result={sensorHealthResult} />

          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 text-teal-700" size={20} aria-hidden />
              <div>
                <h2 className="text-base font-semibold">智能体建议</h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {room?.recommendation ?? "当前数据源暂无可生成建议的房间状态。"}
                </p>
                {room && <p className="mt-3 text-xs text-muted">依据：{room.summary}</p>}
              </div>
            </div>
          </section>

          <AnomalyEventsCard result={anomalyResult} source={source} fallbackAnomalies={room?.anomalies ?? []} />
        </aside>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <h2 className="text-base font-semibold">风险清单</h2>
          <div className="mt-4 space-y-3">
            {riskyDevices.map((device) => (
              <div key={device.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 p-3">
                <div>
                  <p className="text-sm font-semibold">{device.name}</p>
                  <p className="text-xs text-muted">{device.connected_appliance ?? device.type}</p>
                </div>
                <RiskPill risk={device.risk_level} />
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <FileClock className="text-teal-700" size={18} aria-hidden />
            <h2 className="text-base font-semibold">最近审计活动</h2>
          </div>
          <div className="mt-4 space-y-3">
            {auditLogs.slice(0, 4).map((log) => (
              <div key={log.id} className="rounded-lg bg-slate-50 p-3">
                <p className="text-sm font-semibold">{log.action} · {statusLabel(log.result)}</p>
                <p className="mt-1 text-xs text-muted">{formatDateTime(log.timestamp)} · {log.details}</p>
              </div>
            ))}
            {auditLogs.length === 0 && <p className="text-sm leading-6 text-muted">暂无审计活动。</p>}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function AnomalyEventsCard({
  result,
  source,
  fallbackAnomalies
}: {
  result: DataResult<AnomalyEvent[]>;
  source: ReturnType<typeof normalizeTelemetrySource>;
  fallbackAnomalies: string[];
}) {
  const events = result.data ?? [];
  const hasEvents = events.length > 0;

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-amber-600" size={18} aria-hidden />
          <h2 className="text-base font-semibold">异常事件</h2>
        </div>
        {hasEvents && <span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">{events.length} 条</span>}
      </div>

      {result.error ? (
        <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm leading-6 text-rose-700">{result.error}</p>
      ) : hasEvents ? (
        <div className="mt-3 space-y-3">
          {events.slice(0, 5).map((event) => (
            <article key={event.id} className={`rounded-lg border p-3 ${anomalySeverityClass(event.severity)}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-white/70 px-2 py-1 text-xs font-semibold">{anomalySeverityLabel(event.severity)}</span>
                <span className="rounded-md bg-white/70 px-2 py-1 text-xs font-semibold">{anomalyStatusLabel(event.status)}</span>
                {event.metric && <span className="rounded-md bg-white/70 px-2 py-1 text-xs font-semibold">{metricLabel(event.metric)}</span>}
              </div>
              <h3 className="mt-2 text-sm font-semibold">{event.title}</h3>
              <p className="mt-1 text-sm leading-6 opacity-85">{event.detail}</p>
              <p className="mt-2 text-xs leading-5 opacity-80">建议：{event.recommendation}</p>
              <p className="mt-2 text-xs opacity-70">{formatDateTime(event.timestamp)} · {anomalyCategoryLabel(event.category)}</p>
            </article>
          ))}
        </div>
      ) : fallbackAnomalies.length ? (
        <div className="mt-3 space-y-2">
          {fallbackAnomalies.map((item) => (
            <p key={item} className="rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-800">
              {item}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-muted">当前{telemetrySourceLabel(source)}没有异常。</p>
      )}
    </section>
  );
}

async function readData<T>(reader: () => Promise<T>): Promise<DataResult<T>> {
  try {
    return { data: await reader(), error: null };
  } catch (error) {
    return { data: null, error: error instanceof Error ? error.message : "数据读取失败。" };
  }
}

function DataSourceNotice({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
      <p className="font-semibold">{title}</p>
      <p className="mt-1">{detail}</p>
    </section>
  );
}

function SensorHealthCard({ result }: { result: DataResult<SensorHealth[]> }) {
  const health = result.data ?? [];
  const unhealthy = health.filter((item) => item.status !== "ok");
  const label = result.error ? "不可用" : unhealthy.length ? "需关注" : health.length ? "正常" : "无数据";
  const badgeClass = result.error
    ? "bg-rose-50 text-rose-700"
    : unhealthy.length
      ? "bg-amber-50 text-amber-700"
      : health.length
        ? "bg-teal-50 text-teal-700"
        : "bg-slate-100 text-slate-700";

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <RadioTower className="mt-0.5 text-teal-700" size={20} aria-hidden />
          <div>
            <h2 className="text-base font-semibold">传感器健康</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              {result.error ?? (unhealthy.length ? `${unhealthy.length} 个指标需要检查。` : "最新传感器读数在健康窗口内。")}
            </p>
          </div>
        </div>
        <span className={`rounded-md px-2 py-1 text-xs font-semibold ${badgeClass}`}>{label}</span>
      </div>

      {health.length > 0 && (
        <div className="mt-4 grid gap-2">
          {health.map((item) => (
            <div key={item.metric} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 p-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{metricLabel(item.metric)}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{item.message}</p>
              </div>
              <span className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold ${sensorHealthClass(item.status)}`}>
                {statusLabel(item.status)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function TelemetryStatusCard({ result }: { result: DataResult<TelemetryStatus> }) {
  const status = result.data;
  const label = status ? telemetryStatusLabel(status.status) : "未知";
  const badgeClass = status ? telemetryStatusClass(status.status) : "bg-slate-100 text-slate-700";

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Database className="mt-0.5 text-teal-700" size={20} aria-hidden />
          <div>
            <h2 className="text-base font-semibold">遥测链路</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              {result.error ?? status?.message ?? "遥测状态暂不可用。"}
            </p>
          </div>
        </div>
        <span className={`rounded-md px-2 py-1 text-xs font-semibold ${badgeClass}`}>{label}</span>
      </div>

      {status && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs font-semibold text-muted">样本数</dt>
              <dd className="mt-1 font-medium text-ink">{status.total_readings}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">设备 / 指标</dt>
              <dd className="mt-1 font-medium text-ink">
                {status.device_count} / {status.metric_count}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-semibold text-muted">最新入库</dt>
              <dd className="mt-1 font-medium text-ink">
                {status.latest_received_at ? formatDateTime(status.latest_received_at) : "暂无"}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-semibold text-muted">Timescale</dt>
              <dd className="mt-1 font-medium text-ink">{timescaleStatusText(status)}</dd>
            </div>
          </dl>

          {status.sources.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-muted">入站来源</p>
              <div className="mt-2 grid gap-2">
                {status.sources.map((item) => (
                  <div key={item.source} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 p-3">
                    <div>
                      <p className="text-sm font-semibold text-ink">{telemetrySourceName(item.source)}</p>
                      <p className="mt-1 text-xs text-muted">{item.device_count} 个设备</p>
                    </div>
                    <p className="shrink-0 text-sm font-semibold text-ink">{item.total_readings} 条</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {status.devices.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-muted">最近设备</p>
              <div className="mt-2 space-y-2">
                {status.devices.slice(0, 3).map((item) => (
                  <div key={item.device_id} className="rounded-lg bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="min-w-0 truncate text-sm font-semibold text-ink">{item.device_id}</p>
                      <p className="shrink-0 text-xs font-semibold text-slate-600">{item.metric_count} 指标</p>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      {item.total_readings} 条 · {item.latest_received_at ? formatDateTime(item.latest_received_at) : "暂无入库时间"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function telemetryStatusLabel(status: TelemetryStatus["status"]): string {
  const labels = {
    ok: "正常",
    empty: "无数据",
    unavailable: "不可用"
  };
  return labels[status];
}

function telemetryStatusClass(status: TelemetryStatus["status"]): string {
  const classes = {
    ok: "bg-teal-50 text-teal-700",
    empty: "bg-amber-50 text-amber-700",
    unavailable: "bg-rose-50 text-rose-700"
  };
  return classes[status];
}

function anomalySeverityLabel(value: AnomalyEvent["severity"]): string {
  const labels: Record<AnomalyEvent["severity"], string> = {
    info: "提示",
    warning: "关注",
    critical: "严重"
  };
  return labels[value];
}

function anomalySeverityClass(value: AnomalyEvent["severity"]): string {
  const styles: Record<AnomalyEvent["severity"], string> = {
    info: "border-slate-200 bg-slate-50 text-slate-700",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    critical: "border-rose-200 bg-rose-50 text-rose-800"
  };
  return styles[value];
}

function anomalyStatusLabel(value: AnomalyEvent["status"]): string {
  const labels: Record<AnomalyEvent["status"], string> = {
    active: "当前仍在",
    observed: "历史出现",
    resolved: "已恢复"
  };
  return labels[value];
}

function anomalyCategoryLabel(value: AnomalyEvent["category"]): string {
  const labels: Record<AnomalyEvent["category"], string> = {
    environment: "环境阈值",
    sensor_health: "传感器健康"
  };
  return labels[value];
}

function sensorHealthClass(status: SensorHealth["status"]): string {
  const classes = {
    ok: "bg-teal-50 text-teal-700",
    stale: "bg-amber-50 text-amber-700",
    anomaly: "bg-rose-50 text-rose-700",
    offline: "bg-rose-50 text-rose-700",
    unavailable: "bg-rose-50 text-rose-700"
  };
  return classes[status];
}

function timescaleStatusText(status: TelemetryStatus): string {
  if (status.hypertable) {
    return "时序表已启用";
  }
  if (status.timescale_enabled) {
    return "扩展已启用，当前表未转换";
  }
  if (status.timescale_available) {
    return "扩展可用，尚未启用";
  }
  return "扩展不可用，使用 PostgreSQL 表";
}

function telemetrySourceName(source: string): string {
  const labels: Record<string, string> = {
    mqtt: "MQTT",
    http: "HTTP",
    test: "测试写入"
  };
  return labels[source] ?? source;
}
