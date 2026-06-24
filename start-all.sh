#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========================================"
echo "  启动全部服务（后端 + 两个前端）"
echo "========================================"
echo

# 1. 前端（后台常驻）
"$ROOT/start-frontends.sh"
echo

# 2. 后端（若未运行则后台启动）
if curl -sf -o /dev/null http://127.0.0.1:8000/api/health 2>/dev/null; then
  echo "✓ 后端已在运行: http://127.0.0.1:8000"
else
  echo "启动后端..."
  if [[ ! -d ".venv" ]]; then
    echo "错误: 未找到 .venv，请先运行 ./start.sh 完成初始化"
    exit 1
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  nohup bash -c 'uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload' \
    >> data/backend.log 2>&1 &
  echo $! > data/backend.pid
  sleep 3
  if curl -sf -o /dev/null http://127.0.0.1:8000/api/health; then
    echo "✓ 后端 OK: http://127.0.0.1:8000"
  else
    echo "✗ 后端启动失败，查看 data/backend.log"
    tail -20 data/backend.log
    exit 1
  fi
fi

echo
echo "全部就绪："
echo "  用户端  http://127.0.0.1:5173/"
echo "  管理端  http://127.0.0.1:5174/admin/"
echo "  API     http://127.0.0.1:8000"
echo
echo "停止前端: kill \$(cat data/frontend-user.pid) \$(cat data/frontend-admin.pid)"
echo "停止后端: kill \$(cat data/backend.pid)"
