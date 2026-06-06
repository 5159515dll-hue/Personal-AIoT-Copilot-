# 设备连接接口设计

本系统把嵌入式设备接入拆成两条通道：低频设备连接管理和高频遥测入站。ESP32、STM32、树莓派、Linux 网关或后续其他节点都使用同一套 `aiot.v1` 协议，不为单一硬件型号定制接口。

## 连接方式

推荐生产路径：

```text
设备 -> MQTT broker -> mqtt-ingestor -> FastAPI/数据库
```

调试或网关路径：

```text
设备或边缘网关 -> HTTP -> FastAPI/数据库
```

MQTT 适合大量设备持续上报，使用 QoS 1、批量 readings、短消息和 broker 缓冲。HTTP 适合调试、树莓派网关、批量脚本或无法直接接入 MQTT 的设备。

## 统一身份

每个设备必须有稳定 `device_id`。推荐格式：

```text
<平台>_<位置或用途>_<序号>
esp32_room_node_01
stm32_lab_node_01
raspi_gateway_01
```

`device_id` 不从 MQTT topic 推断，必须出现在 payload 或 HTTP path 中。topic 只负责路由，payload/path 才是设备身份来源。

## HTTP 接口

设备连接管理：

```text
POST /api/device-connections/register
POST /api/device-connections/{device_id}/heartbeat
GET  /api/device-connections
```

设备遥测：

```text
POST /api/device-connections/{device_id}/telemetry
```

旧调试入口仍保留：

```text
POST /api/ingest/sensor-readings
```

所有接口都受私有 API 保护。服务器部署时由内部服务令牌或已登录控制台访问；生产设备应通过网关或 broker 层做设备级 token 校验，避免把内部服务令牌直接烧进大量终端。

## 注册 payload

```json
{
  "device_id": "esp32_room_node_01",
  "display_name": "房间 ESP32 节点",
  "device_type": "esp32",
  "transport": "mqtt",
  "protocol_version": "aiot.v1",
  "firmware_version": "0.2.0",
  "hardware_revision": "esp32-s3-devkit",
  "location": "desk",
  "capabilities": [
    {
      "kind": "telemetry",
      "metrics": ["temperature", "humidity", "co2", "light", "presence", "noise"],
      "description": "房间环境遥测"
    }
  ]
}
```

设备注册是幂等操作。新设备首次注册时，服务器会在设备注册表里创建只读设备：`risk_level=read_only`、`controllable=false`。设备不能通过自注册获得控制权限；低风险控制能力必须由服务器侧人工配置和策略引擎确认。

## 心跳 payload

```json
{
  "status": "online",
  "transport": "mqtt",
  "protocol_version": "aiot.v1",
  "firmware_version": "0.2.0",
  "uptime_seconds": 3600,
  "battery_percent": 92.5,
  "rssi_dbm": -58,
  "message_id": "esp32_room_node_01-hb-100",
  "sequence": 100
}
```

心跳用于维护 `last_seen_at`、在线状态、固件版本和诊断指标。设备短时离线不应删除注册记录，只更新状态。

## 遥测 payload

```json
{
  "protocol_version": "aiot.v1",
  "message_id": "esp32_room_node_01-telemetry-101",
  "sequence": 101,
  "sent_at": "2026-06-06T09:50:00+08:00",
  "firmware_version": "0.2.0",
  "readings": [
    { "metric": "temperature", "value": 25.4, "unit": "℃" },
    { "metric": "humidity", "value": 48.2, "unit": "%" },
    { "metric": "co2", "value": 930, "unit": "ppm" },
    { "metric": "noise", "value": 48.5, "unit": "dB" }
  ]
}
```

单次上报最多 64 条 readings。高频节点应合并短窗口数据批量上报，避免每个指标单独建立 HTTP 请求。

## MQTT Topic

推荐统一 topic：

```text
aiot/v1/devices/{device_id}/telemetry
aiot/v1/devices/{device_id}/heartbeat
```

当前入站服务继续兼容旧 topic：

```text
aiot/room/+/telemetry
```

MQTT payload 支持标准 envelope：

```json
{
  "protocol_version": "aiot.v1",
  "message_id": "esp32_room_node_01-101",
  "sequence": 101,
  "sent_at": "2026-06-06T09:50:00+08:00",
  "device": {
    "id": "esp32_room_node_01",
    "type": "esp32",
    "firmware_version": "0.2.0",
    "hardware_revision": "esp32-s3-devkit",
    "capabilities": [
      { "kind": "telemetry", "metrics": ["temperature", "humidity", "co2"] }
    ]
  },
  "telemetry": {
    "readings": [
      { "metric": "temperature", "value": 25.4 },
      { "metric": "co2", "value": 930 }
    ]
  }
}
```

解析器仍兼容旧 batch、单指标和 metric map 格式，保证已有 ESP32 固件和脚本不需要立刻迁移。

## 并发与冗余设计

- 版本字段固定为 `protocol_version`，当前值 `aiot.v1`；未来新增字段不得破坏旧字段语义。
- 每条消息建议带 `message_id` 和递增 `sequence`，方便后续做去重、乱序检测和重放保护。
- MQTT 使用 QoS 1；网关应保留短期离线队列，恢复后按 sequence 补发。
- 遥测写入使用批量 readings；单设备高频采样应在设备端或网关端聚合后上报。
- 服务器按设备连接表维护 `last_seen_at`，按时间序列表维护原始读数，按审计日志追踪关键动作。
- 低于或等于当前 `last_sequence` 的旧心跳、旧遥测和重放消息不会回滚设备连接表中的在线状态、最后消息编号或最后在线时间；历史读数仍可写入时间序列表用于离线补传追溯。
- 新设备默认只读，不参与控制链路；未来控制 topic 必须与遥测 topic 分离，并继续经过策略引擎和审计。
- 树莓派这类网关可以用 `device_type=raspberry_pi` 或 `linux_gateway`，再通过 `metadata` 说明其下挂子设备；子设备仍应有自己的 `device_id`。

## 当前落地状态

- `device_connections` 表保存设备类型、传输方式、固件版本、能力声明、最近心跳、最后消息编号和序号。
- `/api/device-connections/register` 用于设备注册。
- `/api/device-connections/{device_id}/heartbeat` 用于设备心跳。
- `/api/device-connections/{device_id}/telemetry` 用于版本化 HTTP 遥测。
- MQTT 和旧 HTTP 入站都会同步更新设备连接表。
- 新设备进入 `device_registry` 时只能是只读不可控设备。
