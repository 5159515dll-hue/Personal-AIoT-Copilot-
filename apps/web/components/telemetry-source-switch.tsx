import Link from "next/link";
import { Bot, Database } from "lucide-react";
import type { TelemetrySource } from "@/lib/types";

export function TelemetrySourceSwitch({
  source,
  basePath,
  extraParams
}: {
  source: TelemetrySource;
  basePath: string;
  extraParams?: Record<string, string | undefined>;
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
        const href = telemetryHref(basePath, option.value, extraParams);
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

function telemetryHref(basePath: string, source: TelemetrySource, extraParams?: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(extraParams ?? {})) {
    if (value) {
      params.set(key, value);
    }
  }
  if (source === "database") {
    params.set("source", "database");
  } else {
    params.delete("source");
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}
