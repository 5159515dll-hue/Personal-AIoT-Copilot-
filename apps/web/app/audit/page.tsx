import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RiskPill } from "@/components/risk-pill";
import { getAuditLogs } from "@/lib/api";
import { formatDateTime, statusLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function AuditPage() {
  const logs = await getAuditLogs();

  return (
    <AppShell>
      <PageHeader
        title="审计日志"
        description="每次重要智能体回复、控制尝试、策略拒绝和已确认规则创建都可以追溯。"
      />
      {logs.length === 0 ? (
        <EmptyState title="暂无审计日志" detail="使用智能体页面或设备控制功能后，会产生经过策略检查的活动记录。" />
      ) : (
        <section className="overflow-hidden rounded-lg border border-line bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">时间</th>
                  <th className="px-4 py-3 font-semibold">发起方</th>
                  <th className="px-4 py-3 font-semibold">动作</th>
                  <th className="px-4 py-3 font-semibold">策略</th>
                  <th className="px-4 py-3 font-semibold">结果</th>
                  <th className="px-4 py-3 font-semibold">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {logs.map((log) => (
                  <tr key={log.id} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-muted">{formatDateTime(log.timestamp)}</td>
                    <td className="px-4 py-3 font-medium">{statusLabel(log.actor)}</td>
                    <td className="px-4 py-3">{log.action}</td>
                    <td className="px-4 py-3">
                      {log.risk_level ? <RiskPill risk={log.risk_level} /> : <span className="text-muted">无</span>}
                    </td>
                    <td className="px-4 py-3 font-medium">{statusLabel(log.result)}</td>
                    <td className="min-w-80 px-4 py-3 text-muted">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </AppShell>
  );
}
