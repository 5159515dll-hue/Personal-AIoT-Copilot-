#!/usr/bin/env python3
"""让 Yanshee 动起来：播放一个内置动作（可选语音问候）。

安全提示：运行前清空机器人周围空间、扶稳机器人、远离桌沿。机器人会真实运动。

函数名取自官方 YanAPI 2.0.0 接口文档（见仓库记忆 yanapi-reference）：
  - get_motion_list()  查内置动作清单（动作名由机器人返回，不在此硬编码）
  - sync_play_motion(name, direction, speed, repeat)  同步播放
  - start_voice_tts(tts, interrupt)  语音播报

用法：
    python first_motion.py              # 播放 get_motion_list() 的第一个动作
    python first_motion.py <动作名>     # 播放指定动作（名字须来自 get_motion_list()）
"""
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
except ModuleNotFoundError:
    sys.exit("未找到 config.py，请先执行: cp config.example.py config.py 并填入 ROBOT_IP")


def main() -> None:
    try:
        import YanAPI  # type: ignore
    except ImportError:
        sys.exit("未安装 yanapi。请把脚本 scp 到机器人上运行，或 pip install yanapi。")

    ip = config.ROBOT_IP
    print("连接机器人 {} …".format(ip))
    YanAPI.yan_api_init(ip)

    motions = list_motions(YanAPI)
    if motions:
        print("机器人内置动作（{} 个）：{}".format(len(motions), ', '.join(motions[:20]))
              + (" …" if len(motions) > 20 else ""))
    else:
        print("get_motion_list() 未返回动作清单。")

    if len(sys.argv) > 1:
        target = sys.argv[1]
    elif motions:
        target = motions[0]  # 不猜动作名，取机器人实际返回的第一个
    else:
        sys.exit("未能确定动作名。请先用 connect_check.py 看 get_motion_list()，再指定：python first_motion.py <动作名>")

    print("\n⚠️  即将播放动作：{}  —— 确认机器人周围安全后，按回车继续（Ctrl+C 取消）".format(target))
    try:
        input()
    except KeyboardInterrupt:
        sys.exit("\n已取消。")

    say(YanAPI, "你好呀，我在这里陪着你")
    play_motion(YanAPI, target)
    print("完成。")


def list_motions(api) -> List[str]:
    """get_motion_list() 返回内置动作清单。结构按官方为 {'data': {'name': [...]}}，
    这里对返回结构做轻量容错（函数名是确定的，只是不同固件 data 包裹略有差异）。"""
    try:
        res = api.get_motion_list()
    except Exception as exc:  # noqa: BLE001
        print("  get_motion_list() 出错：{!r}".format(exc))
        return []
    if isinstance(res, dict):
        data = res.get("data", res)
        if isinstance(data, dict):
            names = data.get("name")
            if isinstance(names, list):
                return [str(item) for item in names]
        if isinstance(data, list):
            return [str(item) for item in data]
    return []


def play_motion(api, name: str) -> None:
    """sync_play_motion(name, direction, speed, repeat) 同步播放到动作结束。"""
    try:
        print("  sync_play_motion(name={!r}, direction='', speed='normal', repeat=1) …".format(name))
        api.sync_play_motion(name=name, direction="", speed="normal", repeat=1)
    except Exception as exc:  # noqa: BLE001
        print("  播放出错：{!r}（确认动作名来自 get_motion_list()）".format(exc))


def say(api, text: str) -> None:
    """start_voice_tts(tts, interrupt) 语音播报。"""
    try:
        api.start_voice_tts(tts=text, interrupt=True)
    except Exception:  # noqa: BLE001
        pass  # TTS 失败不影响动作演示


if __name__ == "__main__":
    main()
