# ESP32 房间传感器节点

这是 Personal AIoT Copilot 的 ESP32 房间传感器节点。固件会读取真实传感器并按 `docs/device-protocol.md` 定义的 MQTT 遥测协议发布 batch payload，服务器侧 `aiot-mqtt-ingestor` 会写入 PostgreSQL / TimescaleDB。

## 能力边界

- 只发布遥测数据，不订阅控制 topic。
- 不接摄像头、麦克风、原始音频、键盘输入、屏幕内容或精确位置。
- 不控制插座、门锁、报警器、燃气、强电设备或医疗设备。
- Wi-Fi 和 MQTT 密钥只放在本地 `include/config.h`，不要提交到 Git。
- 未接入或读取失败的传感器不会伪造成正常读数；只有显式启用 `AIOT_ALLOW_DEMO_FALLBACK` 时才会上报 `quality=stale` 的演示后备值。

## 准备配置

复制配置模板：

```bash
cp include/config.example.h include/config.h
```

修改：

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `MQTT_HOST`
- `MQTT_PORT`
- `AIOT_ROOM_ID`
- `AIOT_DEVICE_ID`
- `AIOT_I2C_SDA_PIN`
- `AIOT_I2C_SCL_PIN`
- `AIOT_USE_SHT31`
- `AIOT_USE_BH1750`
- `AIOT_USE_SCD4X`
- `AIOT_PRESENCE_PIN`
- 可选 ADC 后备传感器开关和校准范围

## 传感器接线

推荐最小硬件组合：

| 指标 | 推荐传感器 | 默认接口 | 默认地址 / GPIO |
| --- | --- | --- | --- |
| 温度、湿度 | SHT31 | I2C | `0x44` |
| 二氧化碳 | SCD40 / SCD41 | I2C | `0x62` |
| 光照 | BH1750 | I2C | `0x23` |
| 人体存在 | PIR / 毫米波存在模块 | GPIO 数字输入 | `AIOT_PRESENCE_PIN` |
| 噪声分贝 | 模拟声级模块 | ADC | `AIOT_NOISE_ADC_PIN`，需手动校准 |

固件内置 SHT31、BH1750 和 SCD4x 的 I2C 读取流程，不需要额外传感器驱动库。模拟 CO2、光照和噪声只作为后备路径，必须在 `include/config.h` 中显式打开对应 `AIOT_USE_ANALOG_*` 开关，并根据实际模块校准范围。

## 构建与烧录

安装 PlatformIO 后执行：

```bash
pio run
pio run --target upload
pio device monitor
```

## MQTT Payload

固件发布到：

```text
aiot/room/<AIOT_ROOM_ID>/telemetry
```

payload 使用 batch 格式：

```json
{
  "device_id": "room_node_01",
  "readings": [
    { "metric": "temperature", "value": 25.0, "unit": "℃", "quality": "ok" },
    { "metric": "humidity", "value": 48.0, "unit": "%", "quality": "ok" },
    { "metric": "co2", "value": 930.0, "unit": "ppm", "quality": "ok" },
    { "metric": "light", "value": 420.0, "unit": "lux", "quality": "ok" },
    { "metric": "presence", "value": 1.0, "unit": "occupied", "quality": "ok" },
    { "metric": "noise", "value": 48.5, "unit": "dB", "quality": "ok" }
  ]
}
```

服务器端 MQTT 入站服务会解析该 payload 并写入 `sensor_readings` 表。Dashboard、趋势页、规则页和智能体页面切换到“数据库遥测”后即可读取这些入库数据。

## 读取策略

- `readTemperatureC` / `readHumidityPct`：优先读取 SHT31；如果未启用或失败，再使用 SCD4x 自带温湿度。
- `readCo2Ppm`：优先读取 SCD40 / SCD41；如果未启用，可选择模拟 ADC 后备。
- `readLightLux`：优先读取 BH1750；如果未启用，可选择模拟 ADC 后备。
- `readPresence`：读取 GPIO 数字输入，`1` 表示有人，`0` 表示无人。
- `readNoiseDbA`：只支持校准后的 ADC 分贝值，不采集或上传原始音频。

每次发布前会跳过不可用指标。这样数据库和智能体能把缺失指标识别为离线或不可用，而不是把固定值误认为真实环境数据。
