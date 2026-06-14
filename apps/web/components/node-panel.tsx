import {
  Activity,
  Cpu,
  Droplets,
  type LucideIcon,
  Radar,
  Radio,
  Sun,
  Thermometer,
  Volume2,
  Wind
} from "lucide-react";
import { deviceTypeLabel, metricLabel, statusLabel } from "@/lib/format";
import type { NodeSensor, NodeSummary } from "@/lib/types";

const METRIC_ICON: Record<string, LucideIcon> = {
  temperature: Thermometer,
  humidity: Droplets,
  co2: Wind,
  light: Sun,
  presence: Radar,
  noise: Volume2
};

const SENSOR_STATUS: Record<NodeSensor["status"], { label: string; cls: string }> = {
  fresh: { label: "实时", cls: "bg-teal-50 text-teal-700" },
  stale: { label: "陈旧", cls: "bg-amber-50 text-amber-700" },
  silent: { label: "未上报", cls: "bg-slate-100 text-slate-500" }
};

function ago(seconds: number | null): string {
  if (seconds == null) return "从未";
  if (seconds < 60) return `${Math.round(seconds)} 秒前`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`;
  return `${Math.round(seconds / 86400)} 天前`;
}

function formatValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function SensorTile({ sensor }: { sensor: NodeSensor }) {
  const Icon = METRIC_ICON[sensor.metric] ?? Activity;
  const status = SENSOR_STATUS[sensor.status];
  return (
    <div className="rounded-lg border border-line bg-slate-50/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-muted">
          <Icon size={14} aria-hidden />
          {metricLabel(sensor.metric)}
        </span>
        <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${status.cls}`}>{status.label}</span>
      </div>
      <p className="mt-2 text-xl font-semibold tracking-tight text-ink">
        {sensor.value == null ? "—" : formatValue(sensor.value)}
        {sensor.value != null && sensor.unit ? (
          <span className="ml-1 text-xs font-normal text-muted">{sensor.unit}</span>
        ) : null}
      </p>
      <p className="mt-1 text-[11px] text-muted">
        {sensor.status === "silent" ? "等待数据" : ago(sensor.age_seconds)}
        {sensor.quality && sensor.quality !== "ok" ? ` · ${statusLabel(sensor.quality)}` : ""}
      </p>
    </div>
  );
}

function NodeCard({ node }: { node: NodeSummary }) {
  return (
    <article className="rounded-xl border border-line bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <span
              className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${node.online ? "bg-teal-500" : "bg-slate-300"}`}
              aria-hidden
            />
            {node.display_name}
          </h3>
          <p className="mt-0.5 font-mono text-xs text-muted">{node.device_id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-600">{deviceTypeLabel(node.device_type)}</span>
          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-600">{statusLabel(node.transport)}</span>
          <span
            className={`rounded-md px-2 py-0.5 font-semibold ${node.online ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-500"}`}
          >
            {node.online ? "在线" : "离线"} · {ago(node.age_seconds)}
          </span>
        </div>
      </div>

      {node.sensors.length === 0 ? (
        <p className="mt-3 rounded-lg border border-dashed border-line p-3 text-xs text-muted">该节点尚未上报任何传感器指标。</p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {node.sensors.map((sensor) => (
            <SensorTile key={sensor.metric} sensor={sensor} />
          ))}
        </div>
      )}

      <p className="mt-3 text-[11px] text-muted">
        {node.reporting_count}/{node.sensor_count} 个传感器实时上报
        {node.firmware_version ? ` · 固件 ${node.firmware_version}` : ""}
      </p>
    </article>
  );
}

export function NodePanel({ nodes }: { nodes: NodeSummary[] }) {
  const online = nodes.filter((node) => node.online).length;
  const reporting = nodes.reduce((acc, node) => acc + node.reporting_count, 0);
  const sensors = nodes.reduce((acc, node) => acc + node.sensor_count, 0);

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Cpu size={16} className="text-teal-600" aria-hidden />
          接入节点（{nodes.length}）
        </h2>
        <p className="text-xs text-muted">
          {online} 在线 · {reporting}/{sensors} 个传感器实时上报
        </p>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted">
        每个节点（如 ESP32）一张卡片，卡内是它带的传感器——一眼看清现有哪些节点、各自有哪些传感器及状态。
      </p>

      {nodes.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-line p-6 text-center">
          <Radio size={22} className="mx-auto text-slate-400" aria-hidden />
          <p className="mt-2 text-sm font-semibold text-ink">暂无已接入节点</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            给 ESP32 烧录固件并上电后，它会通过 MQTT 自动出现在这里。接线与烧录见「接入」页。
          </p>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {nodes.map((node) => (
            <NodeCard key={node.device_id} node={node} />
          ))}
        </div>
      )}
    </section>
  );
}
