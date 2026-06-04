"use client";

import { FormEvent, useState } from "react";
import { Check, Plus } from "lucide-react";
import { createRule } from "@/lib/api";
import type { AutomationRule } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

export function RulesPanel({ initialRules }: { initialRules: AutomationRule[] }) {
  const [rules, setRules] = useState(initialRules);
  const [condition, setCondition] = useState("二氧化碳 > 1200 ppm 持续 15 分钟");
  const [action, setAction] = useState("发送通风提醒");
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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
        <h2 className="text-base font-semibold text-ink">自动化规则</h2>
        <div className="mt-4 space-y-3">
          {rules.map((rule) => (
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
            </article>
          ))}
          {rules.length === 0 && <p className="text-sm leading-6 text-muted">暂无已确认规则。</p>}
        </div>
      </section>
    </div>
  );
}
