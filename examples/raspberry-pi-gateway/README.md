# 树莓派网关接入示例

这个示例用 Python 把树莓派作为 `aiot.v1` 网关接入服务器。它适合两种场景：

- 树莓派自己采集传感器后上报。
- 树莓派通过串口、蓝牙、局域网或 RS485 汇聚 ESP32、STM32 子设备，再统一转发。

## 环境变量

```bash
export AIOT_API_BASE_URL=http://82.157.148.249
export AIOT_INTERNAL_API_TOKEN=服务器内部服务令牌
export AIOT_DEVICE_ID=raspi_gateway_01
```

示例会禁用系统代理，直接连服务器 IP。

## 运行

```bash
python3 aiot_gateway.py
```

第一次启动会注册设备，之后每 30 秒发送心跳，每 60 秒发送遥测。真实项目只需要替换 `read_sensor_snapshot`。
