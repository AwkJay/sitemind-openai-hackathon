#!/usr/bin/env bash
# Launch the Codebook (standards-service) process. Run from anywhere; it
# cd's to standards-service/. Mirrors backend/run.sh's style exactly.
set -euo pipefail

cd "$(dirname "$0")"

# Create / reuse a local virtualenv and install deps. Prefer Python 3.12 —
# same rationale as backend/run.sh (pinned numpy wheels don't build on 3.14
# yet).
PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
if [ ! -d ".venv" ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
