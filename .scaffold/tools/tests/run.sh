#!/usr/bin/env bash
# Run lane.sh tests. Usage: bash runtime/tools/tests/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../" && pwd)"
exec "$REPO/.bats-vendor/bin/bats" "$HERE"
