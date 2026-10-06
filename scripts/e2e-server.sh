#!/usr/bin/env bash
# Starts the real backend serving the production frontend build, for Playwright.
# Fake Kroger, a throwaway data folder, and the test-only reset endpoints (localhost only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$(mktemp -d)"
export APP_BASE_URL="http://127.0.0.1:4173"
export APP_SECRET_KEY="e2e-only-secret-key-0123456789abcdef"
export APP_PASSWORD="e2e-household-passphrase"
export TZ="America/New_York"
export PORT=4173
export DATA_DIR="$DATA"
export KROGER_MODE=fake
export DINNERBELL_TEST_MODE=1
export DINNERBELL_STATIC_DIR="$ROOT/frontend/dist"
export LOG_LEVEL=WARNING
cd "$ROOT/backend"
uv run dinnerbell serve --host 127.0.0.1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; rm -rf "$DATA"' EXIT INT TERM
wait "$PID"
