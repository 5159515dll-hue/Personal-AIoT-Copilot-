import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { VisualMediaPanel } from "@/components/visual-media-panel";
import { getDeviceEvents, getMediaAssets, getSpaces, getStreams } from "@/lib/api";
import type { DeviceEvent, MediaAsset, StreamSource } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function VisionPage() {
  const spaces = await getSpaces();
  let events: DeviceEvent[] = [];
  let assets: MediaAsset[] = [];
  let streams: StreamSource[] = [];
  let error: string | null = null;
  try {
    [events, assets, streams] = await Promise.all([
      getDeviceEvents({ limit: 80 }),
      getMediaAssets({ limit: 80 }),
      getStreams()
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "视觉与媒体数据暂不可用";
  }

  return (
    <AppShell>
      <PageHeader
        title="视觉与媒体"
        description="查看树莓派边缘识别事件、事件图片/短视频和 RTSP 转 HLS 实时流；原始媒体访问必须经过空间策略与审计边界。"
      />
      <VisualMediaPanel
        initialSpaces={spaces}
        initialEvents={events}
        initialAssets={assets}
        initialStreams={streams}
        error={error}
      />
    </AppShell>
  );
}
