"use client";

import { useState } from "react";
import { Volume2 } from "lucide-react";
import { setCompanionVoice } from "@/lib/api";
import type { CompanionVoiceOption } from "@/lib/api";

export function CompanionVoicePanel({
  current,
  configured,
  voices
}: {
  current: string;
  configured: boolean;
  voices: CompanionVoiceOption[];
}) {
  const [selected, setSelected] = useState(current);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function choose(voice: string) {
    if (pending || voice === selected) {
      return;
    }
    const previous = selected;
    setSelected(voice);
    setPending(true);
    setMessage(null);
    try {
      const res = await setCompanionVoice(voice);
      const name = voices.find((v) => v.voice_type === res.current)?.name ?? res.current;
      setMessage(`已切换音色：${name}（下次机器人朗读即生效）`);
    } catch (error) {
      setSelected(previous);
      setMessage(error instanceof Error ? error.message : "切换音色失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
        <Volume2 size={18} aria-hidden />
        机器人音色
      </h2>
      <p className="mt-1 text-sm leading-6 text-muted">
        机器人朗读由服务器火山语音合成（比机器人自带音色自然），在这里切换音色，对聊天回复即时生效。
      </p>
      {!configured ? (
        <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-800">
          火山 TTS 暂未配置，机器人会回退到自带（机械）音色。
        </p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {voices.map((voice) => (
            <button
              key={voice.voice_type}
              type="button"
              onClick={() => void choose(voice.voice_type)}
              disabled={pending}
              className={`focus-ring rounded-lg border px-3 py-2 text-left text-sm transition disabled:opacity-60 ${
                selected === voice.voice_type
                  ? "border-teal-600 bg-teal-50 font-semibold text-teal-800"
                  : "border-line bg-white text-ink hover:border-teal-300"
              }`}
            >
              {voice.name}
            </button>
          ))}
        </div>
      )}
      {message && <p className="mt-3 text-sm leading-6 text-slate-600">{message}</p>}
    </section>
  );
}
