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

视觉媒体示例使用设备令牌，不使用内部服务令牌：

```bash
export AIOT_API_BASE_URL=http://82.157.148.249
export AIOT_DEVICE_ID=raspi_cam_01
export AIOT_DEVICE_TOKEN=设备页生成的一次性显示令牌
export AIOT_SPACE_ID=space_study_001
export AIOT_ZONE=门口
```

## 运行

```bash
python3 aiot_gateway.py
```

第一次启动会注册设备，之后每 30 秒发送心跳，每 60 秒发送遥测。真实项目只需要替换 `read_sensor_snapshot`。

边缘识别事件和快照上传：

```bash
python3 vision_media_gateway.py
```

RTSP 推流可参考 `vision_media_gateway.py` 中的 `start_rtsp_stream()`，服务器使用 MediaMTX 接收 RTSP，控制台 `/vision` 通过 HLS 播放。
