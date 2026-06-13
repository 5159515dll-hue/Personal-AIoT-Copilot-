"""Yanshee 平台侧控制适配器（plan §5.2 / M6）。

机器人是物理执行器。平台侧只负责【策略门控 + 审计 + 下发抽象手势指令】，
**不在平台硬编码具体 YanAPI 运动名**——内置动作名是机器人/固件特定的，必须用官方
`get_motion_list()` 查，不能凭空捏造。

抽象手势（tilt_head / nod / reach_out …）→ 具体 YanAPI 动作的解析与执行在机器人侧完成
（见 robots/yanshee/，用官方 `get_motion_list()` 校验后 `sync_play_motion(...)` 播放）。
"""
from __future__ import annotations

from app.models import PolicyDecision
from app.policy import assess_companion_gesture


def plan_companion_gesture(*, gesture: str, intent: str = "", confirmed: bool = True) -> PolicyDecision:
    """情绪驱动手势的平台侧门控：只做策略判定，下发抽象手势；不解析具体运动名。"""
    return assess_companion_gesture(gesture=gesture, intent=intent, confirmed=confirmed)
