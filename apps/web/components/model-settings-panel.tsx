"use client";

import { FormEvent, useMemo, useState } from "react";
import { BrainCircuit, CheckCircle2, ExternalLink, KeyRound, PlugZap, Save, TestTube2 } from "lucide-react";
import { saveModelConfig, testModelConnection } from "@/lib/api";
import type {
  ModelConfigRequest,
  ModelConnectionTestResponse,
  ModelProviderCatalog,
  ModelProviderDefinition,
  ProviderEndpoint,
  PublicModelConfig
} from "@/lib/types";
import { formatDateTime } from "@/lib/format";

export function ModelSettingsPanel({ catalog }: { catalog: ModelProviderCatalog }) {
  const initialProvider =
    catalog.providers.find((provider) => provider.id === catalog.active_config?.provider_id) ?? catalog.providers[0];
  const initialEndpoint =
    initialProvider.endpoints.find((endpoint) => endpoint.id === catalog.active_config?.endpoint_id) ??
    initialProvider.endpoints[0];

  const [providerId, setProviderId] = useState(initialProvider.id);
  const [endpointId, setEndpointId] = useState(initialEndpoint.id);
  const [baseUrl, setBaseUrl] = useState(catalog.active_config?.base_url ?? initialEndpoint.base_url);
  const [model, setModel] = useState(catalog.active_config?.model ?? initialProvider.default_model);
  const [apiKey, setApiKey] = useState("");
  const [activeConfig, setActiveConfig] = useState(catalog.active_config);
  const [savedConfigs, setSavedConfigs] = useState<PublicModelConfig[]>(
    catalog.saved_configs.length > 0 ? catalog.saved_configs : catalog.active_config ? [catalog.active_config] : []
  );
  const [result, setResult] = useState<ModelConnectionTestResponse | string | null>(null);
  const [pending, setPending] = useState<"save" | "test" | null>(null);

  const provider = useMemo(
    () => catalog.providers.find((item) => item.id === providerId) ?? catalog.providers[0],
    [catalog.providers, providerId]
  );
  const endpoint = useMemo(
    () => provider.endpoints.find((item) => item.id === endpointId) ?? provider.endpoints[0],
    [endpointId, provider]
  );
  const activeProvider = useMemo(
    () => catalog.providers.find((item) => item.id === activeConfig?.provider_id) ?? null,
    [activeConfig?.provider_id, catalog.providers]
  );
  const savedConfig = useMemo(
    () => findSavedConfig(savedConfigs, provider.id, endpoint.id, endpoint.protocol, baseUrl),
    [baseUrl, endpoint.id, endpoint.protocol, provider.id, savedConfigs]
  );
  const canReuseSavedKey = savedConfig?.api_key_set === true;
  const selectionMatchesActive =
    activeConfig?.provider_id === provider.id &&
    activeConfig.endpoint_id === endpoint.id &&
    activeConfig.protocol === endpoint.protocol &&
    activeConfig.base_url.replace(/\/$/, "") === baseUrl.replace(/\/$/, "") &&
    activeConfig.model === model;
  const hasUsableKey = Boolean(apiKey.trim()) || canReuseSavedKey;

  function changeProvider(next: ModelProviderDefinition) {
    const nextEndpoint = next.endpoints[0];
    const nextSaved = findSavedConfig(savedConfigs, next.id, nextEndpoint.id, nextEndpoint.protocol, nextEndpoint.base_url);
    setProviderId(next.id);
    setEndpointId(nextEndpoint.id);
    setBaseUrl(nextEndpoint.base_url);
    setModel(nextSaved?.model ?? next.default_model);
    setApiKey("");
    setResult(null);
  }

  function changeEndpoint(next: ProviderEndpoint) {
    const nextSaved = findSavedConfig(savedConfigs, provider.id, next.id, next.protocol, next.base_url);
    setEndpointId(next.id);
    setBaseUrl(next.base_url);
    setModel(nextSaved?.model ?? provider.default_model);
    setApiKey("");
    setResult(null);
  }

  function payload(): ModelConfigRequest {
    return {
      provider_id: provider.id,
      endpoint_id: endpoint.id,
      protocol: endpoint.protocol,
      base_url: baseUrl,
      model,
      api_key: apiKey.trim() || null
    };
  }

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasUsableKey) {
      setResult("请先导入当前厂商接口密钥，或切回可复用已导入密钥的配置。");
      return;
    }
    setPending("save");
    setResult(null);
    try {
      const saved = await saveModelConfig(payload());
      setActiveConfig(saved);
      setSavedConfigs((current) => [saved, ...current.filter((item) => !sameConfigTarget(item, saved))]);
      setApiKey("");
      setResult("已保存为智能体当前模型。该厂商接口密钥后续切换回来时会自动复用，接口响应不会回显明文密钥。");
    } catch (error) {
      setResult(error instanceof Error ? error.message : "保存失败");
    } finally {
      setPending(null);
    }
  }

  async function onTest() {
    if (!hasUsableKey) {
      setResult("请先导入当前厂商接口密钥，或切回可复用已导入密钥的配置。");
      return;
    }
    setPending("test");
    setResult(null);
    try {
      const response = await testModelConnection(payload());
      setResult(response);
    } catch (error) {
      setResult(error instanceof Error ? error.message : "测试失败");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <form onSubmit={onSave} className="rounded-lg border border-line bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
            <PlugZap size={20} aria-hidden />
          </span>
          <div>
            <h2 className="text-base font-semibold">接入配置</h2>
            <p className="text-sm text-muted">保存后会成为智能体当前使用的大模型配置。</p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {catalog.providers.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => changeProvider(item)}
              className={[
                "focus-ring rounded-lg border p-4 text-left transition",
                item.id === provider.id ? "border-teal-300 bg-teal-50" : "border-line bg-white hover:border-teal-200"
              ].join(" ")}
            >
              <span className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                {item.label}
                {item.id === provider.id && (
                  <span className="rounded-md bg-white px-2 py-0.5 text-xs font-semibold text-teal-700">正在编辑</span>
                )}
                {item.id === activeConfig?.provider_id && (
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">当前生效</span>
                )}
                {savedConfigs.some((config) => config.provider_id === item.id && config.api_key_set) && (
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">已导入密钥</span>
                )}
              </span>
              <span className="mt-2 block text-sm leading-6 text-muted">{item.description}</span>
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">接口入口</span>
            <select
              value={endpoint.id}
              onChange={(event) => {
                const next = provider.endpoints.find((item) => item.id === event.target.value) ?? provider.endpoints[0];
                changeEndpoint(next);
              }}
              className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
            >
              {provider.endpoints.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <span className="mt-2 block text-xs leading-5 text-muted">{endpoint.description}</span>
          </label>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">模型</span>
            <input
              list="model-options"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
              placeholder="输入或选择模型名"
            />
            <datalist id="model-options">
              {provider.models.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </label>
        </div>

        <label className="mt-4 block">
          <span className="text-sm font-semibold text-slate-700">基础地址</span>
          <input
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
            placeholder="https://..."
          />
        </label>

        <label className="mt-4 block">
          <span className="text-sm font-semibold text-slate-700">接口密钥</span>
          <div className="mt-2 flex gap-2">
            <input
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              type="password"
              className="focus-ring h-11 min-w-0 flex-1 rounded-lg border border-line bg-white px-3 text-sm"
              placeholder={canReuseSavedKey ? "留空则继续使用当前接口密钥" : "粘贴当前厂商接口密钥"}
              autoComplete="off"
            />
          </div>
          <span className="mt-2 block text-xs leading-5 text-muted">
            {canReuseSavedKey
              ? `当前选择可复用已导入密钥：${savedConfig?.api_key_preview ?? "***"}`
              : "该厂商接口尚未导入密钥，首次保存或测试需要粘贴对应平台密钥。"}
          </span>
        </label>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={pending !== null}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Save size={16} aria-hidden />
            保存为当前模型
          </button>
          <button
            type="button"
            onClick={() => void onTest()}
            disabled={pending !== null}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <TestTube2 size={16} aria-hidden />
            测试当前选择
          </button>
        </div>
        {!selectionMatchesActive && (
          <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-800">
            当前页面内容只是待保存选择。点击“保存为当前模型”后，智能体才会使用这个厂商、接口和模型。
          </p>
        )}

        {result && (
          <div
            className={[
              "mt-5 rounded-lg border p-4 text-sm leading-6",
              typeof result === "string"
                ? "border-teal-100 bg-teal-50 text-teal-800"
                : result.ok
                  ? "border-teal-100 bg-teal-50 text-teal-800"
                  : "border-rose-100 bg-rose-50 text-rose-800"
            ].join(" ")}
          >
            {typeof result === "string" ? result : result.message}
          </div>
        )}
      </form>

      <aside className="space-y-5">
        <section className="rounded-lg border border-teal-100 bg-teal-50 p-5">
          <div className="flex items-center gap-2 text-teal-800">
            <BrainCircuit size={18} aria-hidden />
            <h2 className="text-base font-semibold">智能体当前模型</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-teal-800/85">
            智能体会先完成工具调用和策略判断，再用当前模型增强环境分析、规则说明和普通问答；被策略拒绝的请求不会发送给外部模型。
          </p>
          <p className="mt-3 break-all text-sm font-semibold text-teal-900">
            {activeConfig ? `${activeProvider?.label ?? activeConfig.provider_id} · ${activeConfig.model}` : "尚未选择当前模型"}
          </p>
        </section>

        <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-teal-700" aria-hidden />
            <h2 className="text-base font-semibold">当前生效配置</h2>
          </div>
          {activeConfig ? (
            <dl className="mt-4 space-y-3 text-sm">
              <Info label="厂商" value={activeProvider?.label ?? activeConfig.provider_id} />
              <Info label="协议" value={activeConfig.protocol === "openai" ? "OpenAI 兼容" : "Anthropic 兼容"} />
              <Info label="模型" value={activeConfig.model} />
              <Info label="Base URL" value={activeConfig.base_url} />
              <Info label="密钥状态" value={activeConfig.api_key_set ? `已导入 ${activeConfig.api_key_preview}` : "未导入"} />
              {activeConfig.updated_at && <Info label="更新时间" value={formatDateTime(activeConfig.updated_at)} />}
            </dl>
          ) : (
            <p className="mt-4 text-sm leading-6 text-muted">尚未保存模型配置。</p>
          )}
        </section>

        <section className="rounded-lg border border-amber-100 bg-amber-50 p-5">
          <div className="flex items-center gap-2 text-amber-800">
            <CheckCircle2 size={18} aria-hidden />
            <h2 className="text-base font-semibold">密钥处理规则</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-amber-800/85">
            接口密钥按厂商和接口入口写入后端服务器本地数据目录，切换回来时可复用；页面和接口只显示前后缀预览。
            生产环境建议改为系统环境变量或专用密钥管理服务。
          </p>
        </section>

        <a
          href={provider.docs_url}
          target="_blank"
          rel="noreferrer"
          className="focus-ring flex items-center justify-between rounded-lg border border-line bg-white p-4 text-sm font-semibold text-slate-700 shadow-sm"
        >
          查看 {provider.label} 官方文档
          <ExternalLink size={16} aria-hidden />
        </a>
      </aside>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 break-all font-medium text-ink">{value}</dd>
    </div>
  );
}

function findSavedConfig(
  configs: PublicModelConfig[],
  providerId: string,
  endpointId: string,
  protocol: PublicModelConfig["protocol"],
  baseUrl: string
): PublicModelConfig | undefined {
  return configs.find(
    (item) =>
      item.provider_id === providerId &&
      item.endpoint_id === endpointId &&
      item.protocol === protocol &&
      item.base_url.replace(/\/$/, "") === baseUrl.replace(/\/$/, "")
  );
}

function sameConfigTarget(left: PublicModelConfig, right: PublicModelConfig): boolean {
  return (
    left.provider_id === right.provider_id &&
    left.endpoint_id === right.endpoint_id &&
    left.protocol === right.protocol &&
    left.base_url.replace(/\/$/, "") === right.base_url.replace(/\/$/, "")
  );
}
