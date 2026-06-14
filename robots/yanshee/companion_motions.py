# -*- coding: utf-8 -*-
"""平滑拟人动作库（Python 3.5 兼容）。

用舵机插值关键帧替代机械的内置动作：set_servos_angles(angles, runtime_ms) 会在 runtime 内
平滑插值到目标；多关键帧 + 缓动（较长 runtime）+ 小幅振荡 = 自然顺畅。

只做**上半身（手臂 + 头）安全动作**——不动腿、不影响平衡（走路仍用内置平衡已调好的动作）。
动作前后都回到 NEUTRAL（显式设角度，不依赖 Reset，保证一致）。

舵机（17）：手臂 RightShoulder{Roll,Flex}/RightElbowFlex + Left 对称；头 NeckLR（仅左右，无俯仰）。
左右肩/肘角度大致镜像：左 ≈ 180 - 右。下面角度均在实测安全范围内。
"""
import time

# 自然站立中立姿势（手臂下垂、头正）。动作结束回到这里。
NEUTRAL = {
    "RightShoulderRoll": 90, "RightShoulderFlex": 140, "RightElbowFlex": 165,
    "LeftShoulderRoll": 90, "LeftShoulderFlex": 40, "LeftElbowFlex": 15,
    "NeckLR": 90,
}


def _move(angles, ms):
    import YanAPI
    YanAPI.set_servos_angles(angles, int(ms))
    time.sleep(ms / 1000.0 + 0.05)


def go_neutral(ms=700):
    _move(dict(NEUTRAL), ms)


# ---- 各手势的平滑关键帧序列（结尾由 play() 统一回正）----
def _wave():
    """挥手/打招呼：抬右臂 + 轻轻挥两下。"""
    _move({"RightShoulderFlex": 60, "RightElbowFlex": 120}, 650)
    _move({"RightShoulderFlex": 28, "RightElbowFlex": 100, "RightShoulderRoll": 102}, 500)
    for _ in range(2):
        _move({"RightElbowFlex": 70}, 300)
        _move({"RightElbowFlex": 110}, 300)


def _raise_right_hand():
    _move({"RightShoulderFlex": 70, "RightElbowFlex": 120}, 650)
    _move({"RightShoulderFlex": 22, "RightElbowFlex": 100, "RightShoulderRoll": 100}, 600)


def _raise_left_hand():
    _move({"LeftShoulderFlex": 120, "LeftElbowFlex": 60}, 650)
    _move({"LeftShoulderFlex": 158, "LeftElbowFlex": 80, "LeftShoulderRoll": 80}, 600)


def _reach_out():
    """伸手/抱抱：双臂向前环抱（手把手示教捕捉的姿势：上臂保持低位、主要靠 Roll 向前摆）。"""
    # 1) 先摆到中途（平滑弧线）
    _move({"RightShoulderRoll": 52, "LeftShoulderRoll": 128,
           "RightShoulderFlex": 150, "LeftShoulderFlex": 30,
           "RightElbowFlex": 158, "LeftElbowFlex": 22}, 600)
    # 2) 到位：向前环抱
    _move({"RightShoulderRoll": 17, "LeftShoulderRoll": 168,
           "RightShoulderFlex": 158, "LeftShoulderFlex": 24,
           "RightElbowFlex": 153, "LeftElbowFlex": 27}, 600)
    time.sleep(0.3)


def _nod():
    """点头/同意（无俯仰舵机 → 双臂小幅向前轻抬两次近似"嗯嗯"的应和）。"""
    for _ in range(2):
        _move({"RightShoulderFlex": 125, "LeftShoulderFlex": 55}, 260)
        _move({"RightShoulderFlex": 140, "LeftShoulderFlex": 40}, 260)


def _tilt_head():
    """歪头/疑惑：头偏向一侧（NeckLR）。"""
    _move({"NeckLR": 62}, 600)
    time.sleep(0.4)
    _move({"NeckLR": 90}, 500)


def _lean_back():
    """后仰/放松：双臂轻轻向后下方舒展（不动躯干，保平衡）。"""
    _move({"RightShoulderFlex": 158, "RightShoulderRoll": 78,
           "LeftShoulderFlex": 22, "LeftShoulderRoll": 102}, 700)
    time.sleep(0.5)


def _idle_nod():
    """轻点头/陪伴：头轻轻左右各一下，幅度很小。"""
    _move({"NeckLR": 80}, 400)
    _move({"NeckLR": 100}, 400)
    _move({"NeckLR": 90}, 350)


SMOOTH_GESTURES = {
    "wave": _wave,
    "raise_right_hand": _raise_right_hand,
    "raise_left_hand": _raise_left_hand,
    "reach_out": _reach_out,
    "nod": _nod,
    "tilt_head": _tilt_head,
    "lean_back": _lean_back,
    "idle_nod": _idle_nod,
}


def has(gesture):
    return gesture in SMOOTH_GESTURES


def play(gesture, hold_seconds=2.0, return_neutral=True):
    """播放一个平滑手势：先回中立 → 做动作 → 保持几秒 → 回中立。"""
    fn = SMOOTH_GESTURES.get(gesture)
    if fn is None:
        return False
    go_neutral(500)
    fn()
    if hold_seconds > 0:
        time.sleep(hold_seconds)
    if return_neutral:
        go_neutral(700)
    return True
