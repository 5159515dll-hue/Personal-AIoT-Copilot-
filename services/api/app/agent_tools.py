from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.audit import record_audit
from app.mock_data import current_room_state, get_device, query_history, summarize_metric
from app.models import (
    AgentChatRequest,
    AgentChatResponse,
    AgentMessage,
    AutomationRuleCreate,
    ControlDeviceRequest,
    Metric,
    PolicyDecision,
    PolicyResult,
    RiskLevel,
    ToolCall,
)
from app.policy import assess_device_control, detect_prompt_injection, validate_rule
from app.time_utils import now


def handle_chat(request: AgentChatRequest) -> AgentChatResponse:
    message = request.message.strip()
    session_id = request.session_id or f"session_{uuid4().hex[:10]}"
    lowered = message.lower()
    tool_calls: list[ToolCall] = []
    used_data: list[str] = []
    needs_confirmation = False
    policy: PolicyDecision | None = None
    rule_draft: AutomationRuleCreate | None = None

    if detect_prompt_injection(message):
        policy = PolicyDecision(
            result=PolicyResult.denied,
            risk_level=RiskLevel.high,
            requires_confirmation=False,
            reason="检测到提示注入或绕过策略文本。",
            constraints=["即使文本要求忽略规则，工具调用仍然必须受策略约束。"],
        )
        audit = record_audit(
            actor="agent",
            action="agent_refusal",
            result="blocked",
            details=policy.reason,
            parameters={"message": message},
            policy=policy,
        )
        tool_calls.append(
            ToolCall(
                name="policy_check",
                parameters={"message": message},
                result={"audit_log_id": audit.id, "decision": policy.model_dump(mode="json")},
                policy=policy,
                created_at=now(),
            )
        )
        reply = "我不能执行绕过安全策略的指令。该请求已被阻止，并写入审计日志。"
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    if _mentions_forbidden_control(lowered):
        device_id = "smoke_alarm_01" if "smoke" in lowered or "烟雾" in lowered else "smart_plug_01"
        control = _control_tool(device_id, "on", False, message)
        tool_calls.append(control)
        policy = control.policy
        reply = f"我不能执行该控制动作。{policy.reason if policy else '策略引擎已阻止。'}"
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    if _mentions_lamp_control(lowered):
        control = _control_tool("desk_lamp_01", "on", True, message)
        tool_calls.append(control)
        policy = control.policy
        reply = "模拟桌面台灯已通过策略检查链路开启，该动作已写入审计日志。"
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    if _mentions_rule(lowered):
        rule_draft = AutomationRuleCreate(
            condition="二氧化碳 > 1200 ppm 持续 15 分钟且房间有人",
            action="发送通风提醒",
            enabled=True,
            confirmed=False,
        )
        policy = validate_rule(rule_draft)
        needs_confirmation = True
        tool_calls.append(
            ToolCall(
                name="create_automation_rule",
                parameters=rule_draft.model_dump(),
                result={"status": "draft", "policy": policy.model_dump(mode="json")},
                policy=policy,
                created_at=now(),
            )
        )
        reply = (
            "我起草了一条提醒规则：如果二氧化碳在房间有人时持续 15 分钟高于 1200 ppm，"
            "那么发送通风提醒。在你确认之前，我不会保存这条规则。"
        )
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    if _mentions_co2_or_environment(lowered):
        room = current_room_state()
        co2_summary = summarize_metric(Metric.co2)
        used_data.extend(["current_room_state", "co2_24h_summary"])
        tool_calls.append(
            ToolCall(
                name="get_current_room_state",
                parameters={},
                result=room.model_dump(mode="json"),
                created_at=now(),
            )
        )
        tool_calls.append(
            ToolCall(
                name="query_sensor_history",
                parameters={"metric": "co2", "period": "last_24_hours", "bucket": "15m"},
                result=co2_summary,
                created_at=now(),
            )
        )
        reply = (
            f"当前房间状态为 {room.status}。{room.summary}"
            f"最近 24 小时二氧化碳平均值为 {co2_summary['avg']} ppm，峰值为 {co2_summary['max']} ppm。"
            f"建议：{room.recommendation}"
        )
        if room.anomalies:
            reply += f" 不确定性或警告：{'；'.join(room.anomalies)}"
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    if "7" in lowered or "week" in lowered or "一周" in lowered:
        end_ts = now()
        readings = query_history(Metric.co2, end_ts - timedelta(days=7), end_ts, "1h")
        values = [reading.value for reading in readings]
        used_data.append("co2_7d_hourly")
        tool_calls.append(
            ToolCall(
                name="query_sensor_history",
                parameters={"metric": "co2", "period": "last_7_days", "bucket": "1h"},
                result={
                    "avg": round(sum(values) / len(values), 1),
                    "max": max(values),
                    "samples": len(values),
                },
                created_at=now(),
            )
        )
        reply = "一周模式显示，二氧化碳通常在下午和深夜有人时段上升。通风提醒应重点覆盖这些时间窗口。"
        return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    room = current_room_state()
    used_data.append("current_room_state")
    tool_calls.append(
        ToolCall(
            name="get_current_room_state",
            parameters={},
            result=room.model_dump(mode="json"),
            created_at=now(),
        )
    )
    reply = (
        "我可以回答模拟房间状态、二氧化碳趋势、设备、规则和审计日志相关问题。"
        f"当前建议：{room.recommendation}"
    )
    return _response(session_id, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


def _control_tool(device_id: str, state: str, confirmed: bool, intent: str) -> ToolCall:
    device = get_device(device_id)
    policy = assess_device_control(
        device=device,
        requested_state=state,
        confirmed=confirmed,
        intent=intent,
    )
    execution_result = "success" if policy.result == PolicyResult.allowed else "blocked"
    audit = record_audit(
        actor="agent",
        action="control_device",
        result=execution_result,
        details=policy.reason,
        parameters={"device_id": device_id, "state": state, "confirmed": confirmed},
        policy=policy,
    )
    return ToolCall(
        name="control_device",
        parameters={"device_id": device_id, "state": state, "confirmed": confirmed},
        result={"execution_result": execution_result, "audit_log_id": audit.id},
        policy=policy,
        created_at=now(),
    )


def _response(
    session_id: str,
    reply: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    record_audit(
        actor="agent",
        action="agent_chat",
        result="success",
        details="智能体回复已通过受约束工具流程生成。",
        parameters={"session_id": session_id, "tool_calls": [tool.name for tool in tool_calls]},
        policy=policy,
    )
    return AgentChatResponse(
        session_id=session_id,
        message=AgentMessage(role="assistant", content=reply, created_at=now()),
        used_data=used_data,
        tool_calls=tool_calls,
        needs_confirmation=needs_confirmation,
        policy=policy,
        rule_draft=rule_draft,
    )


def _mentions_co2_or_environment(text: str) -> bool:
    return any(token in text for token in ("co2", "二氧化碳", "空气", "环境", "temperature", "humidity", "今天", "room"))


def _mentions_rule(text: str) -> bool:
    return any(token in text for token in ("rule", "automation", "提醒", "规则", "创建"))


def _mentions_lamp_control(text: str) -> bool:
    return ("lamp" in text and "on" in text) or "打开台灯" in text or "开灯" in text


def _mentions_forbidden_control(text: str) -> bool:
    return any(
        token in text
        for token in (
            "unknown plug",
            "smart_plug",
            "all plugs",
            "smoke alarm",
            "disable alarm",
            "未知插座",
            "所有插座",
            "烟雾报警",
            "关闭报警",
        )
    )
