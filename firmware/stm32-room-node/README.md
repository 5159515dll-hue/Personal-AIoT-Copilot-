# STM32 房间节点接入示例

这个目录是 STM32 设备接入 `aiot.v1` 协议的 C/C++ 示例。STM32 本身通常不直接带网络能力，实际项目可以接以太网模块、Wi-Fi 模块、4G 模块或串口网关；示例把网络发送抽象为 `aiot_transport_post_json`，方便移植到 HAL、Arduino STM32、RT-Thread 或 FreeRTOS。

## 接入流程

1. 设备启动后调用 `/api/device-connections/register` 注册。
2. 周期性调用 `/api/device-connections/{device_id}/heartbeat` 写入在线状态。
3. 采集传感器后调用 `/api/device-connections/{device_id}/telemetry` 上报 readings。
4. 后台设备管理页把新设备标为只读，人工确认负载后才允许低风险控制。

## 安全边界

- 不把控制权限写进 STM32 自注册 payload。
- 不在固件里写死后台访问口令。
- 真实部署建议由边缘网关统一保存内部服务令牌，STM32 只连接网关。
- 每条消息带 `message_id` 和递增 `sequence`，服务器会去重并抵抗乱序回滚。

## 移植点

`src/main.cpp` 中只需要替换这些函数：

- `aiot_transport_post_json`
- `read_temperature_c`
- `read_humidity_percent`
- `read_co2_ppm`
- `millis`

网络层可以是 HTTP，也可以由串口网关把 JSON 转发到服务器。
