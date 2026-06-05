from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.audit import list_audit_logs, record_audit
from app.database import latest_sensor_readings_db, query_sensor_history_db
from app.device_adapter import execute_mock_control, get_mock_device
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
        used_data.extend(["database_latest_sensor_readings", "database_co2_24h_history", "anomaly_rules"])
        try:
            latest = latest_sensor_readings_db()
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
        result = _detect_anomalies(latest, co2_readings, source="database")
    else:
        room = current_room_state()
        co2_readings = query_history(Metric.co2, start_ts, end_ts, "15m")
        latest = room.metrics
        used_data.extend(["current_room_state", "co2_24h_history", "anomaly_rules"])
        result = _detect_anomalies(latest, co2_readings, source="mock", room_anomalies=room.anomalies)

    tool_calls.append(
        ToolCall(
            name="detect_anomaly",
            parameters={"source": data_source, "window": "last_24_hours", "rules": ["co2_high", "temperature_range", "humidity_range", "missing_metric"]},
            result=result,
            created_at=now(),
        )
    )
    if result["anomalies"]:
        severe = [item for item in result["anomalies"] if item["severity"] in {"high", "medium"}]
        reply = (
            f"最近 24 小时检测到 {len(result['anomalies'])} 类异常或风险信号，"
            f"其中 {len(severe)} 类需要重点关注。最高二氧化碳为 {result['co2_peak']} ppm，"
            f"超过 1200 ppm 的样本数为 {result['co2_high_samples']}。建议优先通风，并检查传感器在线状态。"
        )
    else:
        reply = (
            f"最近 24 小时未检测到明显异常。最高二氧化碳为 {result['co2_peak']} ppm，"
            "温湿度也在当前规则的舒适范围内。"
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
    device = get_mock_device(device_id)
    policy = assess_device_control(
        device=device,
        requested_state=state,
        confirmed=confirmed,
        intent=intent,
    )
    execution_result = "success" if policy.result == PolicyResult.allowed else "blocked"
    controlled_device = None
    if device and policy.result == PolicyResult.allowed and state in {"on", "off"}:
        controlled_device = execute_mock_control(device, state)
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
        "keywords": ("metric", "指标", "temperature", "humidity", "co2", "light", "presence", "单位"),
        "summary": "支持 temperature、humidity、co2、light、presence，quality 只允许 ok、stale、anomaly。",
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
        "keywords": ("替换", "驱动", "readtemperature", "readhumidity", "readco2", "readlight", "readpresence"),
        "summary": "真实硬件接入时替换 readTemperatureC、readHumidityPct、readCo2Ppm、readLightLux、readPresence；MQTT topic 和 JSON 字段保持不变。",
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

    for text in room_anomalies or []:
        if all(item.get("reason") != text for item in anomalies):
            anomalies.append({"type": "room_state", "severity": "medium", "metric": "room", "reason": text})

    return {
        "source": source,
        "status": "anomaly" if anomalies else "ok",
        "window": "last_24_hours",
        "co2_peak": co2_peak,
        "co2_avg": co2_avg,
        "co2_high_samples": co2_high_samples,
        "samples": len(co2_values),
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


def _mentions_anomaly(text: str) -> bool:
    return any(token in text for token in ("异常", "离线", "不可用", "告警", "异常检测", "anomaly", "abnormal", "传感器坏", "数据缺失"))


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
