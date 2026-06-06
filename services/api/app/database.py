from __future__ import annotations

import os
import json
from datetime import datetime

from app.models import (
    Device,
    DeviceCapability,
    DeviceConnectionRecord,
    DeviceState,
    Metric,
    RiskLevel,
    SensorReading,
    TelemetryDeviceSummary,
    TelemetrySourceSummary,
    TelemetryStatus,
)
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

DEVICE_REGISTRY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS device_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    location TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    controllable BOOLEAN NOT NULL,
    requires_confirmation BOOLEAN NOT NULL,
    online_state TEXT NOT NULL,
    current_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    connected_appliance TEXT,
    max_active_duration_minutes INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_registry_risk
    ON device_registry (risk_level);
"""

DEVICE_CONNECTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS device_connections (
    device_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    transport TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    firmware_version TEXT,
    hardware_revision TEXT,
    location TEXT NOT NULL,
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    online_state TEXT NOT NULL DEFAULT 'unknown',
    last_seen_at TIMESTAMPTZ,
    last_message_id TEXT,
    last_sequence BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_connections_last_seen
    ON device_connections (last_seen_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_device_connections_type
    ON device_connections (device_type);
"""


def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def init_db(url: str | None = None) -> None:
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        _try_enable_timescale(conn)
        conn.execute(SCHEMA_SQL)
        conn.execute(DEVICE_REGISTRY_SCHEMA_SQL)
        conn.execute(DEVICE_CONNECTION_SCHEMA_SQL)
        _try_create_hypertable(conn)


def init_device_registry_db(url: str | None = None) -> None:
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(DEVICE_REGISTRY_SCHEMA_SQL)


def init_device_connections_db(url: str | None = None) -> None:
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(DEVICE_CONNECTION_SCHEMA_SQL)


def seed_device_registry_db(
    devices: list[Device],
    *,
    url: str | None = None,
    ensure_schema: bool = True,
) -> int:
    if ensure_schema:
        init_device_registry_db(url)
    if not devices:
        return 0

    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        count = _device_registry_count(conn)
        if count:
            return 0
        return _upsert_device_rows(conn, devices)


def list_device_registry_db(
    *,
    seed_devices: list[Device] | None = None,
    url: str | None = None,
) -> list[Device]:
    init_device_registry_db(url)
    if seed_devices is not None:
        seed_device_registry_db(seed_devices, url=url, ensure_schema=False)

    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                type,
                location,
                risk_level,
                controllable,
                requires_confirmation,
                online_state,
                current_state,
                connected_appliance,
                max_active_duration_minutes
            FROM device_registry
            ORDER BY
                CASE risk_level
                    WHEN 'read_only' THEN 0
                    WHEN 'low' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'high' THEN 3
                    WHEN 'forbidden' THEN 4
                    ELSE 5
                END,
                id ASC
            """
        ).fetchall()
    return [_row_to_device(row) for row in rows]


def get_device_registry_db(
    device_id: str,
    *,
    seed_devices: list[Device] | None = None,
    url: str | None = None,
) -> Device | None:
    init_device_registry_db(url)
    if seed_devices is not None:
        seed_device_registry_db(seed_devices, url=url, ensure_schema=False)

    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT
                id,
                name,
                type,
                location,
                risk_level,
                controllable,
                requires_confirmation,
                online_state,
                current_state,
                connected_appliance,
                max_active_duration_minutes
            FROM device_registry
            WHERE id = %s
            """,
            (device_id,),
        ).fetchone()
    return _row_to_device(row) if row else None


def upsert_device_connection_db(
    record: DeviceConnectionRecord,
    *,
    url: str | None = None,
    ensure_schema: bool = True,
) -> DeviceConnectionRecord:
    if ensure_schema:
        init_device_connections_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            INSERT INTO device_connections (
                device_id,
                display_name,
                device_type,
                transport,
                protocol_version,
                firmware_version,
                hardware_revision,
                location,
                capabilities,
                metadata,
                online_state,
                last_seen_at,
                last_message_id,
                last_sequence,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, now())
            ON CONFLICT (device_id) DO UPDATE SET
                display_name = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.display_name
                    ELSE EXCLUDED.display_name
                END,
                device_type = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.device_type
                    ELSE EXCLUDED.device_type
                END,
                transport = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.transport
                    ELSE EXCLUDED.transport
                END,
                protocol_version = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.protocol_version
                    ELSE EXCLUDED.protocol_version
                END,
                firmware_version = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.firmware_version
                    ELSE EXCLUDED.firmware_version
                END,
                hardware_revision = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.hardware_revision
                    ELSE EXCLUDED.hardware_revision
                END,
                location = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.location
                    ELSE EXCLUDED.location
                END,
                capabilities = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.capabilities
                    ELSE EXCLUDED.capabilities
                END,
                metadata = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.metadata
                    ELSE EXCLUDED.metadata
                END,
                online_state = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.online_state
                    ELSE EXCLUDED.online_state
                END,
                last_seen_at = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.last_seen_at
                    WHEN device_connections.last_seen_at IS NULL THEN EXCLUDED.last_seen_at
                    WHEN EXCLUDED.last_seen_at IS NULL THEN device_connections.last_seen_at
                    WHEN EXCLUDED.last_seen_at > device_connections.last_seen_at THEN EXCLUDED.last_seen_at
                    ELSE device_connections.last_seen_at
                END,
                last_message_id = CASE
                    WHEN EXCLUDED.last_sequence IS NOT NULL
                     AND device_connections.last_sequence IS NOT NULL
                     AND EXCLUDED.last_sequence <= device_connections.last_sequence
                    THEN device_connections.last_message_id
                    WHEN EXCLUDED.last_message_id IS NULL THEN device_connections.last_message_id
                    ELSE EXCLUDED.last_message_id
                END,
                last_sequence = CASE
                    WHEN EXCLUDED.last_sequence IS NULL THEN device_connections.last_sequence
                    WHEN device_connections.last_sequence IS NULL THEN EXCLUDED.last_sequence
                    WHEN EXCLUDED.last_sequence > device_connections.last_sequence THEN EXCLUDED.last_sequence
                    ELSE device_connections.last_sequence
                END,
                updated_at = now()
            RETURNING
                device_id,
                display_name,
                device_type,
                transport,
                protocol_version,
                firmware_version,
                hardware_revision,
                location,
                capabilities,
                metadata,
                online_state,
                last_seen_at,
                last_message_id,
                last_sequence,
                updated_at
            """,
            _device_connection_params(record),
        ).fetchone()
    return _row_to_device_connection(row)


def get_device_connection_db(
    device_id: str,
    *,
    url: str | None = None,
) -> DeviceConnectionRecord | None:
    init_device_connections_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT
                device_id,
                display_name,
                device_type,
                transport,
                protocol_version,
                firmware_version,
                hardware_revision,
                location,
                capabilities,
                metadata,
                online_state,
                last_seen_at,
                last_message_id,
                last_sequence,
                updated_at
            FROM device_connections
            WHERE device_id = %s
            """,
            (device_id,),
        ).fetchone()
    return _row_to_device_connection(row) if row else None


def list_device_connections_db(
    *,
    url: str | None = None,
    limit: int = 500,
) -> list[DeviceConnectionRecord]:
    init_device_connections_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT
                device_id,
                display_name,
                device_type,
                transport,
                protocol_version,
                firmware_version,
                hardware_revision,
                location,
                capabilities,
                metadata,
                online_state,
                last_seen_at,
                last_message_id,
                last_sequence,
                updated_at
            FROM device_connections
            ORDER BY last_seen_at DESC NULLS LAST, updated_at DESC, device_id ASC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [_row_to_device_connection(row) for row in rows]


def record_device_heartbeat_db(
    device_id: str,
    *,
    transport: str,
    protocol_version: str,
    firmware_version: str | None,
    status: str,
    last_seen_at: datetime,
    message_id: str | None = None,
    sequence: int | None = None,
    metrics: dict | None = None,
    url: str | None = None,
) -> DeviceConnectionRecord:
    existing = get_device_connection_db(device_id, url=url)
    record = DeviceConnectionRecord(
        device_id=device_id,
        display_name=existing.display_name if existing else device_id,
        device_type=existing.device_type if existing else "other",
        transport=transport or (existing.transport if existing else "http"),
        protocol_version=protocol_version or (existing.protocol_version if existing else "aiot.v1"),
        firmware_version=firmware_version or (existing.firmware_version if existing else None),
        hardware_revision=existing.hardware_revision if existing else None,
        location=existing.location if existing else "unknown",
        capabilities=existing.capabilities if existing else [],
        metadata={**(existing.metadata if existing else {}), "heartbeat": metrics or {}},
        online_state=_heartbeat_status_to_device_state(status),
        last_seen_at=last_seen_at,
        last_message_id=message_id,
        last_sequence=sequence,
        updated_at=last_seen_at,
    )
    return upsert_device_connection_db(record, url=url, ensure_schema=False)


def upsert_device_registry_db(
    devices: list[Device],
    *,
    url: str | None = None,
    ensure_schema: bool = True,
) -> int:
    if ensure_schema:
        init_device_registry_db(url)
    if not devices:
        return 0

    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        return _upsert_device_rows(conn, devices)


def update_device_registry_state_db(
    device_id: str,
    state: dict,
    *,
    url: str | None = None,
) -> Device | None:
    init_device_registry_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            UPDATE device_registry
            SET current_state = %s::jsonb,
                updated_at = now()
            WHERE id = %s
            RETURNING
                id,
                name,
                type,
                location,
                risk_level,
                controllable,
                requires_confirmation,
                online_state,
                current_state,
                connected_appliance,
                max_active_duration_minutes
            """,
            (json.dumps(state, ensure_ascii=False), device_id),
        ).fetchone()
    return _row_to_device(row) if row else None


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
            source_rows = conn.execute(
                """
                SELECT
                    source,
                    COUNT(*)::int AS total_readings,
                    COUNT(DISTINCT device_id)::int AS device_count,
                    MAX(time) AS latest_reading_at,
                    MAX(received_at) AS latest_received_at
                FROM sensor_readings
                GROUP BY source
                ORDER BY total_readings DESC, source ASC
                """
            ).fetchall()
            device_rows = conn.execute(
                """
                SELECT
                    device_id,
                    COUNT(*)::int AS total_readings,
                    COUNT(DISTINCT metric)::int AS metric_count,
                    MAX(time) AS latest_reading_at,
                    MAX(received_at) AS latest_received_at
                FROM sensor_readings
                GROUP BY device_id
                ORDER BY latest_received_at DESC, device_id ASC
                LIMIT 8
                """
            ).fetchall()
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
                sources=[
                    TelemetrySourceSummary(
                        source=row["source"],
                        total_readings=int(row["total_readings"] or 0),
                        device_count=int(row["device_count"] or 0),
                        latest_reading_at=row["latest_reading_at"],
                        latest_received_at=row["latest_received_at"],
                    )
                    for row in source_rows
                ],
                devices=[
                    TelemetryDeviceSummary(
                        device_id=row["device_id"],
                        total_readings=int(row["total_readings"] or 0),
                        metric_count=int(row["metric_count"] or 0),
                        latest_reading_at=row["latest_reading_at"],
                        latest_received_at=row["latest_received_at"],
                    )
                    for row in device_rows
                ],
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


def _row_to_device(row: dict) -> Device:
    return Device(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        location=row["location"],
        risk_level=RiskLevel(row["risk_level"]),
        controllable=bool(row["controllable"]),
        requires_confirmation=bool(row["requires_confirmation"]),
        online_state=DeviceState(row["online_state"]),
        current_state=_json_object(row["current_state"]),
        connected_appliance=row["connected_appliance"],
        max_active_duration_minutes=row["max_active_duration_minutes"],
    )


def _row_to_device_connection(row: dict) -> DeviceConnectionRecord:
    return DeviceConnectionRecord(
        device_id=row["device_id"],
        display_name=row["display_name"],
        device_type=row["device_type"],
        transport=row["transport"],
        protocol_version=row["protocol_version"],
        firmware_version=row["firmware_version"],
        hardware_revision=row["hardware_revision"],
        location=row["location"],
        capabilities=[
            DeviceCapability.model_validate(item)
            for item in _json_array(row["capabilities"])
            if isinstance(item, dict)
        ],
        metadata=_json_object(row["metadata"]),
        online_state=DeviceState(row["online_state"]),
        last_seen_at=row["last_seen_at"],
        last_message_id=row["last_message_id"],
        last_sequence=row["last_sequence"],
        updated_at=row["updated_at"],
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


def _device_registry_count(conn) -> int:
    row = conn.execute("SELECT COUNT(*)::int AS count FROM device_registry").fetchone()
    if isinstance(row, dict):
        return int(row["count"] or 0)
    return int(row[0] or 0)


def _upsert_device_rows(conn, devices: list[Device]) -> int:
    rows = [
        (
            device.id,
            device.name,
            device.type,
            device.location,
            device.risk_level.value,
            device.controllable,
            device.requires_confirmation,
            device.online_state.value,
            json.dumps(device.current_state, ensure_ascii=False),
            device.connected_appliance,
            device.max_active_duration_minutes,
        )
        for device in devices
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO device_registry (
                id,
                name,
                type,
                location,
                risk_level,
                controllable,
                requires_confirmation,
                online_state,
                current_state,
                connected_appliance,
                max_active_duration_minutes,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                location = EXCLUDED.location,
                risk_level = EXCLUDED.risk_level,
                controllable = EXCLUDED.controllable,
                requires_confirmation = EXCLUDED.requires_confirmation,
                online_state = EXCLUDED.online_state,
                current_state = EXCLUDED.current_state,
                connected_appliance = EXCLUDED.connected_appliance,
                max_active_duration_minutes = EXCLUDED.max_active_duration_minutes,
                updated_at = now()
            """,
            rows,
        )
    return len(rows)


def _device_connection_params(record: DeviceConnectionRecord) -> tuple:
    return (
        record.device_id,
        record.display_name,
        record.device_type,
        record.transport,
        record.protocol_version,
        record.firmware_version,
        record.hardware_revision,
        record.location,
        json.dumps([item.model_dump(mode="json") for item in record.capabilities], ensure_ascii=False),
        json.dumps(record.metadata, ensure_ascii=False, default=str),
        record.online_state.value,
        record.last_seen_at,
        record.last_message_id,
        record.last_sequence,
    )


def _heartbeat_status_to_device_state(status: str) -> DeviceState:
    if status == "offline":
        return DeviceState.offline
    if status in {"online", "degraded"}:
        return DeviceState.online
    return DeviceState.unknown


def _json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _json_array(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


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
