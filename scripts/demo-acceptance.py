#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.cookiejar
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
ACCESS_CODE = "admin123"


class AcceptanceFailure(AssertionError):
    pass


def main() -> int:
    disable_proxy_env()
    parser = argparse.ArgumentParser(description="运行 Personal AIoT Copilot 3 分钟演示验收。")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--web-base-url", default=os.getenv("WEB_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--token", default=os.getenv("AIOT_INTERNAL_API_TOKEN") or read_internal_token())
    parser.add_argument("--timeout", type=float, default=float(os.getenv("DEMO_ACCEPTANCE_TIMEOUT", "45")))
    args = parser.parse_args()

    api_base_url = args.api_base_url.rstrip("/")
    web_base_url = args.web_base_url.rstrip("/")
    token = (args.token or "").strip()
    if not token:
        print("失败：缺少 AIOT_INTERNAL_API_TOKEN。请通过环境变量或 .dashboard-env 提供内部服务令牌。", file=sys.stderr)
        return 1

    print(f"开始 3 分钟演示验收：WEB={web_base_url} API={api_base_url}")
    started = time.time()
    checks = [
        ("公开项目页可说明系统价值", lambda: check_public_project_page(web_base_url, args.timeout)),
        ("固定口令可进入私有控制台", lambda: check_private_dashboard(web_base_url, args.timeout)),
        ("模拟环境数据和趋势接口可演示", lambda: check_environment_and_trends(api_base_url, token, args.timeout)),
        ("设备风险清单和低风险设备可识别", lambda: check_device_inventory(api_base_url, token, args.timeout)),
    ]

    failures: list[str] = []
    for label, check in checks:
        try:
            check()
            print(f"通过：{label}")
        except Exception as exc:  # noqa: BLE001 - CLI should continue and summarize all failed gates.
            failures.append(f"{label}：{exc}")
            print(f"失败：{label}：{exc}", file=sys.stderr)

    elapsed = round(time.time() - started, 1)
    if failures:
        print(f"3 分钟演示验收失败：{len(failures)} 项未通过，用时 {elapsed} 秒。", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"3 分钟演示验收完成：{len(checks)} 项全部通过，用时 {elapsed} 秒。")
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


def check_public_project_page(web_base_url: str, timeout: float) -> None:
    body = web_request_text(web_base_url, "/", timeout=timeout)
    assert_contains(body, "个人空间智能物联助手", "公开页缺少项目名称")
    assert_contains(body, "已经跑通的工程证据", "公开页缺少工程证据区")
    assert_contains(body, "端到端闭环", "公开页缺少闭环说明")


def check_private_dashboard(web_base_url: str, timeout: float) -> None:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    access_body = web_request_text(web_base_url, "/dashboard", timeout=timeout, opener=opener)
    assert_contains(access_body, "输入访问口令", "未登录访问控制台时没有进入口令页")

    form = urllib.parse.urlencode({"code": ACCESS_CODE, "next": "/dashboard"}).encode("utf-8")
    login_body = web_request_text(
        web_base_url,
        "/access/session",
        timeout=timeout,
        opener=opener,
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert_contains(login_body, "空间总览", "固定口令登录后没有进入空间总览")
    assert_contains(login_body, "情感陪伴", "控制台缺少情感陪伴模块")
    assert_contains(login_body, "最近审计活动", "控制台缺少最近审计活动")


def check_environment_and_trends(api_base_url: str, token: str, timeout: float) -> None:
    room = api_request(api_base_url, "/api/room/current", token, timeout=timeout)
    assert_true(room.get("health_score", -1) >= 0, "当前状态缺少健康分")
    metrics = room.get("metrics", {})
    for metric in ("temperature", "humidity", "co2", "light", "presence", "noise"):
        assert_true(metric in metrics, f"当前状态缺少指标：{metric}")
    assert_true(bool(room.get("recommendation")), "当前状态缺少建议摘要")

    history = api_request(api_base_url, "/api/sensors/history?metric=co2&bucket=15m", token, timeout=timeout)
    assert_true(isinstance(history, list) and len(history) >= 24, "二氧化碳趋势点过少")
    assert_true(all(item.get("metric") == "co2" for item in history[:10]), "趋势接口返回了错误指标")

    anomalies = api_request(api_base_url, "/api/anomalies?source=mock", token, timeout=timeout)
    assert_true(isinstance(anomalies, list) and len(anomalies) >= 1, "模拟异常事件为空")
    first = anomalies[0]
    assert_true(bool(first.get("title")) and bool(first.get("recommendation")), "异常事件缺少标题或建议")


def check_device_inventory(api_base_url: str, token: str, timeout: float) -> None:
    devices = api_request(api_base_url, "/api/devices", token, timeout=timeout)
    assert_true(isinstance(devices, list) and len(devices) >= 3, "设备清单数量不足")
    by_id = {device.get("id"): device for device in devices}
    lamp = by_id.get("desk_lamp_01")
    assert_true(isinstance(lamp, dict), "缺少低风险模拟台灯")
    assert_equal(lamp.get("risk_level"), "low", "台灯风险等级不正确")
    assert_true(lamp.get("controllable") is True, "低风险台灯应可模拟控制")
    assert_true(any(device.get("risk_level") in {"high", "forbidden"} for device in devices), "设备清单缺少高风险或禁止设备")


def api_request(
    api_base_url: str,
    path: str,
    token: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{api_base_url}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-AIoT-Internal-Token": token,
        },
    )
    text = open_request_text(request, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AcceptanceFailure(f"接口没有返回 JSON：{text[:240]}") from exc


def web_request_text(
    web_base_url: str,
    path: str,
    *,
    timeout: float,
    opener: urllib.request.OpenerDirector | None = None,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    request = urllib.request.Request(f"{web_base_url}{path}", data=data, method=method, headers=headers or {})
    return open_request_text(request, timeout=timeout, opener=opener)


def open_request_text(
    request: urllib.request.Request,
    *,
    timeout: float,
    opener: urllib.request.OpenerDirector | None = None,
) -> str:
    client = opener or urllib.request.build_opener()
    try:
        with client.open(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise AcceptanceFailure(f"HTTP 状态异常：{response.status}")
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AcceptanceFailure(f"HTTP {exc.code}：{detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise AcceptanceFailure(f"请求失败：{exc}") from exc


def assert_contains(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AcceptanceFailure(message)


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise AcceptanceFailure(f"{message}，期望 {expected!r}，实际 {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
