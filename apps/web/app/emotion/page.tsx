import { AppShell } from "@/components/app-shell";
import { CompanionCharacterManager } from "@/components/companion-character-manager";
import { CompanionConsole } from "@/components/companion-console";
import { CompanionMemoryPanel } from "@/components/companion-memory-panel";
import { EmotionTimelinePanel } from "@/components/emotion-timeline-panel";
import { PageHeader } from "@/components/page-header";
import {
  getCompanionMemory,
  getCurrentSpace,
  getDeviceEvents,
  getEmotionState,
  listCompanionCharacters
} from "@/lib/api";
import type { CompanionPersona, DeviceEvent, EmotionState, MemorySnapshot, RoomSpace } from "@/lib/types";

const DEFAULT_PERSONA: CompanionPersona = {
  id: "xiaonuan",
  name: "小暖",
  archetype: "gentle_healing",
  companion_for: "",
  notes: null,
  active: true
};

const EMPTY_MEMORY: MemorySnapshot = { profile: null, episodes: [] };

export const dynamic = "force-dynamic";

export default async function EmotionPage() {
  let space: RoomSpace | null = null;
  let state: EmotionState | null = null;
  let events: DeviceEvent[] = [];
  let characters: CompanionPersona[] = [DEFAULT_PERSONA];
  let memory: MemorySnapshot = EMPTY_MEMORY;
  let error: string | null = null;

  try {
    space = await getCurrentSpace();
    [state, events, characters, memory] = await Promise.all([
      getEmotionState(space.id),
      getDeviceEvents({ event_type: "emotion_detected", limit: 50 }),
      listCompanionCharacters(),
      getCompanionMemory()
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "情绪数据暂不可用";
  }

  const spaceId = space?.id ?? "space_study_001";
  const activePersona = characters.find((character) => character.active) ?? characters[0] ?? DEFAULT_PERSONA;

  return (
    <AppShell>
      <PageHeader
        title="情感陪伴"
        description="多模态情绪感知（面部 + 语音 + 文本）与情感陪伴回路；蒙古语作为感知侧特色，回应先中/英。情绪只读，机器人动作经策略门控。"
      />
      <div className="space-y-6">
        <CompanionConsole
          key={activePersona.id}
          spaceId={spaceId}
          initialPersona={activePersona}
          hasEmotionState={Boolean(state)}
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <CompanionCharacterManager characters={characters} />
          <CompanionMemoryPanel memory={memory} characterName={activePersona.name} />
        </div>
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
