#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器人侧情绪手势执行器（plan §6 / B2）。**Python 3.5 兼容**（Yanshee 树莓派为 3.5.3）。

接收平台下发的【抽象手势】(tilt_head/nod/...)，用官方 YanAPI 校验后播放：
  - get_motion_list()  查机器人内置动作名（真实名由机器人返回，结构见下方解析）
  - sync_play_motion(name, direction, speed, repeat)  播放
抽象手势 → 动作名映射在 config.GESTURE_MOTION_MAP（务必用 get_motion_list() 实测真实名）。
安全：手势已在平台经 policy 门控；本脚本只播原地安全动作。运行前清空机器人周围、远离桌沿。

用法（在机器人上）：
    python3 companion_gesture.py --list      # 打印 get_motion_list() 真实动作名
    python3 companion_gesture.py nod         # 播放映射到 nod 的动作
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    sys.exit("未找到 config.py，请先执行: cp config.example.py config.py 并填入 ROBOT_IP")

GESTURE_MOTION_MAP = getattr(
    config,
    "GESTURE_MOTION_MAP",
    {"nod": None, "tilt_head": None, "wave": None, "reach_out": None, "lean_back": None, "idle_nod": None},
)


def _motion_names(api):
    """get_motion_list() 的真实动作名清单。

    官方结构：{'data': {'system_layers_motions': [{'name','music'}], 'system_hts_motions': [...],
    'user_layers_motions': [...], 'user_hts_motions': [...]}}。做轻量容错。
    """
    try:
        res = api.get_motion_list()
    except Exception as exc:
        print("  get_motion_list() 出错：{0!r}".format(exc))
        return []
    data = res.get("data", res) if isinstance(res, dict) else res
    names = []
    if isinstance(data, dict):
        for key in ("system_layers_motions", "system_hts_motions", "user_layers_motions", "user_hts_motions"):
            for item in data.get(key) or []:
                if isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
        if not names and isinstance(data.get("name"), list):  # 兼容旧/扁平结构
            names = [str(item) for item in data["name"]]
    elif isinstance(data, list):
        names = [str(item.get("name") if isinstance(item, dict) else item) for item in data]
    return names


def play_gesture(gesture):
    """播放一个抽象手势对应的机器人动作。成功返回 True。"""
    try:
        import YanAPI
    except ImportError:
        print("未安装 YanAPI。请在机器人上运行。")
        return False
    YanAPI.yan_api_init(config.ROBOT_IP)

    motion = GESTURE_MOTION_MAP.get(gesture)
    if not motion:
        print("手势「{0}」未映射到机器人动作；请先 --list 查真实名再填 GESTURE_MOTION_MAP。".format(gesture))
        return False

    available = _motion_names(YanAPI)
    if available and motion not in available:
        print("动作「{0}」不在 get_motion_list() 返回中。".format(motion))
        return False

    try:
        YanAPI.sync_play_motion(name=motion, direction="", speed="normal", repeat=1)
        print("已播放手势 {0} -> 动作 {1}".format(gesture, motion))
        return True
    except Exception as exc:
        print("播放出错：{0!r}".format(exc))
        return False


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 companion_gesture.py --list | <抽象手势名>")
    if sys.argv[1] == "--list":
        try:
            import YanAPI
        except ImportError:
            sys.exit("未安装 YanAPI，请在机器人上运行。")
        YanAPI.yan_api_init(config.ROBOT_IP)
        names = _motion_names(YanAPI)
        print("机器人内置动作（{0} 个）：{1}".format(len(names), ", ".join(names) if names else "（无）"))
        return
    play_gesture(sys.argv[1])


if __name__ == "__main__":
    main()
