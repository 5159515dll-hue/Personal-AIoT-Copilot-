import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { RulesPanel } from "@/components/rules-panel";
import { getRules } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function RulesPage() {
  const rules = await getRules();

  return (
    <AppShell>
      <PageHeader
        title="自动化规则"
        description="当前版本支持经过确认的简单“如果/那么”规则。智能体草案不会在用户确认前保存。"
      />
      <RulesPanel initialRules={rules} />
    </AppShell>
  );
}
