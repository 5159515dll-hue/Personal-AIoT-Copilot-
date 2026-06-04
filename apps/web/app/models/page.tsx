import { AppShell } from "@/components/app-shell";
import { ModelSettingsPanel } from "@/components/model-settings-panel";
import { PageHeader } from "@/components/page-header";
import { getModelProviderCatalog } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const catalog = await getModelProviderCatalog();

  return (
    <AppShell>
      <PageHeader
        title="模型接入"
        description="选择模型厂商、协议、基础地址、模型，并导入接口密钥。当前预置小米 MiMo 与 Kimi 中国区接口。"
      />
      <ModelSettingsPanel catalog={catalog} />
    </AppShell>
  );
}
