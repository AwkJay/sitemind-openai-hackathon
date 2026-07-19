#!/usr/bin/env bash
# Launch the full SiteMind stack for a demo: Codebook (standards-service),
# backend, and frontend together, with RETRIEVAL_ENABLED/CODEBOOK_ENABLED on.
#
# backend/.env and standards-service keep their own defaults OFF (see
# backend/.env.example) so the tracked eval baseline stays untouched when
# services are started individually via backend/run.sh. This script is the
# one place those flags are turned on, and only for this launcher's own
# processes — it never edits .env.
set -euo pipefail

cd "$(dirname "$0")"

CODEBOOK_PORT=8010
BACKEND_PORT=8000

PIDS=()
cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for() {
  local url="$1" name="$2" tries=60
  until curl -fsS "$url" >/dev/null 2>&1; do
    tries=$((tries - 1))
    if [ "$tries" -le 0 ]; then
      echo "Timed out waiting for $name at $url" >&2
      exit 1
    fi
    sleep 1
  done
}

# Refuse to reuse a process already bound to a port we're about to start on —
# otherwise a stale, unflagged process could pass the health check below and
# we'd silently believe RETRIEVAL_ENABLED/CODEBOOK_ENABLED are live when they
# aren't.
require_port_free() {
  local port="$1" name="$2"
  if curl -fsS "http://127.0.0.1:$port/" >/dev/null 2>&1 || \
     curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 || \
     curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; then
    echo "Port $port is already in use (something is already answering there)." >&2
    echo "Stop whatever is running $name on :$port first, then re-run this script." >&2
    exit 1
  fi
}

require_port_free "$CODEBOOK_PORT" "Codebook"
require_port_free "$BACKEND_PORT" "the backend"

echo "Starting Codebook (standards-service) on :$CODEBOOK_PORT..."
./standards-service/run.sh > /tmp/sitemind-codebook.log 2>&1 &
PIDS+=("$!")
wait_for "http://127.0.0.1:$CODEBOOK_PORT/health" "Codebook"
echo "Codebook is up."

# backend/run.sh hardcodes --port 8000 (no arg passthrough), which matches
# BACKEND_PORT above — this launcher doesn't support running the backend on
# a different port.
echo "Starting backend on :$BACKEND_PORT (RETRIEVAL_ENABLED=1 CODEBOOK_ENABLED=1)..."
RETRIEVAL_ENABLED=1 CODEBOOK_ENABLED=1 ./backend/run.sh > /tmp/sitemind-backend.log 2>&1 &
PIDS+=("$!")
wait_for "http://127.0.0.1:$BACKEND_PORT/api/health" "backend"
echo "Backend is up."

echo "Starting frontend on :3000..."
echo "Logs: /tmp/sitemind-codebook.log /tmp/sitemind-backend.log"
echo "Press Ctrl+C to stop everything."
(cd frontend && npm run dev)
