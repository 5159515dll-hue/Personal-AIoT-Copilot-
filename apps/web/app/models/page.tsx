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
        description="先按厂商导入或覆盖接口密钥，再用独立工具切换智能体当前使用的中国区模型。"
      />
      <ModelSettingsPanel catalog={catalog} />
    </AppShell>
  );
}
