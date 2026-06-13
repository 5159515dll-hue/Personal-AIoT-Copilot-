"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Brain, Trash2 } from "lucide-react";
import { clearCompanionMemory } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { MemorySnapshot } from "@/lib/types";

const EMOTION_LABEL: Record<string, string> = {
  happy: "开心",
  sad: "难过",
  angry: "生气",
  surprise: "惊讶",
  fear: "害怕",
  disgust: "厌恶",
  neutral: "平静"
};

function Chips({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div>
      <p className="text-xs font-semibold text-muted">{title}</p>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span key={item} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export function CompanionMemoryPanel({
  memory,
  characterName
}: {
  memory: MemorySnapshot;
  characterName: string;
}) {
  const router = useRouter();
  const [clearing, setClearing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const profile = memory.profile;
  const episodes = memory.episodes;
  const profileHasContent = Boolean(
    profile &&
      (profile.display_name ||
        profile.preferences.length > 0 ||
        profile.important_people.length > 0 ||
        profile.notes.length > 0)
  );
  const hasMemory = profileHasContent || episodes.length > 0;

  async function clear(): Promise<void> {
    if (!window.confirm(`清除「${characterName}」的全部记忆？画像和情节都会删除，且不可恢复。`)) {
      return;
    }
    setClearing(true);
    setMessage(null);
    try {
      const result = await clearCompanionMemory();
      setMessage(`已清除：情节 ${result.cleared_episodes} 条${result.cleared_profile ? "，画像已清空" : ""}。`);
      router.refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "清除失败");
    } finally {
      setClearing(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Brain size={16} className="text-violet-500" aria-hidden />
          「{characterName}」的记忆
        </h2>
        <button
          type="button"
          onClick={() => void clear()}
          disabled={clearing || !hasMemory}
          title={hasMemory ? "清除该角色的全部记忆" : "暂无可清除的记忆"}
          className="focus-ring inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-rose-500 hover:text-rose-600 disabled:cursor-not-allowed disabled:text-slate-400"
        >
          <Trash2 size={14} aria-hidden />
          {clearing ? "清除中…" : "清除记忆"}
        </button>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted">
        记忆由对话自动沉淀（显著的事才记），用于让陪伴“懂你”。你可以随时查看并行使被遗忘权。
      </p>

      {message && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{message}</p>}

      {!hasMemory ? (
        <p className="mt-4 rounded-lg border border-dashed border-line p-4 text-sm text-muted">
          还没有记忆。多聊几句，陪伴会慢慢记住你的偏好、在意的人和重要的小事。
        </p>
      ) : (
        <div className="mt-4 space-y-5">
          {profileHasContent && profile && (
            <div className="space-y-3 rounded-lg border border-line bg-slate-50/60 p-3">
              {profile.display_name && (
                <div>
                  <p className="text-xs font-semibold text-muted">称呼</p>
                  <p className="mt-0.5 text-sm text-ink">{profile.display_name}</p>
                </div>
              )}
              <Chips title="偏好" items={profile.preferences} />
              <Chips title="在意的人" items={profile.important_people} />
              <Chips title="其他" items={profile.notes} />
              <p className="text-xs text-muted">更新于 {formatDateTime(profile.updated_at)}</p>
            </div>
          )}

          {episodes.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted">最近情节（{episodes.length}）</p>
              <ul className="mt-2 space-y-2">
                {episodes.map((episode) => (
                  <li key={episode.id} className="rounded-lg border border-line p-3">
                    <p className="text-sm leading-6 text-ink">{episode.summary}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <span>{formatDateTime(episode.created_at)}</span>
                      {episode.emotion && (
                        <span className="rounded-md bg-white px-2 py-0.5 text-rose-600">
                          {EMOTION_LABEL[episode.emotion] ?? episode.emotion}
                        </span>
                      )}
                      <span className="rounded-md bg-white px-2 py-0.5">显著度 {Math.round(episode.salience * 100)}%</span>
                      {episode.topics.map((topic) => (
                        <span key={topic} className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">
                          {topic}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
