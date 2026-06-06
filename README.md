# 个人空间智能物联助手

这是一个面向作品集展示的当前版本原型，用来呈现“个人空间智能物联系统”的完整产品形态。系统包含 3D 公开项目页、确定性模拟环境数据、后端接口、前端控制台、工具优先的智能体流程、安全策略检查、审计日志，以及可选的 MQTT / PostgreSQL / TimescaleDB 入站骨架。

默认演示仍不连接真实 ESP32、摄像头、麦克风、强电继电器或真实设备控制。真实硬件数据可以通过 MQTT 或 HTTP 写入时间序列数据库，但设备动作仍是模拟流程，用来证明产品形态与安全边界。

## 当前版本展示内容

- 3D 公开项目页，说明系统价值、架构闭环和已跑通的工程证据。
- 使用模拟房间数据的私有控制台。
- 最近 24 小时和 7 天环境趋势，支持温度、湿度、二氧化碳、光照、人体存在和噪声分贝模拟数据与数据库遥测切换。
- 结构化异常事件列表，展示严重级别、指标、来源、发生时间、证据摘要和处理建议。
- 传感器健康状态检查，识别缺失、过期和异常质量读数。
- 可选 MQTT 遥测入站服务与 TimescaleDB 存储。
- ESP32 房间传感器节点固件，支持 SHT31、BH1750、SCD40 / SCD41、GPIO 存在传感器和可选 ADC 后备，对齐 MQTT/HTTP 设备消息协议。
- 统一设备连接接口，支持 ESP32、STM32、树莓派和 Linux 网关以 `aiot.v1` 协议注册、心跳、声明能力和上报遥测。
- 带风险等级的设备注册表和可持久化模拟控制；配置数据库时会使用 `device_registry`，否则回退到安全模拟清单。
- 受工具约束的智能体对话，可在模拟数据和数据库遥测之间切换，支持日总结、原因解释、安全行动建议、设备状态分析、结构化异常事件解释、本地设备协议查询，并可选调用当前大模型增强分析。
- 中国区模型厂商配置页，预置小米 MiMo 和 Kimi 接口，并可选择智能体当前模型。
- 只允许低风险模拟动作的策略引擎。
- 工具调用、规则创建、用户确认、控制尝试和拒绝操作的审计日志，并支持按发起方、动作、结果、策略、风险和关键词筛选追溯。
- V0 规则引擎可手动启用、暂停和评估已确认规则，支持指标阈值、人体存在和简单时间条件，满足条件时触发提醒并写入审计日志。

## 本地开发

安装前端依赖：

```bash
npm install
```

创建并启用 Python 虚拟环境，然后安装后端依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements-dev.txt
```

同时启动前后端：

```bash
npm run dev
```

访问地址：

- 前端页面：http://localhost:3000
- 后端接口文档：http://localhost:8000/docs

## 私有控制台访问

私有控制台固定启用访问保护，访问口令为：

```text
admin123
```

部署到公网时仍应设置会话密钥和内部服务令牌。访问口令固定为 `admin123`，不会从环境变量读取 `DASHBOARD_ACCESS_CODE`：

```bash
export DASHBOARD_SESSION_SECRET="替换为随机会话密钥"
export AIOT_INTERNAL_API_TOKEN="替换为内部服务令牌"
export DASHBOARD_COOKIE_SECURE="false"
```

访问保护规则：

- `/` 公开项目页继续开放。
- `/dashboard`、`/trends`、`/devices`、`/agent`、`/models`、`/rules`、`/audit` 会跳转到 `/access`。
- `/api/health` 保持公开健康检查。
- 其他 `/api/*` 私有接口需要登录 cookie，或由 Web 服务携带内部服务令牌访问。

如果部署到 HTTPS 域名，可以把 `DASHBOARD_COOKIE_SECURE` 设为 `true`。当前 IP 直连 HTTP 部署应保持 `false`。

前端浏览器端请求统一走同源 `/api/*` 代理，再由 Next.js 服务端转发到 FastAPI。生产 IP 直连时不要把浏览器端 `NEXT_PUBLIC_API_BASE_URL` 配成 `127.0.0.1`，否则访问者浏览器会请求自己的本机地址并出现 `Failed to fetch`。

## 大模型接入

`/models` 页面拆成两个工具：密钥导入工具只负责导入或覆盖厂商密钥；模型切换工具只负责选择智能体当前使用的厂商、接口和模型。当前预置中国区接口：

- 小米 MiMo：`https://token-plan-cn.xiaomimimo.com/v1`
- 小米 MiMo Anthropic 兼容：`https://token-plan-cn.xiaomimimo.com/anthropic`
- Kimi（月之暗面）：`https://api.moonshot.cn/v1`

智能体仍然坚持工具优先和策略优先：传感器查询、规则草案和设备控制判断先由本地工具完成，外部模型只负责在这些结构化结果之后生成更自然的分析说明。提示注入、高风险控制、未知插座和报警器关闭等被策略拒绝的请求不会发送给外部模型。

模型接口密钥按厂商保存在后端本地数据目录。同一厂商第二次导入会覆盖第一次，切换当前模型时不再输入密钥；接口响应只返回脱敏预览。

Kimi K2.6 使用 `max_completion_tokens`，并在 V0 默认关闭 thinking，以避免连接测试或智能体回复只返回推理字段而没有正文。小米 MiMo Token Plan 同时兼容 `api-key` 和 `Authorization: Bearer` 认证头。

## 可选遥测入站

启动本地 TimescaleDB 和 MQTT broker：

```bash
npm run dev:infra
```

启动 MQTT 入站服务：

```bash
source .venv/bin/activate
npm run dev:ingestor
```

也可以用 HTTP 直接写入传感器读数：

```bash
curl -X POST http://localhost:8000/api/ingest/sensor-readings \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  -d '{
    "device_id": "room_node_01",
    "readings": [
      {"metric": "temperature", "value": 25.4},
      {"metric": "humidity", "value": 48.2},
      {"metric": "co2", "value": 1180},
      {"metric": "noise", "value": 48.5}
    ]
  }'
```

查询数据库来源的当前状态和历史数据：

```bash
curl -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" "http://localhost:8000/api/telemetry/status"
curl -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" "http://localhost:8000/api/room/current?source=database"
curl -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" "http://localhost:8000/api/sensors/history?metric=co2&source=database&bucket=15m&from=2026-06-04T00:00:00%2B08:00"
curl -X POST -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" "http://localhost:8000/api/rules/evaluate?source=database"
```

`bucket` 支持 `5m`、`15m`、`1h`、`1d`。mock 和 database 数据源使用同一套时间桶语义；database 数据源会把真实入库读数聚合后返回，避免前端趋势页直接承受原始高频点。

`/dashboard`、`/trends`、`/agent` 和 `/rules` 页面都可以切换到“数据库遥测”。数据库模式会使用已入库的最新传感器读数和历史曲线；如果未配置 `DATABASE_URL` 或暂无数据，控制台会显示明确的不可用或空数据提示。总览页的“遥测链路”卡片会展示数据库连接、样本数、最新入库时间、Timescale 扩展状态、HTTP/MQTT 入站来源分布和最近设备摘要。

设备清单支持 `source=mock|database|auto`。显式请求 `GET /api/devices?source=database` 时，后端会初始化 `device_registry` 表；如果表为空，会用当前安全种子设备填充。未知负载智能插座和报警器仍保持高风险或禁止状态，不会因为进入数据库而变成可控设备。

统一设备接入接口见 `docs/device-connection-interface.md`，传感器消息协议见 `docs/device-protocol.md`，可执行示例见 `services/mqtt-ingestor/examples/room-node-message.json`。ESP32 固件见 `firmware/esp32-room-node`，默认只发布遥测，不接收设备控制指令；未接入或读取失败的传感器不会伪造成正常读数。

生产环境可以使用系统 PostgreSQL、Mosquitto 和 `infra/systemd` 下的 systemd 模板运行 `aiot-api`、`aiot-web` 和 `aiot-mqtt-ingestor`。服务读取私有 `.dashboard-env` 中的会话密钥、内部服务令牌、`DATABASE_URL`、`MQTT_BROKER_HOST`、`MQTT_BROKER_PORT` 和 `MQTT_TOPIC`；访问口令仍固定为 `admin123`。环境文件示例见 `infra/dashboard-env.example`，具体安装和重启步骤见 `infra/systemd/README.md`。

MQTT 入站链路可以单独验收。脚本会发布一条唯一设备编号的 MQTT batch payload，并通过 API 确认该读数已经从 `mqtt` 来源写入数据库：

```bash
npm run smoke:mqtt
```

核心 API 契约可以单独验收。脚本会验证 `RoomState`、`SensorReading`、`Device`、`AutomationRule`、`AgentMessage`、`ToolCall`、`PolicyDecision`、`AuditLog` 和模型厂商目录的关键字段，确认小米 MiMo / Kimi 中国区入口存在，并避免公开接口被后续改动破坏：

```bash
npm run contract:api
```

ESP32 固件协议可以单独验收。脚本会检查固件真实传感器读取路径、配置模板、密钥忽略规则、设备协议文档和 MQTT 示例 payload 是否一致：

```bash
npm run check:firmware
```

Web 页面路由可以单独验收。脚本会验证公开页、访问口令页、未登录拦截、登录后的总览、趋势、设备、智能体、模型、规则、审计页面，以及 Next.js 同源 `/api/*` 代理鉴权：

```bash
npm run smoke:web
```

部署后可运行服务器烟测，脚本会自动禁用代理环境变量，并验证访问口令、私有 API、结构化异常事件、HTTP 入站、数据库遥测、审计筛选、高风险拒绝和智能体工具回复：

```bash
npm run smoke:server
```

智能体安全边界可用独立评测脚本验证，覆盖提示注入、未知插座、报警器控制、只读设备查询、规则草案确认和普通环境查询：

```bash
npm run eval:agent-safety
```

作品集 3 分钟演示链路可用端到端验收脚本验证，覆盖公开项目页、固定口令控制台、模拟环境趋势、设备风险清单、智能体工具问答、规则草案确认保存和拒绝审计追溯：

```bash
npm run acceptance:demo
```

发布前可以运行总验收入口。它会串联后端单元测试、前端类型检查 / lint / 生产构建、API 契约、ESP32 固件协议、Web 页面、MQTT、服务器烟测、智能体安全评测和 3 分钟演示验收：

```bash
npm run verify:release
```

如果 Web 或 API 不在本机端口，可以显式指定：

```bash
API_BASE_URL="http://82.157.148.249:8000" WEB_BASE_URL="http://82.157.148.249" AIOT_INTERNAL_API_TOKEN="内部服务令牌" npm run smoke:server
API_BASE_URL="http://82.157.148.249:8000" AIOT_INTERNAL_API_TOKEN="内部服务令牌" npm run eval:agent-safety
API_BASE_URL="http://82.157.148.249:8000" WEB_BASE_URL="http://82.157.148.249" AIOT_INTERNAL_API_TOKEN="内部服务令牌" npm run acceptance:demo
```

## 常用命令

```bash
npm run test:api
npm run test:web
npm run test
npm run contract:api
npm run check:firmware
npm run smoke:web
npm run smoke:mqtt
npm run smoke:server
npm run eval:agent-safety
npm run acceptance:demo
npm run verify:release
```

## 当前版本边界

- 数据由确定性模拟器根据时间窗口生成。
- 数据库和 MQTT 已有本地开发骨架；公开演示默认仍使用模拟数据，控制台总览、趋势页、Agent 和规则评估可手动切换到数据库遥测。
- 真实设备接入使用 `aiot.v1` 统一协议；设备可注册、心跳、声明遥测能力和批量上报 readings，但不能通过自注册获得控制权限。
- 规则、审计日志、智能体对话记录和模拟设备状态保存在 `services/api/.local/`；配置数据库后，设备风险元数据会保存在 `device_registry` 表，智能体对话记录保留最近 30 天，可在页面手动删除单条记录。
- 智能体可以建议自动化规则，但创建规则必须经过用户确认。
- 已确认规则可在 `/rules` 启用、暂停和手动评估，并可选择模拟数据或数据库遥测；V0 支持指标阈值、人体存在和简单时间提醒条件，只触发提醒类动作，不执行设备控制，并记录触发次数与最近触发时间。
- 中风险模拟设备需要确认，确认动作和执行结果会分别写入审计日志。
- 同一设备短时间内连续执行控制会触发速率限制，避免误触或自动化循环。
- 设备 API 和智能体共用同一个 device adapter；数据库可用时读取 `device_registry`，默认模拟模式读取安全种子清单，低风险模拟控制会更新设备状态并写入审计日志。
- 审计日志支持按发起方、动作、结果、策略结果、风险等级和关键词过滤，可直接搜索设备页、规则页返回的审计编号。
- 大模型密钥按厂商保存在后端本地数据目录，同一厂商再次导入会覆盖原密钥；当前模型选择单独保存，不要把真实密钥提交到 Git。
- 未知插座、禁止设备、提示注入请求和高风险控制请求都会被拒绝。

## 后续路线

- 下一阶段：把 `firmware/esp32-room-node` 烧录到真实 ESP32 节点，按 `include/config.example.h` 接线并让真实环境数据持续进入数据库。
- 再下一阶段：低风险物理设备控制、确认流程和更强的规则引擎。
- 研究扩展：智能体安全评测任务集和提示注入测试。
