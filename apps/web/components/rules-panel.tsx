"use client";

import { FormEvent, useEffect, useState } from "react";
import { BellRing, Check, CircleDashed, Play, Plus, ShieldAlert } from "lucide-react";
import { createRule, evaluateRules } from "@/lib/api";
import { telemetrySourceLabel } from "@/lib/telemetry-source";
import type { AutomationRule, RuleEvaluation, TelemetrySource } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

export function RulesPanel({
  initialRules,
  initialSource
}: {
  initialRules: AutomationRule[];
  initialSource: TelemetrySource;
}) {
  const [rules, setRules] = useState(initialRules);
  const [evaluations, setEvaluations] = useState<RuleEvaluation[]>([]);
  const [condition, setCondition] = useState("二氧化碳 > 1200 ppm 持续 15 分钟");
  const [action, setAction] = useState("发送通风提醒");
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const sourceLabel = telemetrySourceLabel(initialSource);

  useEffect(() => {
    setEvaluations([]);
    setMessage(null);
  }, [initialSource]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      const rule = await createRule({ condition, action, enabled: true, confirmed });
      setRules((current) => [rule, ...current]);
      setMessage("规则已保存，并写入审计日志。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "规则创建失败");
    }
  }

  async function onEvaluate() {
    setEvaluating(true);
    setMessage(null);
    try {
      const result = await evaluateRules(initialSource);
      setEvaluations(result);
      const triggered = result.filter((item) => item.status === "triggered").length;
      setMessage(
        triggered > 0
          ? `已使用${sourceLabel}触发 ${triggered} 条提醒规则，并写入审计日志。`
          : `已使用${sourceLabel}完成评估，当前没有规则被触发。`
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "规则评估失败");
    } finally {
      setEvaluating(false);
    }
  }

  const evaluationByRule = new Map(evaluations.map((item) => [item.rule_id, item]));

  return (
    <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
      <form onSubmit={onSubmit} className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <h2 className="text-base font-semibold text-ink">创建已确认规则</h2>
        <label className="mt-4 block text-sm font-semibold text-slate-700" htmlFor="condition">
          如果条件
        </label>
        <textarea
          id="condition"
          value={condition}
          onChange={(event) => setCondition(event.target.value)}
          className="focus-ring mt-2 min-h-20 w-full resize-none rounded-lg border border-line px-3 py-2 text-sm leading-6"
        />
        <label className="mt-4 block text-sm font-semibold text-slate-700" htmlFor="action">
          那么动作
        </label>
        <textarea
          id="action"
          value={action}
          onChange={(event) => setAction(event.target.value)}
          className="focus-ring mt-2 min-h-20 w-full resize-none rounded-lg border border-line px-3 py-2 text-sm leading-6"
        />
        <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-slate-700">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            className="mt-1 h-4 w-4 rounded border-line text-teal-600"
          />
          我已检查这条简单“如果/那么”规则，并确认保存。
        </label>
        <button
          type="submit"
          className="focus-ring mt-4 inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white"
        >
          <Plus size={16} aria-hidden />
          保存规则
        </button>
        {message && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{message}</p>}
      </form>

      <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink">自动化规则</h2>
            <p className="mt-1 text-xs text-muted">当前评估源：{sourceLabel}</p>
          </div>
          <button
            type="button"
            onClick={onEvaluate}
            disabled={evaluating || rules.length === 0}
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play size={16} aria-hidden />
            {evaluating ? "评估中" : "评估当前规则"}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {rules.map((rule) => {
            const evaluation = evaluationByRule.get(rule.id);
            return (
              <article key={rule.id} className="rounded-lg border border-line bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-ink">如果 {rule.condition}</p>
                    <p className="mt-1 text-sm text-muted">那么 {rule.action}</p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700">
                    <Check size={13} aria-hidden />
                    {rule.enabled ? "已启用" : "已暂停"}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted">创建时间：{formatDateTime(rule.created_at)}</p>
                {evaluation && <RuleEvaluationStatus evaluation={evaluation} />}
              </article>
            );
          })}
          {rules.length === 0 && <p className="text-sm leading-6 text-muted">暂无已确认规则。</p>}
        </div>
      </section>
    </div>
  );
}

function RuleEvaluationStatus({ evaluation }: { evaluation: RuleEvaluation }) {
  const observedSource = evaluation.observed.source === "database" ? "数据库遥测" : "模拟数据";
  const metric = typeof evaluation.observed.metric === "string" ? evaluation.observed.metric : null;
  const value = typeof evaluation.observed.value === "number" ? evaluation.observed.value : null;
  const unit = typeof evaluation.observed.unit === "string" ? evaluation.observed.unit : "";
  const threshold = typeof evaluation.observed.threshold === "number" ? evaluation.observed.threshold : null;
  const style =
    evaluation.status === "triggered"
      ? "border-teal-100 bg-teal-50 text-teal-800"
      : evaluation.status === "unsupported"
        ? "border-amber-100 bg-amber-50 text-amber-800"
        : "border-line bg-white text-slate-700";
  const Icon =
    evaluation.status === "triggered"
      ? BellRing
      : evaluation.status === "unsupported"
        ? ShieldAlert
        : CircleDashed;
  const label =
    evaluation.status === "triggered"
      ? "已触发"
      : evaluation.status === "not_matched"
        ? "未触发"
        : evaluation.status === "disabled"
          ? "已暂停"
          : "暂不支持";

  return (
    <div className={`mt-3 rounded-lg border p-3 text-sm leading-6 ${style}`}>
      <p className="flex flex-wrap items-center gap-2 font-semibold">
        <Icon size={15} aria-hidden />
        {label}
        <span className="font-medium opacity-80">{formatDateTime(evaluation.evaluated_at)}</span>
      </p>
      <p className="mt-1">{evaluation.reason}</p>
      {metric && value !== null && (
        <p className="mt-1 text-xs opacity-80">
          依据：{observedSource} · {metric} {formatObservedNumber(value)} {unit}
          {threshold !== null ? `，阈值 ${formatObservedNumber(threshold)}` : ""}
        </p>
      )}
      {evaluation.audit_log_id && <p className="mt-1 break-all text-xs opacity-80">审计编号：{evaluation.audit_log_id}</p>}
    </div>
  );
}

function formatObservedNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
