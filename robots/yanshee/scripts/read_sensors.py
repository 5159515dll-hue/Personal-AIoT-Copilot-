#!/usr/bin/env python3
"""读取 Yanshee 的电量、环境/IMU/距离传感器和舵机角度，验证平台遥测数据来源。

只读、不驱动任何运动，安全。函数名取自官方 YanAPI 2.0.0 接口文档（见仓库记忆 yanapi-reference）。

用法：
    python read_sensors.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
except ModuleNotFoundError:
    sys.exit("未找到 config.py，请先执行: cp config.example.py config.py 并填入 ROBOT_IP")

_MISSING = object()

# 数据项 -> 官方 YanAPI 真实函数名（YanAPI 2.0.0 接口文档核实）。
READOUTS = {
    "battery": "get_robot_battery_info",
    "sensors_list": "get_sensors_list",
    "gyro/IMU": "get_sensors_gyro",
    "environment": "get_sensors_environment",
    "infrared": "get_sensors_infrared",
    "ultrasonic": "get_sensors_ultrasonic",
    "touch": "get_sensors_touch",
    "pressure": "get_sensors_pressure",
    "servos": "get_servos_angles",
    "version": "get_robot_version_info",
}


def main() -> None:
    try:
        import YanAPI  # type: ignore
    except ImportError:
        sys.exit("未安装 yanapi。请把脚本 scp 到机器人上运行，或 pip install yanapi。")

    ip = config.ROBOT_IP
    print("连接机器人 {} …\n".format(ip))
    YanAPI.yan_api_init(ip)

    snapshot = {}
    for label, func_name in READOUTS.items():
        result = _safe_call(YanAPI, func_name)
        if result is _MISSING:
            print("{:<14}: （此 yanapi 版本无 {}）".format(label, func_name))
        else:
            snapshot[label] = result
            print("{:<14}: [{}] {}".format(label, func_name, json.dumps(result, ensure_ascii=False)[:200]))

    print("\n== JSON 快照（可作为平台遥测来源） ==")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


def _safe_call(api, func_name: str):
    # 外接传感器(environment/infrared/ultrasonic/touch/pressure)未接入时官方接口可能报错，
    # 这里捕获并返回错误信息而非中断，便于一次性看清哪些传感器在线。
    func = getattr(api, func_name, None)
    if func is None or not callable(func):
        return _MISSING
    try:
        return func()
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}


if __name__ == "__main__":
    main()
