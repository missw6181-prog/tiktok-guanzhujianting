#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="follow-monitor-build:local"
PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"

echo ">>> Docker 构建 Linux 二进制 (${PLATFORM}) ..."
docker build --platform "$PLATFORM" -f Dockerfile.build -t "$IMAGE" .

echo ">>> 提取 dist/follow-monitor ..."
docker rm -f fm-extract >/dev/null 2>&1 || true
cid=$(docker create "$IMAGE")
rm -rf "$ROOT/dist/follow-monitor"
mkdir -p "$ROOT/dist"
docker cp "$cid:/src/dist/follow-monitor" "$ROOT/dist/"
docker rm "$cid"

echo ">>> Linux 二进制: $ROOT/dist/follow-monitor/follow-monitor"
