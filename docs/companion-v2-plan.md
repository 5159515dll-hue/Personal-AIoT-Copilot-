# 情感陪伴 v2 规划：多模态融合 · 长期记忆 · 多角色 · 动作

在已落地的 v0（感知→晚融合→豆包共情→手势门控）之上，规划四件事：**接入真实多模态情感模型、长期记忆模块、角色/躯体解耦、回应伴随动作**。本文给出数据模型、模块设计、分阶段路线与待定决策。

**建立在已有基础上**：可插拔情绪后端（`emotion_perception.register_*`）、人格系统（`companion_persona`）、手势执行器（`robots/yanshee/companion_gesture.py`）+ 策略门控（`policy.assess_companion_gesture`）、事件保留期（`media_store` 裁剪）、function-calling 方向（见 §0）。

**贯穿原则**（沿用 `docs/development-guide.md`）：工具优先 / 策略优先、边缘优先隐私、模块化容错隔离、**角色与躯体解耦**、**记忆是敏感个人数据**。

---

## 0. 一次陪伴交互的目标链路（v2 全貌）

```text
多模态感知(脸+声+文→融合 EmotionState)
   → 记忆检索(画像事实 + 相关情节 + 情绪趋势)
      → 按需工具调用(function calling：读环境/事件/设备…)
         → LLM 生成 {共情回应, 建议动作∈安全集}
            → 策略门控动作(policy) + TTS(母语) + 手势(机器人执行器)
               → 写记忆(抽取事实 / 摘要情节 / 更新情绪趋势)
```

«工具调用» 与 «记忆» 是 v0 没有、v2 要补的两块；动作从"情绪驱动"升级为"内容感知但受门控"。

---

## 1. 接入真实多模态情感模型

### 1.1 接入点（已就位的 seam）
v0 已把 `emotion_perception` 做成可插拔后端：`register_face_model` / `register_voice_model` / `register_text_model`。真实模型用一个 `EmotionModalityInput`(7类分布+置信度) 出口即可挂上，**调用方/融合层不变**。

### 1.2 各模态落地
| 模态 | v0 | v2 真实模型 | 部署 |
|---|---|---|---|
| 文本 | 关键词 | 多语种情感模型；蒙古语分支(GTAH 参考) | 服务器 |
| 视觉 FER | 透传桩 | 轻量 FER（7类+VA） | 边缘优先；Pi 3B 不足则服务器 |
| 语音 SER | 透传桩 | 韵律/wav2vec SER | 同上 |
| 融合 | 晚融合+滞回 | 可升级研究级 GTAH（门控Transformer+自适应超模态） | 服务器 |

### 1.3 模型适配契约与治理
- **适配器接口**：每个模型实现 `(input)->EmotionModalityInput|None`，注册到 `register_*`。模型权重/依赖与平台隔离，单模型失败回退默认桩（容错）。
- **版本/灰度/回退**：模型带 `model_id+version`，写进事件 `inference_model`；可灰度并随时 `register_*(None)` 回退。
- **边缘 vs 服务器**：原始音视频默认不出机；边缘出结构化信号或服务器即用即弃（隐私门控 + 不落盘，沿用 v0）。
- **与陪伴的连接**：companion 已读 `EmotionState`（`get_last_state`），**模型一升级，陪伴自动获得更准情绪**，无需改 companion。

---

## 2. 长期记忆模块（核心）

目标：从"单次对话"升级到"记得你是谁、记得发生过什么"。按**时间**与**事件**两个维度组织，分四层。

### 2.1 四层记忆
1. **工作记忆（会话内，短时）**：当前对话最近 N 轮。临时、随会话过期。
2. **情节记忆（按事件）**：显著互动的"事件条目"。
   ```
   Episode { id, character_id, timestamp, summary, emotion, valence,
             salience(0-1), topics[], excerpt? }
   ```
   何时写：情绪强度高 / 用户说"记住" / 出现新信息。检索：近期 + 话题匹配 + 情绪匹配。
3. **画像记忆（按事实，语义）**：关于用户的稳定事实——这是"它真的懂你"的来源。
   ```
   ProfileFact { key, value, confidence, first_seen, last_updated, source_episode_id }
   # 例：{工作:"程序员常加班"}、{重要的人:"奶奶"}、{偏好:"喜欢安静"}
   ```
   由情节抽取/更新；紧凑，每次回应都注入。
4. **情绪记忆（按时间，时序）**：`emotion_detected` 事件流（已有）+ 周期汇总。
   ```
   MoodRollup { character_id, period(day/week), dominant_emotion, valence_avg, summary }
   # 支撑"你这周心情起伏有点大"、情绪趋势。
   ```

### 2.2 写入路径（记忆抽取）
每次有意义的互动后，"记忆写入器"决定记什么：
- **v0（规则）**：情绪强度高 / 显式"记住" / 命中新事实 → 写情节 + upsert 画像事实 + 更新情绪。
- **进阶（LLM 抽取）**：一次轻量 LLM 调用抽 `{facts[], episode_summary, salience}`（豆包，关思考，低成本）。

### 2.3 读取/检索（注入提示）
生成回应前，组"记忆上下文"，受 token 预算约束取 top-N：
- 画像事实（紧凑，常注入）
- 最近 K 条情节（按时间）
- 相关情节（与当前话题/关键词重叠 → 按事件）
- 近期情绪趋势（MoodRollup）
- **v0**：结构化检索（recency + 话题标签重叠 + 情绪匹配）。**进阶**：embedding 向量检索做语义相关（需轻量向量库/模型）。

### 2.4 遗忘 / 衰减 / 时间汇总（关键，像人脑）
- **显著度裁剪**：低 salience 的旧情节压缩/丢弃（复用 B5 的保留期+滞回裁剪）。
- **时间汇总**：日情节→周摘要→月摘要，越久越压缩细节。
- **置信衰减**：长期未被强化的画像事实降置信；用户可纠正/删除。

### 2.5 存储与隐私
- **per-character JSON 存储**（仿 `.local`）：`memory_episodes.json` / `memory_profile.json` / `memory_mood.json`，按 `character_id` 分。
- **隐私（强制）**：本地、限定保留期、**用户可查看/编辑/删除**（后续 `/memory` 管理页）。记忆是敏感个人数据，不外发、不画像贩卖（dev guide 红线）。

### 2.6 关键设计点：记忆跟"角色"走，不跟"躯体"走
见 §3——小暖换个机器人躯体，记忆不丢。

---

## 3. 多角色：角色 ↔ 躯体解耦

### 3.1 核心抽象
把现在耦在一起的"小暖"拆成两个概念：
- **角色 Character**：身份与灵魂——名字、人格(archetype)、嗓音、提示词、**记忆**。
- **躯体 Body**：硬件——某台 Yanshee 机器人（或纯软件无躯体）。
- **入驻 embodiment**：一个角色入驻一个躯体。多机器人 → 各入驻一个角色；记忆**跟角色走**。

### 3.2 数据模型演进（最小改动）
`CompanionPersona` 升级为 `Character`（向后兼容，默认就是小暖）：
```
Character { id, name, archetype, voice, companion_for, persona_notes,
            active }          # 多个角色，但同一时刻一个 active（或 per-body）
Body/Device { device_id, robot_type, active_character_id }   # 躯体绑定哪个角色
```
- 记忆三表的 `character_id` 外键 → 记忆按角色隔离。
- companion 生成回应时按 `(character, user, space)` 上下文，提示词 = 角色人格 + 该角色的记忆。

### 3.3 建议（现在做什么）
- **现在就把数据模型解耦**（Character 实体 + character_id 贯穿记忆/回应），即使只有小暖一个、一个机器人。成本小、未来加角色/机器人零重构。
- **暂不做多角色管理 UI**：前端先维持"一个陪伴 + 人格设置"，把"人格设置"对接到 active Character。多角色切换 UI 等真有第二个角色/机器人再做。
- 一台机器人当前 = 小暖的躯体（`active_character_id = 小暖`）。

---

## 4. 回应伴随动作的设计

### 4.1 动作词表（安全原地集）
沿用并扩展 `policy.SAFE_COMPANION_GESTURES`，每个动作带元数据：
```
Gesture { id, motion_ref(per-body, get_motion_list 查), connotation(情绪含义),
          intensity(0-1), allow_during_speech(bool) }
# 例：nod(认同), tilt_head(倾听/疑惑), reach_out(安抚), wave(打招呼), idle_nod(轻陪伴)
```
扩展须守"原地、安全、不移动"硬约束（走路/移动仍搁置）。

### 4.2 动作选择：内容感知但受门控（三档）
- **情绪驱动（v0，保底）**：情绪→默认手势（确定性、永远安全）。
- **内容驱动（v2）**：LLM 在生成回应时**从允许集里提议一个手势**（结构化输出 `{reply, gesture}`，gesture 限定枚举）。打招呼→wave、安慰→reach_out。
- **混合（推荐）**：LLM 提议 → 若非法/缺失则回退情绪驱动 → **policy 门控**(`assess_companion_gesture`) → 机器人执行器播放。LLM **只能从安全集选**，无法发明"向前走"。

### 4.3 时序同步（动作配合说话）
- 回应 = `{text, gesture}`。手势在 TTS 开始时启动（`allow_during_speech` 的可与语音并行；大动作先做完再说）。
- v0 简单：先播手势再 TTS（或并行）。进阶：按句/关键词触发分解动作。

### 4.4 安全（强制）
- 所有动作经 `policy` 门控 + 限速 + 审计；仅原地安全集；注入文本不能提升动作权限（沿用 v0）。
- 真机执行走 `robots/yanshee/companion_gesture.py`（抽象手势→`get_motion_list`校验→`sync_play_motion`）。

---

## 5. 分阶段路线

| 阶段 | 内容 | 依赖 |
|---|---|---|
| **V2.1 角色解耦** | `CompanionPersona`→`Character`（含 character_id），Body 绑定 active_character；记忆三表按 character 分 | 无（纯重构，向后兼容） |
| **V2.2 记忆 v0** | 情节/画像/情绪三层存储 + 规则写入 + 结构化检索 + 注入提示 + 保留期裁剪 | V2.1 |
| **V2.3 工具调用** | companion 加 function-calling（read_emotion/environment/events…），吸收 agent 工具+policy+审计 | 见上一轮讨论 |
| **V2.4 内容驱动动作** | LLM 结构化输出 {reply, gesture}，混合选择 + 门控 | 无 |
| **V2.5 真实多模态模型** | FER/SER/蒙语文本模型经 register_* 接入 | 模型/数据（部分硬件耦合） |
| **V2.6 进阶** | LLM 记忆抽取、embedding 语义检索、研究级 GTAH 融合、多角色 UI、记忆管理页 | 按需 |

---

## 6. 待定决策（需你拍板）

1. **记忆检索 v0**：结构化（recency+话题+情绪，零依赖）vs 直接上 embedding 语义检索（更准、需向量库）。建议先结构化。
2. **记忆写入**：规则触发 vs LLM 抽取（更聪明、每轮多一次模型调用）。建议 v0 规则 + 关键场景 LLM 抽取。
3. **多角色 UI**：现在只建数据模型、不建切换 UI？（建议是）
4. **动作选择**：纯情绪驱动 vs LLM 提议混合？（建议混合，带门控回退）
5. **记忆边界**：每个角色记忆是否跨空间/跨用户共享？（建议：跟角色走、按用户隔离）

---

## 7. 预计新增/改动模块
- `services/api/app/models.py`：`Character`/`CharacterUpdate`、`Episode`/`ProfileFact`/`MoodRollup`、`{reply,gesture}` 输出。
- `services/api/app/character_store.py`（新，由 `companion_persona` 升级）。
- `services/api/app/memory.py`（新）：写入器 + 检索器 + 裁剪/汇总。
- `services/api/app/companion.py`：注入记忆上下文 + 结构化 {reply,gesture} 输出。
- `services/api/app/routes/companion.py`：记忆读/删端点、角色端点。
- `services/api/app/emotion_perception.py`：真实模型适配器（V2.5）。
- 前端：人格→角色设置、(后续)记忆管理页。
- `robots/yanshee/companion_gesture.py`：动作元数据 + 执行（已有基础）。

---

## 8. 参考
- v0 执行规划：`docs/companion-robot-plan.md`
- 多模态情感设计：`docs/emotion-companion-design.md`
- 工程规范：`docs/development-guide.md`
- 机器人接入：`docs/yanshee-integration.md`
