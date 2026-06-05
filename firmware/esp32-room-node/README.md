# ESP32 房间传感器节点

这是 Personal AIoT Copilot 的 V1 硬件接入骨架。当前 V0 默认仍使用模拟数据和服务器侧入站验证；该固件目录用于把后续真实 ESP32 节点接入 `docs/device-protocol.md` 定义的 MQTT 遥测协议。

## 能力边界

- 只发布遥测数据，不订阅控制 topic。
- 不接摄像头、麦克风、原始音频、键盘输入、屏幕内容或精确位置。
- 不控制插座、门锁、报警器、燃气、强电设备或医疗设备。
- Wi-Fi 和 MQTT 密钥只放在本地 `include/config.h`，不要提交到 Git。

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
- 传感器接线对应的 ADC / GPIO pin

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
    { "metric": "presence", "value": 1.0, "unit": "occupied", "quality": "ok" }
  ]
}
```

服务器端 MQTT 入站服务会解析该 payload 并写入 `sensor_readings` 表。Dashboard、趋势页、规则页和智能体页面切换到“数据库遥测”后即可读取这些入库数据。

## 传感器替换点

`src/main.cpp` 当前只保留安全的占位读取函数：

- `readTemperatureC`
- `readHumidityPct`
- `readCo2Ppm`
- `readLightLux`
- `readPresence`

接入真实硬件时，用具体驱动替换这些函数即可；MQTT topic 和 JSON 字段保持不变。
