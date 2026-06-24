#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

NODE_BIN="$ROOT/.tools/node-v20.18.1-darwin-arm64/bin"
if [[ -d "$NODE_BIN" ]]; then
  export PATH="$NODE_BIN:$PATH"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "错误: 未找到 npm。请先安装 Node，或确认 .tools/node 存在。"
  exit 1
fi

mkdir -p data

stop_port() {
  local port="$1"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "停止端口 $port 上的旧进程: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

daemonize() {
  # macOS 无 setsid，用 nohup + 子 shell 脱离终端
  local logfile="$1"
  shift
  nohup bash -c '"$@"' _ "$@" >> "$logfile" 2>&1 &
  echo $!
}

start_one() {
  local name="$1"
  local dir="$2"
  local port="$3"

  stop_port "$port"
  cd "$dir"

  if [[ ! -x node_modules/.bin/vite ]]; then
    echo "安装 $name 依赖..."
    npm install
  fi

  echo "启动 $name → http://127.0.0.1:$port"
  local pid
  pid=$(daemonize "$ROOT/data/${name}.log" \
    "$dir/node_modules/.bin/vite" --host 127.0.0.1 --port "$port")
  echo "$pid" > "$ROOT/data/${name}.pid"
  cd "$ROOT"
}

start_one "frontend-user" "$ROOT/frontend-user" 5173
start_one "frontend-admin" "$ROOT/frontend-admin" 5174

sleep 3
echo
echo "用户端: http://127.0.0.1:5173/"
echo "管理端: http://127.0.0.1:5174/admin/"
echo "日志: data/frontend-user.log  data/frontend-admin.log"
echo
curl -sf -o /dev/null http://127.0.0.1:5173/ && echo "✓ 用户端 OK" || echo "✗ 用户端未响应，请查看 data/frontend-user.log"
curl -sf -o /dev/null http://127.0.0.1:5174/admin/ && echo "✓ 管理端 OK" || echo "✗ 管理端未响应，请查看 data/frontend-admin.log"
