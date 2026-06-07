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
    -> 设备连接注册与心跳
    -> 边缘事件、媒体索引与实时流配置
    -> 智能体工具层
    -> 策略引擎
    -> 本地规则与审计日志
```

## 运行模块

- `apps/web`：公开项目页和控制台。
- `apps/web/app/api/[...path]/route.ts`：浏览器端同源 API 代理，服务端再转发到 FastAPI，避免 IP 部署时浏览器直连本机地址。
- `apps/web/middleware.ts`：保护私有控制台路由，公开项目页不拦截。
- `firmware/esp32-room-node`：ESP32 房间传感器节点固件，读取真实环境传感器并发布符合设备协议的 MQTT 遥测。
- `services/api/app/routes`：前端使用的后端接口。
- `services/api/app/auth.py`：私有 API 登录 cookie 和内部服务令牌校验。
- `services/api/app/mock_data.py`：确定性传感器数据和设备注册表种子数据。
- `services/api/app/device_adapter.py`：设备注册表适配器；有数据库时读取 `device_registry`，无数据库时回退到模拟清单，并继续持久化模拟控制状态。
- `services/api/app/device_connections.py`：统一设备连接服务，处理注册、心跳、能力声明和遥测入站后的连接状态更新。
- `services/api/app/ingestion.py`：HTTP 与 MQTT payload 转换为统一传感器读数。
- `services/api/app/database.py`：PostgreSQL / TimescaleDB 表结构、传感器读写、设备注册表、设备连接表读写和查询。
- `services/api/app/media_store.py`：边缘识别事件、事件媒体、本机文件索引和实时流配置；图片和视频不进入传感器 readings。
- `services/api/app/anomaly_events.py`：从当前读数、历史曲线和传感器健康状态推导结构化异常事件。
- `services/api/app/agent_tools.py`：工具优先的智能体编排。
- `services/api/app/space_store.py`：多房间/空间配置，保存当前空间、区域、设备绑定和未来感知能力边界。
- `services/api/app/policy.py`：风险分级、确认要求和拒绝逻辑。
- `services/api/app/rule_engine.py`：评估简单 IF/THEN 提醒规则并写入触发审计。
- `services/api/app/audit.py`：持久化审计记录。
- `services/mqtt-ingestor`：订阅 MQTT 遥测并写入时间序列数据库。
- `infra/docker-compose.yml`：本地数据库、MQTT broker、API、前端和入站服务编排。
- `infra/systemd`：生产服务器上的 API、Web、MQTT 入站和 MediaMTX systemd 服务模板。
- `docs/device-protocol.md`：MQTT 与 HTTP 遥测 payload 协议，约束 ESP32 节点、脚本和入站服务的稳定格式。
- `docs/media-streaming.md`：树莓派边缘事件、事件媒体、设备令牌和 RTSP/HLS 实时流边界。

## 默认模拟数据流

1. 前端控制台请求当前房间状态或历史趋势。
2. 后端根据时间窗口返回模拟读数。
3. 智能体请求会被映射到受约束工具。
4. 工具返回结构化数据和必要的策略判断。
5. 设备 API 和智能体先读取设备注册表视图；控制尝试会被允许、要求确认或拒绝；允许的模拟动作通过 device adapter 更新状态。
6. 已确认规则可手动评估，默认使用模拟状态，必要时也可以切换到数据库遥测。
7. 关键事件持久化到 `services/api/.local/`。

## 可选真实遥测数据流

1. 传感器节点向 MQTT topic `aiot/room/+/telemetry` 发布 JSON 消息。
2. `services/mqtt-ingestor` 按 `docs/device-protocol.md` 解析 batch、单指标或 metric map payload。
3. 入站服务将读数写入 `sensor_readings` 表。
4. `GET /api/telemetry/status` 汇总数据库连通性、样本数、最新入库时间和 Timescale 扩展状态。
5. `GET /api/room/current?source=database` 从数据库最新读数生成当前房间摘要。
6. `GET /api/sensors/history?source=database&bucket=15m&from=...` 从数据库读取并聚合历史曲线。
7. `POST /api/rules/evaluate?source=database` 使用数据库最新房间状态评估已确认规则。
8. `/dashboard`、`/trends`、`/agent` 和 `/rules` 可选择 database 数据源，用入库最新读数和历史曲线展示、回答环境问题或评估提醒规则。
9. `/spaces` 管理多个房间或区域；摄像头、人脸、情绪和定位能力默认关闭，只有 `local_only` 并开启媒体策略的空间才接受边缘事件、事件媒体或实时流。
9. `GET /api/devices?source=database` 会初始化并读取 `device_registry` 表；表为空时用当前安全种子设备填充，未知负载插座和报警器仍保持不可控。
10. `POST /api/device-connections/register`、`/heartbeat` 和 `/{device_id}/telemetry` 提供统一设备接入接口，ESP32、STM32、树莓派和 Linux 网关都使用 `aiot.v1` envelope。
11. `POST /api/device-connections/{device_id}/events` 和 `/media` 使用设备令牌接收边缘识别结果和事件媒体；`/api/streams` 管理 RTSP 到 HLS 实时流。
12. 默认控制台仍使用 mock 数据，避免公开演示依赖真实隐私数据。

## ESP32 固件边界

`firmware/esp32-room-node` 已提供真实传感器读取路径，支持 SHT31 温湿度、SCD40 / SCD41 CO2、BH1750 光照、GPIO 人体存在和可选 ADC 噪声分贝。固件只发布遥测，不订阅控制 topic，不接收远程执行命令，也不携带真实 Wi-Fi 或 MQTT 密钥；噪声只上报 dB 数值，不采集或上传原始音频。未接入或读取失败的传感器会被跳过，避免把固定值伪装成真实数据。

树莓派摄像头、人脸识别、情绪识别和位置定位属于高敏感能力。当前版本采用边缘优先：树莓派本地识别，服务器接收结构化事件、事件媒体和受保护 HLS 流；不做人脸身份库、不保存原始音频、不记录精确 GPS。智能体只读取边缘事件和媒体元数据，不直接读取原始图片或视频。

生产部署可以直接使用系统 PostgreSQL 和 Mosquitto。`aiot-api`、`aiot-web` 和 `aiot-mqtt-ingestor` 共用 `.dashboard-env`，其中会话密钥、内部服务令牌、`DATABASE_URL` 与 MQTT 参数只保存在服务器私有环境文件中，不提交到 Git。私有控制台访问口令固定为 `admin123`，不依赖环境变量覆盖。

## 下一阶段替换点

- 烧录并接线真实 ESP32 节点，让真实传感器数据持续写入数据库。
- 基于真实硬件运行长时间离线、乱序和异常读数测试。
- 为数据库设备注册表增加后台管理界面、真实硬件绑定字段和设备下线流程。
- 扩展入站消息去重窗口、乱序补偿策略和大规模 broker 分片压测。
- 用 PostgreSQL 或 TimescaleDB 替换本地规则、审计、媒体事件和实时流 JSON 索引。
- 保持智能体、策略和审计接口稳定。
