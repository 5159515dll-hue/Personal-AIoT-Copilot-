import type { SensorReading } from "@/lib/types";
import { metricLabel, statusLabel } from "@/lib/format";

const qualityStyle = {
  ok: "bg-teal-50 text-teal-700",
  stale: "bg-amber-50 text-amber-700",
  anomaly: "bg-rose-50 text-rose-700"
};

export function MetricCard({ reading }: { reading: SensorReading }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-muted">{metricLabel(reading.metric)}</p>
          <p className="mt-2 text-3xl font-semibold leading-none text-ink">
            {reading.metric === "presence" ? (reading.value ? "有人" : "无人") : reading.value}
            {reading.metric !== "presence" && (
              <span className="ml-1 text-sm font-medium text-muted">{reading.unit}</span>
            )}
          </p>
        </div>
        <span className={`rounded-md px-2 py-1 text-xs font-semibold ${qualityStyle[reading.quality]}`}>
          {statusLabel(reading.quality)}
        </span>
      </div>
    </section>
  );
}
