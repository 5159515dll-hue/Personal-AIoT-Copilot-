from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Shanghai")
BUCKET_DELTAS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def now() -> datetime:
    return datetime.now(tz=APP_TIMEZONE)


def ensure_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)
    return value.astimezone(APP_TIMEZONE)


def bucket_to_delta(bucket: str) -> timedelta:
    if bucket not in BUCKET_DELTAS:
        raise ValueError("bucket 必须是 5m、15m、1h 或 1d")
    return BUCKET_DELTAS[bucket]


def floor_to_bucket(value: datetime, bucket: str) -> datetime:
    value = ensure_tz(value)
    bucket_to_delta(bucket)
    if bucket == "1d":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "1h":
        return value.replace(minute=0, second=0, microsecond=0)

    minutes = 5 if bucket == "5m" else 15
    bucket_minute = value.minute - (value.minute % minutes)
    return value.replace(minute=bucket_minute, second=0, microsecond=0)
