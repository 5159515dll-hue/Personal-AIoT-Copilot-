"use client";

import { useState } from "react";
import { Heart, Send } from "lucide-react";
import { postCompanionReply } from "@/lib/api";
import type { CompanionPersona, CompanionReplyResponse, EmotionLabel } from "@/lib/types";

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
  hasEmotionState
}: {
  spaceId: string;
  initialPersona: CompanionPersona;
  hasEmotionState: boolean;
}) {
  const [message, setMessage] = useState("");
  const [emotion, setEmotion] = useState<EmotionLabel | "">("");
  const [reply, setReply] = useState<CompanionReplyResponse | null>(null);
  const [loading, setLoading] = useState(false);
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
    } catch (talkError) {
      setError(talkError instanceof Error ? talkError.message : "对话失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Heart size={16} className="text-rose-500" aria-hidden />
        和「{initialPersona.name}」聊聊
      </h2>

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

      {reply && (
        <div className="mt-4 rounded-lg border border-rose-100 bg-rose-50/60 p-4">
          <p className="text-sm leading-7 text-ink">{reply.reply}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="rounded-md bg-white px-2 py-1 font-semibold text-rose-600">动作：{GESTURE_LABEL[reply.gesture] ?? reply.gesture}</span>
            <span className="rounded-md bg-white px-2 py-1">基调：{reply.tone}</span>
            <span className="rounded-md bg-white px-2 py-1">
              {reply.model_used ? "豆包生成" : "模板兜底"}
            </span>
          </div>
        </div>
      )}
      <p className="mt-3 text-xs leading-5 text-muted">
        共情回应由当前大模型在情绪判定之后生成；机器人手势仅在策略门控通过后才会真正执行。人格与多角色在下方「陪伴角色」里设置。
      </p>
    </section>
  );
}
