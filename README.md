# 个人空间智能物联助手

这是一个面向作品集展示的当前版本原型，用来呈现“个人空间智能物联系统”的完整产品形态。系统包含 3D 公开项目页、确定性模拟环境数据、后端接口、前端控制台、工具优先的智能体流程、安全策略检查、审计日志，以及可选的 MQTT / PostgreSQL / TimescaleDB 入站骨架。

默认演示仍不连接真实 ESP32、摄像头、麦克风、强电继电器或真实设备控制。真实硬件数据可以通过 MQTT 或 HTTP 写入时间序列数据库，但设备动作仍是模拟流程，用来证明产品形态与安全边界。

## 当前版本展示内容

- 公开项目页，说明系统价值与架构。
- 使用模拟房间数据的私有控制台。
- 最近 24 小时和 7 天环境趋势，支持模拟数据和数据库遥测切换。
- 可选 MQTT 遥测入站服务与 TimescaleDB 存储。
- 带风险等级的设备清单和可持久化模拟控制。
- 受工具约束的智能体对话，可在模拟数据和数据库遥测之间切换，并可选调用当前大模型增强分析。
- 中国区模型厂商配置页，预置小米 MiMo 和 Kimi 接口，并可选择智能体当前模型。
- 只允许低风险模拟动作的策略引擎。
- 工具调用、规则创建、控制尝试和拒绝操作的审计日志。
- V0 规则引擎可手动评估已确认规则，满足条件时触发提醒并写入审计日志。

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

本地开发默认不启用访问保护。部署到公网时应设置以下环境变量：

```bash
export DASHBOARD_ACCESS_CODE="替换为控制台口令"
export DASHBOARD_SESSION_SECRET="替换为随机会话密钥"
export AIOT_INTERNAL_API_TOKEN="替换为内部服务令牌"
export DASHBOARD_COOKIE_SECURE="false"
```

启用后：

- `/` 公开项目页继续开放。
- `/dashboard`、`/trends`、`/devices`、`/agent`、`/models`、`/rules`、`/audit` 会跳转到 `/access`。
- `/api/health` 保持公开健康检查。
- 其他 `/api/*` 私有接口需要登录 cookie，或由 Web 服务携带内部服务令牌访问。

如果部署到 HTTPS 域名，可以把 `DASHBOARD_COOKIE_SECURE` 设为 `true`。当前 IP 直连 HTTP 部署应保持 `false`。

## 大模型接入

`/models` 页面用于选择智能体当前使用的大模型。当前预置中国区接口：

- 小米 MiMo：`https://token-plan-cn.xiaomimimo.com/v1`
- 小米 MiMo Anthropic 兼容：`https://token-plan-cn.xiaomimimo.com/anthropic`
- Kimi（月之暗面）：`https://api.moonshot.cn/v1`

智能体仍然坚持工具优先和策略优先：传感器查询、规则草案和设备控制判断先由本地工具完成，外部模型只负责在这些结构化结果之后生成更自然的分析说明。提示注入、高风险控制、未知插座和报警器关闭等被策略拒绝的请求不会发送给外部模型。

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
  -d '{
    "device_id": "room_node_01",
    "readings": [
      {"metric": "temperature", "value": 25.4},
      {"metric": "humidity", "value": 48.2},
      {"metric": "co2", "value": 1180}
    ]
  }'
```

查询数据库来源的当前状态和历史数据：

```bash
curl "http://localhost:8000/api/room/current?source=database"
curl "http://localhost:8000/api/sensors/history?metric=co2&source=database&bucket=15m&from=2026-06-04T00:00:00%2B08:00"
```

`bucket` 支持 `5m`、`15m`、`1h`、`1d`。mock 和 database 数据源使用同一套时间桶语义；database 数据源会把真实入库读数聚合后返回，避免前端趋势页直接承受原始高频点。

`/dashboard`、`/trends` 和 `/agent` 页面都可以切换到“数据库遥测”。数据库模式会使用已入库的最新传感器读数和历史曲线；如果未配置 `DATABASE_URL` 或暂无数据，控制台会显示明确的不可用或空数据提示。

MQTT 消息示例见 `services/mqtt-ingestor/examples/room-node-message.json`。

生产环境可以使用系统 PostgreSQL、Mosquitto 和 `infra/systemd/aiot-mqtt-ingestor.service`。服务读取私有 `.dashboard-env` 中的 `DATABASE_URL`、`MQTT_BROKER_HOST`、`MQTT_BROKER_PORT` 和 `MQTT_TOPIC`，收到 MQTT 消息后会初始化表结构并写入 `sensor_readings`。

## 常用命令

```bash
npm run test:api
npm run test:web
npm run test
```

## 当前版本边界

- 数据由确定性模拟器根据时间窗口生成。
- 数据库和 MQTT 已有本地开发骨架；公开演示默认仍使用模拟数据，控制台总览、趋势页和 Agent 可手动切换到数据库遥测。
- 规则、审计日志和模拟设备状态保存在 `services/api/.local/`。
- 智能体可以建议自动化规则，但创建规则必须经过用户确认。
- 已确认规则可在 `/rules` 手动评估；V0 只触发提醒类动作，不执行设备控制。
- 设备 API 和智能体共用同一个 mock device adapter；低风险模拟控制会更新设备状态并写入审计日志。
- 大模型密钥保存在后端本地数据目录，接口只返回脱敏预览；不要把真实密钥提交到 Git。
- 未知插座、禁止设备、提示注入请求和高风险控制请求都会被拒绝。

## 后续路线

- 下一阶段：接入 ESP32 传感器节点、消息队列和真实环境数据。
- 再下一阶段：低风险物理设备控制、确认流程和更强的规则引擎。
- 研究扩展：智能体安全评测任务集和提示注入测试。
