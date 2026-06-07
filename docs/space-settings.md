# 房间与空间设置

当前工程不再假设只有一个房间。`/spaces` 页面和 `/api/spaces` 接口用于管理多个空间，例如书房、卧室、客厅、实验台、阳台或其他区域。

## 当前能力

- 新增空间：设置名称、类型、位置标签、楼层、时区。
- 区域划分：例如书桌、床头、门口、沙发区、实验台。
- 设备绑定：保存该空间关联的 `device_id` 列表，后续设备上报时可按空间组织。
- 当前空间：只能有一个空间处于 `is_active=true`，控制台顶部显示当前空间。
- 媒体策略：控制是否允许边缘事件媒体、实时视频流、媒体保留天数和事件保留天数。
- 审计：创建、更新、切换、删除空间都会写入审计日志。

## 感知能力边界

空间设置里包含以下规划字段：

- `camera`
- `face_recognition`
- `emotion_recognition`
- `location_tracking`
- `image_retention`
- `privacy_mode`
- `media_policy`

这些字段的语义如下：

- `disabled`：关闭。
- `planned`：计划接入，但当前不会采集或处理真实数据。
- `local_only`：只允许树莓派或本地网关先做边缘处理，再向服务器上传结构化事件或事件媒体。

当前版本不在服务器做人脸身份库、情绪推断或精确位置追踪。严格隐私模式会强制 `image_retention=none` 并关闭事件媒体和实时流。只有 `camera=local_only`、`privacy_mode=local_only` 且 `media_policy.allow_event_media=true` 时，服务器才接受事件图片或短视频；只有 `media_policy.allow_realtime_stream=true` 时，才允许登记实时流。

## 后续接树莓派摄像头时的要求

1. 先在 `/spaces` 建立空间和区域。
2. 在 `/devices` 中预建树莓派或摄像头网关设备，默认只读。
3. 在 `/devices` 中生成设备令牌；事件和媒体上报必须携带 `X-AIoT-Device-Token`。
4. 设备注册、心跳和遥测仍使用统一 `aiot.v1` 接口。
5. 摄像头、人脸、情绪和定位类数据必须走 `/api/device-connections/{device_id}/events`、`/media` 或 `/api/streams`，不能混入普通环境遥测。
6. 默认不上传原始图像；如需视觉结果，只能先做本地推理，再上传最小化事件摘要和必要事件证据。
7. 所有启用、确认、识别结果写入、媒体删除和拒绝都必须有审计日志。
