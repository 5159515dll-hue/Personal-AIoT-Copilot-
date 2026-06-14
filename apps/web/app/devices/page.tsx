import Link from "next/link";
import { Cable } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { DeviceControlPanel } from "@/components/device-control-panel";
import { DeviceManagementPanel } from "@/components/device-management-panel";
import { NodePanel } from "@/components/node-panel";
import { PageHeader } from "@/components/page-header";
import { getDevices, getManagedDevices, getNodes } from "@/lib/api";
import type { Device, ManagedDevice, NodeSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DevicesPage() {
  let nodes: NodeSummary[] = [];
  try {
    nodes = await getNodes();
  } catch {
    nodes = [];
  }

  let devices: Device[] = [];
  try {
    devices = await getDevices();
  } catch {
    devices = [];
  }

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
        description="先看接入的传感器节点及其传感器；下方是设备管理与控制框架（接入真实可控设备后启用）。"
        action={
          <Link
            href="/hardware"
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Cable size={16} aria-hidden />
            接入帮助
          </Link>
        }
      />
      <div className="space-y-6">
        <NodePanel nodes={nodes} />
        <DeviceManagementPanel initialDevices={managedDevices} error={managementError} />
        <DeviceControlPanel devices={devices} />
      </div>
    </AppShell>
  );
}
