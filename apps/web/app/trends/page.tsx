import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { TrendChart } from "@/components/trend-chart";
import { getSensorHistory } from "@/lib/api";
import type { MetricName } from "@/lib/types";

export const dynamic = "force-dynamic";

const metrics: { key: MetricName; title: string; color: string; bucket: string; days?: number }[] = [
  { key: "co2", title: "二氧化碳 24 小时", color: "#0D9488", bucket: "15m" },
  { key: "temperature", title: "温度 24 小时", color: "#2563EB", bucket: "15m" },
  { key: "humidity", title: "湿度 24 小时", color: "#7C3AED", bucket: "15m" },
  { key: "light", title: "光照 24 小时", color: "#F59E0B", bucket: "15m" },
  { key: "presence", title: "有人状态 7 天", color: "#334155", bucket: "1h", days: 7 }
];

export default async function TrendsPage() {
  const histories = await Promise.all(metrics.map((metric) => getSensorHistory(metric.key, metric.bucket, metric.days)));

  return (
    <AppShell>
      <PageHeader
        title="传感器趋势"
        description="查看模拟房间遥测的时间序列。后续版本会把这里替换为 ESP32 与 MQTT 写入的真实数据。"
      />
      <div className="grid gap-5 xl:grid-cols-2">
        {metrics.map((metric, index) => (
          <section key={metric.key} className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold">{metric.title}</h2>
            <p className="mt-1 text-sm text-muted">指标：{metric.title} · 粒度：{metric.bucket}</p>
            <div className="mt-4">
              <TrendChart readings={histories[index]} color={metric.color} />
            </div>
          </section>
        ))}
      </div>
    </AppShell>
  );
}
