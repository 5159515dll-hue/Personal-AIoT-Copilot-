from __future__ import annotations

import os
from datetime import datetime

from app.models import Metric, SensorReading
from app.time_utils import ensure_tz, now

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    time TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    quality TEXT NOT NULL DEFAULT 'ok',
    source TEXT NOT NULL DEFAULT 'mqtt'
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_metric_time
    ON sensor_readings (metric, time DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_device_time
    ON sensor_readings (device_id, time DESC);
"""


def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def init_db(url: str | None = None) -> None:
    import psycopg

    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        _try_enable_timescale(conn)
        conn.execute(SCHEMA_SQL)
        _try_create_hypertable(conn)


def insert_sensor_readings(
    readings: list[SensorReading],
    *,
    source: str = "mqtt",
    url: str | None = None,
    ensure_schema: bool = False,
) -> int:
    if ensure_schema:
        init_db(url)
    if not readings:
        return 0

    import psycopg

    db_url = _require_url(url)
    rows = [
        (
            ensure_tz(item.timestamp),
            now(),
            item.device_id,
            item.metric.value,
            item.value,
            item.unit,
            item.quality,
            source,
        )
        for item in readings
    ]
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO sensor_readings
                    (time, received_at, device_id, metric, value, unit, quality, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
    return len(rows)


def query_sensor_history_db(
    metric: Metric,
    start: datetime,
    end: datetime,
    *,
    url: str | None = None,
    limit: int = 5000,
) -> list[SensorReading]:
    import psycopg
    from psycopg.rows import dict_row

    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT time, device_id, metric, value, unit, quality
            FROM sensor_readings
            WHERE metric = %s
              AND time >= %s
              AND time <= %s
            ORDER BY time ASC
            LIMIT %s
            """,
            (metric.value, ensure_tz(start), ensure_tz(end), limit),
        ).fetchall()
    return [_row_to_reading(row) for row in rows]


def latest_sensor_readings_db(*, url: str | None = None) -> dict[Metric, SensorReading]:
    import psycopg
    from psycopg.rows import dict_row

    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (metric) time, device_id, metric, value, unit, quality
            FROM sensor_readings
            ORDER BY metric, time DESC
            """
        ).fetchall()
    return {_row_to_reading(row).metric: _row_to_reading(row) for row in rows}


def _row_to_reading(row: dict) -> SensorReading:
    return SensorReading(
        metric=Metric(row["metric"]),
        value=float(row["value"]),
        unit=row["unit"],
        timestamp=row["time"],
        device_id=row["device_id"],
        quality=row["quality"],
    )


def _require_url(url: str | None) -> str:
    db_url = url or database_url()
    if not db_url:
        raise RuntimeError("未配置 DATABASE_URL，无法访问时间序列数据库。")
    return db_url


def _try_enable_timescale(conn) -> None:
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    except Exception:
        conn.rollback()


def _try_create_hypertable(conn) -> None:
    try:
        conn.execute(
            "SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE)"
        )
    except Exception:
        conn.rollback()

