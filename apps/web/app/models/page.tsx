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
        description="选择当前智能体使用的大模型，导入接口密钥，并测试小米 MiMo 与 Kimi 中国区接口连通性。"
      />
      <ModelSettingsPanel catalog={catalog} />
    </AppShell>
  );
}
