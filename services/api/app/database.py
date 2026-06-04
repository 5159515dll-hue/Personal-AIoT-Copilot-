from __future__ import annotations

import os
from datetime import datetime

from app.models import Metric, SensorReading, TelemetryStatus
from app.time_utils import bucket_to_delta, ensure_tz, floor_to_bucket, now

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
    psycopg = _import_psycopg()
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

    psycopg = _import_psycopg()
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
    bucket: str = "15m",
    url: str | None = None,
    limit: int = 5000,
) -> list[SensorReading]:
    bucket_to_delta(bucket)

    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
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
    return bucket_sensor_readings([_row_to_reading(row) for row in rows], bucket)


def latest_sensor_readings_db(*, url: str | None = None) -> dict[Metric, SensorReading]:
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
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


def telemetry_status_db(*, url: str | None = None) -> TelemetryStatus:
    if not (url or database_url()):
        return TelemetryStatus(
            configured=False,
            connected=False,
            status="unavailable",
            message="未配置 DATABASE_URL，无法访问时间序列数据库。",
        )

    try:
        psycopg = _import_psycopg()
        dict_row = _dict_row_factory()
        db_url = _require_url(url)
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            sensor_table_exists = _sensor_table_exists(conn)
            timescale_available = _extension_available(conn, "timescaledb")
            timescale_enabled = _extension_enabled(conn, "timescaledb")
            hypertable = _sensor_table_is_hypertable(conn) if timescale_enabled else False

            if not sensor_table_exists:
                return TelemetryStatus(
                    configured=True,
                    connected=True,
                    sensor_table_exists=False,
                    timescale_available=timescale_available,
                    timescale_enabled=timescale_enabled,
                    hypertable=hypertable,
                    status="empty",
                    message="数据库已连接，但 sensor_readings 表尚未初始化。",
                )

            summary = conn.execute(
                """
                SELECT
                    COUNT(*)::int AS total_readings,
                    COUNT(DISTINCT device_id)::int AS device_count,
                    COUNT(DISTINCT metric)::int AS metric_count,
                    MAX(time) AS latest_reading_at,
                    MAX(received_at) AS latest_received_at
                FROM sensor_readings
                """
            ).fetchone()
            latest_metrics = latest_sensor_readings_db(url=db_url)
            total = int(summary["total_readings"] or 0)
            return TelemetryStatus(
                configured=True,
                connected=True,
                sensor_table_exists=True,
                timescale_available=timescale_available,
                timescale_enabled=timescale_enabled,
                hypertable=hypertable,
                total_readings=total,
                device_count=int(summary["device_count"] or 0),
                metric_count=int(summary["metric_count"] or 0),
                latest_reading_at=summary["latest_reading_at"],
                latest_received_at=summary["latest_received_at"],
                latest_metrics=latest_metrics,
                status="ok" if total else "empty",
                message="数据库遥测链路已有入库数据。" if total else "数据库已连接，但暂无传感器读数。",
            )
    except RuntimeError as exc:
        return TelemetryStatus(
            configured=True,
            connected=False,
            status="unavailable",
            message=_clean_error_text(exc),
        )
    except Exception:
        return TelemetryStatus(
            configured=True,
            connected=False,
            status="unavailable",
            message="数据库连接或查询失败，请检查 DATABASE_URL、网络和数据库服务状态。",
        )


def _row_to_reading(row: dict) -> SensorReading:
    return SensorReading(
        metric=Metric(row["metric"]),
        value=float(row["value"]),
        unit=row["unit"],
        timestamp=row["time"],
        device_id=row["device_id"],
        quality=row["quality"],
    )


def bucket_sensor_readings(readings: list[SensorReading], bucket: str) -> list[SensorReading]:
    bucket_to_delta(bucket)
    grouped: dict[datetime, list[SensorReading]] = {}
    for reading in readings:
        grouped.setdefault(floor_to_bucket(reading.timestamp, bucket), []).append(reading)

    result: list[SensorReading] = []
    for timestamp in sorted(grouped):
        items = grouped[timestamp]
        first = items[0]
        values = [item.value for item in items]
        qualities = {item.quality for item in items}
        device_ids = {item.device_id for item in items}
        quality = "anomaly" if "anomaly" in qualities else "stale" if "stale" in qualities else "ok"
        result.append(
            SensorReading(
                metric=first.metric,
                value=round(sum(values) / len(values), 1),
                unit=first.unit,
                timestamp=timestamp,
                device_id=first.device_id if len(device_ids) == 1 else "database_aggregate",
                quality=quality,
            )
        )
    return result


def _require_url(url: str | None) -> str:
    db_url = url or database_url()
    if not db_url:
        raise RuntimeError("未配置 DATABASE_URL，无法访问时间序列数据库。")
    return db_url


def _import_psycopg():
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("未安装 psycopg，无法访问时间序列数据库。请安装 services/api/requirements.txt。") from exc
    return psycopg


def _dict_row_factory():
    try:
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise RuntimeError("未安装 psycopg，无法访问时间序列数据库。请安装 services/api/requirements.txt。") from exc
    return dict_row


def _sensor_table_exists(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.sensor_readings') AS table_name").fetchone()
    return bool(row and row["table_name"])


def _extension_available(conn, name: str) -> bool:
    row = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = %s) AS exists", (name,)).fetchone()
    return bool(row and row["exists"])


def _extension_enabled(conn, name: str) -> bool:
    row = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = %s) AS exists", (name,)).fetchone()
    return bool(row and row["exists"])


def _sensor_table_is_hypertable(conn) -> bool:
    try:
        row = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                  AND hypertable_name = 'sensor_readings'
            ) AS exists
            """
        ).fetchone()
        return bool(row and row["exists"])
    except Exception:
        conn.rollback()
        return False


def _clean_error_text(exc: Exception) -> str:
    return str(exc).strip().rstrip("。.") + "。"


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
