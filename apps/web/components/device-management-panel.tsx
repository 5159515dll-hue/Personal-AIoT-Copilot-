"use client";

import { useMemo, useState } from "react";
import { Ban, Boxes, CheckSquare, Cpu, KeyRound, Plus, Save, Square, Trash2, Unplug } from "lucide-react";
import {
  batchUpdateDeviceManagement,
  createDeviceManagement,
  deleteDeviceManagement,
  issueDeviceCredential,
  markDeviceOffline,
  updateDeviceManagement
} from "@/lib/api";
import type {
  DeviceBatchManagementItem,
  DeviceManagementCreate,
  DeviceManagementUpdate,
  ManagedDevice
} from "@/lib/types";
import {
  deviceTypeLabel,
  formatDateTime,
  loadTypeLabel,
  riskLabel,
  statusLabel
} from "@/lib/format";
import { RiskPill } from "./risk-pill";

const riskOptions = ["read_only", "low", "medium", "high", "forbidden"] as const;
const loadTypeOptions = [
  "none",
  "low_voltage_light",
  "usb_fan",
  "indicator",
  "relay_unknown",
  "high_power",
  "safety_critical",
  "other"
] as const;
const transportOptions = ["mqtt", "http", "serial_gateway", "edge_gateway"] as const;
const deviceTypeOptions = [
  "esp32",
  "stm32",
  "raspberry_pi",
  "linux_gateway",
  "sensor_node",
  "smart_light",
  "ir_remote",
  "smart_plug",
  "safety_alarm",
  "other"
] as const;
const defaultCreateDraft: DeviceManagementCreate = {
  device_id: "",
  name: "",
  display_name: "",
  device_type: "sensor_node",
  transport: "mqtt",
  protocol_version: "aiot.v1",
  firmware_version: "",
  hardware_revision: "",
  location: "书房",
  risk_level: "read_only",
  controllable: false,
  requires_confirmation: false,
  connected_appliance: "",
  max_active_duration_minutes: null,
  load_type: "none",
  load_label: "",
  load_power_watts: null,
  management_note: "",
  tags: [],
  metadata: {}
};

type DraftMap = Record<string, DeviceManagementUpdate>;

export function DeviceManagementPanel({
  initialDevices,
  error
}: {
  initialDevices: ManagedDevice[];
  error?: string | null;
}) {
  const [items, setItems] = useState(initialDevices);
  const [drafts, setDrafts] = useState<DraftMap>(() => Object.fromEntries(initialDevices.map((item) => [item.device.id, draftFromItem(item)])));
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState(error ?? null);
  const [createDraft, setCreateDraft] = useState<DeviceManagementCreate>(defaultCreateDraft);
  const [batchRisk, setBatchRisk] = useState<DeviceManagementUpdate["risk_level"]>("read_only");
  const [batchLoadType, setBatchLoadType] = useState("none");
  const [batchLoadLabel, setBatchLoadLabel] = useState("");

  const selectedItems = useMemo(() => items.filter((item) => selected.has(item.device.id)), [items, selected]);

  function updateDraft(deviceId: string, patch: DeviceManagementUpdate) {
    setDrafts((current) => ({
      ...current,
      [deviceId]: {
        ...current[deviceId],
        ...patch
      }
    }));
  }

  function updateCreateDraft(patch: Partial<DeviceManagementCreate>) {
    setCreateDraft((current) => ({
      ...current,
      ...patch
    }));
  }

  function toggleSelected(deviceId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(deviceId)) {
        next.delete(deviceId);
      } else {
        next.add(deviceId);
      }
      return next;
    });
  }

  function replaceItem(updated: ManagedDevice) {
    setItems((current) => current.map((item) => (item.device.id === updated.device.id ? updated : item)));
    setDrafts((current) => ({ ...current, [updated.device.id]: draftFromItem(updated) }));
  }

  async function createDevice() {
    const deviceId = createDraft.device_id.trim();
    const name = createDraft.name.trim();
    if (!deviceId || !name) {
      setMessage("请填写设备编号和显示名称。");
      return;
    }
    setPending("create");
    setMessage(null);
    try {
      const response = await createDeviceManagement({
        ...createDraft,
        device_id: deviceId,
        name,
        display_name: createDraft.display_name?.trim() || name,
        location: createDraft.location.trim() || "unknown",
        protocol_version: createDraft.protocol_version.trim() || "aiot.v1",
        firmware_version: createDraft.firmware_version?.trim() || null,
        hardware_revision: createDraft.hardware_revision?.trim() || null,
        connected_appliance: createDraft.connected_appliance?.trim() || null,
        load_label: createDraft.load_label?.trim() || null,
        management_note: createDraft.management_note?.trim() || null,
        controllable: createDraft.risk_level === "low" ? createDraft.controllable : false,
        requires_confirmation: createDraft.risk_level === "medium" ? true : createDraft.requires_confirmation
      });
      setItems((current) => [response.item, ...current.filter((item) => item.device.id !== response.item.device.id)]);
      setDrafts((current) => ({ ...current, [response.item.device.id]: draftFromItem(response.item) }));
      setCreateDraft(defaultCreateDraft);
      setMessage(`设备 ${response.item.device.id} 已创建，审计编号：${response.audit_log_id}`);
    } catch (createError) {
      setMessage(createError instanceof Error ? createError.message : "设备创建失败");
    } finally {
      setPending(null);
    }
  }

  async function saveDevice(item: ManagedDevice) {
    setPending(item.device.id);
    setMessage(null);
    try {
      const response = await updateDeviceManagement(item.device.id, drafts[item.device.id] ?? {});
      replaceItem(response.item);
      setMessage(`设备 ${response.item.device.id} 已保存，审计编号：${response.audit_log_id}`);
    } catch (saveError) {
      setMessage(saveError instanceof Error ? saveError.message : "设备保存失败");
    } finally {
      setPending(null);
    }
  }

  async function offlineDevice(item: ManagedDevice) {
    setPending(item.device.id);
    setMessage(null);
    try {
      const response = await markDeviceOffline(item.device.id, "后台设备管理手动下线");
      replaceItem(response.item);
      setMessage(`设备 ${response.item.device.id} 已下线，审计编号：${response.audit_log_id}`);
    } catch (offlineError) {
      setMessage(offlineError instanceof Error ? offlineError.message : "设备下线失败");
    } finally {
      setPending(null);
    }
  }

  async function deleteDevice(item: ManagedDevice) {
    const confirmed = window.confirm(`确认删除设备档案 ${item.device.id}？历史遥测数据会保留，硬件重新上报后会重新进入后台。`);
    if (!confirmed) {
      return;
    }
    setPending(item.device.id);
    setMessage(null);
    try {
      const response = await deleteDeviceManagement(item.device.id);
      setItems((current) => current.filter((currentItem) => currentItem.device.id !== response.device_id));
      setDrafts((current) => {
        const next = { ...current };
        delete next[response.device_id];
        return next;
      });
      setSelected((current) => {
        const next = new Set(current);
        next.delete(response.device_id);
        return next;
      });
      setMessage(`设备 ${response.device_id} 已删除，审计编号：${response.audit_log_id}`);
    } catch (deleteError) {
      setMessage(deleteError instanceof Error ? deleteError.message : "设备删除失败");
    } finally {
      setPending(null);
    }
  }

  async function issueCredential(item: ManagedDevice) {
    const confirmed = window.confirm(`确认生成或轮换设备 ${item.device.id} 的上报令牌？旧令牌会失效。`);
    if (!confirmed) {
      return;
    }
    setPending(`credential:${item.device.id}`);
    setMessage(null);
    try {
      const response = await issueDeviceCredential(item.device.id);
      setMessage(`设备 ${item.device.id} 的令牌已生成，仅显示一次：${response.token}。审计编号：${response.audit_log_id}`);
    } catch (credentialError) {
      setMessage(credentialError instanceof Error ? credentialError.message : "设备令牌生成失败");
    } finally {
      setPending(null);
    }
  }

  async function applyBatch() {
    if (selectedItems.length === 0) {
      setMessage("请先选择至少一个设备。");
      return;
    }
    setPending("batch");
    setMessage(null);
    const payload: DeviceBatchManagementItem[] = selectedItems.map((item) => ({
      device_id: item.device.id,
      risk_level: batchRisk,
      controllable: batchRisk === "low",
      requires_confirmation: batchRisk === "medium",
      load_type: batchLoadType,
      load_label: batchLoadLabel.trim() || null
    }));
    try {
      const response = await batchUpdateDeviceManagement(payload);
      setItems((current) =>
        current.map((item) => response.updated.find((updated) => updated.device.id === item.device.id) ?? item)
      );
      setDrafts((current) => ({
        ...current,
        ...Object.fromEntries(response.updated.map((item) => [item.device.id, draftFromItem(item)]))
      }));
      setMessage(
        response.failed.length
          ? `批量管理完成，成功 ${response.updated.length} 个，失败 ${response.failed.length} 个。`
          : `批量管理完成，成功 ${response.updated.length} 个。`
      );
    } catch (batchError) {
      setMessage(batchError instanceof Error ? batchError.message : "批量管理失败");
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="mb-6 rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
            <Cpu size={18} aria-hidden />
            真实硬件后台管理
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            绑定真实设备、标记负载、手动下线和批量更新。新设备默认只读，只有明确低风险负载才允许进入控制链路。
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[140px_150px_minmax(0,180px)_auto]">
          <select
            value={batchRisk ?? "read_only"}
            onChange={(event) => setBatchRisk(event.target.value as DeviceManagementUpdate["risk_level"])}
            className="focus-ring h-10 rounded-lg border border-line bg-white px-3 text-sm"
            title="批量风险等级"
          >
            {riskOptions.map((risk) => (
              <option key={risk} value={risk}>
                {riskLabel(risk)}
              </option>
            ))}
          </select>
          <select
            value={batchLoadType}
            onChange={(event) => setBatchLoadType(event.target.value)}
            className="focus-ring h-10 rounded-lg border border-line bg-white px-3 text-sm"
            title="批量负载类型"
          >
            {loadTypeOptions.map((loadType) => (
              <option key={loadType} value={loadType}>
                {loadTypeLabel(loadType)}
              </option>
            ))}
          </select>
          <input
            value={batchLoadLabel}
            onChange={(event) => setBatchLoadLabel(event.target.value)}
            className="focus-ring h-10 rounded-lg border border-line bg-white px-3 text-sm"
            placeholder="批量负载名称"
          />
          <button
            type="button"
            onClick={() => void applyBatch()}
            disabled={pending === "batch"}
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-ink px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Boxes size={16} aria-hidden />
            批量应用
          </button>
        </div>
      </div>

      {message && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-700">{message}</p>}

      <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Plus size={16} aria-hidden />
              新建设备
            </h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              可先为未到货硬件预建设备编号；ESP32、STM32、树莓派后续用同一个编号上报即可自动绑定。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void createDevice()}
            disabled={pending === "create"}
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Plus size={16} aria-hidden />
            新建设备
          </button>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <TextField label="设备编号" value={createDraft.device_id} onChange={(value) => updateCreateDraft({ device_id: value })} />
          <TextField label="显示名称" value={createDraft.name} onChange={(value) => updateCreateDraft({ name: value, display_name: value })} />
          <SelectField
            label="设备类型"
            value={createDraft.device_type}
            options={deviceTypeOptions.map((value) => ({ value, label: deviceTypeLabel(value) }))}
            onChange={(value) => updateCreateDraft({ device_type: value })}
          />
          <SelectField
            label="传输"
            value={createDraft.transport}
            options={transportOptions.map((value) => ({ value, label: statusLabel(value) }))}
            onChange={(value) => updateCreateDraft({ transport: value as DeviceManagementCreate["transport"] })}
          />
          <TextField label="协议版本" value={createDraft.protocol_version} onChange={(value) => updateCreateDraft({ protocol_version: value })} />
          <TextField label="位置" value={createDraft.location} onChange={(value) => updateCreateDraft({ location: value })} />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1fr_auto_auto]">
          <SelectField
            label="风险"
            value={createDraft.risk_level}
            options={riskOptions.map((value) => ({ value, label: riskLabel(value) }))}
            onChange={(value) => updateCreateDraft({ risk_level: value as DeviceManagementCreate["risk_level"] })}
          />
          <SelectField
            label="负载类型"
            value={String(createDraft.load_type ?? "none")}
            options={loadTypeOptions.map((value) => ({ value, label: loadTypeLabel(value) }))}
            onChange={(value) => updateCreateDraft({ load_type: value })}
          />
          <TextField label="负载名称" value={createDraft.load_label ?? ""} onChange={(value) => updateCreateDraft({ load_label: value })} />
          <TextField label="硬件版本" value={createDraft.hardware_revision ?? ""} onChange={(value) => updateCreateDraft({ hardware_revision: value })} />
          <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700 xl:mt-5">
            <input
              type="checkbox"
              checked={Boolean(createDraft.controllable)}
              onChange={(event) => updateCreateDraft({ controllable: event.target.checked })}
              className="h-4 w-4 rounded border-line text-teal-600"
            />
            可控
          </label>
          <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700 xl:mt-5">
            <input
              type="checkbox"
              checked={Boolean(createDraft.requires_confirmation)}
              onChange={(event) => updateCreateDraft({ requires_confirmation: event.target.checked })}
              className="h-4 w-4 rounded border-line text-teal-600"
            />
            需确认
          </label>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {items.map((item) => {
          const draft = drafts[item.device.id] ?? draftFromItem(item);
          const checked = selected.has(item.device.id);
          return (
            <article key={item.device.id} className="rounded-lg border border-line bg-slate-50 p-3">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                <button
                  type="button"
                  onClick={() => toggleSelected(item.device.id)}
                  className="focus-ring flex items-start gap-3 rounded-lg text-left"
                >
                  <span className="mt-1 text-teal-700">
                    {checked ? <CheckSquare size={18} aria-hidden /> : <Square size={18} aria-hidden />}
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-ink">{item.device.name}</span>
                    <span className="mt-1 block break-all text-xs leading-5 text-muted">
                      设备编号：{item.device.id} · {deviceTypeLabel(item.device.type)} · {statusLabel(item.binding_status)}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-muted">
                      最近在线：
                      {item.connection?.last_seen_at ? formatDateTime(item.connection.last_seen_at) : "暂无真实心跳"}
                    </span>
                  </span>
                </button>
                <div className="flex flex-wrap gap-2">
                  <RiskPill risk={item.device.risk_level} />
                  <span className="inline-flex h-7 items-center rounded-md bg-white px-2 text-xs font-semibold text-slate-600">
                    {statusLabel(item.device.online_state)}
                  </span>
                  <span className="inline-flex h-7 items-center rounded-md bg-white px-2 text-xs font-semibold text-slate-600">
                    {loadTypeLabel(stringValue(item.load_mark.type))}
                  </span>
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                <TextField label="显示名称" value={draft.name ?? ""} onChange={(value) => updateDraft(item.device.id, { name: value })} />
                <TextField label="位置" value={draft.location ?? ""} onChange={(value) => updateDraft(item.device.id, { location: value })} />
                <SelectField
                  label="传输"
                  value={draft.transport ?? item.connection?.transport ?? "mqtt"}
                  options={transportOptions.map((value) => ({ value, label: statusLabel(value) }))}
                  onChange={(value) => updateDraft(item.device.id, { transport: value as DeviceManagementUpdate["transport"] })}
                />
                <SelectField
                  label="风险"
                  value={draft.risk_level ?? item.device.risk_level}
                  options={riskOptions.map((value) => ({ value, label: riskLabel(value) }))}
                  onChange={(value) => updateDraft(item.device.id, { risk_level: value as DeviceManagementUpdate["risk_level"] })}
                />
                <SelectField
                  label="负载类型"
                  value={String(draft.load_type ?? "none")}
                  options={loadTypeOptions.map((value) => ({ value, label: loadTypeLabel(value) }))}
                  onChange={(value) => updateDraft(item.device.id, { load_type: value })}
                />
                <TextField
                  label="负载名称"
                  value={draft.load_label ?? ""}
                  onChange={(value) => updateDraft(item.device.id, { load_label: value })}
                />
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto_auto]">
                <TextField
                  label="固件版本"
                  value={draft.firmware_version ?? ""}
                  onChange={(value) => updateDraft(item.device.id, { firmware_version: value })}
                />
                <TextField
                  label="硬件版本"
                  value={draft.hardware_revision ?? ""}
                  onChange={(value) => updateDraft(item.device.id, { hardware_revision: value })}
                />
                <TextField
                  label="管理备注"
                  value={draft.management_note ?? ""}
                  onChange={(value) => updateDraft(item.device.id, { management_note: value })}
                />
                <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700 xl:mt-5">
                  <input
                    type="checkbox"
                    checked={Boolean(draft.controllable)}
                    onChange={(event) => updateDraft(item.device.id, { controllable: event.target.checked })}
                    className="h-4 w-4 rounded border-line text-teal-600"
                  />
                  可控
                </label>
                <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700 xl:mt-5">
                  <input
                    type="checkbox"
                    checked={Boolean(draft.requires_confirmation)}
                    onChange={(event) => updateDraft(item.device.id, { requires_confirmation: event.target.checked })}
                    className="h-4 w-4 rounded border-line text-teal-600"
                  />
                  需确认
                </label>
              </div>

              {item.management_flags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.management_flags.map((flag) => (
                    <span key={flag} className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
                      {flag}
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void saveDevice(item)}
                  disabled={pending === item.device.id}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Save size={16} aria-hidden />
                  保存绑定
                </button>
                <button
                  type="button"
                  onClick={() => void offlineDevice(item)}
                  disabled={pending === item.device.id}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Unplug size={16} aria-hidden />
                  手动下线
                </button>
                <button
                  type="button"
                  onClick={() => void issueCredential(item)}
                  disabled={pending === `credential:${item.device.id}`}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <KeyRound size={16} aria-hidden />
                  设备令牌
                </button>
                <button
                  type="button"
                  onClick={() => void deleteDevice(item)}
                  disabled={pending === item.device.id}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-rose-200 bg-white px-3 text-sm font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Trash2 size={16} aria-hidden />
                  删除档案
                </button>
              </div>
            </article>
          );
        })}

        {items.length === 0 && (
          <div className="rounded-lg border border-dashed border-line bg-slate-50 p-6 text-sm leading-6 text-muted">
            <p className="flex items-center gap-2 font-semibold text-slate-700">
              <Ban size={16} aria-hidden />
              暂无真实硬件记录
            </p>
            <p className="mt-2">可以先在上方新建设备档案；硬件到齐后，使用同一个设备编号调用注册、心跳或遥测接口完成绑定。</p>
          </div>
        )}
      </div>
    </section>
  );
}

function draftFromItem(item: ManagedDevice): DeviceManagementUpdate {
  return {
    name: item.device.name,
    display_name: item.connection?.display_name ?? item.device.name,
    device_type: item.connection?.device_type ?? item.device.type,
    transport: (item.connection?.transport as DeviceManagementUpdate["transport"]) ?? "mqtt",
    firmware_version: item.connection?.firmware_version ?? "",
    hardware_revision: item.connection?.hardware_revision ?? "",
    location: item.device.location,
    risk_level: item.device.risk_level,
    controllable: item.device.controllable,
    requires_confirmation: item.device.requires_confirmation,
    connected_appliance: item.device.connected_appliance ?? "",
    max_active_duration_minutes: item.device.max_active_duration_minutes ?? null,
    load_type: stringValue(item.load_mark.type) ?? "none",
    load_label: stringValue(item.load_mark.label) ?? "",
    load_power_watts: numberValue(item.load_mark.power_watts) ?? null,
    management_note: stringValue(item.device.current_state.management_note) ?? "",
    tags: Array.isArray(item.device.current_state.tags) ? item.device.current_state.tags.map(String) : []
  };
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
