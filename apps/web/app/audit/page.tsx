import Link from "next/link";
import { Filter, RotateCcw } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RiskPill } from "@/components/risk-pill";
import { getAuditLogs } from "@/lib/api";
import { formatDateTime, statusLabel } from "@/lib/format";
import type { AuditLogQuery } from "@/lib/types";

export const dynamic = "force-dynamic";

type AuditPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const actorOptions = [
  { value: "user", label: "用户" },
  { value: "agent", label: "陪伴" },
  { value: "system", label: "系统" }
] as const;

const actionOptions = [
  { value: "control_device", label: "设备控制" },
  { value: "confirm_device_control", label: "设备确认" },
  { value: "companion_gesture", label: "陪伴动作" },
  { value: "update_companion_persona", label: "更新人格" },
  { value: "create_companion_character", label: "新建角色" },
  { value: "activate_companion_character", label: "切换角色" },
  { value: "clear_companion_memory", label: "清除记忆" },
  { value: "create_automation_rule", label: "创建规则" },
  { value: "confirm_automation_rule", label: "确认规则" },
  { value: "update_automation_rule", label: "更新规则" },
  { value: "trigger_automation_rule", label: "触发规则" },
  { value: "trigger_automation_rule_control", label: "规则控制" },
  { value: "update_device_management", label: "设备管理" },
  { value: "offline_device", label: "设备下线" },
  { value: "batch_update_device_management", label: "批量设备" },
  { value: "import_model_provider_key", label: "导入模型密钥" },
  { value: "switch_active_model", label: "切换模型" },
  { value: "test_model_provider", label: "测试模型" },
  { value: "ingest_sensor_readings", label: "遥测入站" },
  { value: "delete_companion_character", label: "删除角色" }
] as const;

const resultOptions = [
  { value: "success", label: "成功" },
  { value: "blocked", label: "已阻止" },
  { value: "requires_confirmation", label: "需要确认" },
  { value: "failed", label: "失败" }
] as const;

const policyOptions = [
  { value: "allowed", label: "允许" },
  { value: "requires_confirmation", label: "需要确认" },
  { value: "denied", label: "拒绝" }
] as const;

const riskOptions = [
  { value: "read_only", label: "只读" },
  { value: "low", label: "低风险" },
  { value: "medium", label: "中风险" },
  { value: "high", label: "高风险" },
  { value: "forbidden", label: "禁止控制" }
] as const;

const limitOptions = [50, 100, 200, 500] as const;

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const params = await searchParams;
  const filters = auditFiltersFrom(params ?? {});
  const logs = await getAuditLogs(filters);
  const activeFilterCount = [
    filters.actor,
    filters.action,
    filters.result,
    filters.policy_result,
    filters.risk_level,
    filters.q
  ].filter(Boolean).length;

  return (
    <AppShell>
      <PageHeader
        title="审计日志"
        description="每次重要智能体回复、控制尝试、用户确认、策略拒绝和规则活动都可以追溯。"
      />
      <form className="mb-5 rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
          <FilterSelect name="actor" label="发起方" value={filters.actor ?? ""} options={actorOptions} />
          <FilterSelect name="action" label="动作" value={filters.action ?? ""} options={actionOptions} />
          <FilterSelect name="result" label="结果" value={filters.result ?? ""} options={resultOptions} />
          <FilterSelect name="policy_result" label="策略结果" value={filters.policy_result ?? ""} options={policyOptions} />
          <FilterSelect name="risk_level" label="风险等级" value={filters.risk_level ?? ""} options={riskOptions} />
          <label className="block">
            <span className="text-xs font-semibold text-muted">条数</span>
            <select
              name="limit"
              defaultValue={filters.limit ?? 100}
              className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none"
            >
              {limitOptions.map((limit) => (
                <option key={limit} value={limit}>
                  最近 {limit} 条
                </option>
              ))}
            </select>
          </label>
          <label className="block md:col-span-2 xl:col-span-1">
            <span className="text-xs font-semibold text-muted">关键词</span>
            <input
              name="q"
              defaultValue={filters.q ?? ""}
              className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none placeholder:text-slate-400"
              placeholder="编号、设备、详情"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">
            当前显示 {logs.length} 条记录{activeFilterCount > 0 ? `，已启用 ${activeFilterCount} 个筛选条件` : "。"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/audit"
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-600 hover:text-ink"
            >
              <RotateCcw size={16} aria-hidden />
              重置
            </Link>
            <button
              type="submit"
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-ink px-4 text-sm font-semibold text-white"
            >
              <Filter size={16} aria-hidden />
              应用筛选
            </button>
          </div>
        </div>
      </form>
      {logs.length === 0 ? (
        <EmptyState
          title={activeFilterCount > 0 ? "没有匹配的审计日志" : "暂无审计日志"}
          detail={
            activeFilterCount > 0
              ? "放宽筛选条件，或复制设备页、规则页中的审计编号到关键词框继续追溯。"
              : "使用智能体页面或设备控制功能后，会产生经过策略检查的活动记录。"
          }
        />
      ) : (
        <section className="overflow-hidden rounded-lg border border-line bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">时间</th>
                  <th className="px-4 py-3 font-semibold">审计编号</th>
                  <th className="px-4 py-3 font-semibold">发起方</th>
                  <th className="px-4 py-3 font-semibold">动作</th>
                  <th className="px-4 py-3 font-semibold">策略结果</th>
                  <th className="px-4 py-3 font-semibold">风险</th>
                  <th className="px-4 py-3 font-semibold">结果</th>
                  <th className="px-4 py-3 font-semibold">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {logs.map((log) => (
                  <tr key={log.id} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-muted">{formatDateTime(log.timestamp)}</td>
                    <td className="max-w-44 break-all px-4 py-3 font-mono text-xs text-muted">{log.id}</td>
                    <td className="px-4 py-3 font-medium">{statusLabel(log.actor)}</td>
                    <td className="whitespace-nowrap px-4 py-3">{actionLabel(log.action)}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-medium">
                      {log.policy_result ? statusLabel(log.policy_result) : <span className="text-muted">无</span>}
                    </td>
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

function FilterSelect({
  name,
  label,
  value,
  options
}: {
  name: string;
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <select
        name={name}
        defaultValue={value}
        className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none"
      >
        <option value="">全部</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function auditFiltersFrom(params: Record<string, string | string[] | undefined>): AuditLogQuery {
  return {
    limit: normalizeLimit(params.limit),
    actor: normalizeOption(params.actor, actorOptions),
    action: normalizeFreeText(params.action),
    result: normalizeFreeText(params.result),
    policy_result: normalizeOption(params.policy_result, policyOptions),
    risk_level: normalizeOption(params.risk_level, riskOptions),
    q: normalizeFreeText(params.q)
  };
}

function normalizeLimit(value: string | string[] | undefined): number {
  const raw = Number(firstValue(value));
  return limitOptions.includes(raw as (typeof limitOptions)[number]) ? raw : 100;
}

function normalizeOption<T extends readonly { value: string; label: string }[]>(
  value: string | string[] | undefined,
  options: T
): T[number]["value"] | "" {
  const raw = normalizeFreeText(value);
  return options.some((option) => option.value === raw) ? raw : "";
}

function normalizeFreeText(value: string | string[] | undefined): string {
  return (firstValue(value) ?? "").trim();
}

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function actionLabel(value: string): string {
  const option = actionOptions.find((item) => item.value === value);
  return option?.label ?? value;
}
