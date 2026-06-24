#!/usr/bin/env bash
# 导出当前 .env 配置的 MySQL 数据库
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# shellcheck disable=SC1091
source .env 2>/dev/null || true

HOST="${MYSQL_HOST:-127.0.0.1}"
PORT="${MYSQL_PORT:-3306}"
USER="${MYSQL_USER:-root}"
PASS="${MYSQL_PASSWORD:-}"
DB="${MYSQL_DATABASE:-follow_monitor}"
OUT="${1:-$ROOT/release/follow_monitor.sql}"

mkdir -p "$(dirname "$OUT")"

if [[ -n "$PASS" ]]; then
  mysqldump -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" \
    --single-transaction --routines --triggers --set-gtid-purged=OFF \
    "$DB" > "$OUT"
else
  mysqldump -h"$HOST" -P"$PORT" -u"$USER" \
    --single-transaction --routines --triggers --set-gtid-purged=OFF \
    "$DB" > "$OUT"
fi

echo "已导出: $OUT ($(du -sh "$OUT" | cut -f1))"
