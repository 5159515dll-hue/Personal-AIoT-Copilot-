from __future__ import annotations

import os
import json
from datetime import datetime

from app.models import (
    AgentConversationEntry,
    AuditLog,
    AutomationRule,
    Device,
    DeviceCapability,
    DeviceConnectionRecord,
    DeviceState,
    Metric,
    PolicyResult,
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

CREATE TABLE IF NOT EXISTS ingest_messages (
    source TEXT NOT NULL,
    device_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    sequence BIGINT,
    protocol_version TEXT,
    reading_count INTEGER NOT NULL DEFAULT 0,
    stored_count INTEGER NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, device_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_ingest_messages_device_seen
    ON ingest_messages (device_id, last_seen_at DESC);
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

PERSISTENCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    policy_result TEXT,
    risk_level TEXT,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    result TEXT NOT NULL,
    details TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp
    ON audit_logs (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_trace
    ON audit_logs (action, result, timestamp DESC);

CREATE TABLE IF NOT EXISTS automation_rules (
    id TEXT PRIMARY KEY,
    condition TEXT NOT NULL,
    action TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    last_triggered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_created
    ON automation_rules (created_at DESC);

CREATE TABLE IF NOT EXISTS agent_conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    data_source TEXT NOT NULL,
    user_message JSONB NOT NULL,
    assistant_message JSONB NOT NULL,
    used_data JSONB NOT NULL DEFAULT '[]'::jsonb,
    tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
    needs_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    model_usage JSONB NOT NULL,
    policy JSONB,
    rule_draft JSONB,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_session
    ON agent_conversations (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_created
    ON agent_conversations (created_at DESC);

CREATE TABLE IF NOT EXISTS device_credentials (
    device_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    token_preview TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS device_events (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    message_id TEXT,
    sequence BIGINT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    space_id TEXT NOT NULL,
    zone TEXT,
    captured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    media_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_device_events_space_time
    ON device_events (space_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_device_events_device_time
    ON device_events (device_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS media_assets (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    zone TEXT,
    media_type TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    content_url TEXT NOT NULL,
    event_id TEXT,
    captured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    retention_policy TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    privacy_level TEXT NOT NULL,
    analysis_status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_media_assets_space_time
    ON media_assets (space_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_sha256
    ON media_assets (sha256);

CREATE TABLE IF NOT EXISTS stream_sources (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,
    hls_url TEXT NOT NULL,
    stream_key TEXT NOT NULL,
    zone TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stream_sources_space
    ON stream_sources (space_id, updated_at DESC);
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
        conn.execute(PERSISTENCE_SCHEMA_SQL)
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


def init_persistence_db(url: str | None = None) -> None:
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(PERSISTENCE_SCHEMA_SQL)


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


def delete_device_registry_device_db(
    device_id: str,
    *,
    url: str | None = None,
) -> bool:
    init_device_registry_db(url)
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        result = conn.execute("DELETE FROM device_registry WHERE id = %s", (device_id,))
        return bool(result.rowcount)


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


def delete_device_connection_db(
    device_id: str,
    *,
    url: str | None = None,
) -> bool:
    init_device_connections_db(url)
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        result = conn.execute("DELETE FROM device_connections WHERE device_id = %s", (device_id,))
        return bool(result.rowcount)


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


def upsert_device_registry_device_db(
    device: Device,
    *,
    url: str | None = None,
) -> Device:
    init_device_registry_db(url)
    upsert_device_registry_db([device], url=url, ensure_schema=False)
    saved = get_device_registry_db(device.id, url=url)
    if saved is None:
        raise RuntimeError("设备注册表保存失败。")
    return saved


def insert_audit_log_db(
    log: AuditLog,
    *,
    url: str | None = None,
    ensure_schema: bool = True,
) -> AuditLog:
    if ensure_schema:
        init_persistence_db(url)
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (
                id,
                timestamp,
                actor,
                action,
                policy_result,
                risk_level,
                parameters,
                result,
                details
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                log.id,
                log.timestamp,
                log.actor,
                log.action,
                log.policy_result.value if log.policy_result else None,
                log.risk_level.value if log.risk_level else None,
                json.dumps(log.parameters, ensure_ascii=False, default=str),
                log.result,
                log.details,
            ),
        )
    return log


def list_audit_logs_db(
    limit: int = 100,
    *,
    actor: str | None = None,
    action: str | None = None,
    result: str | None = None,
    policy_result: str | None = None,
    risk_level: str | None = None,
    q: str | None = None,
    url: str | None = None,
) -> list[AuditLog]:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    filters: list[str] = []
    params: list[object] = []
    for column, value in (
        ("actor", actor),
        ("action", action),
        ("result", result),
        ("policy_result", policy_result),
        ("risk_level", risk_level),
    ):
        if value:
            filters.append(f"{column} = %s")
            params.append(value)
    if q:
        filters.append(
            "(id ILIKE %s OR action ILIKE %s OR result ILIKE %s OR details ILIKE %s OR parameters::text ILIKE %s)"
        )
        keyword = f"%{q}%"
        params.extend([keyword, keyword, keyword, keyword, keyword])
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                timestamp,
                actor,
                action,
                policy_result,
                risk_level,
                parameters,
                result,
                details
            FROM audit_logs
            {where}
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return [_row_to_audit_log(row) for row in rows]


def list_rules_db(*, url: str | None = None) -> list[AutomationRule]:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                condition,
                action,
                enabled,
                created_by,
                created_at,
                trigger_count,
                last_triggered_at
            FROM automation_rules
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_row_to_rule(row) for row in rows]


def save_rule_db(
    rule: AutomationRule,
    *,
    url: str | None = None,
    ensure_schema: bool = True,
) -> AutomationRule:
    if ensure_schema:
        init_persistence_db(url)
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO automation_rules (
                id,
                condition,
                action,
                enabled,
                created_by,
                created_at,
                trigger_count,
                last_triggered_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                condition = EXCLUDED.condition,
                action = EXCLUDED.action,
                enabled = EXCLUDED.enabled,
                created_by = EXCLUDED.created_by,
                created_at = EXCLUDED.created_at,
                trigger_count = EXCLUDED.trigger_count,
                last_triggered_at = EXCLUDED.last_triggered_at
            """,
            (
                rule.id,
                rule.condition,
                rule.action,
                rule.enabled,
                rule.created_by,
                rule.created_at,
                rule.trigger_count,
                rule.last_triggered_at,
            ),
        )
    return rule


def update_rule_enabled_db(
    rule_id: str,
    enabled: bool,
    *,
    url: str | None = None,
) -> AutomationRule | None:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            UPDATE automation_rules
            SET enabled = %s
            WHERE id = %s
            RETURNING
                id,
                condition,
                action,
                enabled,
                created_by,
                created_at,
                trigger_count,
                last_triggered_at
            """,
            (enabled, rule_id),
        ).fetchone()
    return _row_to_rule(row) if row else None


def record_rule_trigger_db(
    rule_id: str,
    triggered_at: datetime,
    *,
    url: str | None = None,
) -> AutomationRule | None:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            UPDATE automation_rules
            SET trigger_count = trigger_count + 1,
                last_triggered_at = %s
            WHERE id = %s
            RETURNING
                id,
                condition,
                action,
                enabled,
                created_by,
                created_at,
                trigger_count,
                last_triggered_at
            """,
            (triggered_at, rule_id),
        ).fetchone()
    return _row_to_rule(row) if row else None


def insert_agent_conversation_db(
    entry: AgentConversationEntry,
    *,
    retention_days: int = 30,
    url: str | None = None,
    ensure_schema: bool = True,
) -> AgentConversationEntry:
    if ensure_schema:
        init_persistence_db(url)
    psycopg = _import_psycopg()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "DELETE FROM agent_conversations WHERE created_at < now() - (%s * interval '1 day')",
            (retention_days,),
        )
        conn.execute(
            """
            INSERT INTO agent_conversations (
                id,
                session_id,
                data_source,
                user_message,
                assistant_message,
                used_data,
                tool_calls,
                needs_confirmation,
                model_usage,
                policy,
                rule_draft,
                created_at
            )
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                entry.id,
                entry.session_id,
                entry.data_source,
                json.dumps(entry.user_message.model_dump(mode="json"), ensure_ascii=False, default=str),
                json.dumps(entry.assistant_message.model_dump(mode="json"), ensure_ascii=False, default=str),
                json.dumps(entry.used_data, ensure_ascii=False, default=str),
                json.dumps([tool.model_dump(mode="json") for tool in entry.tool_calls], ensure_ascii=False, default=str),
                entry.needs_confirmation,
                json.dumps(entry.model_usage.model_dump(mode="json"), ensure_ascii=False, default=str),
                json.dumps(entry.policy.model_dump(mode="json"), ensure_ascii=False, default=str) if entry.policy else None,
                json.dumps(entry.rule_draft.model_dump(mode="json"), ensure_ascii=False, default=str) if entry.rule_draft else None,
                entry.created_at,
            ),
        )
    return entry


def list_agent_conversations_db(
    limit: int = 50,
    *,
    session_id: str | None = None,
    retention_days: int = 30,
    url: str | None = None,
) -> list[AgentConversationEntry]:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    filters = ["created_at >= now() - (%s * interval '1 day')"]
    params: list[object] = [retention_days]
    if session_id:
        filters.append("session_id = %s")
        params.append(session_id)
    params.append(limit)
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                session_id,
                data_source,
                user_message,
                assistant_message,
                used_data,
                tool_calls,
                needs_confirmation,
                model_usage,
                policy,
                rule_draft,
                created_at
            FROM agent_conversations
            WHERE {' AND '.join(filters)}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return [_row_to_agent_conversation(row) for row in rows]


def delete_agent_conversation_db(
    entry_id: str,
    *,
    url: str | None = None,
) -> AgentConversationEntry | None:
    init_persistence_db(url)
    psycopg = _import_psycopg()
    dict_row = _dict_row_factory()
    db_url = _require_url(url)
    with psycopg.connect(db_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            DELETE FROM agent_conversations
            WHERE id = %s
            RETURNING
                id,
                session_id,
                data_source,
                user_message,
                assistant_message,
                used_data,
                tool_calls,
                needs_confirmation,
                model_usage,
                policy,
                rule_draft,
                created_at
            """,
            (entry_id,),
        ).fetchone()
    return _row_to_agent_conversation(row) if row else None


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
    rows = _sensor_reading_rows(readings, source)
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            _insert_sensor_reading_rows(cur, rows)
    return len(rows)


def insert_sensor_readings_idempotent(
    readings: list[SensorReading],
    *,
    source: str,
    device_id: str,
    message_id: str | None,
    sequence: int | None = None,
    protocol_version: str | None = None,
    url: str | None = None,
    ensure_schema: bool = False,
) -> int:
    if not message_id:
        return insert_sensor_readings(readings, source=source, url=url, ensure_schema=ensure_schema)
    if ensure_schema:
        init_db(url)
    if not readings:
        return 0

    psycopg = _import_psycopg()
    db_url = _require_url(url)
    rows = _sensor_reading_rows(readings, source)
    with psycopg.connect(db_url) as conn:
        marker = conn.execute(
            """
            INSERT INTO ingest_messages (
                source,
                device_id,
                message_id,
                sequence,
                protocol_version,
                reading_count,
                stored_count,
                first_seen_at,
                last_seen_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0, now(), now())
            ON CONFLICT (source, device_id, message_id) DO NOTHING
            RETURNING message_id
            """,
            (source, device_id, message_id, sequence, protocol_version, len(readings)),
        ).fetchone()
        if marker is None:
            conn.execute(
                """
                UPDATE ingest_messages
                SET last_seen_at = now()
                WHERE source = %s
                  AND device_id = %s
                  AND message_id = %s
                """,
                (source, device_id, message_id),
            )
            return 0

        with conn.cursor() as cur:
            _insert_sensor_reading_rows(cur, rows)
        conn.execute(
            """
            UPDATE ingest_messages
            SET stored_count = %s
            WHERE source = %s
              AND device_id = %s
              AND message_id = %s
            """,
            (len(rows), source, device_id, message_id),
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


def _row_to_audit_log(row: dict) -> AuditLog:
    return AuditLog(
        id=row["id"],
        timestamp=row["timestamp"],
        actor=row["actor"],
        action=row["action"],
        policy_result=PolicyResult(row["policy_result"]) if row["policy_result"] else None,
        risk_level=RiskLevel(row["risk_level"]) if row["risk_level"] else None,
        parameters=_json_object(row["parameters"]),
        result=row["result"],
        details=row["details"],
    )


def _row_to_rule(row: dict) -> AutomationRule:
    return AutomationRule(
        id=row["id"],
        condition=row["condition"],
        action=row["action"],
        enabled=bool(row["enabled"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
        trigger_count=int(row["trigger_count"] or 0),
        last_triggered_at=row["last_triggered_at"],
    )


def _row_to_agent_conversation(row: dict) -> AgentConversationEntry:
    return AgentConversationEntry.model_validate(
        {
            "id": row["id"],
            "session_id": row["session_id"],
            "data_source": row["data_source"],
            "user_message": _json_object(row["user_message"]),
            "assistant_message": _json_object(row["assistant_message"]),
            "used_data": _json_array(row["used_data"]),
            "tool_calls": _json_array(row["tool_calls"]),
            "needs_confirmation": bool(row["needs_confirmation"]),
            "model_usage": _json_object(row["model_usage"]),
            "policy": _json_object(row["policy"]) if row["policy"] is not None else None,
            "rule_draft": _json_object(row["rule_draft"]) if row["rule_draft"] is not None else None,
            "created_at": row["created_at"],
        }
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


def _sensor_reading_rows(readings: list[SensorReading], source: str) -> list[tuple]:
    return [
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


def _insert_sensor_reading_rows(cur, rows: list[tuple]) -> None:
    cur.executemany(
        """
        INSERT INTO sensor_readings
            (time, received_at, device_id, metric, value, unit, quality, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
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
