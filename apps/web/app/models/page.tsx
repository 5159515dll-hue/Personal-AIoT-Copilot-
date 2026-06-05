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
        description="上方工具切换智能体当前使用的中国区模型；下方工具只导入或覆盖厂商接口密钥。"
      />
      <ModelSettingsPanel catalog={catalog} />
    </AppShell>
  );
}
