"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Pencil, Plus, Trash2, Users, X } from "lucide-react";
import {
  activateCompanionCharacter,
  createCompanionCharacter,
  deleteCompanionCharacter,
  updateCompanionCharacter
} from "@/lib/api";
import type { CompanionArchetype, CompanionPersona } from "@/lib/types";

const ARCHETYPES: { value: CompanionArchetype; label: string }[] = [
  { value: "gentle_healing", label: "温柔治愈" },
  { value: "lively_playful", label: "活泼俏皮" },
  { value: "quiet_companion", label: "安静陪伴" }
];

type Draft = { name: string; archetype: CompanionArchetype; companion_for: string };

const EMPTY_DRAFT: Draft = { name: "", archetype: "gentle_healing", companion_for: "" };

function archetypeLabel(value: string): string {
  return ARCHETYPES.find((item) => item.value === value)?.label ?? value;
}

const FIELD_CLASS = "focus-ring mt-1 h-9 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink";

export function CompanionCharacterManager({ characters }: { characters: CompanionPersona[] }) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Draft>(EMPTY_DRAFT);
  const [showCreate, setShowCreate] = useState(false);
  const [createDraft, setCreateDraft] = useState<Draft>(EMPTY_DRAFT);

  const onlyOne = characters.length <= 1;

  async function run(action: () => Promise<unknown>, id: string, after?: () => void): Promise<void> {
    setBusyId(id);
    setError(null);
    try {
      await action();
      after?.();
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(character: CompanionPersona): void {
    setEditingId(character.id);
    setEditDraft({ name: character.name, archetype: character.archetype, companion_for: character.companion_for });
  }

  async function remove(character: CompanionPersona): Promise<void> {
    if (character.active || onlyOne) return;
    if (!window.confirm(`删除角色「${character.name}」？该角色的记忆也会一并删除，且不可恢复。`)) return;
    await run(() => deleteCompanionCharacter(character.id), character.id);
  }

  async function create(): Promise<void> {
    if (!createDraft.name.trim()) {
      setError("请先填写角色名字");
      return;
    }
    await run(
      () =>
        createCompanionCharacter({
          name: createDraft.name.trim(),
          archetype: createDraft.archetype,
          companion_for: createDraft.companion_for.trim()
        }),
      "__new__",
      () => {
        setShowCreate(false);
        setCreateDraft(EMPTY_DRAFT);
      }
    );
  }

  return (
    <section className="rounded-xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Users size={16} className="text-teal-600" aria-hidden />
          陪伴角色（{characters.length}）
        </h2>
        <button
          type="button"
          onClick={() => setShowCreate((value) => !value)}
          className="focus-ring inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-slate-500 hover:text-ink"
        >
          <Plus size={14} aria-hidden />
          新建角色
        </button>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted">
        记忆按角色独立保存，切换角色即切换记忆与人格（角色与机器人躯体解耦，记忆跟角色走）。
      </p>

      {error && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}

      {showCreate && (
        <div className="mt-3 grid gap-3 rounded-lg border border-line bg-slate-50 p-3 md:grid-cols-3">
          <label className="block">
            <span className="text-xs font-semibold text-muted">名字</span>
            <input
              value={createDraft.name}
              onChange={(event) => setCreateDraft({ ...createDraft, name: event.target.value })}
              placeholder="如：阿福"
              className={FIELD_CLASS}
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted">性格</span>
            <select
              value={createDraft.archetype}
              onChange={(event) => setCreateDraft({ ...createDraft, archetype: event.target.value as CompanionArchetype })}
              className={FIELD_CLASS}
            >
              {ARCHETYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted">主要陪伴</span>
            <input
              value={createDraft.companion_for}
              onChange={(event) => setCreateDraft({ ...createDraft, companion_for: event.target.value })}
              placeholder="如：我自己 / 奶奶"
              className={FIELD_CLASS}
            />
          </label>
          <div className="md:col-span-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => void create()}
              disabled={busyId === "__new__"}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {busyId === "__new__" ? "创建中…" : "创建角色"}
            </button>
          </div>
        </div>
      )}

      <ul className="mt-4 space-y-2">
        {characters.map((character) => (
          <li key={character.id} className="rounded-lg border border-line p-3">
            {editingId === character.id ? (
              <div className="grid gap-3 md:grid-cols-3">
                <label className="block">
                  <span className="text-xs font-semibold text-muted">名字</span>
                  <input
                    value={editDraft.name}
                    onChange={(event) => setEditDraft({ ...editDraft, name: event.target.value })}
                    className={FIELD_CLASS}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-muted">性格</span>
                  <select
                    value={editDraft.archetype}
                    onChange={(event) => setEditDraft({ ...editDraft, archetype: event.target.value as CompanionArchetype })}
                    className={FIELD_CLASS}
                  >
                    {ARCHETYPES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-muted">主要陪伴</span>
                  <input
                    value={editDraft.companion_for}
                    onChange={(event) => setEditDraft({ ...editDraft, companion_for: event.target.value })}
                    className={FIELD_CLASS}
                  />
                </label>
                <div className="md:col-span-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      void run(
                        () =>
                          updateCompanionCharacter(character.id, {
                            name: editDraft.name.trim() || undefined,
                            archetype: editDraft.archetype,
                            companion_for: editDraft.companion_for.trim()
                          }),
                        character.id,
                        () => setEditingId(null)
                      )
                    }
                    disabled={busyId === character.id}
                    className="focus-ring inline-flex h-8 items-center gap-1 rounded-lg bg-teal-600 px-3 text-xs font-semibold text-white disabled:opacity-60"
                  >
                    <Check size={13} aria-hidden />
                    保存
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingId(null)}
                    className="focus-ring inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    <X size={13} aria-hidden />
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                    {character.name}
                    {character.active && (
                      <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-semibold text-teal-700">当前</span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    {archetypeLabel(character.archetype)}
                    {character.companion_for ? ` · 陪伴 ${character.companion_for}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void run(() => activateCompanionCharacter(character.id), character.id)}
                    disabled={character.active || busyId === character.id}
                    className="focus-ring inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs font-semibold text-teal-700 hover:bg-teal-50 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
                  >
                    {character.active ? "已是当前" : "设为当前"}
                  </button>
                  <button
                    type="button"
                    onClick={() => startEdit(character)}
                    className="focus-ring inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    <Pencil size={13} aria-hidden />
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => void remove(character)}
                    disabled={character.active || onlyOne || busyId === character.id}
                    title={character.active ? "当前角色不可删除，请先切换到别的角色" : onlyOne ? "至少保留一个角色" : "删除角色及其记忆"}
                    className="focus-ring inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
                  >
                    <Trash2 size={13} aria-hidden />
                    删除
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
