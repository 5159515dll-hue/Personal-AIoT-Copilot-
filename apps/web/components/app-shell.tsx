"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  FileClock,
  Gauge,
  Home,
  KeyRound,
  ListChecks,
  LogOut,
  ShieldCheck,
  SlidersHorizontal
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "总览", icon: Gauge },
  { href: "/trends", label: "趋势", icon: Activity },
  { href: "/devices", label: "设备", icon: SlidersHorizontal },
  { href: "/agent", label: "智能体", icon: Bot },
  { href: "/models", label: "模型", icon: KeyRound },
  { href: "/rules", label: "规则", icon: ListChecks },
  { href: "/audit", label: "审计", icon: FileClock }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-wash text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-white px-4 py-5 lg:block">
        <Link href="/" className="flex items-center gap-3 rounded-lg px-2 py-2 focus-ring">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-white">
            <ShieldCheck size={20} aria-hidden />
          </span>
          <span>
            <span className="block text-sm font-semibold leading-5">个人空间</span>
            <span className="block text-xs text-muted">智能物联助手</span>
          </span>
        </Link>

        <nav className="mt-8 space-y-1" aria-label="控制台">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium focus-ring",
                  active
                    ? "bg-teal-50 text-teal-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-ink"
                ].join(" ")}
              >
                <Icon size={18} aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-4 right-4 space-y-3">
          <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-700">模拟数据模式</p>
            <p className="mt-1 text-xs leading-5 text-amber-700/80">
              当前版本不会控制真实物理设备。
            </p>
          </div>
          <Link
            href="/access/logout"
            className="focus-ring flex h-10 items-center justify-center gap-2 rounded-lg border border-line bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <LogOut size={16} aria-hidden />
            退出控制台
          </Link>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex min-h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
            <Link href="/" className="flex items-center gap-2 text-sm font-semibold lg:hidden">
              <Home size={18} aria-hidden />
              智能物联助手
            </Link>
            <div className="hidden min-w-0 lg:block">
              <p className="text-sm font-semibold">演示房间 001</p>
              <p className="text-xs text-muted">亚洲/上海 · 模拟遥测 · 策略强制执行</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-teal-500" aria-hidden />
                <span className="font-medium text-slate-700">接口正常</span>
              </span>
              <Link href="/access/logout" className="focus-ring inline-flex items-center gap-1 font-semibold text-slate-500 hover:text-ink">
                <LogOut size={14} aria-hidden />
                退出
              </Link>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-line px-3 py-2 lg:hidden" aria-label="移动端控制台">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium focus-ring",
                    active ? "bg-teal-50 text-teal-700" : "text-slate-600"
                  ].join(" ")}
                >
                  <Icon size={16} aria-hidden />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
