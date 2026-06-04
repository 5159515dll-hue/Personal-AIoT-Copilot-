import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { RulesPanel } from "@/components/rules-panel";
import { TelemetrySourceSwitch } from "@/components/telemetry-source-switch";
import { getRules } from "@/lib/api";
import { normalizeTelemetrySource, telemetrySourceLabel } from "@/lib/telemetry-source";

export const dynamic = "force-dynamic";

type RulesPageProps = {
  searchParams?: Promise<{ source?: string | string[] }>;
};

export default async function RulesPage({ searchParams }: RulesPageProps) {
  const params = await searchParams;
  const source = normalizeTelemetrySource(params?.source);
  const rules = await getRules();

  return (
    <AppShell>
      <PageHeader
        title="自动化规则"
        description={`当前版本支持经过确认的简单“如果/那么”规则。评估数据源：${telemetrySourceLabel(source)}。`}
        action={<TelemetrySourceSwitch source={source} basePath="/rules" />}
      />
      <RulesPanel initialRules={rules} initialSource={source} />
    </AppShell>
  );
}
