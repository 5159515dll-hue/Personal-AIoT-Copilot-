"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, EyeOff, Plus, Save, Trash2 } from "lucide-react";
import { activateSpace, createSpace, deleteSpace, updateSpace } from "@/lib/api";
import type { RoomSpace, RoomSpaceCreate, RoomSpaceUpdate, SpaceCapabilityStatus, SpacePerceptionSettings } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

const spaceTypeOptions = ["study", "bedroom", "living_room", "lab", "balcony", "kitchen", "other"] as const;
const capabilityOptions = ["disabled", "planned", "local_only"] as const;

const defaultPerception: SpacePerceptionSettings = {
  camera: "disabled",
  face_recognition: "disabled",
  emotion_recognition: "disabled",
  location_tracking: "disabled",
  image_retention: "none",
  privacy_mode: "strict",
  media_policy: {
    allow_realtime_stream: false,
    allow_event_media: false,
    media_retention_days: 7,
    event_retention_days: 30
  },
  notes: "当前版本只保存规划状态，不采集图像、人脸、情绪或精确位置。"
};

const defaultCreateDraft: RoomSpaceCreate = {
  name: "",
  space_type: "study",
  location_label: "书房",
  floor: "",
  timezone: "Asia/Shanghai",
  device_ids: [],
  zones: ["书桌"],
  perception: defaultPerception,
  notes: ""
};

type SpaceDraft = RoomSpaceUpdate & {
  device_ids_text: string;
  zones_text: string;
};

export function SpaceSettingsPanel({ initialSpaces }: { initialSpaces: RoomSpace[] }) {
  const [spaces, setSpaces] = useState(initialSpaces);
  const [createDraft, setCreateDraft] = useState<RoomSpaceCreate>(defaultCreateDraft);
  const [drafts, setDrafts] = useState<Record<string, SpaceDraft>>(() =>
    Object.fromEntries(initialSpaces.map((space) => [space.id, draftFromSpace(space)]))
  );
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const activeSpace = useMemo(() => spaces.find((space) => space.is_active) ?? spaces[0] ?? null, [spaces]);

  function updateCreateDraft(patch: Partial<RoomSpaceCreate>) {
    setCreateDraft((current) => ({ ...current, ...patch }));
  }

  function updateCreatePerception(patch: Partial<SpacePerceptionSettings>) {
    setCreateDraft((current) => ({
      ...current,
      perception: { ...current.perception, ...patch }
    }));
  }

  function updateDraft(spaceId: string, patch: Partial<SpaceDraft>) {
    setDrafts((current) => ({
      ...current,
      [spaceId]: {
        ...current[spaceId],
        ...patch
      }
    }));
  }

  function updateDraftPerception(spaceId: string, patch: Partial<SpacePerceptionSettings>) {
    setDrafts((current) => ({
      ...current,
      [spaceId]: {
        ...current[spaceId],
        perception: {
          ...(current[spaceId]?.perception ?? defaultPerception),
          ...patch
        }
      }
    }));
  }

  function replaceSpace(space: RoomSpace) {
    setSpaces((current) => current.map((item) => (item.id === space.id ? space : item)));
    setDrafts((current) => ({ ...current, [space.id]: draftFromSpace(space) }));
  }

  async function createRoomSpace() {
    if (!createDraft.name.trim()) {
      setMessage("请填写空间名称。");
      return;
    }
    setPending("create");
    setMessage(null);
    try {
      const response = await createSpace({
        ...createDraft,
        name: createDraft.name.trim(),
        location_label: createDraft.location_label.trim() || "未命名位置",
        floor: createDraft.floor?.trim() || null,
        device_ids: createDraft.device_ids,
        zones: createDraft.zones,
        notes: createDraft.notes?.trim() || null
      });
      setSpaces((current) => [...current, response.space]);
      setDrafts((current) => ({ ...current, [response.space.id]: draftFromSpace(response.space) }));
      setCreateDraft(defaultCreateDraft);
      setMessage(`空间 ${response.space.name} 已创建，审计编号：${response.audit_log_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "空间创建失败");
    } finally {
      setPending(null);
    }
  }

  async function saveRoomSpace(space: RoomSpace) {
    const draft = drafts[space.id] ?? draftFromSpace(space);
    setPending(space.id);
    setMessage(null);
    try {
      const response = await updateSpace(space.id, {
        name: draft.name?.trim() || space.name,
        space_type: draft.space_type,
        location_label: draft.location_label?.trim() || space.location_label,
        floor: draft.floor?.trim() || null,
        timezone: draft.timezone?.trim() || "Asia/Shanghai",
        device_ids: csvToList(draft.device_ids_text),
        zones: csvToList(draft.zones_text),
        perception: draft.perception,
        notes: draft.notes?.trim() || null
      });
      replaceSpace(response.space);
      setMessage(`空间 ${response.space.name} 已保存，审计编号：${response.audit_log_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "空间保存失败");
    } finally {
      setPending(null);
    }
  }

  async function activateRoomSpace(space: RoomSpace) {
    setPending(`activate:${space.id}`);
    setMessage(null);
    try {
      const response = await activateSpace(space.id);
      setSpaces((current) => current.map((item) => (item.id === response.space.id ? response.space : { ...item, is_active: false })));
      setDrafts((current) => ({ ...current, [response.space.id]: draftFromSpace(response.space) }));
      setMessage(`当前空间已切换为 ${response.space.name}，审计编号：${response.audit_log_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "空间切换失败");
    } finally {
      setPending(null);
    }
  }

  async function removeRoomSpace(space: RoomSpace) {
    const confirmed = window.confirm(`确认删除空间 ${space.name}？设备和历史遥测不会删除，但该空间配置会移除。`);
    if (!confirmed) {
      return;
    }
    setPending(`delete:${space.id}`);
    setMessage(null);
    try {
      const response = await deleteSpace(space.id);
      setSpaces((current) => current.filter((item) => item.id !== response.space_id));
      setDrafts((current) => {
        const next = { ...current };
        delete next[response.space_id];
        return next;
      });
      setMessage(`空间 ${space.name} 已删除，审计编号：${response.audit_log_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "空间删除失败");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="space-y-5">
        <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                <Plus size={18} aria-hidden />
                新增空间
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                可先建立书房、卧室、客厅、实验台等空间。后续树莓派摄像头或定位设备接入时，先绑定到空间再进入策略链路。
              </p>
            </div>
            <button
              type="button"
              onClick={() => void createRoomSpace()}
              disabled={pending === "create"}
              className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus size={16} aria-hidden />
              新增空间
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <TextField label="空间名称" value={createDraft.name} onChange={(value) => updateCreateDraft({ name: value })} />
            <SelectField
              label="空间类型"
              value={createDraft.space_type}
              options={spaceTypeOptions.map((value) => ({ value, label: spaceTypeLabel(value) }))}
              onChange={(value) => updateCreateDraft({ space_type: value as RoomSpace["space_type"] })}
            />
            <TextField label="位置标签" value={createDraft.location_label} onChange={(value) => updateCreateDraft({ location_label: value })} />
            <TextField label="楼层/区域" value={createDraft.floor ?? ""} onChange={(value) => updateCreateDraft({ floor: value })} />
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <TextField label="区域划分，用逗号分隔" value={createDraft.zones.join(", ")} onChange={(value) => updateCreateDraft({ zones: csvToList(value) })} />
            <TextField label="绑定设备编号，用逗号分隔" value={createDraft.device_ids.join(", ")} onChange={(value) => updateCreateDraft({ device_ids: csvToList(value) })} />
          </div>
          <PerceptionFields perception={createDraft.perception} onChange={updateCreatePerception} />
        </div>

        {message && <p className="rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-700">{message}</p>}

        {spaces.map((space) => {
          const draft = drafts[space.id] ?? draftFromSpace(space);
          return (
            <article key={space.id} className="rounded-lg border border-line bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                    {space.name}
                    {space.is_active && (
                      <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700">
                        <CheckCircle2 size={14} aria-hidden />
                        当前空间
                      </span>
                    )}
                  </h2>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    {space.id} · {spaceTypeLabel(space.space_type)} · 更新于 {formatDateTime(space.updated_at)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void activateRoomSpace(space)}
                    disabled={space.is_active || pending === `activate:${space.id}`}
                    className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CheckCircle2 size={16} aria-hidden />
                    设为当前
                  </button>
                  <button
                    type="button"
                    onClick={() => void saveRoomSpace(space)}
                    disabled={pending === space.id}
                    className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Save size={16} aria-hidden />
                    保存
                  </button>
                  <button
                    type="button"
                    onClick={() => void removeRoomSpace(space)}
                    disabled={space.is_active || pending === `delete:${space.id}`}
                    className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-rose-200 bg-white px-3 text-sm font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Trash2 size={16} aria-hidden />
                    删除
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <TextField label="空间名称" value={draft.name ?? ""} onChange={(value) => updateDraft(space.id, { name: value })} />
                <SelectField
                  label="空间类型"
                  value={String(draft.space_type ?? space.space_type)}
                  options={spaceTypeOptions.map((value) => ({ value, label: spaceTypeLabel(value) }))}
                  onChange={(value) => updateDraft(space.id, { space_type: value as RoomSpace["space_type"] })}
                />
                <TextField label="位置标签" value={draft.location_label ?? ""} onChange={(value) => updateDraft(space.id, { location_label: value })} />
                <TextField label="时区" value={draft.timezone ?? ""} onChange={(value) => updateDraft(space.id, { timezone: value })} />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <TextField label="区域划分，用逗号分隔" value={draft.zones_text} onChange={(value) => updateDraft(space.id, { zones_text: value })} />
                <TextField label="绑定设备编号，用逗号分隔" value={draft.device_ids_text} onChange={(value) => updateDraft(space.id, { device_ids_text: value })} />
              </div>
              <PerceptionFields
                perception={(draft.perception as SpacePerceptionSettings) ?? defaultPerception}
                onChange={(patch) => updateDraftPerception(space.id, patch)}
              />
            </article>
          );
        })}
      </section>

      <aside className="space-y-5">
        <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <h2 className="text-base font-semibold text-ink">当前空间</h2>
          {activeSpace ? (
            <div className="mt-3 text-sm leading-6 text-slate-700">
              <p className="font-semibold">{activeSpace.name}</p>
              <p className="text-muted">{activeSpace.location_label} · {spaceTypeLabel(activeSpace.space_type)}</p>
              <p className="mt-2">区域：{activeSpace.zones.length ? activeSpace.zones.join("、") : "未设置"}</p>
              <p>设备：{activeSpace.device_ids.length ? activeSpace.device_ids.join("、") : "未绑定"}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-muted">暂无空间配置。</p>
          )}
        </section>

        <section className="rounded-lg border border-amber-100 bg-amber-50 p-4 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-semibold text-amber-800">
            <EyeOff size={18} aria-hidden />
            视觉与身份能力边界
          </h2>
          <div className="mt-3 space-y-2 text-sm leading-6 text-amber-800/90">
            <p>默认空间不采集摄像头画面，不做人脸身份库、情绪识别或精确位置追踪。</p>
            <p>“规划中”只代表预留能力，只有“仅本地处理”并开启媒体策略后才接受树莓派边缘事件或事件媒体。</p>
            <p>未来接入树莓派摄像头时，必须先完成设备绑定、设备令牌、空间策略和审计记录。</p>
          </div>
        </section>
      </aside>
    </div>
  );
}

function PerceptionFields({
  perception,
  onChange
}: {
  perception: SpacePerceptionSettings;
  onChange: (patch: Partial<SpacePerceptionSettings>) => void;
}) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3">
      <h3 className="text-sm font-semibold text-ink">感知能力规划</h3>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SelectField label="摄像头" value={perception.camera} options={capabilitySelectOptions()} onChange={(value) => onChange({ camera: value as SpaceCapabilityStatus })} />
        <SelectField label="面部识别" value={perception.face_recognition} options={capabilitySelectOptions()} onChange={(value) => onChange({ face_recognition: value as SpaceCapabilityStatus })} />
        <SelectField label="情绪识别" value={perception.emotion_recognition} options={capabilitySelectOptions()} onChange={(value) => onChange({ emotion_recognition: value as SpaceCapabilityStatus })} />
        <SelectField label="位置定位" value={perception.location_tracking} options={capabilitySelectOptions()} onChange={(value) => onChange({ location_tracking: value as SpaceCapabilityStatus })} />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <SelectField
          label="图像保留"
          value={perception.image_retention}
          options={[
            { value: "none", label: "不保留" },
            { value: "metadata_only", label: "仅保留元数据" },
            { value: "event_media", label: "保存事件媒体" }
          ]}
          onChange={(value) => onChange({ image_retention: value as SpacePerceptionSettings["image_retention"] })}
        />
        <SelectField
          label="隐私模式"
          value={perception.privacy_mode}
          options={[
            { value: "strict", label: "严格模式" },
            { value: "local_only", label: "仅本地处理" }
          ]}
          onChange={(value) => onChange({ privacy_mode: value as SpacePerceptionSettings["privacy_mode"] })}
        />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={perception.media_policy.allow_event_media}
            onChange={(event) =>
              onChange({
                media_policy: {
                  ...perception.media_policy,
                  allow_event_media: event.target.checked
                }
              })
            }
            className="h-4 w-4 rounded border-line text-teal-600"
          />
          允许事件媒体
        </label>
        <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={perception.media_policy.allow_realtime_stream}
            onChange={(event) =>
              onChange({
                media_policy: {
                  ...perception.media_policy,
                  allow_realtime_stream: event.target.checked
                }
              })
            }
            className="h-4 w-4 rounded border-line text-teal-600"
          />
          允许实时流
        </label>
        <NumberField
          label="媒体保留天数"
          value={perception.media_policy.media_retention_days}
          onChange={(value) => onChange({ media_policy: { ...perception.media_policy, media_retention_days: value } })}
        />
        <NumberField
          label="事件保留天数"
          value={perception.media_policy.event_retention_days}
          onChange={(value) => onChange({ media_policy: { ...perception.media_policy, event_retention_days: value } })}
        />
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">
        严格模式会强制不保留图像并关闭媒体策略；“规划中”不会启用真实采集，只有“仅本地处理”可进入边缘识别链路。
      </p>
    </div>
  );
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

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <input
        type="number"
        min={1}
        max={180}
        value={value}
        onChange={(event) => onChange(Number(event.target.value || 1))}
        className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
      />
    </label>
  );
}

function capabilitySelectOptions() {
  return capabilityOptions.map((value) => ({ value, label: capabilityLabel(value) }));
}

function capabilityLabel(value: string): string {
  const labels: Record<string, string> = {
    disabled: "关闭",
    planned: "规划中",
    local_only: "仅本地处理"
  };
  return labels[value] ?? value;
}

function spaceTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    study: "书房",
    bedroom: "卧室",
    living_room: "客厅",
    lab: "实验台",
    balcony: "阳台",
    kitchen: "厨房",
    other: "其他"
  };
  return labels[value] ?? value;
}

function draftFromSpace(space: RoomSpace): SpaceDraft {
  return {
    name: space.name,
    space_type: space.space_type,
    location_label: space.location_label,
    floor: space.floor ?? "",
    timezone: space.timezone,
    device_ids: space.device_ids,
    zones: space.zones,
    device_ids_text: space.device_ids.join(", "),
    zones_text: space.zones.join(", "),
    perception: space.perception,
    notes: space.notes ?? ""
  };
}

function csvToList(value: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const part of value.split(/[，,]/)) {
    const item = part.trim();
    if (!item || seen.has(item)) {
      continue;
    }
    seen.add(item);
    result.push(item);
  }
  return result;
}
