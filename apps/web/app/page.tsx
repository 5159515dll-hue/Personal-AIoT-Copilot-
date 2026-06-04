import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Database, Eye, LockKeyhole, ShieldCheck } from "lucide-react";

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
      <section className="relative flex min-h-[82vh] items-end overflow-hidden">
        <Image
          src="/aiot-copilot-concept.png"
          alt="个人空间智能物联助手控制台概念图"
          fill
          priority
          className="object-cover object-center"
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.96)_0%,rgba(255,255,255,0.78)_42%,rgba(255,255,255,0.28)_100%)]" />
        <div className="relative z-10 w-full px-5 pb-12 pt-24 sm:px-8 lg:px-12">
          <div className="max-w-3xl">
            <h1 className="text-4xl font-semibold leading-tight tracking-normal text-ink sm:text-6xl">
              个人空间智能物联助手
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-700">
              一个面向个人学习与生活空间的智能物联原型，把模拟环境感知、
              受约束的大模型工具、安全策略和审计能力放进同一个可运行控制台。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/dashboard"
                className="focus-ring inline-flex h-11 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white"
              >
                打开控制台
                <ArrowRight size={16} aria-hidden />
              </Link>
              <a
                href="#architecture"
                className="focus-ring inline-flex h-11 items-center rounded-lg border border-line bg-white px-4 text-sm font-semibold text-slate-700"
              >
                查看架构
              </a>
            </div>
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
