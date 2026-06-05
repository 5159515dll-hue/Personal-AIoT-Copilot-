#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
METRICS = {"temperature", "humidity", "co2", "light", "presence", "noise"}
ROOM_STATUSES = {"good", "watch", "poor"}
RISK_LEVELS = {"read_only", "low", "medium", "high", "forbidden"}
DEVICE_STATES = {"online", "offline", "unknown"}
POLICY_RESULTS = {"allowed", "requires_confirmation", "denied"}
MODEL_STATUSES = {"not_configured", "used", "fallback", "blocked"}


class ContractFailure(AssertionError):
    pass


def main() -> int:
    disable_proxy_env()
    parser = argparse.ArgumentParser(description="运行 Personal AIoT Copilot 核心 API 契约检查。")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("AIOT_INTERNAL_API_TOKEN") or read_internal_token())
    parser.add_argument("--timeout", type=float, default=float(os.getenv("API_CONTRACT_TIMEOUT", "45")))
    args = parser.parse_args()

    token = (args.token or "").strip()
    if not token:
        print("失败：缺少 AIOT_INTERNAL_API_TOKEN。请通过环境变量或 .dashboard-env 提供内部服务令牌。", file=sys.stderr)
        return 1

    client = ApiClient(args.api_base_url.rstrip("/"), token, timeout=args.timeout)
    print(f"开始核心 API 契约检查：API={client.base_url}")
    started = time.time()
    checks = [
        ("健康检查保持公开", lambda: check_health(client)),
        ("RoomState 当前状态契约", lambda: check_room_state(client)),
        ("SensorReading 历史曲线契约", lambda: check_sensor_history(client)),
        ("Device 设备清单契约", lambda: check_devices(client)),
        ("PolicyDecision 设备控制拒绝契约", lambda: check_control_policy_and_audit(client)),
        ("AutomationRule 创建和评估契约", lambda: check_rules(client)),
        ("AgentMessage 与 ToolCall 智能体契约", lambda: check_agent_chat(client)),
        ("模型厂商目录与密钥脱敏契约", lambda: check_model_provider_catalog(client)),
        ("AuditLog 审计筛选契约", lambda: check_audit_logs(client)),
    ]

    failures: list[str] = []
    for label, check in checks:
        try:
            check()
            print(f"通过：{label}")
        except Exception as exc:  # noqa: BLE001 - report all contract failures in one run.
            failures.append(f"{label}：{exc}")
            print(f"失败：{label}：{exc}", file=sys.stderr)

    elapsed = round(time.time() - started, 1)
    if failures:
        print(f"核心 API 契约检查失败：{len(failures)} 项未通过，用时 {elapsed} 秒。", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"核心 API 契约检查完成：{len(checks)} 项全部通过，用时 {elapsed} 秒。")
    return 0


def disable_proxy_env() -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(name, None)


def read_internal_token() -> str:
    env_file = ROOT_DIR / ".dashboard-env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        if stripped.startswith("AIOT_INTERNAL_API_TOKEN="):
            value = stripped.split("=", 1)[1].strip()
            return value.strip("\"'")
    return ""


class ApiClient:
    def __init__(self, base_url: str, token: str, *, timeout: float) -> None:
        self.base_url = base_url
        self.token = token
        self.timeout = timeout

    def get(self, path: str, *, auth: bool = True, expected_status: int = 200) -> Any:
        return self.request("GET", path, auth=auth, expected_status=expected_status)

    def post(self, path: str, body: dict[str, Any] | None = None, *, expected_status: int = 200) -> Any:
        return self.request("POST", path, body=body, expected_status=expected_status)

    def patch(self, path: str, body: dict[str, Any], *, expected_status: int = 200) -> Any:
        return self.request("PATCH", path, body=body, expected_status=expected_status)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        auth: bool = True,
        expected_status: int = 200,
    ) -> Any:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-AIoT-Internal-Token"] = self.token
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
                if response.status != expected_status:
                    raise ContractFailure(f"{method} {path} 期望 HTTP {expected_status}，实际 HTTP {response.status}：{text[:240]}")
                return json.loads(text) if text else None
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            if exc.code != expected_status:
                raise ContractFailure(f"{method} {path} 期望 HTTP {expected_status}，实际 HTTP {exc.code}：{text[:300]}") from exc
            try:
                return json.loads(text) if text else None
            except json.JSONDecodeError as decode_exc:
                raise ContractFailure(f"{method} {path} 错误响应不是 JSON：{text[:240]}") from decode_exc
        except urllib.error.URLError as exc:
            raise ContractFailure(f"无法访问 {method} {path}：{exc}") from exc


def check_health(client: ApiClient) -> None:
    payload = client.get("/api/health", auth=False)
    require_keys(payload, {"status", "service"}, "Health")
    assert_equal(payload["status"], "ok", "健康检查状态错误")


def check_room_state(client: ApiClient) -> None:
    payload = client.get("/api/room/current")
    assert_room_state(payload)


def check_sensor_history(client: ApiClient) -> None:
    history = client.get("/api/sensors/history?metric=co2&bucket=15m")
    assert_true(isinstance(history, list) and len(history) >= 24, "历史曲线必须至少覆盖 24 个点")
    for item in history[:5]:
        assert_sensor_reading(item)
        assert_equal(item["metric"], "co2", "历史曲线 metric 不一致")


def check_devices(client: ApiClient) -> None:
    devices = client.get("/api/devices")
    assert_true(isinstance(devices, list) and len(devices) >= 3, "设备清单数量不足")
    seen_risks: set[str] = set()
    for device in devices:
        assert_device(device)
        seen_risks.add(device["risk_level"])
    assert_true("low" in seen_risks, "设备清单缺少低风险可控设备")
    assert_true(bool(seen_risks & {"high", "forbidden"}), "设备清单缺少高风险边界设备")


def check_control_policy_and_audit(client: ApiClient) -> None:
    device_id = f"api_contract_unknown_{int(time.time())}"
    payload = client.post(
        f"/api/devices/{device_id}/control",
        {"state": "on", "confirmed": False, "reason": "API 契约检查：未知设备必须拒绝"},
        expected_status=404,
    )
    detail = payload.get("detail")
    assert_true(isinstance(detail, dict), "未知设备拒绝响应 detail 必须是对象")
    require_keys(detail, {"message", "policy", "audit_log_id"}, "ControlDeviceError")
    assert_policy_decision(detail["policy"])
    assert_equal(detail["policy"]["result"], "denied", "未知设备控制必须拒绝")
    assert_equal(detail["policy"]["risk_level"], "high", "未知设备风险等级必须为 high")
    assert_true(str(detail["audit_log_id"]).startswith("audit_"), "拒绝响应缺少审计编号")

    logs = client.get(
        f"/api/audit-logs?action=control_device&result=blocked&policy_result=denied&risk_level=high&q={urllib.parse.quote(device_id)}&limit=20"
    )
    assert_true(any(item.get("id") == detail["audit_log_id"] for item in logs), "审计筛选无法追溯未知设备拒绝记录")


def check_rules(client: ApiClient) -> None:
    before = client.get("/api/rules")
    assert_true(isinstance(before, list), "规则列表必须是数组")

    suffix = int(time.time())
    rule = client.post(
        "/api/rules",
        {
            "condition": f"二氧化碳 > 99999 ppm # api-contract-{suffix}",
            "action": "发送 API 契约检查提醒",
            "enabled": False,
            "confirmed": True,
        },
    )
    assert_automation_rule(rule)
    assert_true(rule["enabled"] is False, "契约检查创建的规则应保持暂停")

    evaluations = client.post("/api/rules/evaluate")
    assert_true(isinstance(evaluations, list), "规则评估响应必须是数组")
    matching = [item for item in evaluations if item.get("rule_id") == rule["id"]]
    assert_true(len(matching) == 1, "规则评估结果缺少刚创建的规则")
    assert_rule_evaluation(matching[0])
    assert_equal(matching[0]["status"], "disabled", "暂停规则评估状态必须为 disabled")

    patched = client.patch(f"/api/rules/{rule['id']}", {"enabled": False})
    assert_automation_rule(patched)


def check_agent_chat(client: ApiClient) -> None:
    payload = client.post(
        "/api/agent/chat",
        {
            "message": "今天二氧化碳情况怎么样？",
            "data_source": "mock",
            "session_id": f"api-contract-{int(time.time())}",
        },
    )
    require_keys(payload, {"session_id", "message", "used_data", "tool_calls", "needs_confirmation", "model_usage"}, "AgentChatResponse")
    assert_agent_message(payload["message"])
    assert_true(isinstance(payload["used_data"], list), "used_data 必须是数组")
    assert_true("current_room_state" in payload["used_data"], "环境问答必须声明 current_room_state 数据依据")
    assert_true(isinstance(payload["tool_calls"], list) and payload["tool_calls"], "tool_calls 不能为空")
    for tool in payload["tool_calls"]:
        assert_tool_call(tool)
    assert_true(any(tool["name"] == "get_current_room_state" for tool in payload["tool_calls"]), "环境问答缺少 get_current_room_state 工具")
    assert_model_usage(payload["model_usage"])


def check_model_provider_catalog(client: ApiClient) -> None:
    catalog = client.get("/api/model-providers")
    require_keys(catalog, {"providers", "active_config", "saved_configs"}, "ModelProviderCatalog")
    assert_true(isinstance(catalog["providers"], list) and len(catalog["providers"]) >= 2, "模型厂商目录至少应包含两个中国区厂商")
    provider_by_id = {provider.get("id"): provider for provider in catalog["providers"]}
    assert_true({"xiaomi_mimo", "kimi"}.issubset(provider_by_id), "模型厂商目录缺少小米 MiMo 或 Kimi")

    xiaomi = provider_by_id["xiaomi_mimo"]
    kimi = provider_by_id["kimi"]
    assert_model_provider_definition(xiaomi)
    assert_model_provider_definition(kimi)

    endpoint_urls = {endpoint["base_url"] for provider in catalog["providers"] for endpoint in provider.get("endpoints", [])}
    assert_true("https://token-plan-cn.xiaomimimo.com/v1" in endpoint_urls, "缺少小米 MiMo 中国区 OpenAI 兼容入口")
    assert_true("https://token-plan-cn.xiaomimimo.com/anthropic" in endpoint_urls, "缺少小米 MiMo 中国区 Anthropic 兼容入口")
    assert_true("https://api.moonshot.cn/v1" in endpoint_urls, "缺少 Kimi 中国区 OpenAI 兼容入口")

    assert_true("kimi-k2.6" in kimi["models"], "Kimi 模型列表缺少 kimi-k2.6")
    assert_true("mimo-v2.5-pro" in xiaomi["models"], "小米 MiMo 模型列表缺少 mimo-v2.5-pro")
    assert_no_plain_api_key_field(catalog, "ModelProviderCatalog")

    if catalog["active_config"] is not None:
        assert_public_model_config(catalog["active_config"])
    assert_true(isinstance(catalog["saved_configs"], list), "saved_configs 必须是数组")
    for config in catalog["saved_configs"]:
        assert_public_model_config(config)

    active = client.get("/api/model-providers/active")
    if active is not None:
        assert_public_model_config(active)
        assert_no_plain_api_key_field(active, "PublicModelConfig")


def check_audit_logs(client: ApiClient) -> None:
    logs = client.get("/api/audit-logs?limit=20")
    assert_true(isinstance(logs, list) and logs, "审计日志列表不能为空")
    for log in logs[:5]:
        assert_audit_log(log)

    filtered = client.get("/api/audit-logs?actor=agent&action=agent_chat&limit=20")
    assert_true(isinstance(filtered, list), "审计筛选响应必须是数组")
    if filtered:
        assert_equal(filtered[0]["actor"], "agent", "按 actor 筛选失效")
        assert_equal(filtered[0]["action"], "agent_chat", "按 action 筛选失效")


def assert_room_state(payload: Any) -> None:
    require_keys(payload, {"timestamp", "health_score", "status", "summary", "metrics", "anomalies", "recommendation"}, "RoomState")
    assert_true(isinstance(payload["health_score"], int) and 0 <= payload["health_score"] <= 100, "health_score 必须是 0-100 整数")
    assert_in(payload["status"], ROOM_STATUSES, "RoomState.status")
    assert_true(isinstance(payload["summary"], str) and payload["summary"], "summary 不能为空")
    assert_true(isinstance(payload["recommendation"], str) and payload["recommendation"], "recommendation 不能为空")
    assert_true(isinstance(payload["anomalies"], list), "anomalies 必须是数组")
    metrics = payload["metrics"]
    assert_true(isinstance(metrics, dict), "metrics 必须是对象")
    assert_true(METRICS.issubset(set(metrics)), "RoomState.metrics 缺少核心指标")
    for metric, reading in metrics.items():
        assert_in(metric, METRICS, "RoomState.metrics key")
        assert_sensor_reading(reading)
        assert_equal(reading["metric"], metric, "SensorReading.metric 必须与 metrics key 一致")


def assert_sensor_reading(payload: Any) -> None:
    require_keys(payload, {"metric", "value", "unit", "timestamp", "device_id", "quality"}, "SensorReading")
    assert_in(payload["metric"], METRICS, "SensorReading.metric")
    assert_true(isinstance(payload["value"], (int, float)), "SensorReading.value 必须是数字")
    assert_true(isinstance(payload["unit"], str) and payload["unit"], "SensorReading.unit 不能为空")
    assert_true(isinstance(payload["timestamp"], str) and payload["timestamp"], "SensorReading.timestamp 不能为空")
    assert_true(isinstance(payload["device_id"], str) and payload["device_id"], "SensorReading.device_id 不能为空")
    assert_in(payload["quality"], {"ok", "stale", "anomaly"}, "SensorReading.quality")


def assert_device(payload: Any) -> None:
    require_keys(
        payload,
        {"id", "name", "type", "location", "risk_level", "controllable", "requires_confirmation", "online_state", "current_state"},
        "Device",
    )
    assert_true(isinstance(payload["id"], str) and payload["id"], "Device.id 不能为空")
    assert_in(payload["risk_level"], RISK_LEVELS, "Device.risk_level")
    assert_true(isinstance(payload["controllable"], bool), "Device.controllable 必须是布尔值")
    assert_true(isinstance(payload["requires_confirmation"], bool), "Device.requires_confirmation 必须是布尔值")
    assert_in(payload["online_state"], DEVICE_STATES, "Device.online_state")
    assert_true(isinstance(payload["current_state"], dict), "Device.current_state 必须是对象")


def assert_policy_decision(payload: Any) -> None:
    require_keys(payload, {"result", "risk_level", "requires_confirmation", "reason", "constraints"}, "PolicyDecision")
    assert_in(payload["result"], POLICY_RESULTS, "PolicyDecision.result")
    assert_in(payload["risk_level"], RISK_LEVELS, "PolicyDecision.risk_level")
    assert_true(isinstance(payload["requires_confirmation"], bool), "PolicyDecision.requires_confirmation 必须是布尔值")
    assert_true(isinstance(payload["reason"], str) and payload["reason"], "PolicyDecision.reason 不能为空")
    assert_true(isinstance(payload["constraints"], list), "PolicyDecision.constraints 必须是数组")


def assert_automation_rule(payload: Any) -> None:
    require_keys(payload, {"id", "condition", "action", "enabled", "created_by", "created_at", "trigger_count", "last_triggered_at"}, "AutomationRule")
    assert_true(str(payload["id"]).startswith("rule_"), "AutomationRule.id 格式错误")
    assert_true(isinstance(payload["condition"], str) and payload["condition"], "AutomationRule.condition 不能为空")
    assert_true(isinstance(payload["action"], str) and payload["action"], "AutomationRule.action 不能为空")
    assert_true(isinstance(payload["enabled"], bool), "AutomationRule.enabled 必须是布尔值")
    assert_in(payload["created_by"], {"user", "agent"}, "AutomationRule.created_by")
    assert_true(isinstance(payload["trigger_count"], int), "AutomationRule.trigger_count 必须是整数")


def assert_rule_evaluation(payload: Any) -> None:
    require_keys(payload, {"rule_id", "condition", "action", "matched", "status", "reason", "evaluated_at", "observed", "audit_log_id"}, "RuleEvaluation")
    assert_true(str(payload["rule_id"]).startswith("rule_"), "RuleEvaluation.rule_id 格式错误")
    assert_true(isinstance(payload["matched"], bool), "RuleEvaluation.matched 必须是布尔值")
    assert_in(payload["status"], {"triggered", "not_matched", "disabled", "unsupported"}, "RuleEvaluation.status")
    assert_true(isinstance(payload["observed"], dict), "RuleEvaluation.observed 必须是对象")


def assert_agent_message(payload: Any) -> None:
    require_keys(payload, {"role", "content", "created_at"}, "AgentMessage")
    assert_in(payload["role"], {"user", "assistant"}, "AgentMessage.role")
    assert_true(isinstance(payload["content"], str) and payload["content"], "AgentMessage.content 不能为空")
    assert_true(isinstance(payload["created_at"], str) and payload["created_at"], "AgentMessage.created_at 不能为空")


def assert_tool_call(payload: Any) -> None:
    require_keys(payload, {"id", "name", "parameters", "result", "policy", "created_at"}, "ToolCall")
    assert_true(str(payload["id"]).startswith("tool_"), "ToolCall.id 格式错误")
    assert_true(isinstance(payload["name"], str) and payload["name"], "ToolCall.name 不能为空")
    assert_true(isinstance(payload["parameters"], dict), "ToolCall.parameters 必须是对象")
    assert_true(isinstance(payload["result"], dict), "ToolCall.result 必须是对象")
    if payload["policy"] is not None:
        assert_policy_decision(payload["policy"])


def assert_model_usage(payload: Any) -> None:
    require_keys(payload, {"provider_id", "provider_label", "model", "protocol", "status", "used", "reason"}, "AgentModelUsage")
    assert_in(payload["status"], MODEL_STATUSES, "AgentModelUsage.status")
    assert_true(isinstance(payload["used"], bool), "AgentModelUsage.used 必须是布尔值")
    assert_true(isinstance(payload["reason"], str) and payload["reason"], "AgentModelUsage.reason 不能为空")


def assert_model_provider_definition(payload: Any) -> None:
    require_keys(payload, {"id", "label", "description", "docs_url", "endpoints", "models", "default_model"}, "ModelProviderDefinition")
    assert_true(isinstance(payload["id"], str) and payload["id"], "ModelProviderDefinition.id 不能为空")
    assert_true(isinstance(payload["label"], str) and payload["label"], "ModelProviderDefinition.label 不能为空")
    assert_true(isinstance(payload["endpoints"], list) and payload["endpoints"], "ModelProviderDefinition.endpoints 不能为空")
    assert_true(isinstance(payload["models"], list) and payload["models"], "ModelProviderDefinition.models 不能为空")
    assert_true(payload["default_model"] in payload["models"], "default_model 必须存在于 models 列表")
    for endpoint in payload["endpoints"]:
        require_keys(endpoint, {"id", "label", "protocol", "base_url", "description"}, "ProviderEndpoint")
        assert_in(endpoint["protocol"], {"openai", "anthropic"}, "ProviderEndpoint.protocol")
        assert_true(str(endpoint["base_url"]).startswith("https://"), "ProviderEndpoint.base_url 必须使用 HTTPS")


def assert_public_model_config(payload: Any) -> None:
    require_keys(payload, {"provider_id", "endpoint_id", "protocol", "base_url", "model", "api_key_set", "api_key_preview", "updated_at"}, "PublicModelConfig")
    assert_true(isinstance(payload["provider_id"], str) and payload["provider_id"], "PublicModelConfig.provider_id 不能为空")
    assert_in(payload["protocol"], {"openai", "anthropic"}, "PublicModelConfig.protocol")
    assert_true(str(payload["base_url"]).startswith("https://"), "PublicModelConfig.base_url 必须使用 HTTPS")
    assert_true(isinstance(payload["model"], str) and payload["model"], "PublicModelConfig.model 不能为空")
    assert_true(isinstance(payload["api_key_set"], bool), "PublicModelConfig.api_key_set 必须是布尔值")
    if payload["api_key_preview"] is not None:
        assert_true(isinstance(payload["api_key_preview"], str), "PublicModelConfig.api_key_preview 必须是字符串或 null")


def assert_audit_log(payload: Any) -> None:
    require_keys(payload, {"id", "timestamp", "actor", "action", "policy_result", "risk_level", "parameters", "result", "details"}, "AuditLog")
    assert_true(str(payload["id"]).startswith("audit_"), "AuditLog.id 格式错误")
    assert_in(payload["actor"], {"user", "agent", "system"}, "AuditLog.actor")
    assert_true(isinstance(payload["action"], str) and payload["action"], "AuditLog.action 不能为空")
    if payload["policy_result"] is not None:
        assert_in(payload["policy_result"], POLICY_RESULTS, "AuditLog.policy_result")
    if payload["risk_level"] is not None:
        assert_in(payload["risk_level"], RISK_LEVELS, "AuditLog.risk_level")
    assert_true(isinstance(payload["parameters"], dict), "AuditLog.parameters 必须是对象")
    assert_true(isinstance(payload["result"], str) and payload["result"], "AuditLog.result 不能为空")
    assert_true(isinstance(payload["details"], str) and payload["details"], "AuditLog.details 不能为空")


def assert_no_plain_api_key_field(payload: Any, label: str) -> None:
    if isinstance(payload, dict):
        if "api_key" in payload:
            raise ContractFailure(f"{label} 不允许回显明文 api_key 字段")
        for key, value in payload.items():
            assert_no_plain_api_key_field(value, f"{label}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            assert_no_plain_api_key_field(item, f"{label}[{index}]")


def require_keys(payload: Any, keys: set[str], label: str) -> None:
    assert_true(isinstance(payload, dict), f"{label} 必须是对象")
    missing = keys - set(payload)
    if missing:
        raise ContractFailure(f"{label} 缺少字段：{', '.join(sorted(missing))}")


def assert_in(value: Any, expected: set[str], label: str) -> None:
    if value not in expected:
        raise ContractFailure(f"{label} 值非法：{value!r}")


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise ContractFailure(f"{message}，期望 {expected!r}，实际 {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
