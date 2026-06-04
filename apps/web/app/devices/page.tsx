import { AppShell } from "@/components/app-shell";
import { DeviceControlPanel } from "@/components/device-control-panel";
import { PageHeader } from "@/components/page-header";
import { getDevices } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DevicesPage() {
  const devices = await getDevices();

  return (
    <AppShell>
      <PageHeader
        title="设备"
        description="带有明确风险元数据的模拟设备清单。当前版本只有低风险模拟灯光可免确认控制。"
      />
      <DeviceControlPanel devices={devices} />
    </AppShell>
  );
}
