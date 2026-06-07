import Link from "next/link";
import { Cable, Cpu, Database, FileCode2, Network, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";

export const dynamic = "force-dynamic";

const esp32Code = `// ESP32 / Arduino：注册后用 MQTT 或 HTTP 上报同一个 device_id
const char* API_BASE = "http://82.157.148.249:8000";
const char* DEVICE_ID = "esp32_room_node_01";

// 推荐：MQTT topic = aiot/v1/devices/esp32_room_node_01/telemetry
{
  "protocol_version": "aiot.v1",
  "message_id": "esp32_room_node_01-101",
  "sequence": 101,
  "device": { "id": "esp32_room_node_01", "type": "esp32" },
  "telemetry": {
    "readings": [
      { "metric": "temperature", "value": 25.4, "unit": "C" },
      { "metric": "co2", "value": 930, "unit": "ppm" }
    ]
  }
}`;

const stm32Code = `// STM32 C/C++：通过网关或蜂窝模组发送 HTTP 遥测
POST http://82.157.148.249:8000/api/device-connections/stm32_lab_node_01/telemetry
Header: X-AIoT-Internal-Token: <内部令牌>

{
  "protocol_version": "aiot.v1",
  "message_id": "stm32_lab_node_01-00042",
  "sequence": 42,
  "firmware_version": "0.1.0",
  "readings": [
    { "metric": "humidity", "value": 48.2, "unit": "%" },
    { "metric": "presence", "value": 1, "unit": "bool" }
  ]
}`;

const raspberryCode = `# 树莓派 Python：适合作为边缘网关，批量转发多个传感器
import requests
from datetime import datetime, timezone

API_BASE = "http://82.157.148.249:8000"
TOKEN = "<内部令牌>"
DEVICE_ID = "raspi_gateway_01"

headers = {"X-AIoT-Internal-Token": TOKEN}
payload = {
    "protocol_version": "aiot.v1",
    "message_id": f"{DEVICE_ID}-telemetry-001",
    "sequence": 1,
    "sent_at": datetime.now(timezone.utc).isoformat(),
    "readings": [
        {"metric": "temperature", "value": 25.1, "unit": "C"},
        {"metric": "noise", "value": 47.5, "unit": "dB"},
    ],
}
requests.post(f"{API_BASE}/api/device-connections/{DEVICE_ID}/telemetry", json=payload, headers=headers, timeout=5)`;

export default function HardwarePage() {
  return (
    <AppShell>
      <PageHeader
        title="硬件接入"
        description="ESP32、STM32、树莓派和后续设备统一使用 aiot.v1 协议；设备默认只读，控制权限必须在服务器后台人工标记并经过策略引擎。"
        action={
          <Link
            href="/devices"
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Cpu size={16} aria-hidden />
            返回设备
          </Link>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="space-y-5">
          <Panel icon={<Network size={18} aria-hidden />} title="统一连接流程">
            <ol className="space-y-3 text-sm leading-6 text-slate-700">
              <li>1. 在设备页预建设备档案，固定 `device_id`、位置、硬件类型和风险等级。</li>
              <li>2. 硬件启动后调用注册接口，服务器自动把同一 `device_id` 的连接记录绑定到档案。</li>
              <li>3. 设备周期性发送心跳，维护在线状态、固件版本、信号强度和最后序号。</li>
              <li>4. 设备批量发送遥测 readings，服务器写入 PostgreSQL / TimescaleDB，并供趋势页、规则和智能体读取。</li>
              <li>5. 低风险控制必须走 `/api/devices/{'{device_id}'}/control`，策略和审计成功后才执行模拟或真实适配器动作。</li>
            </ol>
          </Panel>

          <Panel icon={<Database size={18} aria-hidden />} title="HTTP 接口">
            <div className="grid gap-3 md:grid-cols-2">
              <Endpoint method="POST" path="/api/device-connections/register" note="设备首次注册，幂等写入连接表。" />
              <Endpoint method="POST" path="/api/device-connections/{device_id}/heartbeat" note="周期心跳，更新在线状态和诊断指标。" />
              <Endpoint method="POST" path="/api/device-connections/{device_id}/telemetry" note="版本化遥测，上报多条 readings。" />
              <Endpoint method="GET" path="/api/device-connections" note="后台查看真实连接记录。" />
              <Endpoint method="POST" path="/api/devices/management" note="预建设备档案，硬件未到也能先配置。" />
              <Endpoint method="DELETE" path="/api/devices/{device_id}/management" note="删除后台档案和连接记录，保留历史遥测。" />
            </div>
          </Panel>

          <Panel icon={<ShieldCheck size={18} aria-hidden />} title="并发和安全冗余">
            <ul className="grid gap-3 text-sm leading-6 text-slate-700 md:grid-cols-2">
              <li className="rounded-lg bg-slate-50 p-3">每条消息使用 `message_id` 去重，兼容 MQTT QoS 1 和网关重试。</li>
              <li className="rounded-lg bg-slate-50 p-3">每台设备使用递增 `sequence`，旧心跳不会回滚在线状态。</li>
              <li className="rounded-lg bg-slate-50 p-3">单次遥测最多 64 条 readings，设备端或网关端应先聚合再发送。</li>
              <li className="rounded-lg bg-slate-50 p-3">新设备强制只读，不允许通过 payload 自行提升为可控设备。</li>
              <li className="rounded-lg bg-slate-50 p-3">大模型只能基于工具结果建议或发起低风险策略链路，不能直接绕过控制接口。</li>
              <li className="rounded-lg bg-slate-50 p-3">强电、未知插座、报警器、门锁和燃气设备保持拒绝或人工确认边界。</li>
            </ul>
          </Panel>

          <Panel icon={<FileCode2 size={18} aria-hidden />} title="ESP32 示例">
            <CodeBlock code={esp32Code} />
            <p className="mt-3 text-sm leading-6 text-muted">完整代码位置：`firmware/esp32-room-node/src/main.cpp`。</p>
          </Panel>

          <Panel icon={<FileCode2 size={18} aria-hidden />} title="STM32 示例">
            <CodeBlock code={stm32Code} />
            <p className="mt-3 text-sm leading-6 text-muted">完整代码位置：`firmware/stm32-room-node/src/main.cpp`。</p>
          </Panel>

          <Panel icon={<FileCode2 size={18} aria-hidden />} title="树莓派示例">
            <CodeBlock code={raspberryCode} />
            <p className="mt-3 text-sm leading-6 text-muted">完整代码位置：`examples/raspberry-pi-gateway/aiot_gateway.py`。</p>
          </Panel>
        </section>

        <aside className="space-y-5">
          <Panel icon={<Cable size={18} aria-hidden />} title="接入清单">
            <ul className="space-y-2 text-sm leading-6 text-slate-700">
              <li>设备编号：稳定、唯一、可读。</li>
              <li>协议版本：当前固定 `aiot.v1`。</li>
              <li>数据来源：MQTT 生产优先，HTTP 调试优先。</li>
              <li>令牌：不要直接烧进大量终端，优先由网关保管。</li>
              <li>控制：先标记负载，再启用低风险控制。</li>
            </ul>
          </Panel>

          <Panel icon={<Database size={18} aria-hidden />} title="本地文档">
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>`docs/device-connection-interface.md`：完整接口设计。</p>
              <p>`docs/device-protocol.md`：MQTT 与 HTTP payload 规范。</p>
              <p>`docs/agent-tools.md`：智能体工具和策略链路。</p>
              <p>`docs/security-policy.md`：控制风险和审计边界。</p>
            </div>
          </Panel>
        </aside>
      </div>
    </AppShell>
  );
}

function Panel({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
        <span className="text-teal-700">{icon}</span>
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Endpoint({ method, path, note }: { method: string; path: string; note: string }) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-3">
      <p className="text-xs font-semibold text-teal-700">{method}</p>
      <p className="mt-1 break-all font-mono text-xs text-ink">{path}</p>
      <p className="mt-2 text-xs leading-5 text-muted">{note}</p>
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
      <code>{code}</code>
    </pre>
  );
}
