"use client";

import { FormEvent, useMemo, useState } from "react";
import { ArrowLeftRight, BrainCircuit, CheckCircle2, ExternalLink, KeyRound, PlugZap, TestTube2 } from "lucide-react";
import { importModelProviderKey, switchActiveModel, testModelConnection } from "@/lib/api";
import type {
  ModelConfigRequest,
  ModelConnectionTestResponse,
  ModelProviderCatalog,
  ModelProviderDefinition,
  ProviderEndpoint,
  PublicModelConfig
} from "@/lib/types";
import { formatDateTime } from "@/lib/format";

type PendingSwitchAction = "switch" | "test" | null;
type PanelResult = ModelConnectionTestResponse | string | null;

export function ModelSettingsPanel({ catalog }: { catalog: ModelProviderCatalog }) {
  const firstProvider = catalog.providers[0];
  const initialActiveProvider =
    catalog.providers.find((provider) => provider.id === catalog.active_config?.provider_id) ?? firstProvider;
  const initialActiveEndpoint =
    initialActiveProvider.endpoints.find((endpoint) => endpoint.id === catalog.active_config?.endpoint_id) ??
    initialActiveProvider.endpoints[0];

  const [activeConfig, setActiveConfig] = useState(catalog.active_config);
  const [savedConfigs, setSavedConfigs] = useState<PublicModelConfig[]>(
    catalog.saved_configs.length > 0 ? catalog.saved_configs : catalog.active_config ? [catalog.active_config] : []
  );

  const [keyProviderId, setKeyProviderId] = useState(initialActiveProvider.id);
  const [keyEndpointId, setKeyEndpointId] = useState(initialActiveEndpoint.id);
  const [apiKey, setApiKey] = useState("");
  const [keyPending, setKeyPending] = useState(false);
  const [keyResult, setKeyResult] = useState<PanelResult>(null);

  const [switchProviderId, setSwitchProviderId] = useState(initialActiveProvider.id);
  const [switchEndpointId, setSwitchEndpointId] = useState(initialActiveEndpoint.id);
  const [model, setModel] = useState(catalog.active_config?.model ?? initialActiveProvider.default_model);
  const [switchPending, setSwitchPending] = useState<PendingSwitchAction>(null);
  const [switchResult, setSwitchResult] = useState<PanelResult>(null);

  const keyProvider = useMemo(
    () => catalog.providers.find((item) => item.id === keyProviderId) ?? firstProvider,
    [catalog.providers, firstProvider, keyProviderId]
  );
  const keyEndpoint = useMemo(
    () => keyProvider.endpoints.find((item) => item.id === keyEndpointId) ?? keyProvider.endpoints[0],
    [keyEndpointId, keyProvider]
  );
  const switchProvider = useMemo(
    () => catalog.providers.find((item) => item.id === switchProviderId) ?? firstProvider,
    [catalog.providers, firstProvider, switchProviderId]
  );
  const switchEndpoint = useMemo(
    () => switchProvider.endpoints.find((item) => item.id === switchEndpointId) ?? switchProvider.endpoints[0],
    [switchEndpointId, switchProvider]
  );
  const switchModelOptions = useMemo(() => uniqueModelOptions(switchProvider.models, activeConfig?.model), [
    activeConfig?.model,
    switchProvider.models
  ]);
  const activeProvider = useMemo(
    () => catalog.providers.find((item) => item.id === activeConfig?.provider_id) ?? null,
    [activeConfig?.provider_id, catalog.providers]
  );
  const keySavedConfig = useMemo(
    () => findProviderKeyConfig(savedConfigs, keyProvider.id),
    [keyProvider.id, savedConfigs]
  );
  const switchSavedConfig = useMemo(
    () => findProviderKeyConfig(savedConfigs, switchProvider.id),
    [savedConfigs, switchProvider.id]
  );
  const switchMatchesActive =
    activeConfig?.provider_id === switchProvider.id &&
    activeConfig.endpoint_id === switchEndpoint.id &&
    activeConfig.protocol === switchEndpoint.protocol &&
    activeConfig.base_url.replace(/\/$/, "") === switchEndpoint.base_url.replace(/\/$/, "") &&
    activeConfig.model === model.trim();

  function changeKeyProvider(next: ModelProviderDefinition) {
    const saved = findProviderKeyConfig(savedConfigs, next.id);
    const nextEndpoint = endpointFromConfig(next, saved) ?? next.endpoints[0];
    setKeyProviderId(next.id);
    setKeyEndpointId(nextEndpoint.id);
    setApiKey("");
    setKeyResult(null);
  }

  function changeSwitchProvider(next: ModelProviderDefinition) {
    const saved = findProviderKeyConfig(savedConfigs, next.id);
    const nextEndpoint = endpointFromConfig(next, saved) ?? next.endpoints[0];
    setSwitchProviderId(next.id);
    setSwitchEndpointId(nextEndpoint.id);
    setModel(activeConfig?.provider_id === next.id ? activeConfig.model : next.default_model);
    setSwitchResult(null);
  }

  function switchPayload(): ModelConfigRequest {
    return {
      provider_id: switchProvider.id,
      endpoint_id: switchEndpoint.id,
      protocol: switchEndpoint.protocol,
      base_url: switchEndpoint.base_url,
      model: model.trim(),
      api_key: null
    };
  }

  async function onImportKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      setKeyResult("请先粘贴当前厂商接口密钥。");
      return;
    }
    setKeyPending(true);
    setKeyResult(null);
    try {
      const saved = await importModelProviderKey({
        provider_id: keyProvider.id,
        endpoint_id: keyEndpoint.id,
        protocol: keyEndpoint.protocol,
        base_url: keyEndpoint.base_url,
        api_key: trimmedKey
      });
      setSavedConfigs((current) => [saved, ...current.filter((item) => item.provider_id !== saved.provider_id)]);
      setActiveConfig((current) =>
        current && current.provider_id === saved.provider_id
          ? { ...current, api_key_set: saved.api_key_set, api_key_preview: saved.api_key_preview }
          : current
      );
      setApiKey("");
      setKeyResult(`已导入并覆盖 ${keyProvider.label} 的接口密钥。当前智能体模型没有改变。`);
    } catch (error) {
      setKeyResult(error instanceof Error ? error.message : "密钥导入失败");
    } finally {
      setKeyPending(false);
    }
  }

  async function onSwitchModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!switchSavedConfig?.api_key_set) {
      setSwitchResult("请先在上方导入该厂商密钥，再切换当前模型。");
      return;
    }
    if (!model.trim()) {
      setSwitchResult("请先选择或填写模型名称。");
      return;
    }
    setSwitchPending("switch");
    setSwitchResult(null);
    try {
      const saved = await switchActiveModel({
        provider_id: switchProvider.id,
        endpoint_id: switchEndpoint.id,
        protocol: switchEndpoint.protocol,
        base_url: switchEndpoint.base_url,
        model: model.trim()
      });
      setActiveConfig(saved);
      setSwitchResult("已切换智能体当前使用模型。切换过程没有重新接收接口密钥。");
    } catch (error) {
      setSwitchResult(error instanceof Error ? error.message : "模型切换失败");
    } finally {
      setSwitchPending(null);
    }
  }

  async function onTestSwitchSelection() {
    if (!switchSavedConfig?.api_key_set) {
      setSwitchResult("请先导入该厂商密钥，再测试当前模型。");
      return;
    }
    if (!model.trim()) {
      setSwitchResult("请先选择或填写模型名称。");
      return;
    }
    setSwitchPending("test");
    setSwitchResult(null);
    try {
      const response = await testModelConnection(switchPayload());
      setSwitchResult(response);
    } catch (error) {
      setSwitchResult(error instanceof Error ? error.message : "连接测试失败");
    } finally {
      setSwitchPending(null);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-5">
        <form onSubmit={onImportKey} className="rounded-lg border border-line bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
              <KeyRound size={20} aria-hidden />
            </span>
            <div>
              <h2 className="text-base font-semibold">密钥导入工具</h2>
              <p className="text-sm text-muted">这里只保存厂商密钥。同一厂商只保留一条，第二次导入会覆盖第一次。</p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {catalog.providers.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => changeKeyProvider(item)}
                className={[
                  "focus-ring rounded-lg border p-4 text-left transition",
                  item.id === keyProvider.id ? "border-teal-300 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                ].join(" ")}
              >
                <span className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                  {item.label}
                  {item.id === keyProvider.id && (
                    <span className="rounded-md bg-white px-2 py-0.5 text-xs font-semibold text-teal-700">正在导入</span>
                  )}
                  {findProviderKeyConfig(savedConfigs, item.id)?.api_key_set && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">已有密钥</span>
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
                value={keyEndpoint.id}
                onChange={(event) => {
                  const next = keyProvider.endpoints.find((item) => item.id === event.target.value) ?? keyProvider.endpoints[0];
                  setKeyEndpointId(next.id);
                  setKeyResult(null);
                }}
                className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
              >
                {keyProvider.endpoints.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <span className="mt-2 block text-xs leading-5 text-muted">{keyEndpoint.description}</span>
            </label>

            <div>
              <span className="text-sm font-semibold text-slate-700">密钥状态</span>
              <div className="mt-2 rounded-lg border border-line bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                {keySavedConfig?.api_key_set
                  ? `已导入 ${keySavedConfig.api_key_preview ?? "***"}；再次导入会覆盖上一条。`
                  : "该厂商尚未导入密钥。"}
              </div>
            </div>
          </div>

          <label className="mt-4 block">
            <span className="text-sm font-semibold text-slate-700">接口密钥</span>
            <input
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              type="password"
              className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
              placeholder="粘贴当前厂商接口密钥"
              autoComplete="off"
            />
            <span className="mt-2 block text-xs leading-5 text-muted">同一厂商只保留一条密钥，第二次导入会覆盖第一次。</span>
          </label>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={keyPending}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <PlugZap size={16} aria-hidden />
              {keyPending ? "正在导入" : "导入或覆盖密钥"}
            </button>
          </div>

          <ResultBox result={keyResult} />
        </form>

        <form onSubmit={onSwitchModel} className="rounded-lg border border-line bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
              <ArrowLeftRight size={20} aria-hidden />
            </span>
            <div>
              <h2 className="text-base font-semibold">切换当前模型</h2>
              <p className="text-sm text-muted">选择智能体正在使用的厂商、接口和模型；切换时直接使用已导入密钥。</p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {catalog.providers.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => changeSwitchProvider(item)}
                className={[
                  "focus-ring rounded-lg border p-4 text-left transition",
                  item.id === switchProvider.id ? "border-slate-300 bg-slate-50" : "border-line bg-white hover:border-slate-300"
                ].join(" ")}
              >
                <span className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                  {item.label}
                  {item.id === activeConfig?.provider_id && (
                    <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-semibold text-teal-700">当前生效</span>
                  )}
                  {findProviderKeyConfig(savedConfigs, item.id)?.api_key_set ? (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">可切换</span>
                  ) : (
                    <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">需先导入密钥</span>
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
                value={switchEndpoint.id}
                onChange={(event) => {
                  const next = switchProvider.endpoints.find((item) => item.id === event.target.value) ?? switchProvider.endpoints[0];
                  setSwitchEndpointId(next.id);
                  setSwitchResult(null);
                }}
                className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
              >
                {switchProvider.endpoints.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <span className="mt-2 block text-xs leading-5 text-muted">{switchEndpoint.description}</span>
            </label>

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">模型</span>
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
                className="focus-ring mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"
              >
                {switchModelOptions.map((item) => (
                  <option key={item} value={item} />
                ))}
              </select>
              <span className="mt-2 block text-xs leading-5 text-muted">模型切换不会要求重新输入接口密钥。</span>
            </label>
          </div>

          <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3 text-sm leading-6 text-slate-700">
            {switchSavedConfig?.api_key_set
              ? `将使用已导入的 ${switchProvider.label} 密钥：${switchSavedConfig.api_key_preview ?? "***"}`
              : `尚未导入 ${switchProvider.label} 密钥，不能切换到该厂商。`}
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={switchPending !== null || !switchSavedConfig?.api_key_set}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ArrowLeftRight size={16} aria-hidden />
              {switchPending === "switch" ? "正在切换" : "切换为当前模型"}
            </button>
            <button
              type="button"
              onClick={() => void onTestSwitchSelection()}
              disabled={switchPending !== null || !switchSavedConfig?.api_key_set}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <TestTube2 size={16} aria-hidden />
              测试当前模型
            </button>
          </div>
          {!switchMatchesActive && (
            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-800">
              当前只是待切换选择。点击“切换为当前模型”后，智能体才会使用这个厂商、接口和模型。
            </p>
          )}

          <ResultBox result={switchResult} />
        </form>
      </div>

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
            <CheckCircle2 size={18} className="text-teal-700" aria-hidden />
            <h2 className="text-base font-semibold">当前生效配置</h2>
          </div>
          {activeConfig ? (
            <dl className="mt-4 space-y-3 text-sm">
              <Info label="厂商" value={activeProvider?.label ?? activeConfig.provider_id} />
              <Info label="协议" value={activeConfig.protocol === "openai" ? "开放接口兼容" : "消息接口兼容"} />
              <Info label="模型" value={activeConfig.model} />
              <Info label="基础地址" value={activeConfig.base_url} />
              <Info label="密钥状态" value={activeConfig.api_key_set ? `已导入 ${activeConfig.api_key_preview}` : "未导入"} />
              {activeConfig.updated_at && <Info label="更新时间" value={formatDateTime(activeConfig.updated_at)} />}
            </dl>
          ) : (
            <p className="mt-4 text-sm leading-6 text-muted">尚未保存模型配置。</p>
          )}
        </section>

        <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-slate-700" aria-hidden />
            <h2 className="text-base font-semibold">已导入密钥</h2>
          </div>
          {savedConfigs.length > 0 ? (
            <div className="mt-4 space-y-3">
              {savedConfigs.map((config) => (
                <div key={config.provider_id} className="rounded-lg border border-line bg-slate-50 p-3 text-sm">
                  <p className="font-semibold text-ink">{providerLabel(catalog.providers, config.provider_id)}</p>
                  <p className="mt-1 break-all text-xs leading-5 text-muted">
                    {config.api_key_set ? `密钥预览：${config.api_key_preview ?? "***"}` : "未导入密钥"}
                  </p>
                  {config.updated_at && <p className="mt-1 text-xs text-muted">更新时间：{formatDateTime(config.updated_at)}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-muted">还没有导入任何厂商密钥。</p>
          )}
        </section>

        <section className="rounded-lg border border-amber-100 bg-amber-50 p-5">
          <div className="flex items-center gap-2 text-amber-800">
            <CheckCircle2 size={18} aria-hidden />
            <h2 className="text-base font-semibold">密钥处理规则</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-amber-800/85">
            接口密钥按厂商写入后端服务器本地数据目录；同一厂商第二次导入会覆盖第一次。页面和接口只显示前后缀预览。
          </p>
        </section>

        <a
          href={keyProvider.docs_url}
          target="_blank"
          rel="noreferrer"
          className="focus-ring flex items-center justify-between rounded-lg border border-line bg-white p-4 text-sm font-semibold text-slate-700 shadow-sm"
        >
          查看 {keyProvider.label} 官方文档
          <ExternalLink size={16} aria-hidden />
        </a>
      </aside>
    </div>
  );
}

function ResultBox({ result }: { result: PanelResult }) {
  if (!result) {
    return null;
  }
  const ok = typeof result === "string" || result.ok;
  return (
    <div
      className={[
        "mt-5 rounded-lg border p-4 text-sm leading-6",
        ok ? "border-teal-100 bg-teal-50 text-teal-800" : "border-rose-100 bg-rose-50 text-rose-800"
      ].join(" ")}
    >
      {typeof result === "string" ? result : result.message}
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

function findProviderKeyConfig(configs: PublicModelConfig[], providerId: string): PublicModelConfig | undefined {
  return configs.find((item) => item.provider_id === providerId && item.api_key_set);
}

function endpointFromConfig(provider: ModelProviderDefinition, config: PublicModelConfig | undefined): ProviderEndpoint | undefined {
  if (!config) {
    return undefined;
  }
  return provider.endpoints.find((item) => item.id === config.endpoint_id) ?? provider.endpoints[0];
}

function providerLabel(providers: ModelProviderDefinition[], providerId: string): string {
  return providers.find((item) => item.id === providerId)?.label ?? providerId;
}

function uniqueModelOptions(models: string[], activeModel: string | undefined): string[] {
  return Array.from(new Set([activeModel, ...models].filter((item): item is string => Boolean(item))));
}
