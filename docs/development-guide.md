# 工程开发规范（Development Guide）

本规范适用于本仓库**所有代码**。它把外部接口对接、自有模块设计、健壮性与容错隔离固化成**强制标准**，所有提交都必须遵守。

## 0. 总则（三条铁律）

1. **外部接口照官方文档，禁止捏造。** 任何外部 API（机器人、大模型、第三方服务）以官方文档为唯一事实来源。不确定的函数名 / 参数 / 取值一律标 `TODO` 并查官方文档或运行时查询，**绝不凭记忆编造**。
2. **无官方规范的自有模块，按本规范统一并严格执行。** 自定规范须符合国际通行准则（见各节引用），保持严谨与逻辑一致。
3. **模块化 + 容错隔离。** 单个模块失效只降级该功能，**不得拖垮整个请求或进程**。

---

## 1. 外部接口规范（官方文档优先）

### 1.1 通用规则
- 每个外部接口在代码注释中**注明官方文档出处**（URL 或文档名 + 版本）。
- 函数名 / 端点 / 参数 / 枚举值以官方文档为准；拿不准的标 `TODO(官方文档待核)`，不得用"多名兜底猜测"冒充确定实现。
- 设备 / 机器人**内置资源名**（如动作名）必须**运行时查询**（如 `get_motion_list()`），不在代码里硬编码猜测。
- 密钥 / 令牌**不入库、不写日志、不硬编码**；经 `/models` 导入或服务器私有 `.dashboard-env` 注入。

### 1.2 Yanshee / YanAPI
- 依据：**官方 YanAPI 2.0.0 接口文档**（接口表 `ubtrobot-new.oss-cn-shenzhen.aliyuncs.com/static/MINI/Yanshee/yanapi/html-zh/YansheeSDK.html`）。
- 真实函数名清单见仓库记忆 `yanapi-reference`；典型：`yan_api_init`、`get_motion_list`、`sync_play_motion(name,direction,speed,repeat)`、`start_voice_tts`、`sync_do_voice_iat_value`、`get_robot_battery_info`、`get_sensors_gyro/environment/infrared/ultrasonic`、`get_vision_photo`、`set_robot_led`。
- 内置**动作名**用 `get_motion_list()` 查，禁止硬编码。

### 1.3 大模型接口
- **火山方舟 Ark（豆包）**：OpenAI 兼容，端点 `https://ark.cn-beijing.volces.com/api/v3`。豆包 seed 系列为**推理模型，默认开思考**（实测 14.6s 且超时）；按官方"深度思考"规范用 `thinking={"type":"disabled"}` 关闭，降到 ~2.8s。官方文档 `volcengine.com/docs/82379`。
- **Kimi / 小米 MiMo**：各自官方文档（见 `model_providers.py` 的 `docs_url`）。Kimi 同样关思考。MiMo 支持 `api-key` 与 `Authorization` 双认证头。
- 统一收口在 `model_providers.py` 的声明式 `PROVIDERS` + `apply_speed_params()`；新增厂商加一条，不散落特判。

---

## 2. 自有模块规范（无官方规范 → 自定，须符合国际准则）

### 2.1 协议与版本
- 设备接入统一 `aiot.v1` 协议（`docs/device-connection-interface.md`）。
- 协议 / API 版本遵循**语义化版本 SemVer 2.0.0**：新增字段不破坏旧字段语义；破坏性变更升主版本（`aiot.v2`）。
- 消息带 `message_id` + 递增 `sequence`，支持去重与乱序检测。

### 2.2 数据契约
- 所有 API 输入输出用 **Pydantic（后端）/ TypeScript 类型（前端）显式定义**，禁止裸 dict 出入边界。
- 时间统一 **ISO 8601 / UTC**；JSON 遵循 **RFC 8259**；浮点区间显式约束（如 `valence∈[-1,1]`）。
- 情绪事件 `attributes` 固定结构（`docs/companion-robot-plan.md` §5.1）：`primary_emotion`(7类) / `valence` / `arousal` / `language` / `modalities` / `fusion` / `smoothed`。原始音视频与转写原文**不入事件**。
- 封闭枚举用 `Literal` / `Enum`，越界即 422，不静默接受。

### 2.3 命名
- Python：`snake_case`，类型注解齐全（**PEP 8 / PEP 484**）；模块单一职责，文件名即职责。
- TypeScript：`camelCase`（变量/函数）、`PascalCase`（类型/组件）。
- REST 路径：资源名小写、用连字符；事件类型 / 枚举值小写下划线（`emotion_detected`）。

### 2.4 REST / HTTP
- 状态码遵循 **RFC 9110** 语义：`200` 成功 / `401` 未认证 / `403` 策略拒绝 / `404` 不存在 / `422` 入参非法 / `503` 依赖不可用。
- 鉴权头统一：内部令牌 `X-AIoT-Internal-Token`、设备令牌 `X-AIoT-Device-Token`。
- 错误体统一 `{"detail": ...}`；策略拒绝带 `{"message", "audit_log_id"}`。
- 流式用 SSE（`text/event-stream`），`data: {json}\n\n`，以 `data: [DONE]` 收尾。

### 2.5 模块边界与依赖方向
- 单向依赖，**禁止循环依赖**。情感链路的层次与依赖方向：
  ```
  边缘采集(robots/) → 感知 emotion_perception → 融合 emotion_fusion → 决策 companion/policy → 门控 yanshee_control → 回应(robots/)
  路由层(routes/*) 只编排，不放业务逻辑；业务在 app/*.py 模块。
  ```
- 跨模块只通过显式函数 / 数据契约通信，不共享可变全局（除显式线程安全 store，如 `EmotionSmoother`、`JsonListStore`）。

---

## 3. 健壮性与容错隔离（强制）

### 3.1 失效隔离原则
任一外部依赖（大模型、机器人、数据库、传感器、网络）失效，**只降级对应功能**，不得使整个请求或进程崩溃。安全相关失败一律 **fail-safe（默认拒绝/安全）**。

### 3.2 强制模式
- **外部调用必须有 try/except 边界 + 超时**，失败回退到**确定性兜底**：
  - 大模型失败 → 模板回应（`companion._template_reply`）/ 本地工具链（`generate_agent_reply` fallback）。
  - 某模态缺失 → 晚融合自动降级（`emotion_fusion`）；全缺 → neutral 兜底。
  - 传感器 / 遥测失败 → 跳过该项，不发空、不报 500。
- **可选依赖缺失要能降级运行**：`yanapi` 未安装时机器人侧脚本以桩数据跑通上报链路（`import` 失败不崩）。
- **输入校验在边界**：Pydantic 拦截非法输入返回 4xx，禁止脏数据进入业务层导致 500。
- **隐私即健壮性**：原始音视频不落盘、不写日志；情绪敏感数据限期可删。
- **并发**：进程内共享状态用锁（`threading.Lock`）；JSON store 单进程假设需在文档注明。

### 3.3 禁止
- 裸 `except: pass` 吞错且无任何日志 / 兜底。
- 一个路由模块 import 失败拖垮 `main`（新模块上线前必须本机能 import + 测试通过）。
- 安全 / 策略路径"出错即放行"（必须出错即拒绝）。
- 把未验证的外部接口名当确定实现写死。

---

## 4. 测试规范
- **纯逻辑单测**：融合 / 感知 / 策略 / 共情用确定性输入，只验逻辑正确性（无标注数据时不假装验准确性）。
- **集成测试**：路由用 `TestClient` + 隔离夹具（store 重定向到 `tmp_path`、进程内状态 `reset`）。
- **不依赖真实外部服务**：模型 / 机器人用 mock / stub；CI 与本机基础自检不联网。
- **隐私可证伪验收**：断言原文不入库、零媒体写入。
- 分工：**本机做编程 + 基础自检**（`pytest`、`typecheck`、`lint`）；**完整测试在服务器**（`verify:release` / `smoke:server`）。

---

## 5. 模块清单与容错边界

| 模块 | 职责 | 失效降级行为 |
|---|---|---|
| `model_providers` | 大模型厂商目录 + 调用 | 调用失败 → fallback 链 / 模板 |
| `emotion_perception` | 三模态推理（文本真推理 + FER/SER 可插拔桩） | 模态不可用 → 返回 None，不阻断 |
| `emotion_fusion` | 晚融合 + 滞回平滑 | 缺模态降级；全缺 neutral；纯函数无副作用 |
| `companion` | 共情回应 + 流式 | 模型失败 → 温柔治愈模板 |
| `policy` | 风险门控 | 出错 / 未知 → 拒绝（fail-safe） |
| `yanshee_control` | 平台侧手势门控 | 只门控，不碰真机；动作名机器人侧解析 |
| `routes/*` | HTTP 编排 | 异常映射为 4xx/5xx，不裸抛 500 |
| `robots/yanshee/*` | 边缘采集 / 控制 | 无 yanapi 降级；不落盘；代理隔离 |

---

## 6. 部署规范
- **本地直传服务器**（`rsync`），**不在服务器 `git pull`**（私有仓库免凭据问题，且本机为唯一源）。
- 同步**排除**：`.git`、`node_modules`、`.venv`、`__pycache__`、`.next`、`services/api/.local`、`config.py`、`.dashboard-env`、密钥。
- 密钥 / 令牌只存服务器私有 `.dashboard-env`；服务用 `systemd`（`aiot-api/web/mqtt-ingestor`）。
- 传输后：装依赖 → 重启 systemd → 跑服务器完整测试（`verify:release`）→ 验证关键接口。

---

## 7. 提交与版本
- 提交信息建议 **Conventional Commits**（`feat:` / `fix:` / `docs:` / `refactor:` / `test:`）。
- **不提交**：密钥、`config.py`、`.dashboard-env`、`.local` 运行时数据（已在 `.gitignore`）。
- 对外契约（`aiot.v1`、情绪事件 schema、策略接口）保持稳定，破坏性变更升版本并更新本规范。
