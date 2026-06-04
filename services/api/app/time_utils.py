from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    return datetime.now(tz=APP_TIMEZONE)


def ensure_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)
    return value.astimezone(APP_TIMEZONE)

