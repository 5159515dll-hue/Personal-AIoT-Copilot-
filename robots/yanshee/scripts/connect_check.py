#!/usr/bin/env python3
"""Yanshee 连通性检查 + yanapi API 自省。

这是接入机器人的第一步。它会：
  1) 探测机器人常见服务端口（SSH / RESTful API / JupyterLab）是否可达；
  2) 用 yanapi 连接机器人；
  3) 打印机器人上【实际安装的 yanapi 版本】暴露的全部函数，作为后续开发依据；
  4) 尝试读取电量等基础信息验证链路。

不依赖真实机器人也能运行端口探测部分；yanapi 相关步骤在未装 yanapi 时会跳过并给出提示。

用法：
    cp ../config.example.py ../config.py   # 首次：填好 ROBOT_IP
    python connect_check.py
"""
from __future__ import annotations

import json
import os
import socket
import sys

# 让 `import config` 找到 robots/yanshee/config.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
except ModuleNotFoundError:
    sys.exit(
        "未找到 config.py。请先在 robots/yanshee/ 下执行：\n"
        "    cp config.example.py config.py\n"
        "然后把 ROBOT_IP 改成机器人实际 IP。"
    )

# 机器人上常见的服务端口（用于快速判断机器人是否在线、哪些服务开着）。
CANDIDATE_PORTS = {
    22: "SSH（pi 登录）",
    9090: "RESTful API（推测，以官方文档为准）",
    8888: "JupyterLab（推测）",
    80: "Web / 服务",
}


def probe_ports(ip: str) -> None:
    print(f"== 端口探测 {ip} ==")
    any_open = False
    for port, label in CANDIDATE_PORTS.items():
        state = "open" if _tcp_open(ip, port) else "closed/filtered"
        if state == "open":
            any_open = True
        print(f"  {port:<5} {label:<28} {state}")
    if not any_open:
        print("  ⚠️ 没有探测到任何开放端口：确认机器人已开机、和本机在同一 WiFi、IP 正确。")
    print()


def _tcp_open(ip: str, port: int, timeout: float = 2.0) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((ip, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def inspect_yanapi(ip: str) -> None:
    print("== yanapi 连接与自省 ==")
    try:
        import YanAPI  # type: ignore
    except ImportError:
        print(
            "  未安装 yanapi（import YanAPI 失败）。\n"
            "  - 机器人内置树莓派一般已预装；请把本脚本 scp 到机器人上、SSH 进去运行。\n"
            "  - 或在本机尝试: pip install yanapi"
        )
        return

    try:
        YanAPI.yan_api_init(ip)
        print(f"  YanAPI.yan_api_init('{ip}') 调用成功。")
    except Exception as exc:  # noqa: BLE001 - 第一步需要看到任何失败原因
        print(f"  ⚠️ yan_api_init 失败：{exc!r}")
        print("     仍继续打印 API 列表供参考。")

    funcs = sorted(name for name in dir(YanAPI) if not name.startswith("_") and callable(getattr(YanAPI, name)))
    print(f"\n  机器人上 yanapi 暴露的函数（{len(funcs)} 个，后续开发以此为准）：")
    for i in range(0, len(funcs), 3):
        print("    " + "  ".join(f"{name:<28}" for name in funcs[i : i + 3]))

    print("\n  尝试读取基础信息（官方 YanAPI 真实函数名）：")
    for fname in ("get_robot_version_info", "get_robot_battery_info", "get_motion_list", "get_sensors_list"):
        result = _safe_call(YanAPI, fname)
        if result is not _MISSING:
            print(f"    {fname}() -> {json.dumps(result, ensure_ascii=False)[:300]}")


_MISSING = object()


def _safe_call(api, func_name: str, *args, **kwargs):
    """yanapi 函数名各版本有差异：存在才调用，不存在返回哨兵，异常打印不抛出。"""
    func = getattr(api, func_name, None)
    if func is None or not callable(func):
        return _MISSING
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}


def main() -> None:
    ip = config.ROBOT_IP
    print(f"目标机器人 IP：{ip}\n")
    probe_ports(ip)
    inspect_yanapi(ip)


if __name__ == "__main__":
    main()
