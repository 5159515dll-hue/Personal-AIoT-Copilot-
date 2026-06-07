import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { getAgentSafetyEvaluation } from "@/lib/api";
import { formatDateTime, riskLabel, statusLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function EvaluationPage() {
  const report = await getAgentSafetyEvaluation();

  return (
    <AppShell>
      <PageHeader
        title="V3 研究评测"
        description="统计智能体安全边界、工具调用、越权阻断和多轮一致性，用服务器评测报告驱动。"
      />

      <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink">智能体安全评测报告</h2>
            <p className="mt-1 text-sm leading-6 text-muted">{report.summary}</p>
          </div>
          <span
            className={[
              "inline-flex h-8 items-center rounded-md px-3 text-xs font-semibold",
              report.source === "report_file" ? "bg-teal-50 text-teal-700" : "bg-amber-50 text-amber-800"
            ].join(" ")}
          >
            {report.source === "report_file" ? "服务器报告" : "等待评测"}
          </span>
        </div>
        <p className="mt-2 text-xs text-muted">生成时间：{formatDateTime(report.generated_at)}</p>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {report.metrics.map((metric) => (
            <article key={metric.id} className="rounded-lg border border-line bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-semibold text-ink">{metric.label}</h3>
                <span className={metricStatusClass(metric.status)}>{statusLabel(metric.status)}</span>
              </div>
              <p className="mt-3 text-3xl font-semibold tracking-normal text-ink">
                {metric.unit === "rate" ? `${Math.round(metric.value * 1000) / 10}%` : metric.value}
              </p>
              <p className="mt-2 text-xs leading-5 text-muted">{metric.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-5 overflow-hidden rounded-lg border border-line bg-white shadow-sm">
        <div className="border-b border-line p-4">
          <h2 className="text-base font-semibold text-ink">评测用例</h2>
          <p className="mt-1 text-sm text-muted">
            共 {report.total_cases} 个，通过 {report.passed_cases} 个，失败 {report.failed_cases} 个。
          </p>
        </div>
        {report.cases.length === 0 ? (
          <div className="p-4">
            <EmptyState
              title="暂无服务器评测报告"
              detail="在服务器运行 npm run eval:agent-safety 后，这里会显示误操作率、越权率、工具成功率和多轮一致性结果。"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">用例</th>
                  <th className="px-4 py-3 font-semibold">类别</th>
                  <th className="px-4 py-3 font-semibold">状态</th>
                  <th className="px-4 py-3 font-semibold">策略</th>
                  <th className="px-4 py-3 font-semibold">风险</th>
                  <th className="px-4 py-3 font-semibold">模型</th>
                  <th className="px-4 py-3 font-semibold">工具</th>
                  <th className="px-4 py-3 font-semibold">失败原因</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {report.cases.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="min-w-72 px-4 py-3">
                      <p className="font-semibold text-ink">{item.name}</p>
                      <p className="mt-1 text-xs leading-5 text-muted">{item.message}</p>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">{categoryLabel(item.category)}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className={item.status === "passed" ? "text-teal-700" : "text-rose-700"}>
                        {item.status === "passed" ? "通过" : "失败"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">{item.policy_result ? statusLabel(item.policy_result) : "无"}</td>
                    <td className="whitespace-nowrap px-4 py-3">{item.risk_level ? riskLabel(item.risk_level) : "无"}</td>
                    <td className="whitespace-nowrap px-4 py-3">{item.model_status ? statusLabel(item.model_status) : "无"}</td>
                    <td className="min-w-64 px-4 py-3 text-xs leading-5 text-muted">{item.tool_names.join("、") || "无"}</td>
                    <td className="min-w-64 px-4 py-3 text-muted">{item.failure ?? "无"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}

function metricStatusClass(status: string): string {
  if (status === "pass") {
    return "rounded-md bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700";
  }
  if (status === "fail") {
    return "rounded-md bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700";
  }
  return "rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800";
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    safety: "安全",
    tool: "工具",
    multi_turn: "多轮",
    policy: "策略"
  };
  return labels[category] ?? category;
}
