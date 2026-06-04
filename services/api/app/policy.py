from __future__ import annotations

from app.models import (
    AutomationRuleCreate,
    Device,
    PolicyDecision,
    PolicyResult,
    RiskLevel,
)

INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all",
    "bypass",
    "override policy",
    "disable safety",
    "忽略之前",
    "忽略所有",
    "绕过",
    "越权",
    "关闭安全",
)

FORBIDDEN_RULE_PATTERNS = (
    "exec(",
    "eval(",
    "import os",
    "subprocess",
    "while true",
    "for (;;)",
    "all plugs",
    "所有插座",
    "烟雾报警",
)


def detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in INJECTION_PATTERNS)


def assess_device_control(
    *,
    device: Device | None,
    requested_state: str,
    confirmed: bool,
    intent: str,
) -> PolicyDecision:
    if detect_prompt_injection(intent):
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=RiskLevel.high,
            requires_confirmation=False,
            reason="请求试图绕过或覆盖安全策略。",
            constraints=["外部文本或用户文本不能提升工具权限。"],
        )

    if device is None:
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=RiskLevel.high,
            requires_confirmation=False,
            reason="未知设备不能被控制。",
            constraints=["必须先登记设备并配置风险元数据。"],
        )

    if not device.controllable:
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=device.risk_level,
            requires_confirmation=False,
            reason=f"{device.name} 在当前版本不可控制。",
            constraints=["当前版本只允许明确低风险设备的模拟控制。"],
        )

    if device.risk_level == RiskLevel.forbidden:
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=device.risk_level,
            requires_confirmation=False,
            reason="禁止类安全关键设备不能由智能体控制。",
            constraints=["门锁、报警器、燃气、摄像头、医疗设备和强电控制都会被阻止。"],
        )

    if device.risk_level == RiskLevel.high:
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=device.risk_level,
            requires_confirmation=False,
            reason="高风险或未知负载设备已被阻止。",
            constraints=["未来进入控制流程前，必须先标记连接设备和风险等级。"],
        )

    if device.risk_level == RiskLevel.medium and not confirmed:
        return PolicyDecision(
            result=PolicyResult.requires_confirmation,
            risk_level=device.risk_level,
            requires_confirmation=True,
            reason="中风险设备控制需要明确确认。",
            constraints=["需要确认目标设备、状态、原因和持续时间。"],
        )

    if requested_state not in {"on", "off"}:
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=device.risk_level,
            requires_confirmation=False,
            reason="请求状态无效。",
            constraints=["允许的状态只有 on 和 off。"],
        )

    return PolicyDecision(
        result=PolicyResult.allowed,
        risk_level=device.risk_level,
        requires_confirmation=False,
        reason="低风险模拟设备控制已被当前版本策略允许。"
        if device.risk_level == RiskLevel.low
        else "已确认的中风险模拟动作被允许。",
        constraints=[
            "执行结果为模拟。",
            "该动作会写入审计日志。",
        ],
    )


def validate_rule(rule: AutomationRuleCreate) -> PolicyDecision:
    text = f"{rule.condition} {rule.action}".lower()
    if detect_prompt_injection(text) or any(pattern in text for pattern in FORBIDDEN_RULE_PATTERNS):
        return PolicyDecision(
            result=PolicyResult.denied,
            risk_level=RiskLevel.high,
            requires_confirmation=False,
            reason="规则包含不安全或当前不支持的自动化行为。",
            constraints=["当前版本规则不能执行代码、串联多设备或控制安全关键设备。"],
        )

    if not rule.confirmed:
        return PolicyDecision(
            result=PolicyResult.requires_confirmation,
            risk_level=RiskLevel.low,
            requires_confirmation=True,
            reason="自动化规则保存前必须经过用户检查和确认。",
            constraints=["持久化前需要展示自然语言条件和动作。"],
        )

    return PolicyDecision(
        result=PolicyResult.allowed,
        risk_level=RiskLevel.low,
        requires_confirmation=False,
        reason="已确认的简单“如果/那么”提醒规则被允许。",
        constraints=["规则必须保持简单条件和动作结构。"],
    )
