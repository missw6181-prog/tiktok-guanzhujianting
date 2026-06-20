#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========================================"
echo "  TikTok 直播间关注监听"
echo "========================================"
echo

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PYTHON="$cmd"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "错误: 未找到 Python，请先安装 Python 3.10+"
  exit 1
fi

echo "使用 Python: $($PYTHON --version)"

if [[ ! -d ".venv" ]]; then
  echo "正在创建虚拟环境..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import TikTokLive" >/dev/null 2>&1; then
  echo "正在安装依赖（首次运行可能需要一两分钟）..."
  pip install -q -r requirements.txt
  echo "依赖安装完成"
fi

echo
python main.py
