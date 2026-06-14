"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, Eye, FileVideo2, Plus, Radio, Trash2 } from "lucide-react";
import {
  captureCompanionPhoto,
  companionLiveFrameUrl,
  createStream,
  deleteMediaAsset,
  deleteStream,
  getMediaAssets,
  startCompanionLive,
  stopCompanionLive,
  updateStream
} from "@/lib/api";
import type { DeviceEvent, MediaAsset, RoomSpace, StreamSource, StreamSourceCreate } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

type HlsInstance = import("hls.js").default;

const defaultStreamDraft: StreamSourceCreate = {
  device_id: "",
  space_id: "",
  name: "",
  rtsp_url: "rtsp://82.157.148.249:8554/raspi_cam_01",
  stream_key: "",
  zone: "",
  enabled: true,
  notes: ""
};

export function VisualMediaPanel({
  initialSpaces,
  initialEvents,
  initialAssets,
  initialStreams,
  error
}: {
  initialSpaces: RoomSpace[];
  initialEvents: DeviceEvent[];
  initialAssets: MediaAsset[];
  initialStreams: StreamSource[];
  error?: string | null;
}) {
  const activeSpace = initialSpaces.find((space) => space.is_active) ?? initialSpaces[0] ?? null;
  const [spaceId, setSpaceId] = useState(activeSpace?.id ?? "");
  const [events] = useState(initialEvents);
  const [assets, setAssets] = useState(initialAssets);
  const [streams, setStreams] = useState(initialStreams);
  const [draft, setDraft] = useState<StreamSourceCreate>({
    ...defaultStreamDraft,
    space_id: activeSpace?.id ?? "",
    device_id: activeSpace?.device_ids[0] ?? ""
  });
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(error ?? null);
  const [liveOn, setLiveOn] = useState(false);
  const [liveSrc, setLiveSrc] = useState("");
  const [liveWaiting, setLiveWaiting] = useState(true);
  const [liveError, setLiveError] = useState<string | null>(null);
  const liveOnRef = useRef(false);
  const liveTimer = useRef<number | null>(null);

  const selectedSpace = initialSpaces.find((space) => space.id === spaceId) ?? activeSpace;
  const realtimeAllowed =
    selectedSpace?.perception.camera === "local_only" && !!selectedSpace?.perception.media_policy.allow_realtime_stream;
  const filteredEvents = useMemo(() => events.filter((event) => !spaceId || event.space_id === spaceId), [events, spaceId]);
  const filteredAssets = useMemo(() => assets.filter((asset) => !spaceId || asset.space_id === spaceId), [assets, spaceId]);
  const filteredStreams = useMemo(() => streams.filter((stream) => !spaceId || stream.space_id === spaceId), [streams, spaceId]);

  function updateDraft(patch: Partial<StreamSourceCreate>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  async function createStreamSource() {
    const payload = {
      ...draft,
      space_id: draft.space_id || spaceId,
      device_id: draft.device_id.trim(),
      name: draft.name.trim(),
      rtsp_url: draft.rtsp_url.trim(),
      stream_key: draft.stream_key?.trim() || null,
      zone: draft.zone?.trim() || null,
      notes: draft.notes?.trim() || null
    };
    if (!payload.device_id || !payload.name || !payload.rtsp_url || !payload.space_id) {
      setMessage("请填写设备编号、流名称、RTSP 地址和空间。");
      return;
    }
    setPending("create-stream");
    setMessage(null);
    try {
      const response = await createStream(payload);
      setStreams((current) => [response.stream, ...current.filter((item) => item.id !== response.stream.id)]);
      setMessage(`实时流 ${response.stream.name} 已创建，审计编号：${response.audit_log_id}`);
    } catch (streamError) {
      setMessage(streamError instanceof Error ? streamError.message : "实时流创建失败");
    } finally {
      setPending(null);
    }
  }

  async function markStreamOnline(stream: StreamSource, status: StreamSource["status"]) {
    setPending(stream.id);
    setMessage(null);
    try {
      const response = await updateStream(stream.id, { status });
      setStreams((current) => current.map((item) => (item.id === stream.id ? response.stream : item)));
      setMessage(`实时流状态已更新为 ${streamStatusLabel(status)}，审计编号：${response.audit_log_id}`);
    } catch (streamError) {
      setMessage(streamError instanceof Error ? streamError.message : "实时流状态更新失败");
    } finally {
      setPending(null);
    }
  }

  async function removeAsset(asset: MediaAsset) {
    const confirmed = window.confirm(`确认删除媒体 ${asset.file_name}？该操作会删除服务器本机文件并写入审计。`);
    if (!confirmed) {
      return;
    }
    setPending(asset.id);
    setMessage(null);
    try {
      const response = await deleteMediaAsset(asset.id);
      setAssets((current) => current.filter((item) => item.id !== response.media_id));
      setMessage(`媒体已删除，审计编号：${response.audit_log_id}`);
    } catch (deleteError) {
      setMessage(deleteError instanceof Error ? deleteError.message : "媒体删除失败");
    } finally {
      setPending(null);
    }
  }

  async function removeStream(stream: StreamSource) {
    const confirmed = window.confirm(`确认删除实时流 ${stream.name}？不会删除历史事件或媒体文件。`);
    if (!confirmed) {
      return;
    }
    setPending(`delete:${stream.id}`);
    setMessage(null);
    try {
      const response = await deleteStream(stream.id);
      setStreams((current) => current.filter((item) => item.id !== response.stream_id));
      setMessage(`实时流已删除，审计编号：${response.audit_log_id}`);
    } catch (deleteError) {
      setMessage(deleteError instanceof Error ? deleteError.message : "实时流删除失败");
    } finally {
      setPending(null);
    }
  }

  async function capturePhoto() {
    if (!spaceId) {
      setMessage("请先选择空间。");
      return;
    }
    setPending("capture");
    setMessage("已请求机器人拍照，约 3–5 秒后照片会出现…");
    try {
      await captureCompanionPhoto(spaceId);
      await new Promise((resolve) => setTimeout(resolve, 4500));
      setAssets(await getMediaAssets({ space_id: spaceId, limit: 80 }));
      setMessage("已刷新媒体库（若没看到照片，请确认机器人在线后再点一次）。");
    } catch (captureError) {
      setMessage(captureError instanceof Error ? captureError.message : "拍照请求失败");
    } finally {
      setPending(null);
    }
  }

  function scheduleNextFrame() {
    if (!liveOnRef.current || !spaceId) {
      return;
    }
    if (liveTimer.current) {
      window.clearTimeout(liveTimer.current);
    }
    liveTimer.current = window.setTimeout(() => {
      if (liveOnRef.current) {
        setLiveSrc(`${companionLiveFrameUrl(spaceId)}&t=${Date.now()}`);
      }
    }, 180);
  }

  async function startLive() {
    if (!spaceId) {
      setMessage("请先选择空间。");
      return;
    }
    setLiveError(null);
    setPending("live");
    try {
      await startCompanionLive(spaceId);
      setLiveOn(true);
    } catch (startError) {
      setLiveError(startError instanceof Error ? startError.message : "开始实时画面失败");
    } finally {
      setPending(null);
    }
  }

  async function stopLive() {
    setLiveOn(false);
    try {
      await stopCompanionLive(spaceId);
    } catch {
      /* 浏览器侧已停止显示；机器人侧由看门狗兜底自动停。 */
    }
  }

  // 切换空间时先停掉当前直播（避免对着旧空间继续推流）。
  useEffect(() => {
    setLiveOn(false);
  }, [spaceId]);

  // liveOn 同步到 ref，供 onLoad/onError 链式取帧时判断是否仍在直播。
  useEffect(() => {
    liveOnRef.current = liveOn;
  }, [liveOn]);

  // 直播期间：拉首帧 + 周期性 keepalive（让机器人看门狗知道有人在看）。
  useEffect(() => {
    if (!liveOn || !spaceId) {
      return;
    }
    setLiveWaiting(true);
    setLiveSrc(`${companionLiveFrameUrl(spaceId)}&t=${Date.now()}`);
    const keepalive = window.setInterval(() => {
      void startCompanionLive(spaceId).catch(() => undefined);
    }, 25000);
    return () => {
      window.clearInterval(keepalive);
      if (liveTimer.current) {
        window.clearTimeout(liveTimer.current);
        liveTimer.current = null;
      }
    };
  }, [liveOn, spaceId]);

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
              <Camera size={18} aria-hidden />
              空间媒体策略
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              摄像头、事件媒体和实时流必须先在房间设置里启用“仅本地处理”，硬件再使用设备令牌上报。
            </p>
          </div>
          <label className="block min-w-56">
            <span className="text-xs font-semibold text-muted">当前筛选空间</span>
            <select
              value={spaceId}
              onChange={(event) => {
                setSpaceId(event.target.value);
                updateDraft({ space_id: event.target.value });
              }}
              className="focus-ring mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink"
            >
              {initialSpaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {selectedSpace && (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <PolicyItem label="摄像头" value={capabilityLabel(selectedSpace.perception.camera)} />
            <PolicyItem label="事件媒体" value={selectedSpace.perception.media_policy.allow_event_media ? "允许" : "关闭"} />
            <PolicyItem label="实时流" value={selectedSpace.perception.media_policy.allow_realtime_stream ? "允许" : "关闭"} />
            <PolicyItem label="保留策略" value={`${selectedSpace.perception.media_policy.media_retention_days} 天媒体 / ${selectedSpace.perception.media_policy.event_retention_days} 天事件`} />
          </div>
        )}
        {selectedSpace && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void capturePhoto()}
                disabled={pending === "capture"}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Camera size={15} aria-hidden />
                {pending === "capture" ? "拍照中…" : "机器人拍照"}
              </button>
              {liveOn ? (
                <button
                  type="button"
                  onClick={() => void stopLive()}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-rose-600 px-3 text-sm font-semibold text-white"
                >
                  <Radio size={15} aria-hidden />
                  停止实时
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void startLive()}
                  disabled={!realtimeAllowed || pending === "live"}
                  title={realtimeAllowed ? undefined : "该空间未开启本地摄像头或未允许实时流（请在房间设置里启用）"}
                  className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Eye size={15} aria-hidden />
                  {pending === "live" ? "开启中…" : "开始实时"}
                </button>
              )}
            </div>
            {!realtimeAllowed && (
              <p className="text-xs leading-5 text-muted">
                实时画面需先在房间设置里把该空间的摄像头设为「仅本地处理」并允许实时流。
              </p>
            )}
            {liveError && <p className="text-xs leading-5 text-red-600">{liveError}</p>}
            {liveOn && (
              <div className="overflow-hidden rounded-xl border border-line bg-slate-900">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={liveSrc}
                  alt="机器人实时画面"
                  className="block w-full max-w-xl"
                  onLoad={() => {
                    setLiveWaiting(false);
                    scheduleNextFrame();
                  }}
                  onError={() => {
                    setLiveWaiting(true);
                    scheduleNextFrame();
                  }}
                />
                <div className="flex items-center justify-between px-3 py-2 text-xs text-slate-300">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${liveWaiting ? "bg-amber-400" : "bg-emerald-400"}`}
                      aria-hidden
                    />
                    {liveWaiting ? "等待机器人画面…（约 1-2 秒）" : "实时中 · 机器人摄像头"}
                  </span>
                  <span>≈5 fps · MJPEG 中继</span>
                </div>
              </div>
            )}
          </div>
        )}
        {message && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-700">{message}</p>}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="space-y-5">
          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
              <Radio size={18} aria-hidden />
              实时视频流
            </h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <TextField label="设备编号" value={draft.device_id} onChange={(value) => updateDraft({ device_id: value })} />
              <TextField label="流名称" value={draft.name} onChange={(value) => updateDraft({ name: value })} />
              <TextField label="RTSP 地址" value={draft.rtsp_url} onChange={(value) => updateDraft({ rtsp_url: value })} />
              <TextField label="区域" value={draft.zone ?? ""} onChange={(value) => updateDraft({ zone: value })} />
            </div>
            <button
              type="button"
              onClick={() => void createStreamSource()}
              disabled={pending === "create-stream"}
              className="focus-ring mt-3 inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus size={16} aria-hidden />
              新增实时流
            </button>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {filteredStreams.map((stream) => (
                <article key={stream.id} className="rounded-lg border border-line bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-ink">{stream.name}</p>
                      <p className="mt-1 break-all text-xs leading-5 text-muted">{stream.rtsp_url}</p>
                      <p className="mt-1 text-xs text-muted">HLS：{stream.hls_url}</p>
                    </div>
                    <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                      {streamStatusLabel(stream.status)}
                    </span>
                  </div>
                  {stream.status === "online" ? (
                    <HlsPlayer source={stream.hls_url} />
                  ) : (
                    <div className="mt-3 rounded-lg border border-dashed border-line bg-white p-4 text-sm leading-6 text-muted">
                      推流确认后可把状态标记为在线；HLS 文件不可用时播放器会显示中文错误。
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void markStreamOnline(stream, stream.status === "online" ? "offline" : "online")}
                      disabled={pending === stream.id}
                      className="focus-ring inline-flex h-8 items-center rounded-lg border border-line bg-white px-2 text-xs font-semibold text-slate-700 disabled:opacity-60"
                    >
                      {stream.status === "online" ? "标记离线" : "标记在线"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void markStreamOnline(stream, "error")}
                      disabled={pending === stream.id}
                      className="focus-ring inline-flex h-8 items-center rounded-lg border border-line bg-white px-2 text-xs font-semibold text-slate-700 disabled:opacity-60"
                    >
                      标记异常
                    </button>
                    <button
                      type="button"
                      onClick={() => void removeStream(stream)}
                      disabled={pending === `delete:${stream.id}`}
                      className="focus-ring inline-flex h-8 items-center rounded-lg border border-rose-200 bg-white px-2 text-xs font-semibold text-rose-700 disabled:opacity-60"
                    >
                      删除
                    </button>
                  </div>
                </article>
              ))}
              {filteredStreams.length === 0 && <EmptyState text="暂无实时流配置。请先在空间里启用实时流策略，再添加树莓派 RTSP 推流地址。" />}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
              <FileVideo2 size={18} aria-hidden />
              媒体资产
            </h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filteredAssets.map((asset) => (
                <article key={asset.id} className="rounded-lg border border-line bg-slate-50 p-3">
                  <div className="aspect-video overflow-hidden rounded-lg bg-slate-900">
                    {asset.media_type === "image" ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={asset.content_url} alt={asset.file_name} className="h-full w-full object-cover" />
                    ) : (
                      <video src={asset.content_url} controls className="h-full w-full" />
                    )}
                  </div>
                  <p className="mt-3 truncate text-sm font-semibold text-ink">{asset.file_name}</p>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    {asset.device_id} · {asset.zone ?? "未分区"} · {formatBytes(asset.file_size_bytes)}
                  </p>
                  <p className="text-xs text-muted">保留 {asset.retention_days} 天 · {formatDateTime(asset.received_at)}</p>
                  <button
                    type="button"
                    onClick={() => void removeAsset(asset)}
                    disabled={pending === asset.id}
                    className="focus-ring mt-3 inline-flex h-8 items-center gap-2 rounded-lg border border-rose-200 bg-white px-2 text-xs font-semibold text-rose-700 disabled:opacity-60"
                  >
                    <Trash2 size={14} aria-hidden />
                    删除媒体
                  </button>
                </article>
              ))}
              {filteredAssets.length === 0 && <EmptyState text="暂无事件图片或视频片段。树莓派边缘识别触发事件后，可上传快照或短片段。" />}
            </div>
          </section>
        </section>

        <aside className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
            <Eye size={18} aria-hidden />
            边缘识别事件
          </h2>
          <div className="mt-4 space-y-3">
            {filteredEvents.map((event) => (
              <article key={event.id} className="rounded-lg border border-line bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-ink">{eventTypeLabel(event.event_type)}</p>
                  <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                    {severityLabel(event.severity)}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted">
                  {event.device_id} · {event.zone ?? "未分区"} · {formatDateTime(event.captured_at)}
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-700">
                  置信度：{event.confidence == null ? "未提供" : `${Math.round(event.confidence * 100)}%`}
                </p>
                {Object.keys(event.attributes).length > 0 && (
                  <pre className="mt-2 max-h-28 overflow-auto rounded-lg bg-white p-2 text-xs leading-5 text-slate-700">
                    {JSON.stringify(event.attributes, null, 2)}
                  </pre>
                )}
              </article>
            ))}
            {filteredEvents.length === 0 && <EmptyState text="暂无边缘识别事件。服务器不会主动做人脸或情绪识别，只接收树莓派上报的结构化结果。" />}
          </div>
        </aside>
      </div>
    </div>
  );
}

function HlsPlayer({ source }: { source: string }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let destroyed = false;
    let hls: HlsInstance | null = null;

    async function attach() {
      const video = ref.current;
      if (!video) {
        return;
      }
      setError(null);
      if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = source;
        return;
      }
      try {
        const Hls = (await import("hls.js")).default;
        if (destroyed) {
          return;
        }
        if (Hls.isSupported()) {
          hls = new Hls();
          hls.loadSource(source);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, () => setError("HLS 流暂不可用，请确认树莓派推流和 MediaMTX 服务状态。"));
        } else {
          setError("当前浏览器不支持 HLS 播放。");
        }
      } catch {
        setError("HLS 播放组件加载失败。");
      }
    }

    void attach();
    return () => {
      destroyed = true;
      hls?.destroy();
    };
  }, [source]);

  return (
    <div className="mt-3">
      <video ref={ref} controls className="aspect-video w-full rounded-lg bg-slate-950" />
      {error && <p className="mt-2 rounded-lg bg-amber-50 p-2 text-xs leading-5 text-amber-800">{error}</p>}
    </div>
  );
}

function PolicyItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
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

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-line bg-slate-50 p-4 text-sm leading-6 text-muted">{text}</div>;
}

function capabilityLabel(value: string): string {
  const labels: Record<string, string> = {
    disabled: "关闭",
    planned: "规划中",
    local_only: "仅本地处理"
  };
  return labels[value] ?? value;
}

function streamStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    configured: "已配置",
    online: "在线",
    offline: "离线",
    error: "异常"
  };
  return labels[value] ?? value;
}

function eventTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    presence_detected: "人体存在",
    motion_detected: "移动侦测",
    face_detected: "人脸检测",
    emotion_detected: "情绪识别",
    location_update: "位置变化",
    safety_alert: "安全告警",
    custom: "自定义事件"
  };
  return labels[value] ?? value;
}

function severityLabel(value: string): string {
  const labels: Record<string, string> = {
    info: "信息",
    warning: "预警",
    critical: "严重"
  };
  return labels[value] ?? value;
}

function formatBytes(value: number): string {
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)}MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)}KB`;
  }
  return `${value}B`;
}
