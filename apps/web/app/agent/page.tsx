import { AgentConsole } from "@/components/agent-console";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";

export default function AgentPage() {
  return (
    <AppShell>
      <PageHeader
        title="智能体"
        description="一个确定性的工具优先智能体演示。查询、规则草案、允许控制和拒绝操作都会显示工具依据。"
      />
      <AgentConsole />
    </AppShell>
  );
}
