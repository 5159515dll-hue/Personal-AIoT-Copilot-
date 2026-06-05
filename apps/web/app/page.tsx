import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Bot,
  Database,
  Eye,
  FileClock,
  LockKeyhole,
  RadioTower,
  ShieldCheck,
  Workflow
} from "lucide-react";
import { Home3DScene } from "@/components/home-3d-scene";

const pillars = [
  {
    icon: Eye,
    title: "感知空间",
    text: "覆盖温度、湿度、二氧化碳、光照、人体存在和噪声分贝，演示数据和数据库遥测可以切换查看。"
  },
  {
    icon: Database,
    title: "形成记忆",
    text: "MQTT 与 HTTP 入站写入 PostgreSQL / TimescaleDB，控制台展示 24 小时和 7 天趋势。"
  },
  {
    icon: ShieldCheck,
    title: "约束行动",
    text: "每个控制意图都经过策略引擎，中风险需要确认，高风险、未知设备和注入请求会被拒绝。"
  },
  {
    icon: LockKeyhole,
    title: "保护隐私",
    text: "当前版本不采集摄像头、原始语音、屏幕内容或精确位置，只保存必要的环境指标和审计记录。"
  }
];

const evidence = [
  {
    icon: RadioTower,
    title: "遥测入站",
    text: "支持 MQTT 订阅和 HTTP 调试写入，总览页能看到来源分布、最新设备和入库时间。"
  },
  {
    icon: Activity,
    title: "趋势分析",
    text: "同一套接口支持模拟数据和数据库遥测，按 5 分钟、15 分钟、1 小时和 1 天聚合。"
  },
  {
    icon: Bot,
    title: "智能体工具层",
    text: "房间状态、历史曲线、异常检测、规则草案和安全策略都先走本地工具，再由模型增强说明。"
  },
  {
    icon: FileClock,
    title: "可追溯审计",
    text: "模型切换、工具调用、规则确认、设备控制、拒绝操作和对话删除都会写入审计日志。"
  }
];

const architectureSteps = ["传感器节点", "MQTT / HTTP", "时序数据库", "控制台与智能体", "策略与审计"];

export default function HomePage() {
  return (
    <main className="bg-white text-ink">
      <section className="relative min-h-[92svh] overflow-hidden bg-[#03070d] text-white">
        <Home3DScene />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_72%_45%,rgba(36,230,238,0.1)_0%,rgba(3,7,13,0)_42%),linear-gradient(90deg,rgba(3,7,13,0.9)_0%,rgba(3,7,13,0.54)_39%,rgba(3,7,13,0.04)_100%)]" />
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
                把环境感知、遥测入库、模型推理、设备策略和审计记录放进一个可运行原型。
                当前版本可以用模拟数据演示，也可以读取服务器上的 MQTT / 数据库遥测链路。
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
                  <dt className="text-slate-400">感知指标</dt>
                  <dd className="mt-1 font-semibold text-white">6 类环境数据</dd>
                </div>
                <div>
                  <dt className="text-slate-400">遥测链路</dt>
                  <dd className="mt-1 font-semibold text-white">MQTT / HTTP</dd>
                </div>
                <div>
                  <dt className="text-slate-400">执行边界</dt>
                  <dd className="mt-1 font-semibold text-white">策略与审计</dd>
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
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-normal">已经跑通的工程证据</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
                这个版本不是静态展示页。控制台、接口、数据库、智能体、安全策略和审计都可以在服务器上直接演示。
              </p>
            </div>
            <Link
              href="/dashboard?source=database"
              className="focus-ring inline-flex h-10 w-fit items-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              查看数据库遥测
              <ArrowRight size={16} aria-hidden />
            </Link>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {evidence.map((item) => {
              const Icon = item.icon;
              return (
                <article key={item.title} className="rounded-lg border border-line bg-white p-5 shadow-sm">
                  <Icon className="text-sky-700" size={22} aria-hidden />
                  <h3 className="mt-4 text-base font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{item.text}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-y border-line bg-[#0b1117] px-5 py-14 text-white sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="flex items-start gap-3">
            <Workflow className="mt-1 text-amber-200" size={24} aria-hidden />
            <div>
              <h2 className="text-2xl font-semibold tracking-normal">端到端闭环</h2>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
                真实传感器接入前，系统用模拟数据保证演示稳定；服务器部署同时保留 MQTT、数据库和健康检查，
                用于验证硬件上报后如何进入同一个智能体和控制台闭环。
              </p>
            </div>
          </div>

          <div className="mt-8 grid gap-3 lg:grid-cols-5">
            {architectureSteps.map((step, index) => (
              <div key={step} className="rounded-lg border border-white/12 bg-white/6 p-4">
                <p className="text-xs font-semibold text-amber-200">步骤 {index + 1}</p>
                <p className="mt-3 text-sm font-semibold text-white">{step}</p>
                <p className="mt-2 text-xs leading-5 text-slate-400">{architectureDescription(step)}</p>
              </div>
            ))}
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

function architectureDescription(step: string): string {
  const descriptions: Record<string, string> = {
    传感器节点: "ESP32 固件骨架只发布环境遥测，不订阅远程控制命令。",
    "MQTT / HTTP": "批量、单指标和扁平 map payload 会被统一解析。",
    时序数据库: "读数进入 sensor_readings，并保留来源、设备和质量状态。",
    控制台与智能体: "页面和工具层共享同一套房间状态、趋势和设备接口。",
    策略与审计: "允许、确认、拒绝、触发和删除动作都有审计记录。"
  };
  return descriptions[step] ?? "";
}
