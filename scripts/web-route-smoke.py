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
ERROR_MARKERS = (
    "Application error",
    "Internal Server Error",
    "NEXT_NOT_FOUND",
    "后端 API 代理失败",
    "__next_error__",
)


class WebSmokeFailure(AssertionError):
    pass


def main() -> int:
    disable_proxy_env()
    parser = argparse.ArgumentParser(description="运行 Personal AIoT Copilot Web 页面路由烟测。")
    parser.add_argument("--web-base-url", default=os.getenv("WEB_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("WEB_ROUTE_SMOKE_TIMEOUT", "45")))
    args = parser.parse_args()

    web_base_url = args.web_base_url.rstrip("/")
    public_client = make_client()
    authed_client = make_client()

    print(f"开始 Web 页面路由烟测：WEB={web_base_url}")
    started = time.time()
    checks = [
        ("公开项目页可访问", lambda: check_html(public_client, web_base_url, "/", ["个人空间智能物联助手", "已经跑通的工程证据", "端到端闭环"], args.timeout)),
        ("访问口令页可访问", lambda: check_html(public_client, web_base_url, "/access", ["输入访问口令", "访问个人空间数据前需要确认身份"], args.timeout)),
        ("未登录访问私有页会被拦截", lambda: check_private_route_redirect(public_client, web_base_url, args.timeout)),
        ("固定口令可建立控制台会话", lambda: login(authed_client, web_base_url, args.timeout)),
        ("总览页可渲染", lambda: check_html(authed_client, web_base_url, "/dashboard?source=mock", ["空间总览", "智能体建议", "最近审计活动"], args.timeout)),
        ("房间设置页可渲染多空间能力", lambda: check_html(authed_client, web_base_url, "/spaces", ["房间设置", "新增空间", "感知能力规划", "视觉与身份能力边界"], args.timeout)),
        ("趋势页可渲染 24 小时与 7 天", lambda: check_trends_pages(authed_client, web_base_url, args.timeout)),
        ("设备页可渲染后台管理", lambda: check_html(authed_client, web_base_url, "/devices", ["设备", "真实硬件后台管理", "新建设备", "删除档案"], args.timeout)),
        ("硬件接入页可渲染示例代码", lambda: check_html(authed_client, web_base_url, "/hardware", ["硬件接入", "POST", "/api/device-connections/register", "树莓派示例"], args.timeout)),
        ("智能体页可渲染工具说明", lambda: check_html(authed_client, web_base_url, "/agent", ["智能体", "工具和策略先执行", "询问房间状态"], args.timeout)),
        ("模型页可渲染中国区模型工具", lambda: check_html(authed_client, web_base_url, "/models", ["模型接入", "当前模型切换工具", "密钥导入工具", "小米", "Kimi"], args.timeout)),
        ("规则页可渲染", lambda: check_html(authed_client, web_base_url, "/rules", ["自动化规则", "创建已确认规则", "评估当前规则"], args.timeout)),
        ("审计页可渲染筛选器", lambda: check_html(authed_client, web_base_url, "/audit", ["审计日志", "发起方", "关键词"], args.timeout)),
        ("同源 API 代理鉴权正常", lambda: check_api_proxy(public_client, authed_client, web_base_url, args.timeout)),
    ]

    failures: list[str] = []
    for label, check in checks:
        try:
            check()
            print(f"通过：{label}")
        except Exception as exc:  # noqa: BLE001 - route smoke should show every broken page.
            failures.append(f"{label}：{exc}")
            print(f"失败：{label}：{exc}", file=sys.stderr)

    elapsed = round(time.time() - started, 1)
    if failures:
        print(f"Web 页面路由烟测失败：{len(failures)} 项未通过，用时 {elapsed} 秒。", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Web 页面路由烟测完成：{len(checks)} 项全部通过，用时 {elapsed} 秒。")
    return 0


def disable_proxy_env() -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(name, None)


def make_client() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def login(client: urllib.request.OpenerDirector, web_base_url: str, timeout: float) -> None:
    form = urllib.parse.urlencode({"code": ACCESS_CODE, "next": "/dashboard"}).encode("utf-8")
    text = request_text(
        client,
        web_base_url,
        "/access/session",
        timeout=timeout,
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert_contains(text, "空间总览", "登录后没有进入总览页")


def check_private_route_redirect(client: urllib.request.OpenerDirector, web_base_url: str, timeout: float) -> None:
    text = request_text(client, web_base_url, "/dashboard", timeout=timeout)
    assert_contains(text, "输入访问口令", "未登录访问私有页没有跳转到口令页")
    assert_contains(text, "私有控制台", "口令页缺少私有控制台说明")


def check_trends_pages(client: urllib.request.OpenerDirector, web_base_url: str, timeout: float) -> None:
    check_html(client, web_base_url, "/trends", ["传感器趋势", "二氧化碳 24 小时", "噪声 24 小时"], timeout)
    check_html(client, web_base_url, "/trends?window=7d", ["传感器趋势", "二氧化碳 7 天", "有人状态 7 天"], timeout)


def check_api_proxy(
    public_client: urllib.request.OpenerDirector,
    authed_client: urllib.request.OpenerDirector,
    web_base_url: str,
    timeout: float,
) -> None:
    health = request_json(public_client, web_base_url, "/api/health", timeout=timeout)
    assert_equal(health.get("status"), "ok", "同源公开健康检查异常")

    private_failure = request_json(public_client, web_base_url, "/api/room/current", timeout=timeout, expected_status=401)
    assert_contains(private_failure.get("detail", ""), "私有接口需要先通过控制台访问口令验证", "同源私有 API 未登录错误不正确")

    room = request_json(authed_client, web_base_url, "/api/room/current", timeout=timeout)
    assert_true("metrics" in room and "co2" in room["metrics"], "登录后同源 API 代理没有返回房间状态")


def check_html(
    client: urllib.request.OpenerDirector,
    web_base_url: str,
    path: str,
    required_text: list[str],
    timeout: float,
) -> None:
    text = request_text(client, web_base_url, path, timeout=timeout)
    for marker in ERROR_MARKERS:
        if marker in text:
            raise WebSmokeFailure(f"{path} 出现错误标记：{marker}")
    for item in required_text:
        assert_contains(text, item, f"{path} 缺少文本：{item}")


def request_json(
    client: urllib.request.OpenerDirector,
    web_base_url: str,
    path: str,
    *,
    timeout: float,
    expected_status: int = 200,
) -> Any:
    text = request_text(client, web_base_url, path, timeout=timeout, expected_status=expected_status)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise WebSmokeFailure(f"{path} 响应不是 JSON：{text[:240]}") from exc


def request_text(
    client: urllib.request.OpenerDirector,
    web_base_url: str,
    path: str,
    *,
    timeout: float,
    expected_status: int = 200,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    request = urllib.request.Request(f"{web_base_url}{path}", data=data, method=method, headers=headers or {})
    try:
        with client.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status != expected_status:
                raise WebSmokeFailure(f"{path} 期望 HTTP {expected_status}，实际 HTTP {response.status}：{body[:240]}")
            return body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == expected_status:
            return body
        raise WebSmokeFailure(f"{path} 期望 HTTP {expected_status}，实际 HTTP {exc.code}：{body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise WebSmokeFailure(f"{path} 请求失败：{exc}") from exc


def assert_contains(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise WebSmokeFailure(message)


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise WebSmokeFailure(f"{message}，期望 {expected!r}，实际 {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise WebSmokeFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
