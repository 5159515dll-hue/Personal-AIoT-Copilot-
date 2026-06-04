import { AgentConsole } from "@/components/agent-console";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";

export default function AgentPage() {
  return (
    <AppShell>
      <PageHeader
        title="智能体"
        description="工具和策略先执行，当前大模型只在安全边界内增强分析表达；每次回复都会显示模型状态和工具依据。"
      />
      <AgentConsole />
    </AppShell>
  );
}
