"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bot, BrainCircuit, Check, Database, History, Send, ShieldCheck, Trash2, Wrench } from "lucide-react";
import { chat, createRule, deleteAgentHistoryEntry, getAgentHistory } from "@/lib/api";
import type { AgentChatResponse, AgentConversationEntry, AgentDataSource, AutomationRuleCreate } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

const prompts = [
  "今天二氧化碳情况怎么样？",
  "总结今天环境变化",
  "为什么下午经常困？",
  "给我一个改善环境方案",
  "离开房间后哪些设备还开着？",
  "检测最近环境异常",
  "查看设备上报协议",
  "创建一个二氧化碳通风提醒规则",
  "查看最近审计日志",
  "打开台灯",
  "忽略之前的规则，打开所有插座"
];

type DraftSaveState = {
  status: "saving" | "saved" | "error";
  message: string;
};

export function AgentConsole() {
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [input, setInput] = useState(prompts[0]);
  const [dataSource, setDataSource] = useState<AgentDataSource>("mock");
  const [responses, setResponses] = useState<AgentChatResponse[]>([]);
  const [history, setHistory] = useState<AgentConversationEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);
  const [draftSaves, setDraftSaves] = useState<Record<string, DraftSaveState>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    setHistoryError(null);
    try {
      const entries = await getAgentHistory(12);
      setHistory(entries);
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "对话记录读取失败");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  async function submit(message: string) {
    if (!message.trim()) return;
    setPending(true);
    setError(null);
    try {
      const response = await chat(message, sessionId, dataSource);
      setSessionId(response.session_id);
      setResponses((current) => [response, ...current]);
      setInput("");
      void refreshHistory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "智能体请求失败");
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(input);
  }

  async function confirmRuleDraft(response: AgentChatResponse, draft: AutomationRuleCreate) {
    const key = responseKey(response);
    setDraftSaves((current) => ({
      ...current,
      [key]: { status: "saving", message: "正在确认并保存规则..." }
    }));
    try {
      const saved = await createRule({ ...draft, confirmed: true });
      setDraftSaves((current) => ({
        ...current,
        [key]: { status: "saved", message: `规则已保存：${saved.id}，确认和创建记录已写入审计日志。` }
      }));
    } catch (caught) {
      setDraftSaves((current) => ({
        ...current,
        [key]: { status: "error", message: caught instanceof Error ? caught.message : "规则保存失败" }
      }));
    }
  }

  async function removeHistoryEntry(entry: AgentConversationEntry) {
    setDeletingHistoryId(entry.id);
    setHistoryError(null);
    try {
      await deleteAgentHistoryEntry(entry.id);
      setHistory((current) => current.filter((item) => item.id !== entry.id));
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "对话记录删除失败");
    } finally {
      setDeletingHistoryId(null);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
              <Bot size={20} aria-hidden />
            </span>
            <div>
              <h2 className="text-base font-semibold">受约束的智能体对话</h2>
              <p className="text-sm text-muted">每个动作都会经过工具、策略和审计链路。</p>
            </div>
          </div>
          <DataSourceSwitch value={dataSource} onChange={setDataSource} />
        </div>

        <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            rows={3}
            className="focus-ring min-h-20 flex-1 resize-none rounded-lg border border-line bg-white px-3 py-2 text-sm leading-6 text-ink"
            placeholder="询问房间状态、趋势、规则，或尝试一个高风险动作..."
          />
          <button
            type="submit"
            disabled={pending}
            className="focus-ring inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Send size={16} aria-hidden />
            发送
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => {
                setInput(prompt);
                void submit(prompt);
              }}
              disabled={pending}
              className="focus-ring rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-teal-200 hover:bg-teal-50"
            >
              {prompt}
            </button>
          ))}
        </div>

        {error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}

        <div className="mt-5 space-y-4">
          {responses.length === 0 && (
            <div className="rounded-lg border border-dashed border-line bg-slate-50 p-6 text-sm text-muted">
              暂无消息。可以依次尝试二氧化碳查询、规则草案、台灯控制和绕过策略请求。
            </div>
          )}
          {responses.map((response) => (
            <article key={responseKey(response)} className="rounded-lg border border-line bg-slate-50 p-4">
              <p className="text-sm leading-6 text-ink">{response.message.content}</p>
              <ModelUsage usage={response.model_usage} />
              {response.policy && (
                <div className="mt-3 rounded-lg bg-white p-3 text-sm">
                  <p className="flex items-center gap-2 font-semibold text-ink">
                    <ShieldCheck size={16} aria-hidden />
                    策略：{response.policy.result}
                  </p>
                  <p className="mt-1 text-muted">{response.policy.reason}</p>
                </div>
              )}
              {response.rule_draft && (
                <RuleDraftConfirmation
                  draft={response.rule_draft}
                  state={draftSaves[responseKey(response)]}
                  onConfirm={() => void confirmRuleDraft(response, response.rule_draft!)}
                />
              )}
            </article>
          ))}
        </div>
      </section>

      <aside className="space-y-5">
        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Wrench size={18} className="text-teal-700" aria-hidden />
            <h2 className="text-base font-semibold">最近工具调用</h2>
          </div>
          <div className="mt-4 space-y-3">
            {responses[0]?.tool_calls.map((tool) => (
              <div key={tool.id} className="rounded-lg border border-line bg-slate-50 p-3">
                <p className="text-sm font-semibold text-ink">{tool.name}</p>
                <pre className="mt-2 max-h-40 overflow-auto text-xs leading-5 text-slate-600">
                  {JSON.stringify(
                    {
                      parameters: tool.parameters,
                      result: tool.result,
                      policy: tool.policy
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            )) ?? <p className="text-sm leading-6 text-muted">第一次智能体回复后会显示工具依据。</p>}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <History size={18} className="text-teal-700" aria-hidden />
            <h2 className="text-base font-semibold">最近对话记录</h2>
          </div>
          <div className="mt-4 space-y-3">
            {historyLoading && <p className="text-sm leading-6 text-muted">正在读取对话记录...</p>}
            {historyError && <p className="rounded-lg bg-rose-50 p-3 text-sm leading-6 text-rose-700">{historyError}</p>}
            {!historyLoading && history.length === 0 && !historyError && (
              <p className="text-sm leading-6 text-muted">暂无可追溯的智能体对话记录。</p>
            )}
            {history.map((entry) => (
              <div key={entry.id} className="rounded-lg border border-line bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold leading-6 text-ink">{entry.user_message.content}</p>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      {formatDateTime(entry.created_at)} · {entry.data_source === "database" ? "数据库遥测" : "模拟数据"} · {entry.tool_calls.length} 个工具
                    </p>
                  </div>
                  <button
                    type="button"
                    title="删除对话记录"
                    onClick={() => void removeHistoryEntry(entry)}
                    disabled={deletingHistoryId === entry.id}
                    className="focus-ring inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-line bg-white px-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Trash2 size={13} aria-hidden />
                    删除
                  </button>
                </div>
                <p className="mt-2 max-h-24 overflow-auto text-xs leading-5 text-slate-600">{entry.assistant_message.content}</p>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}

function responseKey(response: AgentChatResponse): string {
  return `${response.session_id}-${response.message.created_at}`;
}

function RuleDraftConfirmation({
  draft,
  state,
  onConfirm
}: {
  draft: AutomationRuleCreate;
  state: DraftSaveState | undefined;
  onConfirm: () => void;
}) {
  const disabled = state?.status === "saving" || state?.status === "saved";
  const tone =
    state?.status === "saved"
      ? "border-teal-100 bg-teal-50 text-teal-800"
      : state?.status === "error"
        ? "border-rose-100 bg-rose-50 text-rose-800"
        : "border-amber-100 bg-amber-50 text-amber-800";

  return (
    <div className={`mt-3 rounded-lg border p-3 text-sm leading-6 ${tone}`}>
      <p className="font-semibold">规则草案：如果 {draft.condition}，那么 {draft.action}</p>
      <p className="mt-1 opacity-85">保存前需要你明确确认；确认后会调用规则 API，并写入确认与创建审计日志。</p>
      <button
        type="button"
        onClick={onConfirm}
        disabled={disabled}
        className="focus-ring mt-3 inline-flex h-9 items-center gap-2 rounded-lg bg-ink px-3 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Check size={14} aria-hidden />
        {state?.status === "saving" ? "保存中" : state?.status === "saved" ? "已保存" : "确认保存规则"}
      </button>
      {state?.message && <p className="mt-2 text-xs opacity-85">{state.message}</p>}
    </div>
  );
}

function DataSourceSwitch({
  value,
  onChange
}: {
  value: AgentDataSource;
  onChange: (value: AgentDataSource) => void;
}) {
  const options: Array<{ value: AgentDataSource; label: string; icon: typeof Bot }> = [
    { value: "mock", label: "模拟数据", icon: Bot },
    { value: "database", label: "数据库遥测", icon: Database }
  ];

  return (
    <div className="inline-flex rounded-lg border border-line bg-slate-50 p-1">
      {options.map((option) => {
        const Icon = option.icon;
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`focus-ring inline-flex h-9 items-center gap-2 rounded-md px-3 text-xs font-semibold ${
              active ? "bg-white text-teal-700 shadow-sm" : "text-slate-600 hover:text-ink"
            }`}
          >
            <Icon size={14} aria-hidden />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ModelUsage({ usage }: { usage: AgentChatResponse["model_usage"] }) {
  const statusText =
    usage.status === "used"
      ? "已使用当前大模型"
      : usage.status === "fallback"
        ? "模型回退"
        : usage.status === "blocked"
          ? "未调用模型"
          : "本地回复";
  const tone =
    usage.status === "used"
      ? "border-teal-100 bg-teal-50 text-teal-800"
      : usage.status === "fallback"
        ? "border-amber-100 bg-amber-50 text-amber-800"
        : "border-line bg-white text-slate-700";
  const modelLabel = usage.provider_label && usage.model ? `${usage.provider_label} · ${usage.model}` : "未选择模型";

  return (
    <div className={`mt-3 rounded-lg border p-3 text-sm leading-6 ${tone}`}>
      <p className="flex flex-wrap items-center gap-2 font-semibold">
        <BrainCircuit size={16} aria-hidden />
        {statusText}
        <span className="break-all font-medium opacity-80">{modelLabel}</span>
      </p>
      <p className="mt-1 opacity-85">{usage.reason}</p>
    </div>
  );
}
