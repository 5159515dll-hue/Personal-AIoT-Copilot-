#!/usr/bin/env python3
"""机器人侧情绪手势执行器（plan §6 / B2）。

接收平台下发的【抽象手势】(tilt_head/nod/...)，用官方 YanAPI 校验后播放：
  - get_motion_list()  查机器人内置动作名（真实名由机器人返回）
  - sync_play_motion(name, direction, speed, repeat)  播放

抽象手势 → 机器人内置动作名的映射，**必须用 get_motion_list() 查到的真实动作名填写**
（不同固件动作名不同，不在此硬编码捏造）。默认全为 None，请先跑 connect_check.py / 下面的
 --list 看真实动作名，再填进 GESTURE_MOTION_MAP（或在 config.py 里覆盖同名变量）。

安全：手势已在平台经 policy.assess_companion_gesture 门控；本脚本只负责执行已确认的原地手势。
运行前清空机器人周围、远离桌沿。

用法（在机器人上）：
    python companion_gesture.py --list        # 打印 get_motion_list() 真实动作名
    python companion_gesture.py nod           # 播放映射到 nod 的动作
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ModuleNotFoundError:
    sys.exit("未找到 config.py，请先执行: cp config.example.py config.py 并填入 ROBOT_IP")

# 抽象手势 → 机器人内置动作名（占位 None，请用 get_motion_list() 的真实名填写；
# 也可在 config.py 定义 GESTURE_MOTION_MAP 覆盖本默认）。
GESTURE_MOTION_MAP: dict[str, str | None] = getattr(
    config,
    "GESTURE_MOTION_MAP",
    {
        "nod": None,
        "tilt_head": None,
        "wave": None,
        "reach_out": None,
        "lean_back": None,
        "idle_nod": None,
    },
)


def _motion_names(api) -> list[str]:
    """get_motion_list() 返回内置动作清单（结构按官方 {'data': {'name': [...]}}，做轻量容错）。"""
    try:
        res = api.get_motion_list()
    except Exception as exc:  # noqa: BLE001
        print(f"  get_motion_list() 出错：{exc!r}")
        return []
    if isinstance(res, dict):
        data = res.get("data", res)
        if isinstance(data, dict) and isinstance(data.get("name"), list):
            return [str(item) for item in data["name"]]
        if isinstance(data, list):
            return [str(item) for item in data]
    return []


def play_gesture(gesture: str) -> bool:
    """播放一个抽象手势对应的机器人动作。成功返回 True。"""
    try:
        import YanAPI  # type: ignore
    except ImportError:
        print("未安装 yanapi。请在机器人上运行。")
        return False
    YanAPI.yan_api_init(config.ROBOT_IP)

    motion = GESTURE_MOTION_MAP.get(gesture)
    if not motion:
        print(
            f"手势「{gesture}」未映射到机器人动作。\n"
            "请先 `python companion_gesture.py --list` 查真实动作名，再填进 GESTURE_MOTION_MAP。"
        )
        return False

    available = _motion_names(YanAPI)
    if available and motion not in available:
        print(f"动作「{motion}」不在 get_motion_list() 返回中：{', '.join(available[:20])} …")
        return False

    try:
        YanAPI.sync_play_motion(name=motion, direction="", speed="normal", repeat=1)
        print(f"已播放手势 {gesture} -> 动作 {motion}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"播放出错：{exc!r}")
        return False


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("用法：python companion_gesture.py --list | <抽象手势名>")
    if sys.argv[1] == "--list":
        try:
            import YanAPI  # type: ignore
        except ImportError:
            sys.exit("未安装 yanapi，请在机器人上运行。")
        YanAPI.yan_api_init(config.ROBOT_IP)
        names = _motion_names(YanAPI)
        print(f"机器人内置动作（{len(names)} 个）：{', '.join(names) if names else '（get_motion_list 未返回）'}")
        print("把上面真实动作名填进 GESTURE_MOTION_MAP（或 config.py 的同名变量）。")
        return
    play_gesture(sys.argv[1])


if __name__ == "__main__":
    main()
