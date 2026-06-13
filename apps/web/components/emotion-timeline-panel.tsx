import type { DeviceEvent, EmotionLabel, EmotionState } from "@/lib/types";

const EMOTION_LABEL_ZH: Record<EmotionLabel, string> = {
  happy: "开心",
  sad: "难过",
  angry: "生气",
  surprise: "惊讶",
  fear: "害怕",
  disgust: "厌恶",
  neutral: "平静"
};

const EMOTION_EMOJI: Record<EmotionLabel, string> = {
  happy: "😊",
  sad: "😔",
  angry: "😠",
  surprise: "😮",
  fear: "😨",
  disgust: "😖",
  neutral: "🙂"
};

function emotionDisplay(value: unknown): string {
  if (typeof value === "string" && value in EMOTION_LABEL_ZH) {
    const label = value as EmotionLabel;
    return `${EMOTION_EMOJI[label]} ${EMOTION_LABEL_ZH[label]}`;
  }
  return "—";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex flex-col">
      <span className="text-xs text-muted">{label}</span>
      <span className="text-base font-semibold text-ink">{value}</span>
    </span>
  );
}

export function EmotionTimelinePanel({
  spaceName,
  state,
  events,
  error
}: {
  spaceName: string;
  state: EmotionState | null;
  events: DeviceEvent[];
  error: string | null;
}) {
  const emotionEvents = events.filter((event) => event.event_type === "emotion_detected");

  return (
    <div className="space-y-6">
      {error ? (
        <p className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">{error}</p>
      ) : null}

      <section className="rounded-xl border border-line bg-white p-5">
        <h2 className="text-sm font-semibold text-ink">当前情绪 · {spaceName}</h2>
        {state ? (
          <div className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-3">
            <span className="text-3xl">{emotionDisplay(state.primary_emotion)}</span>
            <Stat label="效价 valence" value={state.valence.toFixed(2)} />
            <Stat label="唤醒 arousal" value={state.arousal.toFixed(2)} />
            <Stat label="置信度" value={state.confidence.toFixed(2)} />
            <Stat label="语言" value={state.language} />
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted">
            该空间暂无情绪状态。需先在「空间」把摄像头与情绪识别开成 local_only，再由情绪采集上报。
          </p>
        )}
      </section>

      <section className="rounded-xl border border-line bg-white p-5">
        <h2 className="text-sm font-semibold text-ink">情绪轨迹</h2>
        {emotionEvents.length === 0 ? (
          <p className="mt-3 text-sm text-muted">暂无情绪事件。</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {emotionEvents.map((event) => {
              const attributes = event.attributes ?? {};
              return (
                <li key={event.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
                  <span className="font-medium text-ink">{emotionDisplay(attributes.primary_emotion)}</span>
                  <span className="text-xs text-muted">语言 {String(attributes.language ?? "—")}</span>
                  <span className="text-xs text-muted">{new Date(event.captured_at).toLocaleString("zh-CN")}</span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-4 text-xs text-muted">
          情绪为只读感知结果，不存原始音视频；驱动机器人动作须经策略门控与确认。
        </p>
      </section>
    </div>
  );
}
