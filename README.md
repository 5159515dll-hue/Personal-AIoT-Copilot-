# 个人空间智能物联助手

这是一个面向作品集展示的当前版本原型，用来呈现“个人空间智能物联系统”的完整产品形态。系统包含 3D 公开项目页、确定性模拟环境数据、后端接口、前端控制台、工具优先的智能体流程、安全策略检查、审计日志，以及可选的 MQTT / PostgreSQL / TimescaleDB 入站骨架。

默认演示仍不连接真实 ESP32、摄像头、麦克风、强电继电器或真实设备控制。真实硬件数据可以通过 MQTT 或 HTTP 写入时间序列数据库，但设备动作仍是模拟流程，用来证明产品形态与安全边界。

## 当前版本展示内容

- 公开项目页，说明系统价值与架构。
- 使用模拟房间数据的私有控制台。
- 最近 24 小时和 7 天环境趋势。
- 可选 MQTT 遥测入站服务与 TimescaleDB 存储。
- 带风险等级的设备清单和模拟控制。
- 受工具约束的智能体对话。
- 中国区模型厂商配置页，预置小米 MiMo 和 Kimi 接口。
- 只允许低风险模拟动作的策略引擎。
- 工具调用、规则创建、控制尝试和拒绝操作的审计日志。

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

查询数据库来源的历史数据：

```bash
curl "http://localhost:8000/api/sensors/history?metric=co2&source=database&from=2026-06-04T00:00:00%2B08:00"
```

MQTT 消息示例见 `services/mqtt-ingestor/examples/room-node-message.json`。

## 常用命令

```bash
npm run test:api
npm run test:web
npm run test
```

## 当前版本边界

- 数据由确定性模拟器根据时间窗口生成。
- 数据库和 MQTT 已有本地开发骨架，但公开演示默认仍使用模拟数据。
- 规则和审计日志保存在 `services/api/.local/`。
- 智能体可以建议自动化规则，但创建规则必须经过用户确认。
- 未知插座、禁止设备、提示注入请求和高风险控制请求都会被拒绝。

## 后续路线

- 下一阶段：接入 ESP32 传感器节点、消息队列和真实环境数据。
- 再下一阶段：低风险物理设备控制、确认流程和更强的规则引擎。
- 研究扩展：智能体安全评测任务集和提示注入测试。
