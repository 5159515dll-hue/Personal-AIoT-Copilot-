import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { TelemetrySourceSwitch } from "@/components/telemetry-source-switch";
import { TrendChart } from "@/components/trend-chart";
import { getSensorHistory } from "@/lib/api";
import { normalizeTelemetrySource, telemetrySourceLabel } from "@/lib/telemetry-source";
import type { MetricName, SensorReading } from "@/lib/types";

export const dynamic = "force-dynamic";

const metrics: { key: MetricName; title: string; color: string; bucket: string; days?: number }[] = [
  { key: "co2", title: "二氧化碳 24 小时", color: "#0D9488", bucket: "15m" },
  { key: "temperature", title: "温度 24 小时", color: "#2563EB", bucket: "15m" },
  { key: "humidity", title: "湿度 24 小时", color: "#7C3AED", bucket: "15m" },
  { key: "light", title: "光照 24 小时", color: "#F59E0B", bucket: "15m" },
  { key: "noise", title: "噪声 24 小时", color: "#E11D48", bucket: "15m" },
  { key: "presence", title: "有人状态 7 天", color: "#334155", bucket: "1h", days: 7 }
];

type TrendsPageProps = {
  searchParams?: Promise<{ source?: string | string[] }>;
};

type HistoryResult = {
  readings: SensorReading[];
  error: string | null;
};

export default async function TrendsPage({ searchParams }: TrendsPageProps) {
  const params = await searchParams;
  const source = normalizeTelemetrySource(params?.source);
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
        description={`查看${telemetrySourceLabel(source)}的时间序列。数据库遥测来自 MQTT 或 HTTP 入库后的 TimescaleDB 聚合结果。`}
        action={<TelemetrySourceSwitch source={source} basePath="/trends" />}
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
