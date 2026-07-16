#!/usr/bin/env bash
# Launch the SiteMind backend. Run from anywhere; it cd's to backend/.
set -euo pipefail

cd "$(dirname "$0")"

# Create / reuse a local virtualenv and install deps. Prefer Python 3.12 — the
# pinned numpy/pandas wheels don't build on 3.14 yet.
PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
if [ ! -d ".venv" ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt

# Offline-mode demo works with no API key; set ANTHROPIC_API_KEY in backend/.env
# to enable LLM-written prose/answers.
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
