#!/usr/bin/env bash
set -euo pipefail

unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
WEB_BASE_URL="${WEB_BASE_URL:-http://127.0.0.1:3000}"
DASHBOARD_ACCESS_CODE="admin123"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

if [ -z "${AIOT_INTERNAL_API_TOKEN:-}" ] && [ -f "$ROOT_DIR/.dashboard-env" ]; then
  AIOT_INTERNAL_API_TOKEN="$(
    grep -E '^(export[[:space:]]+)?AIOT_INTERNAL_API_TOKEN=' "$ROOT_DIR/.dashboard-env" \
      | tail -n 1 \
      | sed -E 's/^(export[[:space:]]+)?AIOT_INTERNAL_API_TOKEN=//' \
      || true
  )"
  AIOT_INTERNAL_API_TOKEN="${AIOT_INTERNAL_API_TOKEN%$'\r'}"
  AIOT_INTERNAL_API_TOKEN="${AIOT_INTERNAL_API_TOKEN%\"}"
  AIOT_INTERNAL_API_TOKEN="${AIOT_INTERNAL_API_TOKEN#\"}"
  AIOT_INTERNAL_API_TOKEN="${AIOT_INTERNAL_API_TOKEN%\'}"
  AIOT_INTERNAL_API_TOKEN="${AIOT_INTERNAL_API_TOKEN#\'}"
fi

if [ -z "${AIOT_INTERNAL_API_TOKEN:-}" ]; then
  echo "失败：缺少 AIOT_INTERNAL_API_TOKEN。请通过环境变量或服务器 .dashboard-env 提供内部服务令牌。" >&2
  exit 1
fi

COOKIE_JAR="$(mktemp)"
BODY_FILE="$(mktemp)"
INGEST_BODY="$(mktemp)"
DEVICE_CONNECT_BODY="$(mktemp)"
DEVICE_HEARTBEAT_BODY="$(mktemp)"
DEVICE_TELEMETRY_BODY="$(mktemp)"
DEVICE_OLD_HEARTBEAT_BODY="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$BODY_FILE" "$INGEST_BODY" "$DEVICE_CONNECT_BODY" "$DEVICE_HEARTBEAT_BODY" "$DEVICE_TELEMETRY_BODY" "$DEVICE_OLD_HEARTBEAT_BODY"' EXIT

SMOKE_RUN_ID="${SMOKE_RUN_ID:-$(date +%s)}"
SMOKE_DEVICE_ID="${SMOKE_DEVICE_ID:-room_node_http_smoke_$SMOKE_RUN_ID}"
UNKNOWN_DEVICE_ID="${UNKNOWN_DEVICE_ID:-unknown_plug_smoke_$SMOKE_RUN_ID}"
EMBEDDED_DEVICE_ID="${EMBEDDED_DEVICE_ID:-esp32_connection_smoke_$SMOKE_RUN_ID}"

pass() {
  printf '通过：%s\n' "$1"
}

fail() {
  printf '失败：%s\n' "$1" >&2
  if [ -s "$BODY_FILE" ]; then
    printf '响应：' >&2
    tr '\n' ' ' < "$BODY_FILE" >&2
    printf '\n' >&2
  fi
  exit 1
}

expect_status() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  if [ "$actual" = "$expected" ]; then
    pass "$label"
  else
    fail "$label，期望 HTTP $expected，实际 HTTP $actual"
  fi
}

assert_json() {
  local file="$1"
  local expression="$2"
  local label="$3"
  "$PYTHON_BIN" - "$file" "$expression" <<'PY' || fail "$label"
import json
import sys

path, expression = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

allowed = {
    "payload": payload,
    "any": any,
    "all": all,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}
if not eval(expression, {"__builtins__": {}}, allowed):
    raise SystemExit(1)
PY
  pass "$label"
}

printf '开始服务器烟测：API=%s WEB=%s\n' "$API_BASE_URL" "$WEB_BASE_URL"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' "$API_BASE_URL/api/health")"
expect_status "$status" "200" "公开健康检查可访问"
assert_json "$BODY_FILE" 'payload["status"] == "ok"' "健康检查响应结构正确"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' "$API_BASE_URL/api/room/current")"
expect_status "$status" "401" "未登录私有 API 会被拒绝"

login_result="$(
  curl -sS -o "$BODY_FILE" -w '%{http_code} %{redirect_url}' \
    -c "$COOKIE_JAR" \
    -X POST "$WEB_BASE_URL/access/session" \
    -F "code=$DASHBOARD_ACCESS_CODE" \
    -F "next=/dashboard"
)"
login_status="${login_result%% *}"
expect_status "$login_status" "303" "固定访问口令可以创建控制台会话"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' -b "$COOKIE_JAR" "$WEB_BASE_URL/dashboard")"
expect_status "$status" "200" "登录后可以打开控制台总览"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/room/current")"
expect_status "$status" "200" "内部服务令牌可以访问私有 API"
assert_json "$BODY_FILE" 'payload["health_score"] >= 0 and "metrics" in payload' "当前房间状态结构正确"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/anomalies?source=mock")"
expect_status "$status" "200" "结构化异常事件接口可访问"
assert_json "$BODY_FILE" 'len(payload) >= 1 and payload[0]["title"] and payload[0]["recommendation"]' "结构化异常事件响应正确"

cat > "$INGEST_BODY" <<JSON
{
  "device_id": "$SMOKE_DEVICE_ID",
  "source": "http",
  "readings": [
    { "metric": "temperature", "value": 25.4 },
    { "metric": "humidity", "value": 48.2 },
    { "metric": "co2", "value": 930 },
    { "metric": "light", "value": 620 },
    { "metric": "presence", "value": 1 },
    { "metric": "noise", "value": 48.5 }
  ]
}
JSON

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/ingest/sensor-readings" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$INGEST_BODY")"
expect_status "$status" "200" "HTTP 遥测入站写入成功"
assert_json "$BODY_FILE" 'payload["accepted"] == 6 and payload["stored"] == 6 and payload["source"] == "http"' "HTTP 入站响应结构正确"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/telemetry/status")"
expect_status "$status" "200" "遥测链路状态可读取"
assert_json "$BODY_FILE" 'payload["configured"] and payload["connected"] and payload["total_readings"] >= 6' "数据库遥测链路已连接且有数据"
assert_json "$BODY_FILE" 'any(item["source"] == "http" and item["total_readings"] >= 6 for item in payload["sources"])' "遥测来源统计包含 HTTP"
assert_json "$BODY_FILE" "any(item[\"device_id\"] == \"$SMOKE_DEVICE_ID\" for item in payload[\"devices\"])" "最近设备统计包含烟测设备"

cat > "$DEVICE_CONNECT_BODY" <<JSON
{
  "device_id": "$EMBEDDED_DEVICE_ID",
  "display_name": "ESP32 连接烟测节点",
  "device_type": "esp32",
  "transport": "mqtt",
  "protocol_version": "aiot.v1",
  "firmware_version": "0.2.0",
  "hardware_revision": "esp32-s3-devkit",
  "location": "server-smoke",
  "capabilities": [
    { "kind": "telemetry", "metrics": ["temperature", "humidity", "co2", "noise"] }
  ]
}
JSON

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/device-connections/register" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$DEVICE_CONNECT_BODY")"
expect_status "$status" "200" "统一设备连接注册接口可用"
assert_json "$BODY_FILE" "payload[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and payload[\"device_type\"] == \"esp32\" and payload[\"protocol_version\"] == \"aiot.v1\"" "设备注册响应结构正确"

cat > "$DEVICE_HEARTBEAT_BODY" <<JSON
{
  "status": "online",
  "transport": "mqtt",
  "protocol_version": "aiot.v1",
  "firmware_version": "0.2.0",
  "uptime_seconds": 3600,
  "battery_percent": 91.5,
  "rssi_dbm": -58,
  "message_id": "$EMBEDDED_DEVICE_ID-hb",
  "sequence": 10
}
JSON

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/device-connections/$EMBEDDED_DEVICE_ID/heartbeat" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$DEVICE_HEARTBEAT_BODY")"
expect_status "$status" "200" "统一设备心跳接口可用"
assert_json "$BODY_FILE" "payload[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and payload[\"online_state\"] == \"online\"" "设备心跳响应结构正确"

cat > "$DEVICE_TELEMETRY_BODY" <<JSON
{
  "protocol_version": "aiot.v1",
  "message_id": "$EMBEDDED_DEVICE_ID-telemetry",
  "sequence": 11,
  "firmware_version": "0.2.0",
  "readings": [
    { "metric": "temperature", "value": 25.8 },
    { "metric": "humidity", "value": 47.9 },
    { "metric": "co2", "value": 940 },
    { "metric": "noise", "value": 49.1 }
  ],
  "capabilities": [
    { "kind": "telemetry", "metrics": ["temperature", "humidity", "co2", "noise"] }
  ]
}
JSON

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/device-connections/$EMBEDDED_DEVICE_ID/telemetry" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$DEVICE_TELEMETRY_BODY")"
expect_status "$status" "200" "统一设备遥测接口可用"
assert_json "$BODY_FILE" "payload[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and payload[\"accepted\"] == 4 and payload[\"stored\"] == 4" "设备遥测响应结构正确"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/device-connections/$EMBEDDED_DEVICE_ID/telemetry" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$DEVICE_TELEMETRY_BODY")"
expect_status "$status" "200" "重复设备遥测消息可被幂等处理"
assert_json "$BODY_FILE" "payload[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and payload[\"accepted\"] == 4 and payload[\"stored\"] == 0" "重复设备遥测不会重复写入时间序列"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/device-connections?limit=50")"
expect_status "$status" "200" "设备连接列表可读取"
assert_json "$BODY_FILE" "any(item[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and item[\"protocol_version\"] == \"aiot.v1\" for item in payload)" "设备连接列表包含烟测设备"

cat > "$DEVICE_OLD_HEARTBEAT_BODY" <<JSON
{
  "status": "offline",
  "transport": "mqtt",
  "protocol_version": "aiot.v1",
  "firmware_version": "0.1.0",
  "uptime_seconds": 120,
  "battery_percent": 12.5,
  "rssi_dbm": -88,
  "message_id": "$EMBEDDED_DEVICE_ID-hb-old",
  "sequence": 9,
  "sent_at": "2026-01-01T00:00:00+08:00"
}
JSON

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/device-connections/$EMBEDDED_DEVICE_ID/heartbeat" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  --data-binary "@$DEVICE_OLD_HEARTBEAT_BODY")"
expect_status "$status" "200" "乱序旧心跳可被接收"
assert_json "$BODY_FILE" 'payload["online_state"] == "online"' "乱序旧心跳不会覆盖当前在线状态"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/device-connections?limit=50")"
expect_status "$status" "200" "乱序旧心跳后设备连接列表可读取"
assert_json "$BODY_FILE" "any(item[\"device_id\"] == \"$EMBEDDED_DEVICE_ID\" and item.get(\"last_sequence\") == 11 and item.get(\"last_message_id\") == \"$EMBEDDED_DEVICE_ID-telemetry\" and item.get(\"online_state\") == \"online\" for item in payload)" "乱序旧心跳不会回滚设备连接序号和最新消息"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/audit-logs?action=ingest_sensor_readings&q=$SMOKE_DEVICE_ID&limit=20")"
expect_status "$status" "200" "可按设备追溯遥测入站审计"
assert_json "$BODY_FILE" 'len(payload) >= 1 and payload[0]["action"] == "ingest_sensor_readings"' "遥测入站审计记录可检索"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -X POST "$API_BASE_URL/api/devices/$UNKNOWN_DEVICE_ID/control" \
  -H "content-type: application/json" \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  -d '{"state":"on","confirmed":false,"reason":"服务器烟测：未知设备必须拒绝"}')"
expect_status "$status" "404" "未知设备控制会被策略拒绝"
assert_json "$BODY_FILE" 'payload["detail"]["policy"]["result"] == "denied" and payload["detail"]["audit_log_id"]' "拒绝响应包含策略判断和审计编号"

status="$(curl -sS -o "$BODY_FILE" -w '%{http_code}' \
  -H "X-AIoT-Internal-Token: $AIOT_INTERNAL_API_TOKEN" \
  "$API_BASE_URL/api/audit-logs?action=control_device&result=blocked&policy_result=denied&risk_level=high&q=$UNKNOWN_DEVICE_ID&limit=20")"
expect_status "$status" "200" "可筛选高风险拒绝审计"
assert_json "$BODY_FILE" 'len(payload) >= 1 and payload[0]["result"] == "blocked" and payload[0]["policy_result"] == "denied"' "高风险拒绝审计记录可检索"

printf '服务器烟测完成。\n'
