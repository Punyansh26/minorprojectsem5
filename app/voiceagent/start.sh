#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEMO2_DIR="$(cd -- "$SCRIPT_DIR/../../code/demo2" && pwd)"
PYTHON_BIN="/home/rtx/miniconda3/envs/minor/bin/python"
API_PORT="${DEMO2_API_PORT:-8020}"
WEB_PORT="${PORT:-3001}"

echo "==> Starting IIIT-NR Voice Helpdesk (Demo 2) FastAPI Backend on http://127.0.0.1:${API_PORT} ..."
if ! curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
  (
    cd "$DEMO2_DIR"
    "$PYTHON_BIN" -m uvicorn api_server:app --host 127.0.0.1 --port "$API_PORT" &
    echo $! > "$SCRIPT_DIR/.backend.pid"
  )
  for _ in {1..30}; do
    if curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
      echo "==> Demo 2 Backend is live and ready!"
      break
    fi
    sleep 0.5
  done
else
  echo "==> Demo 2 Backend is already running on port ${API_PORT}."
fi

echo "==> Starting Next.js Web Application on http://localhost:${WEB_PORT} ..."
cd "$SCRIPT_DIR"
exec npx next dev -p "$WEB_PORT"
