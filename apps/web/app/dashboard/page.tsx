import Link from "next/link";
import { AlertTriangle, ArrowRight, FileClock, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { RiskPill } from "@/components/risk-pill";
import { TrendChart } from "@/components/trend-chart";
import { getAuditLogs, getDevices, getRoomState, getSensorHistory } from "@/lib/api";
import { formatDateTime, statusLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [room, co2History, devices, auditLogs] = await Promise.all([
    getRoomState(),
    getSensorHistory("co2", "15m"),
    getDevices(),
    getAuditLogs()
  ]);

  const riskyDevices = devices.filter((device) => ["medium", "high", "forbidden"].includes(device.risk_level));

  return (
    <AppShell>
      <PageHeader
        title="空间总览"
        description="查看当前模拟环境、智能体建议、安全状态和最近审计活动。"
        action={
          <Link
            href="/agent"
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white"
          >
            询问智能体
            <ArrowRight size={16} aria-hidden />
          </Link>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {Object.values(room.metrics).map((reading) => (
          <MetricCard key={reading.metric} reading={reading} />
        ))}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">二氧化碳最近 24 小时</h2>
              <p className="mt-1 text-sm text-muted">异常窗口会在下午和晚间有人时段模拟生成。</p>
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
              {statusLabel(room.status)}
            </span>
          </div>
          <div className="mt-4">
            <TrendChart readings={co2History} />
          </div>
        </section>

        <aside className="space-y-5">
          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 text-teal-700" size={20} aria-hidden />
              <div>
                <h2 className="text-base font-semibold">智能体建议</h2>
                <p className="mt-2 text-sm leading-6 text-muted">{room.recommendation}</p>
                <p className="mt-3 text-xs text-muted">依据：{room.summary}</p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <AlertTriangle className="text-amber-600" size={18} aria-hidden />
              <h2 className="text-base font-semibold">异常事件</h2>
            </div>
            <div className="mt-3 space-y-2">
              {room.anomalies.length ? (
                room.anomalies.map((item) => (
                  <p key={item} className="rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-800">
                    {item}
                  </p>
                ))
              ) : (
                <p className="text-sm leading-6 text-muted">当前模拟房间没有异常。</p>
              )}
            </div>
          </section>
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
