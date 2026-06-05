# 智能体工具

当前版本智能体是工具优先实现。工具调用和策略判断由后端确定性执行，当前大模型只在这些结果之后参与自然语言分析。Agent 请求支持 `data_source=mock|database`，默认使用模拟数据，切换到 database 时会读取 TimescaleDB 最新读数和聚合历史曲线。

## 已实现工具

- `get_current_room_state`：返回当前房间指标；mock 使用确定性模拟器，database 使用入库最新读数。
- `query_sensor_history`：返回二氧化碳、温湿度、光照、人体存在和噪声分贝等指标的聚合证据；mock 和 database 使用同一套 bucket 语义。
- `summarize_daily_environment`：聚合最近 24 小时温度、湿度、二氧化碳、光照、有人状态和噪声分贝，返回每日摘要、最差空气时间、噪声峰值提示和解释。
- `summarize_weekly_environment`：聚合最近 7 天六类环境指标，比较有人状态与二氧化碳均值，用于回答一周环境趋势和学习/停留状态关系；人体存在只作为弱代理，不推断真实学习效率。
- `explain_environment_issue`：解释下午犯困、二氧化碳上升、空气变差等问题，返回证据、可能原因和不确定性。
- `recommend_action`：给出安全行动建议，只返回提醒或人工低风险动作，不直接控制高风险设备。
- `get_device_status`：读取 mock device adapter 中的设备状态和风险元数据，回答哪些设备开启、离线或需要关注；该工具只读，不执行控制。
- `detect_anomaly`：读取当前状态、最近 24 小时曲线和传感器健康状态，按缺失指标、过期读数、异常质量、CO2 阈值、温湿度范围和噪声阈值生成异常摘要；database 不可用时返回明确不可用原因。
- `search_device_docs`：只查询项目内设备协议和 ESP32 固件说明，返回 MQTT topic、payload、HTTP 入站、入库语义和安全边界摘要。
- `create_automation_rule`：只创建草案；保存必须通过用户确认。当前支持二氧化碳等指标提醒和“晚上 11 点后”这类简单时间提醒草案。
- `control_device`：将设备动作请求送入策略引擎、速率限制和审计日志；允许的低风险模拟动作会写入 mock device adapter 状态。
- `get_audit_log`：读取最近审计摘要，用于回答“刚才发生了什么”“哪些动作被拒绝”等追溯问题；工具结果不包含完整原始参数。
- `policy_check`：记录提示注入或绕过策略的拒绝决定。
- `llm_response_generation`：可选语言生成层，读取当前模型配置，把工具结果整理为更自然的中文解释。

## 回复结构

`POST /api/agent/chat` 返回：

- `message`：智能体回复。
- `used_data`：回复使用的数据来源。
- `tool_calls`：结构化工具证据。
- `policy`：相关安全策略判断。
- `needs_confirmation`：下一步是否需要用户确认。
- `model_usage`：本次是否使用当前大模型、使用的厂商和模型、失败或阻止原因。
- `rule_draft`：必要时返回规则草案。

当 `rule_draft` 存在时，前端只展示草案和确认按钮。用户点击“确认保存规则”后，浏览器再调用 `POST /api/rules` 并把 `confirmed=true` 发送给后端；后端会重新运行规则策略检查，并分别记录确认与创建审计日志。

每日总结、一周总结、问题解释和行动建议都支持 `mock` 与 `database` 数据源。数据库不可用、缺少最新读数或历史曲线为空时，工具结果会返回 `status=unavailable|empty`，智能体必须说明原因并避免给出伪确定结论。

## 对话记录

每次 `POST /api/agent/chat` 成功后，后端都会把用户消息、助手回复、工具调用、模型状态、策略判断和数据源写入本地 `agent_conversations.json`。记录保留最近 30 天，页面右侧的“最近对话记录”会读取 `GET /api/agent/history`，用户可以通过 `DELETE /api/agent/history/{entry_id}` 手动删除单条记录；删除动作会写入审计日志。

对话记录不是密钥仓库。保存前会对 `sk-`、`tp-` 等常见密钥样式，以及 `api_key`、`token`、`authorization`、`password`、`密钥`、`口令` 等字段做基础脱敏。

## 模型接入边界

`/models` 页面提供中国区模型厂商配置、密钥导入和当前模型选择，已预置小米 MiMo 与 Kimi 接口。密钥导入和模型切换是两个独立动作：导入密钥不会改变智能体当前模型，切换当前模型不会要求重新输入密钥。

模型接入遵守以下边界：

- 智能体先把用户问题映射到工具，再用工具返回结构化结果。
- 设备控制类意图必须先经过策略引擎。
- 策略拒绝、提示注入、未知插座、报警器关闭等请求不会外发给大模型。
- 审计查询只把最近日志摘要送入模型增强层，不传递完整参数或密钥。
- 接口密钥按厂商保存，同一厂商再次导入会覆盖原密钥；当前模型选择只引用已导入的厂商密钥。
- 模型调用失败、未配置密钥或返回空文本时，自动回退到本地工具链回复。
- Kimi K2.6 默认关闭 thinking 并使用 `max_completion_tokens`，保证连接测试和智能体回复能拿到正文。
- 小米 MiMo Token Plan OpenAI 入口同时发送 `api-key` 与 `Authorization: Bearer`，兼容不同网关认证实现。
- 审计日志会记录工具列表和模型使用状态，但不会记录明文密钥。
