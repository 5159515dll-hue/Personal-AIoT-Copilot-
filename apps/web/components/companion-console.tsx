"use client";

import { useState } from "react";
import { Heart, Send, Settings2 } from "lucide-react";
import { postCompanionPersona, postCompanionReply } from "@/lib/api";
import type { CompanionArchetype, CompanionPersona, CompanionReplyResponse, EmotionLabel } from "@/lib/types";

const EMOTIONS: { value: EmotionLabel; label: string }[] = [
  { value: "happy", label: "😊 开心" },
  { value: "sad", label: "😔 难过" },
  { value: "angry", label: "😠 生气" },
  { value: "surprise", label: "😮 惊讶" },
  { value: "fear", label: "😨 害怕" },
  { value: "disgust", label: "😖 厌恶" },
  { value: "neutral", label: "🙂 平静" }
];

const ARCHETYPES: { value: CompanionArchetype; label: string }[] = [
  { value: "gentle_healing", label: "温柔治愈" },
  { value: "lively_playful", label: "活泼俏皮" },
  { value: "quiet_companion", label: "安静陪伴" }
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
  const [persona, setPersona] = useState<CompanionPersona>(initialPersona);
  const [message, setMessage] = useState("");
  const [emotion, setEmotion] = useState<EmotionLabel | "">("");
  const [reply, setReply] = useState<CompanionReplyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showSettings, setShowSettings] = useState(false);
  const [draft, setDraft] = useState<CompanionPersona>(initialPersona);
  const [savingPersona, setSavingPersona] = useState(false);
  const [personaMessage, setPersonaMessage] = useState<string | null>(null);

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

  async function savePersona() {
    setSavingPersona(true);
    setPersonaMessage(null);
    try {
      const saved = await postCompanionPersona({
        name: draft.name.trim() || persona.name,
        archetype: draft.archetype,
        companion_for: draft.companion_for.trim()
      });
      setPersona(saved);
      setDraft(saved);
      setPersonaMessage(`已保存：${saved.name}`);
    } catch (saveError) {
      setPersonaMessage(saveError instanceof Error ? saveError.message : "人格保存失败");
    } finally {
      setSavingPersona(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Heart size={16} className="text-rose-500" aria-hidden />
          和「{persona.name}」聊聊
        </h2>
        <button
          type="button"
          onClick={() => setShowSettings((value) => !value)}
          className="focus-ring inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-slate-500 hover:text-ink"
        >
          <Settings2 size={14} aria-hidden />
          人格设置
        </button>
      </div>

      {showSettings && (
        <div className="mt-3 grid gap-3 rounded-lg border border-line bg-slate-50 p-3 md:grid-cols-3">
          <label className="block">
            <span className="text-xs font-semibold text-muted">名字</span>
            <input
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              className="focus-ring mt-1 h-9 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted">性格</span>
            <select
              value={draft.archetype}
              onChange={(event) => setDraft({ ...draft, archetype: event.target.value as CompanionArchetype })}
              className="focus-ring mt-1 h-9 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
            >
              {ARCHETYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted">主要陪伴</span>
            <input
              value={draft.companion_for}
              onChange={(event) => setDraft({ ...draft, companion_for: event.target.value })}
              placeholder="如：我自己 / 奶奶"
              className="focus-ring mt-1 h-9 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
            />
          </label>
          <div className="md:col-span-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => void savePersona()}
              disabled={savingPersona}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              保存人格
            </button>
            {personaMessage && <span className="text-xs text-muted">{personaMessage}</span>}
          </div>
        </div>
      )}

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
        共情回应由当前大模型在情绪判定之后生成；机器人手势仅在策略门控通过后才会真正执行。
      </p>
    </section>
  );
}
