import Link from "next/link";
import { CalendarDays, Clock3 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { TelemetrySourceSwitch } from "@/components/telemetry-source-switch";
import { TrendChart } from "@/components/trend-chart";
import { getSensorHistory } from "@/lib/api";
import { normalizeTelemetrySource, telemetrySourceLabel } from "@/lib/telemetry-source";
import type { MetricName, SensorReading } from "@/lib/types";

export const dynamic = "force-dynamic";

type TrendWindow = "24h" | "7d";

const metricDefinitions: { key: MetricName; label: string; color: string }[] = [
  { key: "co2", label: "二氧化碳", color: "#0D9488" },
  { key: "temperature", label: "温度", color: "#2563EB" },
  { key: "humidity", label: "湿度", color: "#7C3AED" },
  { key: "light", label: "光照", color: "#F59E0B" },
  { key: "noise", label: "噪声", color: "#E11D48" },
  { key: "presence", label: "有人状态", color: "#334155" }
];

type TrendsPageProps = {
  searchParams?: Promise<{ source?: string | string[]; window?: string | string[] }>;
};

type HistoryResult = {
  readings: SensorReading[];
  error: string | null;
};

export default async function TrendsPage({ searchParams }: TrendsPageProps) {
  const params = await searchParams;
  const source = normalizeTelemetrySource(params?.source);
  const trendWindow = normalizeTrendWindow(params?.window);
  const windowConfig = trendWindowConfig(trendWindow);
  const metrics = metricDefinitions.map((metric) => ({
    ...metric,
    title: `${metric.label} ${windowConfig.title}`,
    bucket: windowConfig.bucket,
    days: windowConfig.days
  }));
  const histories = await Promise.all(
    metrics.map(async (metric): Promise<HistoryResult> => {
      try {
        return {
          readings: await getSensorHistory(metric.key, metric.bucket, metric.days, source),
          error: null
        };
      } catch (error) {
        return {
          readings: [],
          error: error instanceof Error ? error.message : "曲线读取失败。"
        };
      }
    })
  );

  return (
    <AppShell>
      <PageHeader
        title="传感器趋势"
        description={`查看${telemetrySourceLabel(source)}的${windowConfig.title}时间序列。数据库遥测来自 MQTT 或 HTTP 入库后的 TimescaleDB 聚合结果。`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <TelemetrySourceSwitch
              source={source}
              basePath="/trends"
              extraParams={trendWindow === "7d" ? { window: "7d" } : undefined}
            />
            <TrendWindowSwitch source={source} value={trendWindow} />
          </div>
        }
      />
      <div className="grid gap-5 xl:grid-cols-2">
        {metrics.map((metric, index) => (
          <section key={metric.key} className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold">{metric.title}</h2>
            <p className="mt-1 text-sm text-muted">指标：{metric.title} · 粒度：{metric.bucket}</p>
            {histories[index].error && <p className="mt-3 text-sm leading-6 text-rose-700">{histories[index].error}</p>}
            <div className="mt-4">
              <TrendChart readings={histories[index].readings} color={metric.color} />
            </div>
          </section>
        ))}
      </div>
    </AppShell>
  );
}

function normalizeTrendWindow(value: string | string[] | undefined): TrendWindow {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "7d" ? "7d" : "24h";
}

function trendWindowConfig(value: TrendWindow): { title: string; bucket: string; days?: number } {
  if (value === "7d") {
    return { title: "7 天", bucket: "1h", days: 7 };
  }
  return { title: "24 小时", bucket: "15m" };
}

function TrendWindowSwitch({ source, value }: { source: ReturnType<typeof normalizeTelemetrySource>; value: TrendWindow }) {
  const options: Array<{ value: TrendWindow; label: string; icon: typeof Clock3 }> = [
    { value: "24h", label: "24 小时", icon: Clock3 },
    { value: "7d", label: "7 天", icon: CalendarDays }
  ];

  return (
    <div className="inline-flex rounded-lg border border-line bg-slate-50 p-1">
      {options.map((option) => {
        const Icon = option.icon;
        const active = value === option.value;
        return (
          <Link
            key={option.value}
            href={trendHref(source, option.value)}
            className={`focus-ring inline-flex h-9 items-center gap-2 rounded-md px-3 text-xs font-semibold ${
              active ? "bg-white text-teal-700 shadow-sm" : "text-slate-600 hover:text-ink"
            }`}
          >
            <Icon size={14} aria-hidden />
            {option.label}
          </Link>
        );
      })}
    </div>
  );
}

function trendHref(source: ReturnType<typeof normalizeTelemetrySource>, window: TrendWindow): string {
  const params = new URLSearchParams();
  if (source === "database") {
    params.set("source", "database");
  }
  if (window === "7d") {
    params.set("window", "7d");
  }
  const query = params.toString();
  return query ? `/trends?${query}` : "/trends";
}
