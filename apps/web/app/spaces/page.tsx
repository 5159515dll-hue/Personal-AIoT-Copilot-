import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { SpaceSettingsPanel } from "@/components/space-settings-panel";
import { getSpaces } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SpacesPage() {
  const spaces = await getSpaces();

  return (
    <AppShell>
      <PageHeader
        title="房间设置"
        description="管理多个房间、区域、设备绑定和未来感知能力边界。摄像头、人脸、情绪和定位当前只保存规划状态，不启用真实采集。"
      />
      <SpaceSettingsPanel initialSpaces={spaces} />
    </AppShell>
  );
}
