import { AppShell } from "@/components/app-shell";
import { DeviceControlPanel } from "@/components/device-control-panel";
import { DeviceManagementPanel } from "@/components/device-management-panel";
import { PageHeader } from "@/components/page-header";
import { getDevices, getManagedDevices } from "@/lib/api";
import type { ManagedDevice } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DevicesPage() {
  const devices = await getDevices();
  let managedDevices: ManagedDevice[] = [];
  let managementError: string | null = null;
  try {
    managedDevices = await getManagedDevices();
  } catch (error) {
    managementError = error instanceof Error ? error.message : "设备管理后台暂不可用";
  }

  return (
    <AppShell>
      <PageHeader
        title="设备"
        description="真实硬件绑定、负载标记、手动下线和策略控制演示集中在这里管理。"
      />
      <DeviceManagementPanel initialDevices={managedDevices} error={managementError} />
      <DeviceControlPanel devices={devices} />
    </AppShell>
  );
}
