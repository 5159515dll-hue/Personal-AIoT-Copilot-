from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.audit import record_audit
from app.database import latest_sensor_readings_db, query_sensor_history_db
from app.mock_data import current_room_state, get_device, query_history, summarize_metric
from app.model_providers import generate_agent_reply
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


async def handle_chat(request: AgentChatRequest) -> AgentChatResponse:
    message = request.message.strip()
    session_id = request.session_id or f"session_{uuid4().hex[:10]}"
    lowered = message.lower()
    data_source = request.data_source
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
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
            allow_model=False,
        )

    if _mentions_forbidden_control(lowered):
        device_id = "smoke_alarm_01" if "smoke" in lowered or "烟雾" in lowered else "smart_plug_01"
        control = _control_tool(device_id, "on", False, message)
        tool_calls.append(control)
        policy = control.policy
        reply = f"我不能执行该控制动作。{policy.reason if policy else '策略引擎已阻止。'}"
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
            allow_model=False,
        )

    if _mentions_lamp_control(lowered):
        control = _control_tool("desk_lamp_01", "on", True, message)
        tool_calls.append(control)
        policy = control.policy
        reply = "模拟桌面台灯已通过策略检查链路开启，该动作已写入审计日志。"
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
            allow_model=False,
        )

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
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
        )

    if _mentions_co2_or_environment(lowered):
        if data_source == "database":
            return await _database_environment_response(
                session_id=session_id,
                message=message,
                used_data=used_data,
                tool_calls=tool_calls,
                needs_confirmation=needs_confirmation,
                policy=policy,
                rule_draft=rule_draft,
            )

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
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
        )

    if "7" in lowered or "week" in lowered or "一周" in lowered:
        if data_source == "database":
            return await _database_weekly_response(
                session_id=session_id,
                message=message,
                used_data=used_data,
                tool_calls=tool_calls,
                needs_confirmation=needs_confirmation,
                policy=policy,
                rule_draft=rule_draft,
            )

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
        return await _response(
            session_id,
            message,
            reply,
            used_data,
            tool_calls,
            needs_confirmation,
            policy,
            rule_draft,
        )

    if data_source == "database":
        return await _database_environment_response(
            session_id=session_id,
            message=message,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

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
    return await _response(
        session_id,
        message,
        reply,
        used_data,
        tool_calls,
        needs_confirmation,
        policy,
        rule_draft,
    )


async def _database_environment_response(
    *,
    session_id: str,
    message: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(hours=24)
    used_data.extend(["database_latest_sensor_readings", "database_co2_24h_history"])
    try:
        latest = latest_sensor_readings_db()
        readings = query_sensor_history_db(Metric.co2, start_ts, end_ts, bucket="15m")
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="get_current_room_state",
                parameters={"source": "database"},
                result={"source": "database", "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"数据库数据源暂不可用：{error_text}。可以切回模拟数据继续演示，或配置 DATABASE_URL 后再查询真实遥测。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    latest_payload = {
        metric.value: reading.model_dump(mode="json")
        for metric, reading in latest.items()
    }
    tool_calls.append(
        ToolCall(
            name="get_current_room_state",
            parameters={"source": "database"},
            result={
                "source": "database",
                "status": "ok" if latest_payload else "empty",
                "metrics": latest_payload,
            },
            created_at=now(),
        )
    )
    summary = _summarize_readings(readings)
    tool_calls.append(
        ToolCall(
            name="query_sensor_history",
            parameters={"source": "database", "metric": "co2", "period": "last_24_hours", "bucket": "15m"},
            result=summary,
            created_at=now(),
        )
    )

    latest_co2 = latest.get(Metric.co2)
    if not latest_co2 and not readings:
        reply = "数据库数据源当前没有可用的二氧化碳读数。请确认 MQTT 入站服务和 TimescaleDB 写入链路已经启动。"
    elif latest_co2 and summary["samples"]:
        reply = (
            f"数据库最新二氧化碳读数为 {latest_co2.value:.0f} {latest_co2.unit}。"
            f"最近 24 小时数据库曲线平均值为 {summary['avg']} ppm，峰值为 {summary['max']} ppm。"
        )
    elif latest_co2:
        reply = f"数据库最新二氧化碳读数为 {latest_co2.value:.0f} {latest_co2.unit}，但最近 24 小时历史曲线暂无可聚合样本。"
    else:
        reply = "数据库有历史曲线样本，但当前最新读数缺少二氧化碳指标。请检查 MQTT payload 的 metric 字段。"

    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _database_weekly_response(
    *,
    session_id: str,
    message: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(days=7)
    used_data.append("database_co2_7d_hourly")
    try:
        readings = query_sensor_history_db(Metric.co2, start_ts, end_ts, bucket="1h")
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="query_sensor_history",
                parameters={"source": "database", "metric": "co2", "period": "last_7_days", "bucket": "1h"},
                result={"source": "database", "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"数据库 7 天趋势暂不可用：{error_text}。可以切回模拟数据，或先启动数据库和 MQTT 入站链路。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    summary = _summarize_readings(readings)
    tool_calls.append(
        ToolCall(
            name="query_sensor_history",
            parameters={"source": "database", "metric": "co2", "period": "last_7_days", "bucket": "1h"},
            result=summary,
            created_at=now(),
        )
    )
    if summary["samples"]:
        reply = (
            f"数据库 7 天趋势已有 {summary['samples']} 个小时级样本，"
            f"平均值为 {summary['avg']} ppm，峰值为 {summary['max']} ppm。"
        )
    else:
        reply = "数据库 7 天趋势暂无二氧化碳样本。请确认传感器数据已经通过 MQTT 或 HTTP 入库。"
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


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


def _summarize_readings(readings: list) -> dict[str, float | int | str]:
    if not readings:
        return {"status": "empty", "min": 0, "max": 0, "avg": 0, "samples": 0}
    values = [reading.value for reading in readings]
    return {
        "status": "ok",
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 1),
        "samples": len(values),
    }


def _clean_error_text(exc: Exception) -> str:
    return str(exc).strip().rstrip("。.")


def _database_error_text(exc: Exception) -> str:
    if isinstance(exc, RuntimeError):
        return _clean_error_text(exc)
    return "数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态"


async def _response(
    session_id: str,
    user_message: str,
    reply: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
    allow_model: bool = True,
) -> AgentChatResponse:
    final_reply, model_usage = await generate_agent_reply(
        user_message=user_message,
        fallback_reply=reply,
        used_data=used_data,
        tool_calls=tool_calls,
        needs_confirmation=needs_confirmation,
        policy=policy,
        rule_draft=rule_draft,
        allow_model=allow_model,
    )
    record_audit(
        actor="agent",
        action="agent_chat",
        result="success",
        details=f"智能体回复已通过受约束工具流程生成。模型状态：{model_usage.status}。",
        parameters={
            "session_id": session_id,
            "tool_calls": [tool.name for tool in tool_calls],
            "model_usage": model_usage.model_dump(mode="json"),
        },
        policy=policy,
    )
    return AgentChatResponse(
        session_id=session_id,
        message=AgentMessage(role="assistant", content=final_reply, created_at=now()),
        used_data=used_data,
        tool_calls=tool_calls,
        needs_confirmation=needs_confirmation,
        model_usage=model_usage,
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
