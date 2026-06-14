"use client";

import { useState } from "react";
import { Heart, Send, Trash2 } from "lucide-react";
import {
  clearCompanionChat,
  deleteCompanionChatMessage,
  getCompanionChat,
  postCompanionReply
} from "@/lib/api";
import type { ChatMessage, CompanionPersona, CompanionReplyResponse, EmotionLabel } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

const EMOTIONS: { value: EmotionLabel; label: string }[] = [
  { value: "happy", label: "😊 开心" },
  { value: "sad", label: "😔 难过" },
  { value: "angry", label: "😠 生气" },
  { value: "surprise", label: "😮 惊讶" },
  { value: "fear", label: "😨 害怕" },
  { value: "disgust", label: "😖 厌恶" },
  { value: "neutral", label: "🙂 平静" }
];

const GESTURE_LABEL: Record<string, string> = {
  tilt_head: "歪头",
  nod: "点头",
  lean_back: "后仰",
  reach_out: "伸手",
  idle_nod: "轻点头",
  wave: "招手"
};

export function CompanionConsole({
  spaceId,
  initialPersona,
  hasEmotionState,
  initialHistory = []
}: {
  spaceId: string;
  initialPersona: CompanionPersona;
  hasEmotionState: boolean;
  initialHistory?: ChatMessage[];
}) {
  const [message, setMessage] = useState("");
  const [emotion, setEmotion] = useState<EmotionLabel | "">("");
  const [reply, setReply] = useState<CompanionReplyResponse | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>(initialHistory);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canTalk = Boolean(emotion) || hasEmotionState || Boolean(message.trim());

  async function talk() {
    setLoading(true);
    setError(null);
    try {
      const body: { space_id: string; message?: string; primary_emotion?: EmotionLabel } = { space_id: spaceId };
      if (message.trim()) body.message = message.trim();
      if (emotion) body.primary_emotion = emotion;
      setReply(await postCompanionReply(body));
      setMessage("");
      try {
        setHistory(await getCompanionChat());
      } catch {
        /* 记录刷新失败不影响对话 */
      }
    } catch (talkError) {
      setError(talkError instanceof Error ? talkError.message : "对话失败");
    } finally {
      setLoading(false);
    }
  }

  async function removeOne(id: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteCompanionChatMessage(id);
      setHistory((current) => current.filter((item) => item.id !== id));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function clearAll() {
    if (!window.confirm("确认清空与该角色的全部聊天记录？此操作不可恢复。")) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await clearCompanionChat();
      setHistory([]);
      setReply(null);
    } catch (clearError) {
      setError(clearError instanceof Error ? clearError.message : "清空失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Heart size={16} className="text-rose-500" aria-hidden />
          和「{initialPersona.name}」聊聊
        </h2>
        {history.length > 0 && (
          <button
            type="button"
            onClick={() => void clearAll()}
            disabled={busy}
            className="focus-ring inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:text-rose-600 disabled:opacity-60"
          >
            <Trash2 size={13} aria-hidden />
            清空记录
          </button>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[200px_1fr_auto] md:items-end">
        <label className="block">
          <span className="text-xs font-semibold text-muted">当前情绪（可选）</span>
          <select
            value={emotion}
            onChange={(event) => setEmotion(event.target.value as EmotionLabel | "")}
            className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
          >
            <option value="">{hasEmotionState ? "用当前感知到的情绪" : "请选择一个情绪"}</option>
            {EMOTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-muted">想说点什么（可选）</span>
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && canTalk && !loading) void talk();
            }}
            placeholder="我今天有点累…"
            className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
          />
        </label>
        <button
          type="button"
          onClick={() => void talk()}
          disabled={loading || !canTalk}
          className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-rose-500 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Send size={15} aria-hidden />
          {loading ? "在想…" : "聊聊"}
        </button>
      </div>

      {!canTalk && (
        <p className="mt-2 text-xs text-muted">先选一个情绪或写一句话；空间有实时情绪时也可直接聊。</p>
      )}
      {error && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}

      <div className="mt-4 max-h-96 space-y-2 overflow-y-auto pr-1">
        {history.length === 0 ? (
          <p className="rounded-lg bg-slate-50 p-3 text-xs leading-6 text-muted">
            还没有聊天记录。和小暖聊一句（或用语音对话）就会记录在这里，可随时删除单条或清空。
          </p>
        ) : (
          history.map((item) => (
            <div key={item.id} className={`group flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`relative max-w-[82%] rounded-2xl px-3 py-2 text-sm leading-6 ${
                  item.role === "user" ? "bg-rose-500 text-white" : "bg-slate-100 text-ink"
                }`}
              >
                <p className="whitespace-pre-wrap">{item.text}</p>
                <div className={`mt-1 flex flex-wrap items-center gap-2 text-[10px] ${item.role === "user" ? "text-white/70" : "text-muted"}`}>
                  <span>{formatDateTime(item.created_at)}</span>
                  {item.source === "voice" && <span>🎙 语音</span>}
                  {item.gesture && <span>动作：{GESTURE_LABEL[item.gesture] ?? item.gesture}</span>}
                </div>
                <button
                  type="button"
                  onClick={() => void removeOne(item.id)}
                  disabled={busy}
                  title="删除这条"
                  className="focus-ring absolute -right-2 -top-2 hidden rounded-full bg-white p-1 text-slate-400 shadow group-hover:block hover:text-rose-600 disabled:opacity-60"
                >
                  <Trash2 size={12} aria-hidden />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {reply && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="rounded-md bg-rose-50 px-2 py-1 font-semibold text-rose-600">动作：{GESTURE_LABEL[reply.gesture] ?? reply.gesture}</span>
          <span className="rounded-md bg-slate-50 px-2 py-1">基调：{reply.tone}</span>
          <span className="rounded-md bg-slate-50 px-2 py-1">{reply.model_used ? "豆包生成" : "模板兜底"}</span>
        </div>
      )}
      <p className="mt-3 text-xs leading-5 text-muted">
        聊天记录按角色保存（浏览器与语音对话都会记），可删除单条或清空。共情回应由大模型在情绪判定后生成；机器人手势经策略门控才执行。
      </p>
    </section>
  );
}
