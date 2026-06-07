#!/usr/bin/env bash
set -euo pipefail

unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

started_at="$(date +%s)"

run_step() {
  local label="$1"
  shift
  printf '\n==> %s\n' "$label"
  "$@"
  printf '通过：%s\n' "$label"
}

printf '开始发布总验收：%s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
printf '项目目录：%s\n' "$ROOT_DIR"

run_step "后端 API 单元测试" bash -lc "cd '$ROOT_DIR/services/api' && '$PYTHON_BIN' -m pytest -q"
run_step "前端 TypeScript 类型检查" npm --workspace apps/web run typecheck
run_step "前端 ESLint 检查" npm --workspace apps/web run lint
run_step "前端生产构建" npm --workspace apps/web run build
run_step "核心 API 契约检查" npm run contract:api
run_step "ESP32 固件协议检查" npm run check:firmware
run_step "Web 页面路由烟测" npm run smoke:web
run_step "MQTT 遥测入站烟测" npm run smoke:mqtt
run_step "媒体事件与实时流烟测" npm run smoke:media
run_step "服务器部署烟测" npm run smoke:server
run_step "智能体安全评测" npm run eval:agent-safety
run_step "3 分钟演示验收" npm run acceptance:demo

elapsed="$(( $(date +%s) - started_at ))"
printf '\n发布总验收完成，用时 %s 秒。\n' "$elapsed"
