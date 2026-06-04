import Link from "next/link";
import { Bot, Database } from "lucide-react";
import type { TelemetrySource } from "@/lib/types";

export function TelemetrySourceSwitch({
  source,
  basePath
}: {
  source: TelemetrySource;
  basePath: string;
}) {
  const options: Array<{ value: TelemetrySource; label: string; icon: typeof Bot }> = [
    { value: "mock", label: "模拟数据", icon: Bot },
    { value: "database", label: "数据库遥测", icon: Database }
  ];

  return (
    <div className="inline-flex rounded-lg border border-line bg-slate-50 p-1">
      {options.map((option) => {
        const Icon = option.icon;
        const active = source === option.value;
        const href = option.value === "database" ? `${basePath}?source=database` : basePath;
        return (
          <Link
            key={option.value}
            href={href}
            className={`focus-ring inline-flex h-9 items-center gap-2 rounded-md px-3 text-xs font-semibold ${
              active ? "bg-white text-teal-700 shadow-sm" : "text-slate-600 hover:text-ink"
            }`}
          >
            <Icon size={14} aria-hidden />
            {option.label}
          </Link>
        );
      })}
    </div>
  );
}
