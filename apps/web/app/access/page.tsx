import Link from "next/link";
import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import { dashboardAccessCode, safeNextPath } from "@/lib/auth";

type AccessPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const errorText: Record<string, string> = {
  invalid: "访问口令不正确，请重新输入。",
  unconfigured: "当前环境尚未配置控制台访问口令。",
};

export default async function AccessPage({ searchParams }: AccessPageProps) {
  const params = (await searchParams) ?? {};
  const nextPath = safeNextPath(firstValue(params.next));
  const error = firstValue(params.error);
  const status = firstValue(params.status);
  const authEnabled = dashboardAccessCode() !== null;

  return (
    <main className="min-h-screen bg-[#03070d] px-5 py-8 text-white sm:px-8 lg:px-12">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col">
        <header className="flex items-center justify-between gap-4 text-sm">
          <Link href="/" className="focus-ring font-semibold">
            个人空间智能物联助手
          </Link>
          <Link href="/" className="focus-ring text-slate-300 hover:text-white">
            返回公开页
          </Link>
        </header>

        <section className="grid flex-1 gap-10 py-14 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
          <div className="max-w-2xl">
            <p className="inline-flex items-center gap-2 text-sm font-semibold tracking-[0.16em] text-amber-200">
              <ShieldCheck size={16} aria-hidden />
              私有控制台
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal sm:text-5xl">
              访问个人空间数据前需要确认身份
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
              公开项目页只展示脱敏演示内容。实时房间状态、设备入口、模型密钥、智能体对话和审计日志属于私有控制台范围。
            </p>
          </div>

          <div className="w-full max-w-md justify-self-start rounded-lg border border-white/12 bg-white/[0.06] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.32)] backdrop-blur lg:justify-self-end">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-teal-400 text-[#031316]">
              <LockKeyhole size={22} aria-hidden />
            </div>
            <h2 className="mt-5 text-xl font-semibold">输入访问口令</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              当前会话有效期为 8 小时，退出后需要重新输入。
            </p>

            {error && (
              <p className="mt-4 rounded-lg border border-red-300/20 bg-red-400/10 p-3 text-sm leading-6 text-red-100">
                {errorText[error] ?? "访问验证失败，请重试。"}
              </p>
            )}
            {status === "logged_out" && (
              <p className="mt-4 rounded-lg border border-teal-300/20 bg-teal-400/10 p-3 text-sm leading-6 text-teal-100">
                已退出控制台。
              </p>
            )}

            <form action="/access/session" method="post" className="mt-5 space-y-4">
              <input type="hidden" name="next" value={nextPath} />
              <label className="block">
                <span className="text-sm font-medium text-slate-200">访问口令</span>
                <input
                  name="code"
                  type="password"
                  autoComplete="current-password"
                  className="focus-ring mt-2 h-11 w-full rounded-lg border border-white/16 bg-[#071017] px-3 text-sm text-white outline-none placeholder:text-slate-500"
                  placeholder={authEnabled ? "输入控制台口令" : "当前环境未启用"}
                  disabled={!authEnabled}
                />
              </label>
              <button
                type="submit"
                disabled={!authEnabled}
                className="focus-ring inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-teal-400 px-4 text-sm font-semibold text-[#031316] disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
              >
                进入控制台
                <ArrowRight size={16} aria-hidden />
              </button>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}
