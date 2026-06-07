# 视觉、媒体与实时流协议

当前版本把设备数据拆成三条独立通道：遥测 JSON、边缘事件 JSON、媒体文件/实时流。图片和视频不会进入 `readings`，避免破坏 ESP32、STM32 和 MQTT 传感器协议。

## 空间策略

摄像头相关能力默认关闭。要接收树莓派视觉事件、图片、短视频或实时流，必须先在 `/spaces` 中把目标空间设置为：

- 摄像头：`local_only`
- 隐私模式：`local_only`
- 图像保留：`event_media`
- 媒体策略：允许事件媒体或实时流

`planned` 只表示规划中，不会接收真实媒体。严格模式会强制关闭媒体保留和实时流。

## 设备令牌

真实硬件上报事件和媒体必须使用设备令牌：

```text
X-AIoT-Device-Token: <设备页生成的一次性显示令牌>
```

后台在 `/devices` 中点击“设备令牌”生成或轮换。服务端只保存哈希，旧令牌会失效。服务器脚本仍可使用 `X-AIoT-Internal-Token` 做验收。

## 边缘事件

```text
POST /api/device-connections/{device_id}/events
```

示例：

```json
{
  "event_type": "presence_detected",
  "severity": "info",
  "confidence": 0.91,
  "space_id": "space_study_001",
  "zone": "门口",
  "attributes": {
    "person_count": 1,
    "edge_model": "local-yolo-lite"
  }
}
```

支持事件类型：`presence_detected`、`motion_detected`、`face_detected`、`emotion_detected`、`location_update`、`safety_alert`、`custom`。

人脸第一版只保存匿名结果，例如 `face_count`、`known=false`、`face_id_hash`；不建立真实身份库。情绪识别只保存粗粒度类别和置信度，不上传原始音频。

## 事件媒体

```text
POST /api/device-connections/{device_id}/media
Content-Type: multipart/form-data
```

字段：

- `file`：JPEG、PNG 或 MP4。
- `space_id`：必须是已启用媒体策略的空间。
- `zone`：可选区域。
- `event_id`：可选，关联边缘事件。

限制：

- 图片最大 10MB。
- MP4 最大 100MB。
- 默认媒体保留 7 天。
- 文件保存在 `AIOT_MEDIA_ROOT`，数据库或 JSON 索引只保存相对路径、哈希、大小和审计信息。

## 实时流

树莓派推荐推 RTSP 到服务器，网页通过 HLS 播放：

```bash
libcamera-vid -t 0 --inline --width 1280 --height 720 --framerate 15 -o - \
  | ffmpeg -re -i - -c:v copy -f rtsp rtsp://82.157.148.249:8554/raspi_cam_01
```

控制台 `/vision` 创建实时流后，后端会生成：

```text
GET /api/streams/{stream_id}/hls/index.m3u8
```

如果配置 `MEDIAMTX_HLS_BASE_URL`，FastAPI 会代理本机 MediaMTX HLS；否则读取 `AIOT_STREAM_ROOT` 下的 HLS 文件。HLS 入口受控制台鉴权保护，不直接暴露本机目录。

## 智能体边界

智能体新增只读工具：

- `get_recent_device_events`
- `get_stream_status`
- `get_media_asset_summary`
- `plan_adjustment_from_events`

智能体默认只读取结构化事件和媒体元数据，不读取原始图片或视频内容。任何控制动作仍必须经过设备注册表、负载标记、策略引擎和审计日志。
