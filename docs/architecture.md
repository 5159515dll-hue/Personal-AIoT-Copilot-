# 架构说明

个人空间智能物联助手当前版本是一个作品集优先的分阶段实现，用来展示个人空间智能体系统的端到端形态。默认演示使用模拟数据，同时保留 MQTT 和时间序列数据库入站链路，方便后续接入真实 ESP32 传感器节点。

```text
前端控制台
  -> 访问口令会话
  -> 后端接口
    -> 确定性模拟遥测
    -> HTTP 传感器写入接口
    -> MQTT 入站服务
    -> PostgreSQL / TimescaleDB
    -> 智能体工具层
    -> 策略引擎
    -> 本地规则与审计日志
```

## 运行模块

- `apps/web`：公开项目页和控制台。
- `apps/web/middleware.ts`：保护私有控制台路由，公开项目页不拦截。
- `services/api/app/routes`：前端使用的后端接口。
- `services/api/app/auth.py`：私有 API 登录 cookie 和内部服务令牌校验。
- `services/api/app/mock_data.py`：确定性传感器与设备数据。
- `services/api/app/ingestion.py`：HTTP 与 MQTT payload 转换为统一传感器读数。
- `services/api/app/database.py`：PostgreSQL / TimescaleDB 表结构、写入和查询。
- `services/api/app/agent_tools.py`：工具优先的智能体编排。
- `services/api/app/policy.py`：风险分级、确认要求和拒绝逻辑。
- `services/api/app/audit.py`：持久化审计记录。
- `services/mqtt-ingestor`：订阅 MQTT 遥测并写入时间序列数据库。
- `infra/docker-compose.yml`：本地数据库、MQTT broker、API、前端和入站服务编排。

## 默认模拟数据流

1. 前端控制台请求当前房间状态或历史趋势。
2. 后端根据时间窗口返回模拟读数。
3. 智能体请求会被映射到受约束工具。
4. 工具返回结构化数据和必要的策略判断。
5. 控制尝试会被允许、要求确认或拒绝。
6. 关键事件持久化到 `services/api/.local/`。

## 可选真实遥测数据流

1. 传感器节点向 MQTT topic `aiot/room/+/telemetry` 发布 JSON 消息。
2. `services/mqtt-ingestor` 解析 batch、单指标或 metric map payload。
3. 入站服务将读数写入 `sensor_readings` 表。
4. `GET /api/sensors/history?source=database&from=...` 从数据库读取历史曲线。
5. 默认 dashboard 仍使用 mock 数据，避免公开演示依赖真实隐私数据。

## 下一阶段替换点

- 用数据库设备注册表替换静态设备清单。
- 让 Agent 工具按用户选择从 mock 或 database 数据源读取。
- 用 PostgreSQL 或 TimescaleDB 替换本地规则与审计 JSON 持久化。
- 保持智能体、策略和审计接口稳定。
