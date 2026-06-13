import { AppShell } from "@/components/app-shell";
import { CompanionConsole } from "@/components/companion-console";
import { EmotionTimelinePanel } from "@/components/emotion-timeline-panel";
import { PageHeader } from "@/components/page-header";
import { getCompanionPersona, getCurrentSpace, getDeviceEvents, getEmotionState } from "@/lib/api";
import type { CompanionPersona, DeviceEvent, EmotionState, RoomSpace } from "@/lib/types";

const DEFAULT_PERSONA: CompanionPersona = {
  name: "小暖",
  archetype: "gentle_healing",
  companion_for: "",
  notes: null
};

export const dynamic = "force-dynamic";

export default async function EmotionPage() {
  let space: RoomSpace | null = null;
  let state: EmotionState | null = null;
  let events: DeviceEvent[] = [];
  let persona: CompanionPersona = DEFAULT_PERSONA;
  let error: string | null = null;

  try {
    space = await getCurrentSpace();
    [state, events, persona] = await Promise.all([
      getEmotionState(space.id),
      getDeviceEvents({ event_type: "emotion_detected", limit: 50 }),
      getCompanionPersona()
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "情绪数据暂不可用";
  }

  const spaceId = space?.id ?? "space_study_001";

  return (
    <AppShell>
      <PageHeader
        title="情感陪伴"
        description="多模态情绪感知（面部 + 语音 + 文本）与情感陪伴回路；蒙古语作为感知侧特色，回应先中/英。情绪只读，机器人动作经策略门控。"
      />
      <div className="space-y-6">
        <CompanionConsole spaceId={spaceId} initialPersona={persona} hasEmotionState={Boolean(state)} />
        <EmotionTimelinePanel
          spaceName={space?.name ?? "当前空间"}
          state={state}
          events={events}
          error={error}
        />
      </div>
    </AppShell>
  );
}
