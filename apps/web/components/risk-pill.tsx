import type { Device } from "@/lib/types";
import { riskLabel } from "@/lib/format";

const styles: Record<Device["risk_level"], string> = {
  read_only: "bg-slate-100 text-slate-700",
  low: "bg-teal-50 text-teal-700",
  medium: "bg-amber-50 text-amber-700",
  high: "bg-rose-50 text-rose-700",
  forbidden: "bg-slate-900 text-white"
};

export function RiskPill({ risk }: { risk: Device["risk_level"] }) {
  return <span className={`rounded-md px-2 py-1 text-xs font-semibold ${styles[risk]}`}>{riskLabel(risk)}</span>;
}
