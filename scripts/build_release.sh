#!/usr/bin/env bash
# 一键打包：编译前端 + Linux 后端 + 组装 release 目录
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.nvm/versions/node/current/bin:${PATH}"

RELEASE_DIR="$ROOT/release/follow-monitor"
ARCHIVE="$ROOT/release/follow-monitor-linux-amd64.tar.gz"
SKIP_BACKEND=false
SKIP_DOCKER=false

usage() {
  cat <<'EOF'
用法: ./scripts/build_release.sh [选项]

  --skip-backend    只编译前端，不打包 Python
  --skip-docker     在本机 Linux 上直接用 PyInstaller（需在 Linux 环境运行）
  -h, --help        显示帮助

产物目录: release/follow-monitor/
压缩包:   release/follow-monitor-linux-amd64.tar.gz
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-backend) SKIP_BACKEND=true ;;
    --skip-docker) SKIP_DOCKER=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1"; usage; exit 1 ;;
  esac
  shift
done

echo "========================================"
echo "  打包 TikTok 关注监听 (生产发布)"
echo "========================================"

build_frontend() {
  local name="$1"
  local dir="$2"
  echo
  echo ">>> 编译 $name ..."
  cd "$ROOT/$dir"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  npm run build
  cd "$ROOT"
}

build_frontend "用户端" "frontend-user"
build_frontend "管理端" "frontend-admin"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR/data"

echo
echo ">>> 复制前端产物 ..."
mkdir -p "$RELEASE_DIR/frontend-user" "$RELEASE_DIR/frontend-admin"
cp -R "$ROOT/frontend-user/dist" "$RELEASE_DIR/frontend-user/"
cp -R "$ROOT/frontend-admin/dist" "$RELEASE_DIR/frontend-admin/"

cp "$ROOT/.env.example" "$RELEASE_DIR/.env.example"
cp "$ROOT/scripts/migrate_sqlite_to_mysql.py" "$RELEASE_DIR/" 2>/dev/null || true

cat > "$RELEASE_DIR/start.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export SERVE_STATIC=true
if [[ ! -f .env ]]; then
  echo "请先复制 .env.example 为 .env 并修改 JWT_SECRET 等配置"
  exit 1
fi
# PyInstaller 以可执行文件所在目录为根，需把 .env 和前端目录链到二进制目录
BIN_DIR="./follow-monitor"
ln -sfn "$(pwd)/.env" "$BIN_DIR/.env"
ln -sfn "$(pwd)/frontend-user" "$BIN_DIR/frontend-user" 2>/dev/null || true
ln -sfn "$(pwd)/frontend-admin" "$BIN_DIR/frontend-admin" 2>/dev/null || true
exec "$BIN_DIR/follow-monitor" run --host 0.0.0.0 --port "${PORT:-8000}"
EOF
chmod +x "$RELEASE_DIR/start.sh"

if [[ "$SKIP_BACKEND" == true ]]; then
  echo
  echo "已跳过 Python 打包（--skip-backend）"
else
  echo
  echo ">>> 打包 Linux 后端 ..."
  if [[ "$SKIP_DOCKER" == true ]]; then
    if [[ "$(uname -s)" != "Linux" ]]; then
      echo "错误: --skip-docker 只能在 Linux 上运行"
      exit 1
    fi
    "$ROOT/scripts/build_linux_native.sh"
  else
    if ! command -v docker >/dev/null 2>&1; then
      echo "错误: 未找到 Docker。Mac 上打包 Linux 二进制需要 Docker Desktop。"
      echo "      安装后重试，或在 Linux 服务器上运行: ./scripts/build_release.sh --skip-docker"
      exit 1
    fi
    "$ROOT/scripts/build_linux_docker.sh"
  fi
  rm -rf "$RELEASE_DIR/follow-monitor"
  cp -R "$ROOT/dist/follow-monitor" "$RELEASE_DIR/follow-monitor"
  chmod +x "$RELEASE_DIR/follow-monitor/follow-monitor"
fi

echo
echo ">>> 生成压缩包 ..."
mkdir -p "$ROOT/release"
tar -czf "$ARCHIVE" -C "$ROOT/release" follow-monitor

echo
echo "========================================"
echo "  打包完成"
echo "========================================"
echo "目录: $RELEASE_DIR"
echo "压缩: $ARCHIVE"
echo
echo "上传到服务器后："
echo "  tar -xzf follow-monitor-linux-amd64.tar.gz"
echo "  cd follow-monitor"
echo "  cp .env.example .env   # 编辑 JWT_SECRET、数据库等"
echo "  ./follow-monitor/follow-monitor init-db --email admin@example.com --password yourpassword"
echo "  ./start.sh"
echo
echo "访问: http://服务器IP:8000/  管理端: http://服务器IP:8000/admin/"
