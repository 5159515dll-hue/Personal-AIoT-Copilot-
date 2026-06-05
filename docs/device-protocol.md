# 设备消息协议

当前版本已经包含 ESP32 房间传感器节点固件、MQTT 入站服务和 HTTP 调试入站协议。该文档定义传感器消息格式；真实硬件、脚本和服务器烟测都应保持这些字段稳定。

## MQTT Topic

默认订阅：

```text
aiot/room/+/telemetry
```

示例：

```text
aiot/room/001/telemetry
```

MQTT 入站服务会从消息体读取 `device_id`，不会从 topic 反推设备编号。这样可以让 topic 只负责路由，设备身份仍由 payload 明确声明。

## 指标

V0 支持以下指标：

| metric | 单位 | 说明 |
| --- | --- | --- |
| `temperature` | `℃` | 空间温度 |
| `humidity` | `%` | 相对湿度 |
| `co2` | `ppm` | 二氧化碳浓度 |
| `light` | `lux` | 光照强度 |
| `presence` | `occupied` | 人体存在，`1` 表示有人，`0` 表示无人 |
| `noise` | `dB` | 噪声等级，只上报分贝数值，不上传原始音频 |

`quality` 可选，允许值为 `ok`、`stale`、`anomaly`。未提供时默认为 `ok`。

## Batch 格式

推荐硬件节点使用 batch 格式一次上报多个指标：

```json
{
  "device_id": "room_node_01",
  "timestamp": "2026-06-04T17:30:00+08:00",
  "readings": [
    { "metric": "temperature", "value": 25.4, "unit": "℃" },
    { "metric": "humidity", "value": 48.2, "unit": "%" },
    { "metric": "co2", "value": 1180, "unit": "ppm", "quality": "ok" },
    { "metric": "light", "value": 620, "unit": "lux" },
    { "metric": "presence", "value": 1, "unit": "occupied" },
    { "metric": "noise", "value": 48.5, "unit": "dB" }
  ]
}
```

如果单条 reading 未提供 `timestamp`，解析器会继承顶层 `timestamp`。如果顶层也没有时间戳，后端会使用入站时间。

## 单指标格式

低资源节点也可以只上报一个指标：

```json
{
  "device_id": "room_node_01",
  "metric": "co2",
  "value": 930,
  "unit": "ppm",
  "timestamp": "2026-06-04T17:30:00+08:00"
}
```

## Metric Map 格式

为了方便 ESP32 或脚本快速调试，也支持扁平 map：

```json
{
  "device_id": "room_node_01",
  "timestamp": "2026-06-04T17:30:00+08:00",
  "temperature": 25.4,
  "humidity": 48.2,
  "co2": 930,
  "light": 620,
  "presence": 1,
  "noise": 48.5
}
```

这种格式会被展开为多条标准读数，单位使用系统默认值。

## HTTP 入站

HTTP 入站接口：

```text
POST /api/ingest/sensor-readings
X-AIoT-Internal-Token: <内部服务令牌>
```

请求体与 batch 格式一致：

```json
{
  "device_id": "room_node_01",
  "readings": [
    { "metric": "temperature", "value": 25.4 },
    { "metric": "humidity", "value": 48.2 },
    { "metric": "co2", "value": 930 },
    { "metric": "noise", "value": 48.5 }
  ]
}
```

HTTP 入站用于本地调试、部署验证和脚本写入。生产公网环境下应继续放在私有 API 保护之后，或只允许内部服务令牌访问。

本地或服务器可用同一条格式验证写入：

```bash
curl -X POST http://localhost:8000/api/ingest/sensor-readings \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  -d '{
    "device_id": "room_node_01",
    "source": "http",
    "readings": [
      { "metric": "temperature", "value": 25.4 },
      { "metric": "humidity", "value": 48.2 },
      { "metric": "co2", "value": 930 },
      { "metric": "noise", "value": 48.5 }
    ]
  }'
```

## 入库语义

- 入站服务会初始化 `sensor_readings` 表。
- PostgreSQL 可直接使用；如果 TimescaleDB 扩展可用，会自动尝试创建 hypertable。
- 每条读数会记录 `time`、`received_at`、`device_id`、`metric`、`value`、`unit`、`quality` 和 `source`。
- 当前版本不从遥测 payload 执行任何设备控制动作。

## 安全边界

- 不接收摄像头、麦克风、原始音频、键盘输入、屏幕内容或精确地理位置。
- MQTT/HTTP payload 只能写入遥测数据，不能创建规则、控制设备或提升权限。
- 未知字段会被忽略或导致解析失败，不会被解释为控制指令。
- 设备控制必须走 `/api/devices/{id}/control`，并经过策略引擎和审计日志。

## 测试样例

可执行示例文件：

```text
services/mqtt-ingestor/examples/room-node-message.json
```

后端测试会读取该文件并通过当前 MQTT 解析器验证，确保文档示例和实际入站协议保持一致。ESP32 固件位于 `firmware/esp32-room-node`，内置 SHT31、BH1750、SCD40 / SCD41 和 GPIO 存在传感器读取流程，并发布同一套 batch payload。

固件不会把未接入传感器伪造成正常读数。不可用指标会被跳过；只有显式启用 `AIOT_ALLOW_DEMO_FALLBACK` 时，固件才会发布 `quality=stale` 的演示后备值。

服务器部署后可以运行真实 MQTT 入站烟测：

```bash
npm run smoke:mqtt
```

脚本会向 `MQTT_BROKER_HOST:MQTT_BROKER_PORT` 发布一条 batch payload，再通过 `/api/telemetry/status` 确认数据库已经出现本次 `source=mqtt` 的设备读数。
