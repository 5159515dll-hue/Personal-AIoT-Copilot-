# 边缘情绪采集（perception/）

在机器人内置树莓派上运行的情绪采集层。设计见 [`docs/companion-robot-plan.md`](../../../docs/companion-robot-plan.md) §2 / M2。

## 边界（重要）

- **边缘只做廉价门控采集**：仅在"检测到人 + 有语音活动(VAD)"时采一个 1–2s 窗口，不逐帧、不常开。
- **推理全在服务器**：原始帧/音频窗 POST 到 `/api/emotion/ingest`，由服务器做三模态推理 + 融合。
- **绝不落盘、绝不发 `/media`**：原始音视频用完即弃，本目录脚本不写任何文件、不缓存原始数据。
- 文本转写原文只过境服务器、不在边缘留存；服务器也只存推理出的情绪，不存原文。

## 文件

- `capture.py`：采集主循环。廉价门控 → 采窗 → POST `/api/emotion/ingest`。

## 运行

```bash
cd robots/yanshee
cp config.example.py config.py   # 填 ROBOT_IP、SPACE_ID、DEVICE_TOKEN（/devices 生成）
# 先在 /spaces 把该空间的 camera + emotion_recognition 开成 local_only（双门控）
python perception/capture.py
```

无 yanapi 环境下也能启动（以桩数据跑通上报链路）。

## 当前为可插拔桩（待真机/真模型替换）

`capture.py` 里以下函数是 **TODO 桩**，标好了替换点：

| 函数 | v0 桩 | 真机替换为 |
|---|---|---|
| `person_present()` | 恒 True | 轻量人脸存在 / 运动 / 亮度触发 |
| `voice_active()` | 恒 True | 能量阈值 / WebRTC VAD |
| `capture_transcript()` | None | 中/英 ASR（蒙语 ASR 见 M4/M7） |
| `capture_face_reading()` | None | 轻量 FER 或交服务器推理 |
| `capture_voice_reading()` | None | 韵律特征 / SER |

服务器侧推理桩见 `services/api/app/emotion_perception.py`（文本已真推理；FER/SER 为可插拔桩）。
