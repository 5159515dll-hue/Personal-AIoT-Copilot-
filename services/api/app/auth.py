from __future__ import annotations

import hashlib
import hmac
import os
import re

from fastapi import Request

from app.device_credentials import DEVICE_TOKEN_HEADER, verify_device_token

DASHBOARD_SESSION_COOKIE = "aiot_dashboard_session"
INTERNAL_API_TOKEN_HEADER = "x-aiot-internal-token"

PUBLIC_API_PATHS = {
    "/api/health",
}
DEFAULT_DASHBOARD_ACCESS_CODE = "admin123"


def dashboard_access_code() -> str:
    return DEFAULT_DASHBOARD_ACCESS_CODE


def internal_api_token() -> str | None:
    value = os.getenv("AIOT_INTERNAL_API_TOKEN", "").strip()
    return value or None


def api_auth_enabled() -> bool:
    return True


def is_public_api_path(path: str) -> bool:
    return path in PUBLIC_API_PATHS


def session_token_for(access_code: str) -> str:
    secret = os.getenv("DASHBOARD_SESSION_SECRET", "").strip() or "personal-aiot-copilot-dashboard"
    raw = f"aiot-copilot:{secret}:{access_code}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def request_is_authorized(request: Request) -> bool:
    access_code = dashboard_access_code()
    if not access_code:
        return True

    configured_internal_token = internal_api_token()
    submitted_internal_token = request.headers.get(INTERNAL_API_TOKEN_HEADER)
    if (
        configured_internal_token
        and submitted_internal_token
        and hmac.compare_digest(submitted_internal_token, configured_internal_token)
    ):
        return True

    device_match = re.match(r"^/api/device-connections/([^/]+)/(events|media|heartbeat|telemetry)$", request.url.path)
    if device_match and verify_device_token(device_match.group(1), request.headers.get(DEVICE_TOKEN_HEADER)):
        return True

    submitted_session_token = request.cookies.get(DASHBOARD_SESSION_COOKIE)
    return bool(submitted_session_token) and hmac.compare_digest(
        submitted_session_token,
        session_token_for(access_code),
    )
