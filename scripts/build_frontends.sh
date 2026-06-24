#!/usr/bin/env bash
# 仅编译两个前端（不上传 Python）
set -euo pipefail
exec "$(dirname "$0")/build_release.sh" --skip-backend "$@"
