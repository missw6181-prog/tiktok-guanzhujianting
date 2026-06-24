#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PAUSE=false
for arg in "$@"; do
  if [[ "$arg" == "--pause" ]]; then
    PAUSE=true
  fi
done

echo "========================================"
echo "  TikTok 直播间关注监听 (Web 版)"
echo "========================================"
echo

export PATH="${HOME}/.local/bin:${PATH}"

USE_UV=false
if command -v uv >/dev/null 2>&1; then
  USE_UV=true
fi

if [[ "$USE_UV" == true ]]; then
  if ! uv python find 3.12 >/dev/null 2>&1; then
    echo "正在安装 Python 3.12..."
    uv python install 3.12
  fi
  if [[ ! -d ".venv" ]]; then
    echo "正在创建虚拟环境..."
    uv venv .venv --python 3.12
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  VENV_PY=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  if (( ${VENV_PY%%.*} < 3 || (${VENV_PY%%.*} == 3 && ${VENV_PY#*.} < 10) )); then
    echo "虚拟环境 Python 版本过低 ($VENV_PY)，正在重建..."
    rm -rf .venv
    uv venv .venv --python 3.12
    source .venv/bin/activate
  fi
  if ! python -c "import fastapi" >/dev/null 2>&1; then
    echo "正在安装依赖（首次运行可能需要一两分钟）..."
    uv pip install --prerelease=allow -r requirements.txt
    echo "依赖安装完成"
  fi
else
  PYTHON=""
  for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      PYTHON="$cmd"
      break
    fi
  done

  if [[ -z "$PYTHON" ]]; then
    echo "错误: 未找到 Python 3.10+，请先安装或运行: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi

  PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
  PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
  if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 10) )); then
    echo "错误: 需要 Python 3.10+，当前: $($PYTHON --version)"
    exit 1
  fi

  echo "使用 Python: $($PYTHON --version)"

  if [[ ! -d ".venv" ]]; then
    echo "正在创建虚拟环境..."
    "$PYTHON" -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate

  if ! python -c "import fastapi" >/dev/null 2>&1; then
    echo "正在安装依赖（首次运行可能需要一两分钟）..."
    pip install -q --pre -r requirements.txt
    echo "依赖安装完成"
  fi
fi

echo "使用 Python: $(python --version)"

if ! python - <<'PY' >/dev/null 2>&1
import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.database import SessionLocal
with SessionLocal() as db:
    db.scalar(text("SELECT 1"))
PY
then
  echo
  echo "数据库连接失败，请检查 .env 中的 MYSQL_* 或 DATABASE_URL"
  echo
elif ! python - <<'PY' >/dev/null 2>&1
import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.database import SessionLocal
with SessionLocal() as db:
    n = db.scalar(text("SELECT COUNT(*) FROM users"))
    sys.exit(0 if n else 1)
PY
then
  echo
  echo "数据库已连接，但尚无用户，请先运行："
  echo "  python scripts/init_db.py --email admin@example.com --password yourpassword"
  echo
fi

echo
echo "API: http://127.0.0.1:8000"
echo "用户端: http://127.0.0.1:5173/"
echo "管理端: http://127.0.0.1:5174/admin/"
echo
echo "提示: 本脚本只启动后端。要一键启动全部服务请运行: ./start-all.sh"
echo "      或另开终端运行: ./start-frontends.sh"
echo

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

if [[ "$PAUSE" == true ]]; then
  echo
  read -r -p "按回车键关闭窗口..."
fi
