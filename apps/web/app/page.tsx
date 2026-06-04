import Link from "next/link";
import { ArrowRight, Bot, Database, Eye, LockKeyhole, ShieldCheck } from "lucide-react";
import { Home3DScene } from "@/components/home-3d-scene";

const pillars = [
  {
    icon: Eye,
    title: "感知空间",
    text: "当前版本使用确定性的模拟遥测，覆盖二氧化碳、温度、湿度、光照、有人状态、设备和异常事件。"
  },
  {
    icon: Database,
    title: "形成记忆",
    text: "后端提供时间窗口查询，并在本地持久化自动化规则与审计记录。"
  },
  {
    icon: ShieldCheck,
    title: "约束行动",
    text: "智能体意图必须经过工具结构、策略检查、确认规则和审计日志。"
  },
  {
    icon: LockKeyhole,
    title: "保护隐私",
    text: "当前版本不包含摄像头、麦克风、真实设备控制或个人实时隐私数据。"
  }
];

export default function HomePage() {
  return (
    <main className="bg-white text-ink">
      <section className="relative min-h-[92svh] overflow-hidden bg-[#03070d] text-white">
        <Home3DScene />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_72%_45%,rgba(26,207,217,0.14)_0%,rgba(3,7,13,0)_44%),linear-gradient(90deg,rgba(3,7,13,0.98)_0%,rgba(3,7,13,0.72)_43%,rgba(3,7,13,0.18)_100%)]" />
        <div className="absolute inset-x-0 top-0 z-10 px-5 py-5 sm:px-8 lg:px-12">
          <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 text-sm">
            <Link href="/" className="focus-ring font-semibold tracking-normal text-white">
              个人空间智能物联助手
            </Link>
            <div className="flex items-center gap-2 text-xs text-slate-300 sm:gap-4">
              <Link href="/dashboard" className="focus-ring hover:text-white">
                控制台
              </Link>
              <Link href="/agent" className="focus-ring hover:text-white">
                智能体
              </Link>
              <Link href="/models" className="focus-ring hover:text-white">
                模型
              </Link>
            </div>
          </nav>
        </div>
        <div className="relative z-10 flex min-h-[92svh] items-center px-5 pb-14 pt-24 sm:px-8 lg:px-12">
          <div className="mx-auto w-full max-w-7xl">
            <div className="max-w-[780px]">
              <p className="text-sm font-semibold tracking-[0.18em] text-amber-200">模拟空间 · 安全策略 · 可审计智能体</p>
              <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal text-white sm:text-5xl md:whitespace-nowrap lg:text-6xl">
                <span className="block sm:inline">个人空间智能</span>
                <span className="block sm:inline">物联助手</span>
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-slate-200 sm:text-lg">
                把环境感知、模型推理、设备策略和审计记录放进一个可运行原型。当前版本使用模拟数据，
                用来展示智能物联系统从理解空间到安全执行的完整链路。
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/dashboard"
                  className="focus-ring inline-flex h-11 items-center gap-2 rounded-lg bg-teal-500 px-4 text-sm font-semibold text-[#031316] shadow-[0_0_36px_rgba(20,184,166,0.35)]"
                >
                  打开控制台
                  <ArrowRight size={16} aria-hidden />
                </Link>
                <a
                  href="#architecture"
                  className="focus-ring inline-flex h-11 items-center rounded-lg border border-white/24 bg-white/8 px-4 text-sm font-semibold text-white backdrop-blur"
                >
                  查看架构
                </a>
              </div>
              <dl className="mt-10 grid max-w-xl grid-cols-3 gap-4 border-t border-white/16 pt-5 text-sm">
                <div>
                  <dt className="text-slate-400">数据窗口</dt>
                  <dd className="mt-1 font-semibold text-white">24 小时 / 7 天</dd>
                </div>
                <div>
                  <dt className="text-slate-400">动作边界</dt>
                  <dd className="mt-1 font-semibold text-white">策略强制</dd>
                </div>
                <div>
                  <dt className="text-slate-400">记录方式</dt>
                  <dd className="mt-1 font-semibold text-white">全链路审计</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
        <div className="absolute inset-x-0 bottom-0 z-10 h-16 border-t border-white/10 bg-[linear-gradient(180deg,rgba(3,7,13,0)_0%,rgba(7,14,21,0.84)_100%)]" />
      </section>

      <section className="border-b border-line bg-[#071017] px-5 py-5 text-white sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 text-sm">
          <span className="text-slate-300">下一步可以直接进入演示控制台，也可以查看系统边界与模型接入。</span>
          <div className="flex flex-wrap gap-2">
            {[
              { href: "/trends", label: "趋势数据" },
              { href: "/devices", label: "设备策略" },
              { href: "/audit", label: "审计日志" }
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="focus-ring rounded-lg border border-white/12 px-3 py-2 text-xs font-semibold text-slate-100 hover:border-teal-300/60"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section id="architecture" className="border-y border-line bg-wash px-5 py-12 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <h2 className="text-2xl font-semibold tracking-normal">当前版本系统形态</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {pillars.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <article key={pillar.title} className="rounded-lg border border-line bg-white p-5 shadow-sm">
                  <Icon className="text-teal-700" size={22} aria-hidden />
                  <h3 className="mt-4 text-base font-semibold">{pillar.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{pillar.text}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="px-5 py-14 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div>
            <h2 className="text-2xl font-semibold tracking-normal">安全优先的智能体闭环</h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              智能体不会直接调用物理设备接口。它先生成行动意图，再由受约束工具收集数据或请求动作，
              策略引擎做最终判断，每个关键步骤都会写入审计日志。
            </p>
            <Link
              href="/agent"
              className="focus-ring mt-6 inline-flex h-10 items-center gap-2 rounded-lg bg-ink px-4 text-sm font-semibold text-white"
            >
              试用智能体
              <Bot size={16} aria-hidden />
            </Link>
          </div>
          <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
            <div className="grid gap-3 text-sm font-medium text-slate-700 sm:grid-cols-4">
              {["遥测数据", "工具调用", "策略判断", "审计记录"].map((step, index) => (
                <div key={step} className="rounded-lg bg-slate-50 p-4">
                  <p className="text-xs text-muted">步骤 {index + 1}</p>
                  <p className="mt-2">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
