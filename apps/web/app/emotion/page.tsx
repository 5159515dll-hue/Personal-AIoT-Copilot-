import { AppShell } from "@/components/app-shell";
import { EmotionTimelinePanel } from "@/components/emotion-timeline-panel";
import { PageHeader } from "@/components/page-header";
import { getCurrentSpace, getDeviceEvents, getEmotionState } from "@/lib/api";
import type { DeviceEvent, EmotionState, RoomSpace } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function EmotionPage() {
  let space: RoomSpace | null = null;
  let state: EmotionState | null = null;
  let events: DeviceEvent[] = [];
  let error: string | null = null;

  try {
    space = await getCurrentSpace();
    [state, events] = await Promise.all([
      getEmotionState(space.id),
      getDeviceEvents({ event_type: "emotion_detected", limit: 50 })
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "情绪数据暂不可用";
  }

  return (
    <AppShell>
      <PageHeader
        title="情感陪伴"
        description="多模态情绪感知（面部 + 语音 + 文本）与情感陪伴回路；蒙古语作为感知侧特色，回应先中/英。情绪只读，机器人动作经策略门控。"
      />
      <EmotionTimelinePanel
        spaceName={space?.name ?? "当前空间"}
        state={state}
        events={events}
        error={error}
      />
    </AppShell>
  );
}
