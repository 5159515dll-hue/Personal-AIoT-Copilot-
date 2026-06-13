# 原地情感陪伴机器人 · 总执行规划

把"蒙古语多模态情感感知 + 情感陪伴回路"落到 **UBTECH Yanshee 人形机器人**（内置树莓派 3B）上，作为 AIoT Copilot 平台的新目标产品。本文是合成五个维度子规划后的**可执行总规划**，按依赖排序，所有任务落到仓库真实文件。

**配套设计文档**（本文是它们的落地版，不重复论证，只编排执行）：

- [`docs/emotion-companion-design.md`](emotion-companion-design.md) — 多模态情感 + 陪伴回路总设计
- [`docs/yanshee-integration.md`](yanshee-integration.md) — 机器人接入 + `aiot.v1`
- [`docs/device-connection-interface.md`](device-connection-interface.md) — 注册/心跳/遥测/事件协议
- [`docs/safety-policy.md`](safety-policy.md) — 策略边界
- [`docs/space-settings.md`](space-settings.md) — 空间能力门控

---

## 1. 产品定义与范围

**产品**：原地情感陪伴机器人。载体是 Yanshee 人形机器人（树莓派 3B、17 个**位置控制**舵机、8MP 前置摄像头、麦克风阵列、扬声器、9 轴 IMU），放在安全平面上、远离桌沿，面向坐在它前方 **0.3–1.5m 的单个用户**做情感陪伴。

**能力主轴**：

1. **多模态情感感知** — 面部表情 (FER) + 语音韵律 (SER) + 文本语义 (ASR→情感)。蒙古语是一等公民，中文/英文同时一等可用。原则"特色但不唯一"：视觉 + 韵律**语言无关**做共享底座，文本**按语种分支**，蒙古语是被重点建设的分支。
2. **共情对话** — 豆包 Doubao（火山引擎 Ark，OpenAI 兼容，国内响应最快）生成共情话语，流式输出；Kimi / 小米 MiMo 兜底。
3. **受控原地回应** — TTS（用户母语，含蒙古语）+ 安全手势集（点头/歪头/伸手/眼灯/小幅转身），全程经 `policy.py` 门控。

### 1.1 范围内：原地表达 + 小范围活动（硬约束）

- 头部转动、手臂/手部姿态、眼灯、语音、姿态切换、**小幅转身**、安全范围内**最多几步**移动。
- 表达性动作，不依赖走路鲁棒性，机器人始终在安全平面上**静态平衡**。

### 1.2 明确搁置（本产品不做，规划全程尊重）

| 搁置项 | 原因 |
|---|---|
| **自主导航 / 路径规划** | 超出"原地"范围；Pi 3B 算力不支撑 |
| **避障 / 跨越障碍物** | 位置舵机无力控、无足底力反馈，不具备动态平衡 |
| **跨房间行走 / 地形适应** | 走路鲁棒性不可依赖，安全风险高 |
| **多人跟踪 / 人脸身份库** | 隐私红线 + 场景只面向单个近距用户 |
| **逐帧实时感知** | Pi 3B 算力弱；用 1–2s 近实时窗口替代 |
| **重计算放 Pi 3B** | 算力弱；FER/SER/ASR/LLM 全部上服务器 |

### 1.3 产品红线（伦理）

- 机器人动作 = 物理执行器，必须经 `policy.py` 门控 + 确认 + 限速 + 审计。
- 边缘优先：**不存原始音视频、不建人脸库**；情绪是敏感个人数据，限定保留期、用户可删。
- **绝不利用检测到的情绪做诱导、上瘾设计或商业操控。**

---

## 2. 总体架构

```text
        ┌──────────────── Yanshee 机器人（边缘 / Pi 3B）─────────────────┐
 用户   │  摄像头 ─┐                                                     │
（表情/ │  麦克风 ─┼─→ 廉价门控：人脸存在检测 + VAD                       │
 说话/ │          │   （只在"有脸/有声"时采 1–2s 窗口，不逐帧、不落盘）  │
 沉默）→│          └─→ perception/capture.py                            │
        │                    │ HTTPS（帧 + 音频窗，过境不落地）          │
        │  bridge/yanshee_agent.py：注册/心跳/遥测（只读，已就绪）       │
        └────────────────────┼──────────────────────────────────────────┘
                             ▼  POST /api/emotion/ingest（设备令牌；不落媒体）
        ┌──────────────────────────── 平台后端（服务器）──────────────────────┐
        │  emotion_perception.py：infer_face / infer_voice / infer_text       │
        │      + detect_language（推理后立即丢弃输入，不入库、不调 /media）    │
        │  emotion_fusion.py：晚融合（置信度加权）+ EmotionSmoother（滞回）   │
        │      → EmotionState{primary, valence, arousal, language, modalities}│
        │                    │ 显著变化 / 每 N 秒，节流上报                    │
        │   POST /api/device-connections/{id}/events  event_type=emotion_detected│
        │      → media_store.record_device_event（空间门控已就绪）            │
        │      → device_events.json                                           │
        │  ── 陪伴回路 ─────────────────────────────────────────────────────  │
        │  策略层：情绪 → 回应策略（确定性，不经 LLM）                        │
        │      → 豆包 LLM 生成共情话语（按 language，流式）                   │
        │      → policy.py 门控手势（安全集 / 确认 / 限速 / 审计）           │
        │  agent_tools.read_current_emotion（只读工具，read_only）           │
        └────────────────────┼────────────────────────────────────────────────┘
                             ▼  受控回应（已确认动作）
        Yanshee 适配器 → RESTful 运动接口：TTS（母语）+ 安全手势（原地）
```

**职责切分**：边缘只做"廉价门控采集"（人脸存在 + VAD），原始音视频过境服务器、即用即弃；服务器做三模态推理、晚融合、决策、生成、门控；机器人做受控原地回应。

**关键架构决策（已定）**：原地场景没有导航/避障的实时算力负担，Pi 3B 唯一算力客户就是感知，而它跑 FER/SER/ASR 仍吃力 → **v0 三模态全部服务器推理**，边缘只做廉价门控。隐私用"过境不落地 + 不建人脸库 + 空间门控"补偿；进阶再把 FER-lite 下沉边缘换隐私（待定决策）。

---

## 3. 分阶段里程碑

里程碑按**依赖严格排序**。每个阶段标注【目标 / 任务 / 涉及文件 / 验收 / 依赖 / 工作量】。工作量为粗估人日（1 人）。

> **关键发现（影响排期）**：情绪事件通道**后端已部分就绪**——
> - `emotion_detected` 已是合法 `DeviceEventType`（`services/api/app/models.py:441`）
> - 空间门控 `perception.emotion_recognition=="local_only"` 已实现（`services/api/app/media_store.py:249`）
> - 查询接口 `GET /api/device-events?event_type=emotion_detected` 已存在（`services/api/app/routes/device_events.py:11`）
> - `emotion_detected` 已在 `VISUAL_EVENT_TYPES`，受 `camera=="local_only"` 门控（`media_store.py:23`）
> - `RiskLevel.read_only` 已是合法枚举（`models.py:21`）
>
> **因此不需要新建事件端点或事件类型**。真正缺的是：边缘采集门控层、服务器三模态推理、晚融合 + 平滑、感知摄取路由、豆包厂商条目、策略手势集、陪伴回路、前端展示，以及把 `space_store.py:127` 默认 `emotion_recognition="disabled"` 开成可配 `local_only`。

### M0 — 最小闭环（豆包流式 + 机器人原地动起来 + 只读情绪事件打通）

**目标**：三条独立短链路各自跑通，证明"模型快、机器人能受控动、情绪能进事件流"，为后续融合/回路打地基。**本阶段不做真实感知模型、不做融合**，情绪事件用假数据/合成分布验证通道。

**任务清单**：

1. **豆包上线（并行快赢）**：`model_providers.py` 的 `PROVIDERS` 加一条 `doubao` 厂商条目（火山引擎 Ark，`protocol=openai`，`base_url=https://ark.cn-beijing.volces.com/api/v3`，接入前核对模型名）。沿用既有 `validate_model_target` 白名单 Base URL 机制。
2. **确认 / 接通 `/agent` 流式**：核对 `routes/agent.py` 链路是否已 SSE 流式；陪伴对话对延迟敏感，先出字。若未流式，标记为 M3 前置任务（不阻塞 M0 其余项）。
3. **机器人受控原地动起来**：在机器人上用 `robots/yanshee/scripts/first_motion.py` 跑通一个内置安全动作（点头/挥手），确认 `yanapi` 运动接口可用、舵机已校准、机器人在安全平面静态平衡。
4. **只读遥测桥已在跑**：确认 `bridge/yanshee_agent.py` 注册/心跳/遥测三件套对平台正常（已实现，仅需在真机验证）。
5. **空间门控打通**：在 `/spaces` 把一个测试空间的 `emotion_recognition` 开成 `local_only`（需先放开 `space_store.py:127` 默认值的可配置路径），用**假 `emotion_detected` 事件**直接 POST `/api/device-connections/{id}/events`（带 `X-AIoT-Device-Token`），验证 `media_store.py:249` 门控**放行/拒绝两条路径**，事件落 `device_events.json`，并能被 `GET /api/device-events?event_type=emotion_detected` 查到。

**涉及文件**：

- 改 `services/api/app/model_providers.py`（加 `doubao` 条目）
- 改 `services/api/app/space_store.py`（默认 `emotion_recognition` 可经 `/spaces` 开成 `local_only`）
- 验证（不改）`services/api/app/media_store.py`、`routes/device_connections.py`、`routes/device_events.py`、`bridge/yanshee_agent.py`、`scripts/first_motion.py`、`scripts/connect_check.py`

**验收标准**：

- 豆包配好密钥后 `/models` 测试连接成功；`/agent` 用豆包生成回复（若流式已就绪则流式）。
- 机器人执行一个受控安全动作，物理上稳定、不摔。
- 测试空间未开 `local_only` 时假 `emotion_detected` 被 403 拒绝；开成 `local_only` 后放行、落库、可查询。

**依赖**：无（M0 是起点）。
**工作量**：约 3–4 人日。

---

### M1 — 感知契约 + 融合引擎 v0（纯逻辑，不依赖真实模型）

**目标**：把"情绪状态"的数据契约和**晚融合 + 时序平滑**做出来并单测通过，与设计文档第 4/7 节完全对齐。**这是纯数据 + 纯函数层，可先于任何真实模型落地**，是后续所有感知工作的契约地基。

**任务清单**：

1. **契约先行**：`models.py` 新增 `EmotionModality`、`EmotionState`、`EmotionIngestRequest/Response` Pydantic 模型；约定 `emotion_detected` 事件的 `attributes` 子结构（见 §5.1），**复用现成 `DeviceEventType.emotion_detected` 与 `DeviceEventCreate.attributes`，不改事件表结构**。
2. **序列化 adapter**：写一个把 `EmotionState` 序列化成 `DeviceEventCreate(event_type="emotion_detected")` 的函数。
3. **融合引擎**：`emotion_fusion.py`（设计文档第 12 节已点名）实现 `fuse(face, voice, text)->EmotionState`（置信度加权晚融合）+ `EmotionSmoother`（滚动窗口 + 滞回）+ 一个按 `device_id/space_id` 维持窗口状态的轻量 store。
4. **统一标签空间**：约定融合只在 7 类 `{happy,sad,angry,surprise,fear,disgust,neutral}` + `valence(-1..1)` + `arousal(0..1)` 上做。
5. **单元测试**：用合成三模态分布测"某模态缺位降级""滞回不抖动""三模态齐全加权正确"。

**涉及文件**：

- 改 `services/api/app/models.py`（新增情感模型）
- 新增 `services/api/app/emotion_fusion.py`
- 新增 `services/api/tests/test_emotion_fusion.py`（或仓库现有测试目录）

**验收标准**：

- 只给"脸"、只给"声"、三模态齐全三种输入都产出合法 `EmotionState`；text 缺位时 `modalities.text.status=="unavailable"` 且 `primary_emotion` 仍稳定。
- 连续输入抖动的瞬时分布，平滑后 `primary_emotion` 不逐帧跳变（滞回生效）。
- `EmotionState` 经 adapter 能产出合法 `DeviceEventCreate`，被 M0 验证过的门控/查询链路接受。

**依赖**：M0（门控链路已验证）。
**工作量**：约 3 人日。

---

### M2 — 语言无关感知底座（FER + SER）+ 边缘采集层 + 感知摄取路由

**目标**：把**视觉 + 韵律**两条语言无关链路从边缘采集打通到服务器推理再到融合，产出真实 `emotion_detected` 事件落库。这是**蒙语用户的首日可用路径**（不等 ASR）。

**任务清单**：

1. **感知摄取路由**：`routes/emotion.py` 新增 `POST /api/emotion/ingest`——边缘把帧/音频窗发这里，服务器调 `emotion_perception` + `emotion_fusion` 返回 `EmotionState`；**该路由不落音视频、推理后立即丢弃输入**。鉴权复用 `_require_device_ingest_auth`（设备令牌，与事件上报一致）。另加 `GET /api/emotion/state?space_id=` 读当前平滑情绪。
2. **三模态推理骨架**：`emotion_perception.py` 定义 `infer_face`、`infer_voice`、`infer_text`、`detect_language`，按 `model_providers.py` 风格做**声明式可插拔**（本地权重 or 远程推理服务）。每个返回"情绪分布 + 置信度"，出口统一映射到约定 7 类 + valence/arousal。
3. **韵律底座（先上）**：实现 `infer_voice`（openSMILE 韵律特征 + 分类器 或 wav2vec2-SER）。
4. **FER 底座**：实现 `infer_face`（轻量 7 类 + valence/arousal）。
5. **边缘采集层**：`robots/yanshee/perception/capture.py` 在机器人上跑——复用 `read_sensors.py` 的 `_safe_call` 兜底风格调 `yanapi` 取帧 + 音频；内置轻量**人脸存在检测 + VAD 门控**（只在"有脸/有声"时采）；POST 到 `/api/emotion/ingest`；**不落盘、不发 `/media`**；配置复用 `config.py`。先在无 yanapi 环境用本地摄像头/麦克风桩验证链路（沿用桥接"无硬件降级"思路）。
6. **结果回报**：`perception/capture.py` 拿融合结果后，按 `aiot.v1` 组装 `emotion_detected` 事件 POST 到 `/api/device-connections/{id}/events`（带 `X-AIoT-Device-Token`），沿用 `yanshee_agent.py` 的 `post_json` / `trust_env=False`。
7. **桥接能力声明**：`DeviceCapability.kind` 是封闭 `Literal`（`models.py:71`：telemetry/control/gateway/diagnostic/media/vision/stream），**没有 `emotion_event`/`vision_event`**。情绪/视觉能力统一归到合法的 `kind="vision"`（摄像头来源）；若要独立语义再先扩 Literal。注：`bridge/yanshee_agent.py` 的注册校验 bug（`device_type="yanshee"`、`kind="vision_event"`、非法 `battery` metric）已在审查后修复并用 `.venv` 实测通过。
8. **节流**：融合层只在情绪显著变化或每 N 秒上报一条，避免 `device_events.json` 膨胀。
9. **边界说明**：`robots/yanshee/perception/README.md` 写清"边缘只采集门控、推理在服务器、原始音视频不落地"。

**涉及文件**：

- 新增 `services/api/app/emotion_perception.py`
- 新增 `services/api/app/routes/emotion.py`（在 `main.py` 注册路由）
- 改 `services/api/app/main.py`（挂载 emotion 路由）
- 新增 `robots/yanshee/perception/capture.py`、`robots/yanshee/perception/report_emotion.py`（或并入 capture）、`robots/yanshee/perception/README.md`
- 改 `robots/yanshee/bridge/yanshee_agent.py`（capabilities 加 `emotion_event`）

**验收标准**：

- 端到端：`capture.py`（或桩）→ `/api/emotion/ingest` → 融合 → `emotion_detected` 事件落 `device_events.json` → 可被查询接口查到。
- **隐私**：全链路 grep 不到把帧/音频写盘或写 `/media` 的路径；`/api/emotion/ingest` 推理后输入对象不被持有。
- **蒙语首日可用**：蒙语用户在无文本模态下，靠 face+voice 两模态得到带 `language` 占位的有效情绪事件（语种此时由空间默认语言提供）。

**依赖**：M1（契约 + 融合）。
**工作量**：约 6–8 人日（含模型选型/对接）。

---

### M3 — 文本分支（zh/en）+ 豆包共情对话流式接通

**目标**：补上文本模态的中英分支，三模态对中英用户齐全；同时把豆包共情对话流式链路接到融合结果之后（理解环节）。

**任务清单**：

1. **语种路由**：`detect_language(audio)->lang` 用 ASR 自带语种识别（Whisper 类）做主路由；不可用/置信低时回退**空间配置的默认语言**。路由结果写入事件 `attributes.language` 和 `modalities.text.transcript_lang`。
2. **文本情感 zh/en**：`infer_text(transcript, lang)` 用成熟多语种情感模型跑通中英。
3. **豆包共情生成**：在融合结果（确定性的情绪 + 回应策略）之后，调豆包按 `language` 生成共情话语，流式输出。LLM **只负责把话说自然**，情绪判定/安全检查/手势选择都由确定性逻辑完成（对齐设计文档第 5 节"工具优先、策略优先"）。
4. **降级兜底**：豆包为主，Kimi / 小米 MiMo 兜底（沿用 `generate_agent_reply` 既有 fallback 链）。

**涉及文件**：

- 改 `services/api/app/emotion_perception.py`（`detect_language`、`infer_text` zh/en）
- 改 `services/api/app/model_providers.py` / `routes/agent.py`（流式生成接通，若 M0 未完成流式）

**验收标准**：

- 中/英用户三模态齐全，事件 `modalities.text` 有有效转写语种和情感。
- 融合情绪 → 豆包生成共情话语，按用户语言、流式先出字。

**依赖**：M2（感知 + 摄取路由）；M0（豆包条目）。
**工作量**：约 4–5 人日。

---

### M4 — 蒙古语文本分支（特色）+ 务实降级

**目标**：把蒙古语作为被重点建设的文本分支接入，**务实承认蒙语 ASR 是瓶颈**，链路在文本缺位时仍稳定产出两模态情绪事件。

**任务清单**：

1. **蒙语文本情感**：接公开蒙语文本情感模型 / 在公开语料微调（参考设计文档第 9 节 GTAH）。
2. **蒙语 ASR 务实降级**：v0 **明确允许蒙语文本模态缺位**——晚融合天然降级，此时蒙语用户靠"视觉 + 韵律"工作，事件 `modalities.text.status=="unavailable"`，`attributes.language` 仍标 `"mn"`。ASR 作为独立可替换组件，选型/微调挂进阶，不阻塞本里程碑。
3. **数据策略**：v0 不自建数据集，先公开资源 + 零样本/few-shot；"是否采集标注蒙语情感数据"作为研究决策上挂（见 §7）。

**涉及文件**：

- 改 `services/api/app/emotion_perception.py`（mn 文本情感分支）

**验收标准**：

- 蒙语用户在 ASR 缺位下，靠 face+voice 两模态仍得到 `language:"mn"` 的有效情绪事件；文本到位时蒙语情感正确接入融合。

**依赖**：M3（文本分支框架）。
**工作量**：约 4–6 人日（取决于蒙语模型可得性）。

---

### M5 — 智能体只读情绪工具 + 前端情绪轨迹展示

**目标**：把"当前情绪"接成智能体只读工具，前端能看情绪轨迹，形成可演示的感知闭环。

**任务清单**：

1. **只读情绪工具**：`agent_tools.py` 新增 `read_current_emotion(space_id)`，从 `emotion_fusion` 平滑状态读当前情绪，`risk_level="read_only"`，对齐既有只读工具模式（参考 `get_recent_device_events` `agent_tools.py:1109`，及 `read_only` 风险标注）。**只读情绪，不触发任何物理动作**；回应动作仍走 `policy.py`（属 M6）。
2. **前端情绪轨迹**：复用 `apps/web/` 既有面板风格，新增情绪轨迹展示（消费 `GET /api/device-events?event_type=emotion_detected` 或 `GET /api/emotion/state`）。
3. **前端宠物人格设置入口**：复用 `/spaces` 能力门控页（`space-settings-panel.tsx`），把情绪能力开关 + 宠物人格设定挂上。

**涉及文件**：

- 改 `services/api/app/agent_tools.py`（`read_current_emotion`）
- 新增/改 `apps/web/` 情绪轨迹组件 + 宠物人格设置（参考 `space-settings-panel.tsx`、`agent-console.tsx`、`model-settings-panel.tsx`）

**验收标准**：

- `read_current_emotion(space_id)` 返回当前平滑情绪，`risk_level="read_only"`，不触发物理动作。
- 前端能展示情绪轨迹；空间能开/关情绪能力。

**依赖**：M2（事件落库）；可与 M3/M4 并行。
**工作量**：约 4–5 人日。

---

### M6 — 陪伴回路 + 受控原地动作（策略门控）

**目标**：闭合"情绪 → 共情 → TTS + 安全手势"回路，机器人在严格策略门控下做**原地受控回应**。这是产品的情感陪伴核心，也是物理风险最高的一环。

**任务清单**：

1. **安全手势集 + 门控规则**：`policy.py` 新增情绪驱动手势的**安全手势集**与确认规则（设计文档第 12 节已点名）。手势限定在原地范围（点头/歪头/伸手/眼灯/小幅转身/安全范围几步），非平凡动作需确认，连续动作限速，全部写审计；沿用既有注入检测（外部/用户文本不能提升动作权限，`policy.py:37`）。机器人控制能力由**服务端人工配置**到设备注册表，不靠自注册（`controllable`/`risk_level` 由后台设，对齐 `yanshee-integration.md` 第 5.2 节）。
2. **回应策略**：情绪 → 回应基调 + 手势 + 语音的确定性映射（设计文档第 5 节表），可配置。
3. **Yanshee 控制适配器**：平台侧把已确认动作翻译成机器人 RESTful 运动接口调用（受控原地动作）。
4. **TTS 母语回应**：按 `language` 选 TTS 语言（含蒙古语），与共情话语对齐。

**涉及文件**：

- 改 `services/api/app/policy.py`（安全手势集 + 确认/限速规则）
- 新增 Yanshee 控制适配器（平台侧，参考 `device_adapter.py` 风格）
- 改 `robots/yanshee/`（受控手势回应脚本，接 RESTful 运动接口）

**验收标准**：

- 情绪事件 → 回应策略 → 豆包共情 → 已确认手势经 `policy.py` 放行 → 机器人原地执行；未确认的非平凡动作被要求确认；连续动作被限速；全部进审计。
- 注入文本 / "忽略安全策略"无法提升动作权限。
- 所有动作严格在原地范围内，机器人静态平衡不摔。

**依赖**：M3（共情生成）、M5（情绪可读）；M0（机器人受控动起来已验证）。
**工作量**：约 6–8 人日。

---

### M7 — 进阶（挂后，不阻塞 v0）

- **FER-lite 下沉边缘**换隐私（需产品拍板隐私 vs 算力）。
- **蒙语 ASR** 选型/微调或数据采集。
- **研究级融合**（GTAH 门控 Transformer + 自适应超模态、多级注意力）。
- **蒙语 TTS 人格**（MnTTS2 约 30h 可助力声学侧）、长期记忆与个性化。
- **宠物人格与记忆存储**（仿 `services/api/.local/` JSON 存储，保留期对齐 `agent_conversations` 30 天，用户可删）。

**依赖**：v0（M0–M6）完成。
**工作量**：研究级，按需立项。

---

## 4. 模块改动总清单

### 4.1 后端（`services/api/app/`）

| 文件 | 改动 | 里程碑 |
|---|---|---|
| `model_providers.py` | 新增 `doubao` 厂商条目 + 流式接通 | M0 / M3 |
| `space_store.py` | 默认 `emotion_recognition` 可经 `/spaces` 开成 `local_only`（`:127`） | M0 |
| `models.py` | 新增 `EmotionModality`/`EmotionState`/`EmotionIngestRequest/Response`；复用 `DeviceEventType.emotion_detected` | M1 |
| `emotion_fusion.py` | **新增**：晚融合 `fuse` + `EmotionSmoother` + 窗口 store | M1 |
| `emotion_perception.py` | **新增**：`infer_face`/`infer_voice`/`infer_text`/`detect_language`，声明式可插拔 | M2 / M3 / M4 |
| `routes/emotion.py` | **新增**：`POST /api/emotion/ingest`（不落媒体）+ `GET /api/emotion/state` | M2 |
| `main.py` | 挂载 emotion 路由 | M2 |
| `agent_tools.py` | 新增 `read_current_emotion(space_id)`，`read_only` | M5 |
| `policy.py` | 安全手势集 + 确认/限速规则 | M6 |
| Yanshee 控制适配器（仿 `device_adapter.py`） | **新增**：已确认动作 → RESTful 运动接口 | M6 |

> 门控逻辑无需改：`media_store.py:249` 已就绪。事件端点/类型/查询接口均已存在，不新建。

### 4.2 前端（`apps/web/`）

| 页面/组件 | 改动 | 里程碑 |
|---|---|---|
| 情绪轨迹组件（新） | 消费 `device-events?event_type=emotion_detected` / `emotion/state` | M5 |
| `space-settings-panel.tsx` | 情绪能力开关 + 宠物人格设定入口 | M5 |
| `model-settings-panel.tsx` | 豆包出现在厂商目录（随后端 `PROVIDERS` 自动） | M0 |

### 4.3 机器人（`robots/yanshee/`）

| 文件 | 改动 | 里程碑 |
|---|---|---|
| `perception/capture.py`（新） | 边缘采集 + 人脸存在/VAD 门控 + POST `/api/emotion/ingest`，不落盘 | M2 |
| `perception/report_emotion.py`（新，或并入 capture） | 融合结果 → `emotion_detected` 事件上报 | M2 |
| `perception/README.md`（新） | 边界说明 | M2 |
| `bridge/yanshee_agent.py` | ✅ 已修注册校验 bug（`device_type`→`raspberry_pi`、`kind`→`vision`、去掉非法 `battery` metric，已实测）；情绪能力归 `vision` | M0(已修)/M2 |
| 受控手势回应脚本 | 接 RESTful 运动接口，原地安全集 | M6 |
| `scripts/first_motion.py` / `connect_check.py` | 真机验证（不改） | M0 |

---

## 5. 关键接口契约

### 5.1 情绪事件 `attributes`（落 `device_events.json`，与设计文档第 7 节对齐）

```json
{
  "event_type": "emotion_detected",
  "severity": "info",
  "confidence": 0.82,
  "space_id": "space_living_001",
  "zone": "沙发",
  "attributes": {
    "primary_emotion": "sad",
    "valence": -0.4,
    "arousal": 0.2,
    "language": "mn",
    "modalities": {
      "face":  {"emotion": "sad",     "confidence": 0.78},
      "voice": {"emotion": "sad",     "confidence": 0.71},
      "text":  {"status": "unavailable"}
    },
    "fusion": "late_weighted",
    "smoothed": true,
    "inference_model": "ser+fer+mn-text-emo"
  }
}
```

- `primary_emotion ∈ {happy,sad,angry,surprise,fear,disgust,neutral}`；`valence∈[-1,1]`；`arousal∈[0,1]`；`language∈{zh,en,mn}`。
- 每个模态为 `{emotion, confidence}`（text 另带 `transcript_lang`）或 `{status:"unavailable"}`。
- 上报走 `POST /api/device-connections/{device_id}/events`，需 `X-AIoT-Device-Token`（`routes/device_connections.py:240` `_require_device_ingest_auth` 接受设备令牌或内部令牌）。
- 落库前经 `media_store.record_device_event`，受 `_assert_space_allows_event`（`media_store.py:242`）双重门控：`camera=="local_only"` 且 `emotion_recognition=="local_only"`。

### 5.2 感知摄取（新端点，不落媒体）

```
POST /api/emotion/ingest        # 边缘发帧/音频窗；服务器推理+融合，返回 EmotionState；不落音视频
GET  /api/emotion/state?space_id=  # 读当前平滑情绪（供 agent 工具 / 前端）
```

鉴权：复用 `_require_device_ingest_auth`（设备令牌）。**待定**：原始媒体过境端点是否需比事件上报更强约束（见 §7）。

### 5.3 动作门控规则（`policy.py`）

- 机器人动作 = 物理执行器：`controllable` / `risk_level` 由**服务端人工配置**，不靠自注册（`yanshee-integration.md` §5.2）。
- 手势限定**安全集**（原地范围）；非平凡动作 `requires_confirmation`；连续动作限速；全部 `record_audit`。
- 沿用 `detect_prompt_injection`（`policy.py:37`）：外部/用户文本不能提升动作权限。
- 风险分级对齐 `safety-policy.md`：门锁/报警器/强电 `forbidden`；机器人运动按物理动作定 `medium`/`high`，经确认才放行。

### 5.4 豆包 `PROVIDERS` 条目（`model_providers.py`，形态示意，接入前核对模型名）

```python
ModelProviderDefinition(
    id="doubao",
    label="字节豆包",
    description="字节豆包大模型，火山引擎 Ark，OpenAI 兼容，国内响应最快，用于共情对话。",
    docs_url="https://www.volcengine.com/docs/82379",
    endpoints=[
        ProviderEndpoint(
            id="doubao_ark_openai",
            label="火山引擎 Ark · OpenAI 兼容",
            protocol=ProviderProtocol.openai,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            description="火山引擎 Ark OpenAI 兼容入口。",
        ),
    ],
    models=["<接入前核对>"],
    default_model="<接入前核对>",
)
```

> 沿用 `validate_model_target`（`model_providers.py:323`）白名单 Base URL；`_openai_headers` / `_openai_agent_payload` 已支持 OpenAI 协议，豆包大概率零特判即可，接入时核对鉴权头与 `temperature` 兼容性。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| **服务器推理需音视频过境**（与"边缘优先"张力） | HTTPS + 内存即用即弃 + 不落库 + 不建人脸库 + 空间双门控 + 设备令牌；进阶把 FER 下沉边缘 |
| **蒙语 ASR 不成熟** | 管线设计成"文本模态可选"，蒙语先靠视觉+韵律两模态；ASR 独立可替换，选型/微调挂进阶，不阻塞 v0 |
| **Pi 3B 采集 + 门控也吃力** | 边缘只做廉价人脸存在/VAD 门控，1–2s 采样不逐帧，推理全在服务器；仍紧张则降采样或"被唤醒/检测到人"才启感知 |
| **事件刷库（`device_events.json` 膨胀）** | 融合层节流：只在情绪显著变化或每 N 秒上报一条 |
| **跨模态标签空间不一致**（FER 7 类 vs SER vs 各文本模型） | `emotion_perception` 出口统一映射到约定 7 类 + valence/arousal，融合只在统一空间做 |
| **模型供给不确定**（本地权重 vs 远程服务） | `emotion_perception` 按 `model_providers.py` 声明式可插拔，先用易得模型跑通契约再替换 |
| **机器人物理动作风险** | 严格原地范围 + 静态平衡 + `policy.py` 门控/确认/限速/审计 + 服务端配置控制能力 + 安全平面远离桌沿 |
| **走路鲁棒性不可依赖** | 范围内已搁置导航/避障/跨房间，只做原地表达 + 安全范围几步 |
| **情绪数据敏感 / 操控风险** | 限定保留期、用户可删、不外发、不画像；产品红线：绝不利用情绪诱导/上瘾/操控，在策略与提示层显式约束 |
| **豆包模型名/鉴权细节未核** | 接入前在火山引擎 Ark 控制台核对 `base_url`/模型名；保留 Kimi/MiMo fallback 兜底 |

---

## 7. 已定决策（2026-06-13 拍板）

7 项原待定决策全部定案，v0 范围据此锁定：

| 决策 | 结论 | 对里程碑的影响 |
|---|---|---|
| **宠物人格** | **温柔治愈型** —— 轻声、共情、安抚为主，动作温和 | 驱动 M3 共情提示词、M6 回应策略与手势（偏柔和：歪头/缓伸手/暖色眼灯）。名字与主要陪伴对象可后补。 |
| **蒙古语深度** | **v0 仅识别支持蒙语**，回应先中/英 | ✅ **蒙语 TTS 高危项移出 v0 关键路径**；M6"按 language 选 TTS"v0 只做 zh/en；蒙语语音回应 + 界面 i18n 挂 M7 |
| **蒙古语数据** | **两步走**：先公开资源/零样本跑通，再按需自建 | M4 只做"接公开蒙语情感模型或零样本"，不阻塞；自建标注数据集作为 M7 研究项 |
| **FER/SER 部署位** | **v0 全服务器推理，音视频过境即弃** | 锁定 §2 架构；边缘只做廉价门控；FER 下沉边缘换隐私挂 M7（进阶可选） |
| **`/api/emotion/ingest` 鉴权** | **设备令牌**（复用 `_require_device_ingest_auth`） | M2 直接复用现有鉴权，不另造 |
| **三模态权重/滞回阈值** | **保守默认值**，有真实数据再标定 | M1 只验融合/平滑**逻辑正确性**，不验情绪准确性 |
| **采样触发** | **检测到人/被唤醒才感知**（非常开） | M2 边缘门控＝人在场/被唤醒才采 1–2s 窗口；护 Pi 负载与隐私观感 |

---

## 8. 建议的第一步（M0 起手，具体到文件）

按"零物理风险、并行快赢、立即可验证"排序，**前三步可并行**：

1. **加豆包厂商条目** — 改 `services/api/app/model_providers.py` 的 `PROVIDERS`，加 `doubao`（§5.4），核对火山引擎 Ark `base_url` 与模型名，在 `/models` 配密钥并测试连接。**纯后端、零硬件、立即可验证响应速度。**
2. **放开情绪能力门控** — 改 `services/api/app/space_store.py:127`，让测试空间能在 `/spaces` 把 `emotion_recognition` 开成 `local_only`，然后用假 `emotion_detected` 事件 POST `/api/device-connections/{id}/events`（带 `X-AIoT-Device-Token`）验证 `media_store.py:249` 门控放行/拒绝两条路径。**打通情绪事件通道，不依赖任何模型。**
3. **机器人受控动起来** — 在真机上跑 `robots/yanshee/scripts/connect_check.py` 自省 yanapi，再用 `scripts/first_motion.py` 执行一个安全动作，确认舵机已校准、机器人在安全平面静态平衡。**验证物理回应基础。**

随后进入 M1：在 `services/api/app/models.py` 固化 `EmotionState` 契约，新建 `services/api/app/emotion_fusion.py` 把晚融合 + 滞回平滑写出来并单测——**这是后续所有感知工作的契约地基，纯逻辑、不依赖真实模型，可最先稳定下来。**

---

## 9. 审查修正（对抗性可行性审查已采纳）

> 本规划经过一轮对抗性审查（含 `.venv` 实测）。结论：**方向正确、整体可行，但需以下修正**。审查同时发现并修复了一个已存在的代码 bug。

### 9.1 已修复（代码）

- **`bridge/yanshee_agent.py` 注册校验 bug**（审查用 `.venv` 实测确认）：`device_type="yanshee"`、`kind="vision_event"`、`metrics=["battery",...]` 全部违反封闭模型，真机 `/register` 与 `/telemetry` 本会 422。**已修**：`device_type→raspberry_pi`、`kind→vision`、机器人状态改用 `diagnostic`+空 metrics、电量走心跳 `battery_percent`、`build_readings` 返回空（机器人无 6 类环境量），并实测注册/心跳通过。

### 9.2 高危修正

| # | 问题 | 采纳修正 |
|---|---|---|
| H1 | `DeviceCapability.kind` 是封闭 Literal，规划原计划的 `emotion_event` 非法 | 情绪/视觉能力统一归 `kind="vision"`；要独立语义则先扩 Literal。已改 §4.3 / M2 任务7 / §5.1。 |
| H2 | **蒙语 TTS 被当成"选个 language 参数"**，但机载 TTS 几乎只支持中/英，蒙语需"外部 TTS 合成 wav→机器人播放音频文件"这条未验证链路 | 在 M4/M6 前插入 **spike**：验证 Yanshee 能否播放任意外部音频 + 外部蒙语 TTS(MnTTS2) 产出可播 wav。把蒙语 TTS 升级为独立技术风险项，降级位＝蒙语识别+中/英安抚语 或 非语言声效+手势。**【决策 2026-06-13】v0 已定"仅识别支持蒙语、回应先中/英"，蒙语 TTS 与蒙语回应一并挂 M7，已移出 v0 关键路径。** |

### 9.3 中危修正

- **M0 拆为 M0a / M0b**：M0a＝纯仓库内零外部依赖可交付内核（假情绪事件门控放行/拒绝两路 + 豆包 `PROVIDERS` 条目静态注册与 schema 校验）；M0b＝带外部依赖（真密钥连通、真机首动作）。"最小闭环"内核落在 M0a。
- **豆包流式是跨层结构改造，非"顺手接通"**：实测 `routes/agent.py` 零流式、`generate_agent_reply`（`model_providers.py:342+`）阻塞式。独立成 **3–5 人日**子任务，明确同时改 `model_providers`/agent route/前端 EventSource；M3 共情验收不预设流式已成。
- **`read_current_emotion` 缺触发接线**：`handle_chat`（`agent_tools.py:42`）是关键词路由，M5 须显式加 `_mentions_emotion(lowered)` 分支并组装 `ToolCall`，否则工具建好也触发不了。
- **`device_events.json` 写放大**：`JsonListStore.append`（`storage.py:34`）整文件重写、无轮转；情绪高频累积会拖慢全部事件读写。M2 在节流外补 **`emotion_detected` 独立保留期(30天)+裁剪/轮转或分库**，验收加事件量级压测。
- **隐私验收要可证伪**：把"grep 不到落盘"换成可执行断言——mock 文件系统/媒体存储断言**零写入**、日志不含原始帧字节、处理后无临时残留；"禁止 log 原始音视频"写入代码规范。
- **蒙语文本情感模型给同级降级**：若无可用模型，蒙语文本模态标 `unavailable`、靠视觉+韵律两模态、`language` 仍标 `mn`；"找/微调蒙语情感模型"作为可挂起研究项，不作 M4 硬交付。
- **M1 只验逻辑、不验情绪准确性**：无标注数据时 M1 单测只断言融合/平滑的确定性行为，"情绪判定准确性"标定挂到有真实数据之后。

### 9.4 范围收敛（砍过度设计）

- **M6 的"安全范围最多几步移动"从 v0 手势集移除**——一迈步就触及"走路鲁棒性"，与"只做原地静态平衡"硬约束冲突；头/臂/眼灯/语音已足够表达。
- **M2 边缘"人脸存在检测"简化**——既然三模态全服务器推理，边缘别在 Pi 3B 上叠人脸模型；用运动/亮度触发或服务器侧判帧是否有脸替代，VAD 保留。
- **`edge_model` 字段改名 `inference_model`**（服务器推理，原名误导）。已改 §5.1。
- **M7 研究级融合(GTAH)明确不在产品关键路径**——晚融合+滞回对陪伴已足够，研究融合是论文贡献。

### 9.5 排序修正

- **宠物人格 UI 后移**：人格（名字/语气/对象）仍是 §7 待定决策，M5 前端先只放"情绪能力开关"，人格设置等决策落地。
- **M2 前置一个轻量"模型选型 spike"**：FER/SER 用本地权重还是远程服务仍待定（§7），选型未定不应压进 M2 固定工作量。
- **M3 语种路由对 ASR 的依赖要澄清**：`detect_language` 依赖 ASR，而蒙语 ASR 明确后置/挂起；M3 落地前先定义"中英 ASR 组件就绪度"，避免 `detect_language` 悬空。
- **M6 真机集成窗口前移**：别让"前面全是服务器逻辑、到 M6 才第一次真机闭环"；M0b 的真机受控动作 + Yanshee 控制适配器联调应作为独立集成窗口提前安排。

### 9.6 审查确认为真（无需改）

`emotion_detected` 是合法 `DeviceEventType`（`models.py:441`）、`camera`+`emotion_recognition` 双门控均需 `local_only`（`media_store.py:245/249`）、`attributes` 为 `dict[str,Any]` 可承载嵌套情绪载荷、`RiskLevel.read_only` 合法、`/api/agent/chat` 确实零流式（规划正确地未假定就绪）、单 uvicorn 进程（故 M1 进程内平滑状态可行）。**事件类型/查询接口确实已存在，不新建**——这一省力判断成立。
