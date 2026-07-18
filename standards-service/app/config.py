"""Runtime configuration for Codebook (standards-service) — own process, own
`.env`. Mirrors `backend/app/config.py`'s OFFLINE_MODE/LLM_PROVIDER pattern
exactly (docs/BUILD_PLAN_CODEBOOK.md step 4), but this module does NOT import
`backend/app/config.py` and is never imported by it — this service must stay
independently runnable, per the "never import across the backend/
standards-service process boundary" rule that already governs `app/retrieval/`.

OFFLINE_MODE is the single source of truth for "is a usable LLM provider
configured". `check_document_against_corpus`'s pass/fail DECISION is always
deterministic Python regardless of this flag (see `document_check.py`); only
the composed PROSE changes — a Python string template offline, an LLM
handed the already-made decision + real clause text online. Same
non-negotiable boundary as `backend/app/agents/compliance.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# standards-service/  (this file lives in standards-service/app/config.py)
SERVICE_DIR = Path(__file__).resolve().parent.parent

# Load standards-service/.env if present (no error if it's missing — the
# default, zero-config path is OFFLINE_MODE=True with no .env at all).
load_dotenv(SERVICE_DIR / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL_SMART: str = os.getenv("ANTHROPIC_MODEL_SMART", "claude-3-5-sonnet-latest").strip()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.1").strip()

# Which LLM backend composes prose. "offline" (default, and the ONLY mode
# ever exercised by this service's own eval — see docs/BUILD_PLAN_CODEBOOK.md's
# non-negotiable "must work fully offline" rule) uses a deterministic Python
# string template. Override in standards-service/.env.
#   offline | openai | anthropic
# (No "codex" option here, unlike backend/app/config.py: the Codex SDK
# package isn't in this service's requirements.txt, and CLAUDE.md already
# documents codex as ~185s/call — impractical for a standing default
# anywhere in this project, let alone a new service.)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "").strip().lower()
if not LLM_PROVIDER:
    # Back-compat: infer from whichever key is present, else stay offline.
    if ANTHROPIC_API_KEY:
        LLM_PROVIDER = "anthropic"
    elif OPENAI_API_KEY:
        LLM_PROVIDER = "openai"
    else:
        LLM_PROVIDER = "offline"


def _provider_usable() -> bool:
    if LLM_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if LLM_PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    return False


# Offline when no usable provider. check_document_against_corpus's decisions +
# citations are ALWAYS deterministic regardless of this flag; only prose changes.
OFFLINE_MODE: bool = not _provider_usable()
