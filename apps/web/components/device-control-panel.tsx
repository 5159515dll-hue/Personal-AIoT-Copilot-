"use client";

import { useState } from "react";
import { CheckCircle2, Power, ShieldAlert } from "lucide-react";
import { controlDevice } from "@/lib/api";
import type { ControlDeviceResponse, Device } from "@/lib/types";
import { applianceLabel, deviceTypeLabel, locationLabel, statusLabel, translatedState } from "@/lib/format";
import { RiskPill } from "./risk-pill";

type PendingConfirmation = {
  state: "on" | "off";
  auditLogId: string;
};

export function DeviceControlPanel({ devices }: { devices: Device[] }) {
  const [deviceList, setDeviceList] = useState(devices);
  const [results, setResults] = useState<Record<string, ControlDeviceResponse | string>>({});
  const [confirmations, setConfirmations] = useState<Record<string, PendingConfirmation | undefined>>({});
  const [pending, setPending] = useState<string | null>(null);

  async function handleControl(device: Device, state: "on" | "off", confirmed = false) {
    setPending(device.id);
    try {
      const response = await controlDevice(device.id, state, confirmed);
      const updatedDevice = response.device;
      if (updatedDevice) {
        setDeviceList((current) => current.map((item) => (item.id === updatedDevice.id ? updatedDevice : item)));
      }
      if (response.execution_result === "requires_confirmation") {
        setConfirmations((current) => ({
          ...current,
          [device.id]: { state, auditLogId: response.audit_log_id }
        }));
      } else {
        setConfirmations((current) => {
          const next = { ...current };
          delete next[device.id];
          return next;
        });
      }
      setResults((current) => ({ ...current, [device.id]: response }));
    } catch (error) {
      setResults((current) => ({
        ...current,
        [device.id]: error instanceof Error ? error.message : "控制失败"
      }));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {deviceList.map((device) => {
        const result = results[device.id];
        const confirmation = confirmations[device.id];
        return (
          <section key={device.id} className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-ink">{device.name}</h2>
                <p className="mt-1 text-sm text-muted">
                  {deviceTypeLabel(device.type)} · {locationLabel(device.location)} · {statusLabel(device.online_state)}
                </p>
              </div>
              <RiskPill risk={device.risk_level} />
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs font-semibold text-muted">是否可控</dt>
                <dd className="mt-1 font-medium text-ink">{device.controllable ? "是" : "否"}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">连接设备</dt>
                <dd className="mt-1 font-medium text-ink">{applianceLabel(device.connected_appliance)}</dd>
              </div>
            </dl>

            <pre className="mt-4 overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-700">
              {JSON.stringify(translatedState(device.current_state), null, 2)}
            </pre>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleControl(device, "on")}
                disabled={pending === device.id}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                title="请求经过策略检查的模拟开启"
              >
                <Power size={16} aria-hidden />
                开启
              </button>
              <button
                type="button"
                onClick={() => handleControl(device, "off")}
                disabled={pending === device.id}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                title="请求经过策略检查的模拟关闭"
              >
                <Power size={16} aria-hidden />
                关闭
              </button>
            </div>

            {result && (
              <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3 text-sm">
                {typeof result === "string" ? (
                  <p className="break-words text-rose-700">{result}</p>
                ) : (
                  <div className="space-y-2">
                    <p className="flex items-center gap-2 font-semibold text-ink">
                      <ShieldAlert size={16} aria-hidden />
                      {statusLabel(result.execution_result)}
                    </p>
                    <p className="text-muted">{result.policy.reason}</p>
                    <p className="text-xs text-muted">审计编号：{result.audit_log_id}</p>
                    {result.execution_result === "requires_confirmation" && confirmation && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
                        <p className="text-sm font-semibold">需要二次确认：{confirmation.state === "on" ? "开启" : "关闭"}该中风险模拟设备。</p>
                        <p className="mt-1 text-xs leading-5 opacity-80">确认请求审计编号：{confirmation.auditLogId}</p>
                        <button
                          type="button"
                          onClick={() => handleControl(device, confirmation.state, true)}
                          disabled={pending === device.id}
                          className="focus-ring mt-3 inline-flex h-9 items-center gap-2 rounded-lg bg-amber-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <CheckCircle2 size={16} aria-hidden />
                          确认执行
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
