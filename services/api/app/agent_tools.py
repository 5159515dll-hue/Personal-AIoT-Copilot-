from __future__ import annotations

from datetime import timedelta
from typing import Literal
from uuid import uuid4

from app.agent_history import record_agent_conversation, redact_sensitive_text, redact_tool_call
from app.audit import list_audit_logs, record_audit
from app.database import latest_sensor_readings_db, query_sensor_history_db
from app.device_adapter import execute_mock_control, get_mock_device, list_mock_devices
from app.device_rate_limit import assess_device_control_rate_limit, record_device_control_execution
from app.mock_data import current_room_state, query_history, summarize_metric
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
from app.sensor_health import evaluate_sensor_health
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
            parameters={"message": redact_sensitive_text(message)},
            policy=policy,
        )
        tool_calls.append(
            ToolCall(
                name="policy_check",
                parameters={"message": redact_sensitive_text(message)},
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

    if _mentions_audit_log(lowered):
        return await _audit_log_response(
            session_id=session_id,
            message=message,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_device_docs(lowered):
        return await _device_docs_response(
            session_id=session_id,
            message=message,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_device_status(lowered):
        return await _device_status_response(
            session_id=session_id,
            message=message,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_anomaly(lowered):
        return await _anomaly_response(
            session_id=session_id,
            message=message,
            data_source=data_source,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
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
        if control.result.get("execution_result") == "success":
            reply = "模拟桌面台灯已通过策略检查链路开启，该动作已写入审计日志。"
        else:
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

    if _mentions_daily_summary(lowered):
        return await _daily_summary_response(
            session_id=session_id,
            message=message,
            data_source=data_source,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_environment_explanation(lowered):
        return await _environment_explanation_response(
            session_id=session_id,
            message=message,
            data_source=data_source,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_action_recommendation(lowered):
        return await _action_recommendation_response(
            session_id=session_id,
            message=message,
            data_source=data_source,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
        )

    if _mentions_rule(lowered):
        if _mentions_rest_time_rule(lowered):
            rule_draft = AutomationRuleCreate(
                condition="晚上 11 点后",
                action="发送休息提醒",
                enabled=True,
                confirmed=False,
            )
            reply = (
                "我起草了一条休息提醒规则：如果当前时间在晚上 11 点后，"
                "那么发送休息提醒。在你确认之前，我不会保存这条规则。"
            )
        else:
            rule_draft = AutomationRuleCreate(
                condition="二氧化碳 > 1200 ppm 持续 15 分钟且房间有人",
                action="发送通风提醒",
                enabled=True,
                confirmed=False,
            )
            reply = (
                "我起草了一条提醒规则：如果二氧化碳在房间有人时持续 15 分钟高于 1200 ppm，"
                "那么发送通风提醒。在你确认之前，我不会保存这条规则。"
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

    if _mentions_weekly_summary(lowered):
        return await _weekly_summary_response(
            session_id=session_id,
            message=message,
            data_source=data_source,
            used_data=used_data,
            tool_calls=tool_calls,
            needs_confirmation=needs_confirmation,
            policy=policy,
            rule_draft=rule_draft,
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


async def _audit_log_response(
    *,
    session_id: str,
    message: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    logs = list_audit_logs(limit=8)
    summaries = [_audit_log_summary(log) for log in logs]
    used_data.append("audit_logs_recent")
    tool_calls.append(
        ToolCall(
            name="get_audit_log",
            parameters={"limit": 8, "redacted_parameters": True},
            result={"count": len(summaries), "logs": summaries},
            created_at=now(),
        )
    )

    if not logs:
        reply = "当前还没有审计日志。执行一次智能体查询、设备控制或规则确认后，这里会出现可追溯记录。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    action_counts: dict[str, int] = {}
    attention_count = 0
    for log in logs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
        if log.result in {"blocked", "requires_confirmation", "failed"} or log.policy_result == PolicyResult.denied:
            attention_count += 1
    action_summary = "，".join(f"{action} {count} 条" for action, count in action_counts.items())
    latest = logs[0]
    reply = (
        f"最近 {len(logs)} 条审计日志中，最新记录是 {latest.actor} 发起的 {latest.action}，结果为 {latest.result}。"
        f"动作分布：{action_summary}。"
    )
    if attention_count:
        reply += f"其中 {attention_count} 条需要重点关注，包含拒绝、确认或失败结果。"
    else:
        reply += "最近记录没有发现失败或被策略拒绝的动作。"
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _device_docs_response(
    *,
    session_id: str,
    message: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    matches = _search_device_docs(message)
    used_data.append("local_device_docs")
    tool_calls.append(
        ToolCall(
            name="search_device_docs",
            parameters={"query": message, "sources": ["docs/device-protocol.md", "firmware/esp32-room-node/README.md"]},
            result={"count": len(matches), "matches": matches},
            created_at=now(),
        )
    )
    if not matches:
        reply = "本地设备文档里没有找到直接匹配的条目。当前可查询 MQTT topic、payload 指标、HTTP 入站、入库语义、固件边界和安全边界。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    first = matches[0]
    reply = (
        f"我查到了本地设备文档：{first['source']} 的「{first['title']}」。"
        f"{first['summary']} 这个查询只读取项目内协议和固件说明，不会访问外部网页或执行设备命令。"
    )
    if len(matches) > 1:
        reply += f"另外还有 {len(matches) - 1} 条相关边界说明可在工具调用结果里查看。"
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _device_status_response(
    *,
    session_id: str,
    message: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    devices = list_mock_devices()
    room = current_room_state()
    presence_reading = room.metrics.get(Metric.presence)
    presence = bool(getattr(presence_reading, "value", 0))
    powered_on = [_device_status_summary(device) for device in devices if _device_power(device) == "on"]
    offline_devices = [_device_status_summary(device) for device in devices if device.online_state.value == "offline"]
    controllable_on = [device for device in powered_on if device["controllable"]]
    read_only_on = [device for device in powered_on if not device["controllable"]]
    away_context = _mentions_away_context(message.lower()) or not presence
    attention: list[str] = []
    if away_context and controllable_on:
        names = "、".join(str(device["name"]) for device in controllable_on)
        attention.append(f"离开场景下仍有可控低/中风险设备处于开启状态：{names}。")
    if read_only_on:
        names = "、".join(str(device["name"]) for device in read_only_on)
        attention.append(f"有只读或不可控设备显示为开启状态，仅作为状态提示：{names}。")
    if offline_devices:
        names = "、".join(str(device["name"]) for device in offline_devices)
        attention.append(f"有设备离线，需要先恢复上报再判断状态：{names}。")

    result = {
        "source": "mock_device_adapter",
        "status": "ok",
        "presence_detected": presence,
        "away_context": away_context,
        "device_count": len(devices),
        "powered_on_count": len(powered_on),
        "offline_count": len(offline_devices),
        "devices": [_device_status_summary(device) for device in devices],
        "powered_on_devices": powered_on,
        "offline_devices": offline_devices,
        "attention": attention,
        "safety_boundary": "该工具只读取设备状态和风险元数据，不会自动关闭设备；控制动作必须另走 control_device 策略链路。",
    }
    used_data.extend(["mock_device_states", "current_room_presence"])
    tool_calls.append(
        ToolCall(
            name="get_device_status",
            parameters={"source": "mock", "scope": "powered_on_and_presence"},
            result=result,
            created_at=now(),
        )
    )

    if powered_on:
        names = "、".join(str(device["name"]) for device in powered_on)
        if away_context:
            reply = f"当前检测到 {len(powered_on)} 个设备仍处于开启状态：{names}。"
        else:
            reply = f"当前有 {len(powered_on)} 个设备处于开启状态：{names}。"
    else:
        reply = "当前没有检测到处于开启状态的设备。"
    if attention:
        reply += f"{attention[0]}"
    reply += "我只做状态分析，不会自动关闭任何设备；如需控制，必须经过设备风险策略和审计记录。"
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _anomaly_response(
    *,
    session_id: str,
    message: str,
    data_source: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(hours=24)
    if data_source == "database":
        used_data.extend(["database_latest_sensor_readings", "database_co2_24h_history", "sensor_health", "anomaly_rules"])
        try:
            latest = latest_sensor_readings_db()
            sensor_health = evaluate_sensor_health(latest, source="database")
            co2_readings = query_sensor_history_db(Metric.co2, start_ts, end_ts, bucket="15m")
        except Exception as exc:
            error_text = _database_error_text(exc)
            tool_calls.append(
                ToolCall(
                    name="detect_anomaly",
                    parameters={"source": "database", "window": "last_24_hours"},
                    result={"source": "database", "status": "unavailable", "error": error_text},
                    created_at=now(),
                )
            )
            reply = f"数据库异常检测暂不可用：{error_text}。可以切回模拟数据，或先检查 DATABASE_URL、MQTT 入站和 TimescaleDB。"
            return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)
        result = _detect_anomalies(latest, co2_readings, source="database", sensor_health=sensor_health)
    else:
        room = current_room_state()
        co2_readings = query_history(Metric.co2, start_ts, end_ts, "15m")
        latest = room.metrics
        sensor_health = evaluate_sensor_health(latest, source="mock")
        used_data.extend(["current_room_state", "co2_24h_history", "sensor_health", "anomaly_rules"])
        result = _detect_anomalies(latest, co2_readings, source="mock", room_anomalies=room.anomalies, sensor_health=sensor_health)

    tool_calls.append(
        ToolCall(
            name="detect_anomaly",
            parameters={"source": data_source, "window": "last_24_hours", "rules": ["co2_high", "temperature_range", "humidity_range", "noise_high", "sensor_health"]},
            result=result,
            created_at=now(),
        )
    )
    if result["anomalies"]:
        severe = [item for item in result["anomalies"] if item["severity"] in {"high", "medium"}]
        unhealthy = [item for item in result.get("sensor_health", []) if item.get("status") != "ok"]
        sensor_text = f"另有 {len(unhealthy)} 个传感器健康项需要检查。" if unhealthy else "传感器健康状态正常。"
        reply = (
            f"最近 24 小时检测到 {len(result['anomalies'])} 类异常或风险信号，"
            f"其中 {len(severe)} 类需要重点关注。最高二氧化碳为 {result['co2_peak']} ppm，"
            f"超过 1200 ppm 的样本数为 {result['co2_high_samples']}。{sensor_text}建议优先通风，并检查传感器在线状态。"
        )
    else:
        reply = (
            f"最近 24 小时未检测到明显异常。最高二氧化碳为 {result['co2_peak']} ppm，"
            "温湿度也在当前规则的舒适范围内。"
        )
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _daily_summary_response(
    *,
    session_id: str,
    message: str,
    data_source: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(hours=24)
    used_data.append(f"{data_source}_daily_environment_24h")
    try:
        histories = _query_metric_histories(
            data_source,
            start_ts,
            end_ts,
            "1h",
            [Metric.co2, Metric.temperature, Metric.humidity, Metric.light, Metric.presence, Metric.noise],
        )
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="summarize_daily_environment",
                parameters={"source": data_source, "window": "last_24_hours", "bucket": "1h"},
                result={"source": data_source, "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"每日环境总结暂不可用：{error_text}。可以切回模拟数据，或先检查数据库和 MQTT 入站链路。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    metrics = {metric.value: _metric_summary(readings) for metric, readings in histories.items()}
    co2 = metrics.get(Metric.co2.value, {})
    result = {
        "source": data_source,
        "status": "ok" if any(summary["samples"] for summary in metrics.values()) else "empty",
        "window": "last_24_hours",
        "bucket": "1h",
        "metrics": metrics,
        "worst_air_time": co2.get("max_at"),
        "interpretation": _daily_interpretation(metrics),
    }
    tool_calls.append(
        ToolCall(
            name="summarize_daily_environment",
            parameters={"source": data_source, "window": "last_24_hours", "bucket": "1h"},
            result=result,
            created_at=now(),
        )
    )
    if result["status"] == "empty":
        reply = "最近 24 小时没有可总结的环境样本。请确认传感器数据已经产生，或切回模拟数据继续演示。"
    else:
        reply = (
            f"最近 24 小时环境总结：二氧化碳平均 {co2.get('avg', 0)} ppm，"
            f"峰值 {co2.get('max', 0)} ppm，最差空气时间约为 {_time_label(co2.get('max_at'))}。"
            f"{result['interpretation']}"
        )
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _weekly_summary_response(
    *,
    session_id: str,
    message: str,
    data_source: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(days=7)
    used_data.append(f"{data_source}_weekly_environment_7d")
    try:
        histories = _query_metric_histories(
            data_source,
            start_ts,
            end_ts,
            "1h",
            [Metric.co2, Metric.temperature, Metric.humidity, Metric.light, Metric.presence, Metric.noise],
        )
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="summarize_weekly_environment",
                parameters={"source": data_source, "window": "last_7_days", "bucket": "1h"},
                result={"source": data_source, "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"一周环境总结暂不可用：{error_text}。可以切回模拟数据，或先检查数据库和 MQTT 入站链路。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    metrics = {metric.value: _metric_summary(readings) for metric, readings in histories.items()}
    result = {
        "source": data_source,
        "status": "ok" if any(summary["samples"] for summary in metrics.values()) else "empty",
        "window": "last_7_days",
        "bucket": "1h",
        "metrics": metrics,
        "relationship": _weekly_relationship(histories),
        "uncertainty": "当前只用人体存在作为学习或停留状态的弱代理，不能证明真实学习效率、睡眠、饮食或心理压力。",
    }
    tool_calls.append(
        ToolCall(
            name="summarize_weekly_environment",
            parameters={"source": data_source, "window": "last_7_days", "bucket": "1h"},
            result=result,
            created_at=now(),
        )
    )

    if result["status"] == "empty":
        reply = "最近 7 天没有可总结的环境样本。请确认传感器数据已经产生，或切回模拟数据继续演示。"
    else:
        co2 = metrics.get(Metric.co2.value, {})
        temperature = metrics.get(Metric.temperature.value, {})
        humidity = metrics.get(Metric.humidity.value, {})
        noise = metrics.get(Metric.noise.value, {})
        relationship = result["relationship"]
        reply = (
            f"最近 7 天环境总结：二氧化碳平均 {co2.get('avg', 0)} ppm，峰值 {co2.get('max', 0)} ppm；"
            f"温度范围 {temperature.get('min', 0)}-{temperature.get('max', 0)}℃，"
            f"湿度范围 {humidity.get('min', 0)}-{humidity.get('max', 0)}%，"
            f"噪声峰值 {noise.get('max', 0)} dB。"
            f"有人状态覆盖约 {relationship['presence_active_ratio']}% 的小时样本，"
            f"有人时 CO2 均值约 {relationship['co2_avg_when_present']} ppm。"
            f"不确定性：{result['uncertainty']}"
        )
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _environment_explanation_response(
    *,
    session_id: str,
    message: str,
    data_source: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    end_ts = now()
    start_ts = end_ts - timedelta(hours=24)
    used_data.extend([f"{data_source}_co2_24h_history", "environment_issue_rules"])
    try:
        histories = _query_metric_histories(
            data_source,
            start_ts,
            end_ts,
            "15m",
            [Metric.co2, Metric.temperature, Metric.humidity, Metric.presence, Metric.noise],
        )
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="explain_environment_issue",
                parameters={"source": data_source, "issue": "environment_discomfort", "window": "last_24_hours"},
                result={"source": data_source, "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"环境问题解释暂不可用：{error_text}。我不会在缺少数据时假装确定原因。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    explanation = _explain_environment_issue(histories, data_source)
    tool_calls.append(
        ToolCall(
            name="explain_environment_issue",
            parameters={"source": data_source, "issue": explanation["issue"], "window": "last_24_hours"},
            result=explanation,
            created_at=now(),
        )
    )
    reply = (
        f"初步解释：{explanation['summary']}"
        f"主要证据是 {explanation['evidence_summary']}。"
        f"不确定性：{explanation['uncertainty']}"
    )
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


async def _action_recommendation_response(
    *,
    session_id: str,
    message: str,
    data_source: str,
    used_data: list[str],
    tool_calls: list[ToolCall],
    needs_confirmation: bool,
    policy: PolicyDecision | None,
    rule_draft: AutomationRuleCreate | None,
) -> AgentChatResponse:
    used_data.append(f"{data_source}_current_room_state")
    try:
        if data_source == "database":
            metrics = latest_sensor_readings_db()
            room_payload = {"source": "database", "metrics": {metric.value: reading.model_dump(mode="json") for metric, reading in metrics.items()}}
        else:
            room = current_room_state()
            metrics = room.metrics
            room_payload = room.model_dump(mode="json")
    except Exception as exc:
        error_text = _database_error_text(exc)
        tool_calls.append(
            ToolCall(
                name="recommend_action",
                parameters={"source": data_source, "scope": "safe_environment_actions"},
                result={"source": data_source, "status": "unavailable", "error": error_text},
                created_at=now(),
            )
        )
        reply = f"行动建议暂不可用：{error_text}。在缺少可靠数据时，我不会建议任何自动控制动作。"
        return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)

    recommendation = _recommend_safe_actions(metrics)
    result = {
        "source": data_source,
        "status": "ok",
        "room_state": room_payload,
        "actions": recommendation["actions"],
        "safety_boundary": recommendation["safety_boundary"],
        "not_allowed": recommendation["not_allowed"],
    }
    tool_calls.append(
        ToolCall(
            name="recommend_action",
            parameters={"source": data_source, "scope": "safe_environment_actions"},
            result=result,
            created_at=now(),
        )
    )
    first_action = recommendation["actions"][0]["title"] if recommendation["actions"] else "继续观察"
    reply = (
        f"建议优先执行：{first_action}。"
        f"这些建议只属于提醒或低风险人工动作，不会直接控制窗户、空调、未知插座或报警器。"
        f"安全边界：{recommendation['safety_boundary']}"
    )
    return await _response(session_id, message, reply, used_data, tool_calls, needs_confirmation, policy, rule_draft)


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


def _control_tool(device_id: str, state: str, confirmed: bool, intent: str) -> ToolCall:
    device = get_mock_device(device_id)
    policy = assess_device_control(
        device=device,
        requested_state=state,
        confirmed=confirmed,
        intent=intent,
    )
    if policy.result == PolicyResult.allowed:
        policy = assess_device_control_rate_limit(device) or policy
    execution_result = "success" if policy.result == PolicyResult.allowed else "blocked"
    controlled_device = None
    if device and policy.result == PolicyResult.allowed and state in {"on", "off"}:
        controlled_device = execute_mock_control(device, state)
        record_device_control_execution(device.id, "agent")
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
        result={
            "execution_result": execution_result,
            "audit_log_id": audit.id,
            "device": controlled_device.model_dump(mode="json") if controlled_device else None,
        },
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


def _query_metric_histories(
    source: str,
    start_ts,
    end_ts,
    bucket: str,
    metrics: list[Metric],
) -> dict[Metric, list]:
    histories: dict[Metric, list] = {}
    for metric in metrics:
        if source == "database":
            histories[metric] = query_sensor_history_db(metric, start_ts, end_ts, bucket=bucket)
        else:
            histories[metric] = query_history(metric, start_ts, end_ts, bucket)
    return histories


def _metric_summary(readings: list) -> dict[str, float | int | str | None]:
    if not readings:
        return {"status": "empty", "min": 0, "max": 0, "avg": 0, "samples": 0, "max_at": None}
    values = [reading.value for reading in readings]
    peak = max(readings, key=lambda reading: reading.value)
    return {
        "status": "ok",
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 1),
        "samples": len(values),
        "max_at": peak.timestamp.isoformat(),
    }


def _weekly_relationship(histories: dict[Metric, list]) -> dict[str, float | int]:
    presence_readings = histories.get(Metric.presence, [])
    co2_readings = histories.get(Metric.co2, [])
    presence_by_hour = {reading.timestamp.replace(minute=0, second=0, microsecond=0): reading.value for reading in presence_readings}
    present_co2_values = [
        reading.value
        for reading in co2_readings
        if presence_by_hour.get(reading.timestamp.replace(minute=0, second=0, microsecond=0), 0) >= 0.5
    ]
    absent_co2_values = [
        reading.value
        for reading in co2_readings
        if presence_by_hour.get(reading.timestamp.replace(minute=0, second=0, microsecond=0), 0) < 0.5
    ]
    active_hours = sum(1 for reading in presence_readings if reading.value >= 0.5)
    total_hours = len(presence_readings)
    return {
        "presence_active_hours": active_hours,
        "presence_total_hours": total_hours,
        "presence_active_ratio": round(active_hours / total_hours * 100, 1) if total_hours else 0,
        "co2_avg_when_present": _avg(present_co2_values),
        "co2_avg_when_absent": _avg(absent_co2_values),
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0


def _daily_interpretation(metrics: dict[str, dict]) -> str:
    co2 = metrics.get(Metric.co2.value, {})
    temperature = metrics.get(Metric.temperature.value, {})
    humidity = metrics.get(Metric.humidity.value, {})
    noise = metrics.get(Metric.noise.value, {})
    notes: list[str] = []
    if co2.get("max", 0) > 1200:
        notes.append("空气最差时段已经超过 1200 ppm 专注阈值，适合加入通风提醒。")
    elif co2.get("max", 0) > 900:
        notes.append("二氧化碳有上升趋势，但仍处于可通过定时通风管理的范围。")
    else:
        notes.append("二氧化碳整体保持在舒适范围。")
    if temperature.get("max", 0) > 28:
        notes.append("温度峰值偏高，可能影响长时间学习。")
    if humidity.get("min", 50) < 35 or humidity.get("max", 50) > 65:
        notes.append("湿度曾离开 35%-65% 舒适区间。")
    if noise.get("max", 0) > 65:
        notes.append("噪声峰值超过 65 dB，可能影响专注学习。")
    return "".join(notes)


def _time_label(value: object) -> str:
    if not isinstance(value, str):
        return "未知"
    try:
        return value[11:16]
    except Exception:
        return "未知"


def _explain_environment_issue(histories: dict[Metric, list], source: str) -> dict:
    co2_readings = histories.get(Metric.co2, [])
    temp_readings = histories.get(Metric.temperature, [])
    humidity_readings = histories.get(Metric.humidity, [])
    noise_readings = histories.get(Metric.noise, [])
    co2_summary = _metric_summary(co2_readings)
    co2_values = [reading.value for reading in co2_readings]
    high_samples = sum(1 for value in co2_values if value > 1200)
    afternoon_values = [reading.value for reading in co2_readings if 14 <= reading.timestamp.hour < 17]
    afternoon_avg = round(sum(afternoon_values) / len(afternoon_values), 1) if afternoon_values else 0
    overall_avg = co2_summary.get("avg", 0) if isinstance(co2_summary.get("avg"), (int, float)) else 0

    likely_causes: list[str] = []
    if afternoon_values and afternoon_avg > float(overall_avg) + 120:
        likely_causes.append("下午 CO2 均值明显高于全天均值，常见原因是有人停留叠加通风不足。")
    if high_samples:
        likely_causes.append("最近 24 小时存在 CO2 超过 1200 ppm 的样本，可能带来困倦和专注下降。")
    if temp_readings and max(reading.value for reading in temp_readings) > 28:
        likely_causes.append("温度峰值偏高，会放大闷热和疲劳感。")
    if humidity_readings and (min(reading.value for reading in humidity_readings) < 35 or max(reading.value for reading in humidity_readings) > 65):
        likely_causes.append("湿度离开舒适区间，可能造成体感不适。")
    if noise_readings and max(reading.value for reading in noise_readings) > 65:
        likely_causes.append("噪声峰值超过 65 dB，可能干扰专注和休息。")
    if not likely_causes:
        likely_causes.append("当前环境数据没有显示强异常，更可能是作息、饮水或学习节奏等非传感器因素。")

    return {
        "source": source,
        "status": "ok",
        "issue": "afternoon_sleepiness_or_air_quality",
        "summary": likely_causes[0],
        "likely_causes": likely_causes,
        "evidence": {
            "co2_avg": overall_avg,
            "co2_peak": co2_summary.get("max", 0),
            "co2_peak_at": co2_summary.get("max_at"),
            "co2_high_samples": high_samples,
            "afternoon_co2_avg": afternoon_avg,
            "samples": co2_summary.get("samples", 0),
            "noise_peak": max((reading.value for reading in noise_readings), default=0),
        },
        "evidence_summary": f"CO2 平均 {overall_avg} ppm，峰值 {co2_summary.get('max', 0)} ppm，超标样本 {high_samples} 个",
        "uncertainty": "当前只使用环境传感器数据，不能判断睡眠、饮食、运动或心理压力等个人因素。",
    }


def _recommend_safe_actions(metrics: dict[Metric, object]) -> dict:
    co2 = _metric_value(metrics.get(Metric.co2))
    temperature = _metric_value(metrics.get(Metric.temperature))
    humidity = _metric_value(metrics.get(Metric.humidity))
    light = _metric_value(metrics.get(Metric.light))
    noise = _metric_value(metrics.get(Metric.noise))
    actions: list[dict[str, object]] = []
    if co2 is None:
        actions.append({"title": "先检查 CO2 传感器上报", "reason": "缺少空气质量核心指标。", "risk_level": "read_only"})
    elif co2 > 1200:
        actions.append({"title": "立即开窗或短时通风 10 分钟", "reason": "CO2 已超过 1200 ppm 专注阈值。", "risk_level": "low"})
    elif co2 > 900:
        actions.append({"title": "未来 20 分钟内安排一次通风", "reason": "空气质量正在变差。", "risk_level": "low"})
    else:
        actions.append({"title": "保持当前通风节奏", "reason": "CO2 当前处于可接受范围。", "risk_level": "read_only"})

    if temperature is not None and temperature > 28:
        actions.append({"title": "降低室温或减少热源", "reason": "温度偏高会影响长时间专注。", "risk_level": "low"})
    if humidity is not None and (humidity < 35 or humidity > 65):
        actions.append({"title": "调整加湿或除湿策略", "reason": "湿度不在 35%-65% 舒适区间。", "risk_level": "low"})
    if light is not None and light < 250:
        actions.append({"title": "补充桌面照明", "reason": "光照偏低可能影响阅读和专注。", "risk_level": "low"})
    if noise is not None and noise > 65:
        actions.append({"title": "降低环境噪声或切换到安静模式", "reason": "噪声超过 65 dB，可能影响专注。", "risk_level": "low"})

    return {
        "actions": actions[:4],
        "safety_boundary": "只给出建议和提醒；不会直接控制窗户、空调、未知插座、报警器或其他高风险设备。",
        "not_allowed": ["未知负载智能插座", "烟雾报警器", "门锁", "燃气或强电设备"],
    }


def _metric_value(reading: object | None) -> float | None:
    value = getattr(reading, "value", None)
    return float(value) if isinstance(value, (int, float)) else None


def _device_power(device) -> str | None:
    power = device.current_state.get("power")
    return str(power) if power is not None else None


def _device_status_summary(device) -> dict[str, object]:
    return {
        "id": device.id,
        "name": device.name,
        "type": device.type,
        "location": device.location,
        "risk_level": device.risk_level.value,
        "controllable": device.controllable,
        "requires_confirmation": device.requires_confirmation,
        "online_state": device.online_state.value,
        "power": _device_power(device),
        "connected_appliance": device.connected_appliance,
    }


def _clean_error_text(exc: Exception) -> str:
    return str(exc).strip().rstrip("。.")


def _database_error_text(exc: Exception) -> str:
    if isinstance(exc, RuntimeError):
        return _clean_error_text(exc)
    return "数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态"


def _audit_log_summary(log) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat(),
        "actor": log.actor,
        "action": log.action,
        "result": log.result,
        "policy_result": log.policy_result.value if log.policy_result else None,
        "risk_level": log.risk_level.value if log.risk_level else None,
        "details": log.details,
    }


DEVICE_DOC_ENTRIES = [
    {
        "title": "MQTT Topic",
        "source": "docs/device-protocol.md",
        "keywords": ("mqtt", "topic", "主题", "上报", "telemetry"),
        "summary": "默认订阅 aiot/room/+/telemetry；入站服务从 payload 的 device_id 识别设备，不从 topic 反推设备身份。",
    },
    {
        "title": "遥测指标",
        "source": "docs/device-protocol.md",
        "keywords": ("metric", "指标", "temperature", "humidity", "co2", "light", "presence", "noise", "噪声", "分贝", "单位"),
        "summary": "支持 temperature、humidity、co2、light、presence、noise；noise 只上报 dB 数值，不采集原始音频，quality 只允许 ok、stale、anomaly。",
    },
    {
        "title": "Batch Payload",
        "source": "docs/device-protocol.md",
        "keywords": ("payload", "json", "batch", "格式", "readings", "消息"),
        "summary": "推荐 batch 格式一次上报多个 readings；单条 reading 可继承顶层 timestamp，缺失时间时使用入站时间。",
    },
    {
        "title": "HTTP 入站",
        "source": "docs/device-protocol.md",
        "keywords": ("http", "ingest", "入站", "sensor-readings", "接口"),
        "summary": "HTTP 调试接口是 POST /api/ingest/sensor-readings，生产环境应放在私有 API 保护或内部令牌之后。",
    },
    {
        "title": "入库语义",
        "source": "docs/device-protocol.md",
        "keywords": ("postgresql", "timescale", "入库", "hypertable", "sensor_readings", "database"),
        "summary": "入站服务初始化 sensor_readings 表；TimescaleDB 可用时会尝试创建 hypertable，并记录 time、received_at、metric、value、quality、source。",
    },
    {
        "title": "安全边界",
        "source": "docs/device-protocol.md",
        "keywords": ("安全", "控制", "边界", "摄像头", "麦克风", "权限", "未知字段"),
        "summary": "MQTT/HTTP payload 只能写入遥测，不能创建规则、控制设备或提升权限；设备控制必须走策略引擎和审计日志。",
    },
    {
        "title": "ESP32 固件边界",
        "source": "firmware/esp32-room-node/README.md",
        "keywords": ("esp32", "固件", "platformio", "wifi", "config", "传感器"),
        "summary": "ESP32 固件骨架只发布遥测，不订阅控制 topic；Wi-Fi 和 MQTT 密钥只放在本地 include/config.h，不提交到 Git。",
    },
    {
        "title": "传感器替换点",
        "source": "firmware/esp32-room-node/README.md",
        "keywords": ("替换", "驱动", "readtemperature", "readhumidity", "readco2", "readlight", "readpresence", "readnoise"),
        "summary": "真实硬件接入时替换 readTemperatureC、readHumidityPct、readCo2Ppm、readLightLux、readPresence、readNoiseDbA；MQTT topic 和 JSON 字段保持不变。",
    },
]


def _search_device_docs(query: str) -> list[dict[str, str]]:
    lowered = query.lower()
    scored: list[tuple[int, dict[str, str]]] = []
    for entry in DEVICE_DOC_ENTRIES:
        score = sum(1 for keyword in entry["keywords"] if keyword in lowered)
        if score:
            scored.append((score, {key: str(entry[key]) for key in ("title", "source", "summary")}))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in scored[:4]]


def _detect_anomalies(
    latest: dict[Metric, object],
    co2_readings: list,
    *,
    source: str,
    room_anomalies: list[str] | None = None,
    sensor_health: list | None = None,
) -> dict:
    anomalies: list[dict[str, object]] = []
    missing = [metric.value for metric in Metric if metric not in latest]
    if missing:
        anomalies.append(
            {
                "type": "missing_metric",
                "severity": "medium",
                "metric": ",".join(missing),
                "reason": "当前状态缺少部分传感器指标，Agent 不能对这些维度做确定判断。",
            }
        )

    co2_values = [reading.value for reading in co2_readings]
    co2_peak = max(co2_values) if co2_values else 0
    co2_avg = round(sum(co2_values) / len(co2_values), 1) if co2_values else 0
    co2_high_samples = sum(1 for value in co2_values if value > 1200)
    if co2_high_samples:
        anomalies.append(
            {
                "type": "co2_high",
                "severity": "high" if co2_peak >= 1500 else "medium",
                "metric": "co2",
                "threshold": 1200,
                "observed_peak": co2_peak,
                "samples": co2_high_samples,
                "reason": "二氧化碳存在超过专注阈值的时间窗口。",
            }
        )

    temperature = latest.get(Metric.temperature)
    if temperature and getattr(temperature, "value", 0) > 28:
        anomalies.append(
            {
                "type": "temperature_high",
                "severity": "medium",
                "metric": "temperature",
                "threshold": 28,
                "observed": getattr(temperature, "value", None),
                "reason": "当前温度偏高，可能影响长时间专注。",
            }
        )

    humidity = latest.get(Metric.humidity)
    if humidity and (getattr(humidity, "value", 50) < 35 or getattr(humidity, "value", 50) > 65):
        anomalies.append(
            {
                "type": "humidity_out_of_range",
                "severity": "medium",
                "metric": "humidity",
                "range": "35-65",
                "observed": getattr(humidity, "value", None),
                "reason": "当前湿度不在舒适区间。",
            }
        )

    noise = latest.get(Metric.noise)
    if noise and getattr(noise, "value", 0) > 65:
        anomalies.append(
            {
                "type": "noise_high",
                "severity": "medium",
                "metric": "noise",
                "threshold": 65,
                "observed": getattr(noise, "value", None),
                "reason": "当前噪声等级偏高，可能影响专注或休息。",
            }
        )

    for text in room_anomalies or []:
        if all(item.get("reason") != text for item in anomalies):
            anomalies.append({"type": "room_state", "severity": "medium", "metric": "room", "reason": text})

    health_payload = [item.model_dump(mode="json") for item in sensor_health or []]
    for health in health_payload:
        status = health.get("status")
        if status == "ok":
            continue
        severity = "high" if status == "offline" else "medium"
        anomalies.append(
            {
                "type": "sensor_health",
                "severity": severity,
                "metric": health.get("metric"),
                "status": status,
                "reason": health.get("message", "传感器健康状态异常。"),
            }
        )

    return {
        "source": source,
        "status": "anomaly" if anomalies else "ok",
        "window": "last_24_hours",
        "co2_peak": co2_peak,
        "co2_avg": co2_avg,
        "co2_high_samples": co2_high_samples,
        "samples": len(co2_values),
        "sensor_health": health_payload,
        "anomalies": anomalies,
    }


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
        user_message=redact_sensitive_text(user_message),
        fallback_reply=reply,
        used_data=used_data,
        tool_calls=[redact_tool_call(tool) for tool in tool_calls],
        needs_confirmation=needs_confirmation,
        policy=policy,
        rule_draft=rule_draft,
        allow_model=allow_model,
    )
    safe_tool_calls = [redact_tool_call(tool) for tool in tool_calls]
    safe_reply = redact_sensitive_text(final_reply)
    record_audit(
        actor="agent",
        action="agent_chat",
        result="success",
        details=f"智能体回复已通过受约束工具流程生成。模型状态：{model_usage.status}。",
        parameters={
            "session_id": session_id,
            "tool_calls": [tool.name for tool in safe_tool_calls],
            "model_usage": model_usage.model_dump(mode="json"),
        },
        policy=policy,
    )
    response = AgentChatResponse(
        session_id=session_id,
        message=AgentMessage(role="assistant", content=safe_reply, created_at=now()),
        used_data=used_data,
        tool_calls=safe_tool_calls,
        needs_confirmation=needs_confirmation,
        model_usage=model_usage,
        policy=policy,
        rule_draft=rule_draft,
    )
    record_agent_conversation(
        session_id=session_id,
        data_source=_conversation_data_source(tool_calls),
        user_message=user_message,
        response=response,
    )
    return response


def _conversation_data_source(tool_calls: list[ToolCall]) -> Literal["mock", "database"]:
    for tool in tool_calls:
        source = tool.parameters.get("source")
        if source in {"mock", "database"}:
            return source
    return "mock"


def _mentions_co2_or_environment(text: str) -> bool:
    return any(token in text for token in ("co2", "二氧化碳", "空气", "环境", "temperature", "humidity", "noise", "噪声", "噪音", "分贝", "今天", "room"))


def _mentions_audit_log(text: str) -> bool:
    return any(token in text for token in ("audit", "audit log", "审计", "日志", "记录", "追溯"))


def _mentions_device_docs(text: str) -> bool:
    return any(
        token in text
        for token in (
            "文档",
            "协议",
            "payload",
            "topic",
            "mqtt",
            "http 入站",
            "设备说明",
            "固件",
            "esp32",
            "错误码",
        )
    )


def _mentions_device_status(text: str) -> bool:
    device_tokens = ("设备", "台灯", "灯", "风扇", "插座", "报警器", "device", "lamp", "fan", "plug")
    status_tokens = ("状态", "开着", "还开", "打开着", "关了", "离开", "在线", "离线", "哪些", "powered on", "left on")
    return any(token in text for token in device_tokens) and any(token in text for token in status_tokens)


def _mentions_away_context(text: str) -> bool:
    return any(token in text for token in ("离开", "不在房间", "走后", "出门", "away"))


def _mentions_anomaly(text: str) -> bool:
    return any(token in text for token in ("异常", "离线", "不可用", "告警", "异常检测", "anomaly", "abnormal", "传感器坏", "数据缺失"))


def _mentions_daily_summary(text: str) -> bool:
    return any(token in text for token in ("总结今天", "今日总结", "一天", "日总结", "空气最差", "什么时候房间空气最差", "daily summary"))


def _mentions_environment_explanation(text: str) -> bool:
    issue_tokens = ("困", "犯困", "下午", "co2 上升", "二氧化碳上升", "空气变差", "闷", "通风不足")
    context_tokens = ("环境", "空气", "co2", "二氧化碳", "温度", "湿度", "通风", "噪声", "噪音", "noise")
    return any(token in text for token in issue_tokens) or (
        any(token in text for token in ("为什么", "原因", "解释")) and any(token in text for token in context_tokens)
    )


def _mentions_action_recommendation(text: str) -> bool:
    return any(token in text for token in ("改善", "方案", "怎么做", "怎么办", "建议我", "行动建议", "recommend", "适合专注"))


def _mentions_weekly_summary(text: str) -> bool:
    return "7" in text or "week" in text or "一周" in text or "7 天" in text or "七天" in text


def _mentions_rule(text: str) -> bool:
    return any(token in text for token in ("rule", "automation", "提醒", "规则", "创建"))


def _mentions_rest_time_rule(text: str) -> bool:
    rest_tokens = ("休息", "睡觉", "睡眠", "rest", "sleep")
    time_tokens = ("晚上", "晚间", "夜间", "11", "23", "十一点", "23:00", "时间")
    return any(token in text for token in rest_tokens) and any(token in text for token in time_tokens)


def _mentions_lamp_control(text: str) -> bool:
    return ("lamp" in text and "on" in text) or "打开台灯" in text or "开灯" in text


def _mentions_forbidden_control(text: str) -> bool:
    action_tokens = ("打开", "关闭", "禁用", "控制", "turn on", "turn off", "disable", "control")
    target_tokens = (
        "unknown plug",
        "smart_plug",
        "all plugs",
        "smoke alarm",
        "alarm",
        "未知插座",
        "所有插座",
        "烟雾报警",
        "报警",
        "报警器",
    )
    return any(action in text for action in action_tokens) and any(target in text for target in target_tokens)
