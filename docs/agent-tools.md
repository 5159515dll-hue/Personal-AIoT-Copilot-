# 智能体工具

当前版本智能体是确定性的工具优先实现，不依赖自由执行。

## 已实现工具

- `get_current_room_state`：返回当前模拟房间指标、健康分、异常和建议。
- `query_sensor_history`：返回二氧化碳等指标的聚合证据。
- `create_automation_rule`：只创建草案；保存必须通过用户确认。
- `control_device`：将设备动作请求送入策略引擎和审计日志。
- `policy_check`：记录提示注入或绕过策略的拒绝决定。

## 回复结构

`POST /api/agent/chat` 返回：

- `message`：智能体回复。
- `used_data`：回复使用的数据来源。
- `tool_calls`：结构化工具证据。
- `policy`：相关安全策略判断。
- `needs_confirmation`：下一步是否需要用户确认。
- `rule_draft`：必要时返回规则草案。

## 模型边界

当前版本使用确定性的模拟智能体。未来可以替换语言生成层，但工具结构、策略判断和审计日志必须保持最终权威。

