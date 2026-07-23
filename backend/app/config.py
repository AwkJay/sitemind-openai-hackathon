"""Runtime configuration. Loads backend/.env and exposes the offline-mode flag.

OFFLINE_MODE is the single source of truth for "do we have a usable API key".
When it is True the whole demo runs from deterministic Python + cached fixtures,
which is exactly what we want on a hackathon stage with flaky wifi.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/  (this file lives in backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"

# Load backend/.env if present (no error if it's missing).
load_dotenv(BACKEND_DIR / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL_SMART: str = os.getenv("ANTHROPIC_MODEL_SMART", "claude-sonnet-4-6").strip()

# LLM-powered PERCEIVE step for compliance uploads (app/llm_extract.py). OFF by
# default so the demo stays deterministic. When 1, POST /api/compliance/ingest
# calls Claude (via the Claude Agent SDK, Claude Code subscription auth — a
# CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`, NOT an API key) to extract
# parameters, then a pure-Python span-verification gate keeps only values quoted
# verbatim from the document. Regex stays as the floor + fallback, so this can
# only ever add coverage, never regress. The pass/fail DECISION stays in
# checks.py regardless — the LLM never decides.
LLM_EXTRACTION_ENABLED: bool = os.getenv("LLM_EXTRACTION_ENABLED", "0").strip() == "1"
# Read here only so load_dotenv() surfaces it into the environment the Agent SDK
# subprocess inherits; the SDK itself consumes the env var directly.
CLAUDE_CODE_OAUTH_TOKEN: str = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.1").strip()

# Hugging Face Inference API — used only by app/embeddings.py for Copilot's
# semantic retrieval (a free token from https://huggingface.co/settings/tokens).
# Independent of LLM_PROVIDER/OFFLINE_MODE, which govern prose generation only.
HF_TOKEN: str = os.getenv("HF_TOKEN", "").strip()

# Codex SDK uses local ChatGPT login (no API key); we only need a model id.
CODEX_MODEL: str = os.getenv("CODEX_MODEL", "gpt-5.4").strip()

# Langfuse (real tracing, optional — see app/langfuse_sink.py). trace.py's local
# provenance log is always written regardless; when both keys are present it is
# ALSO mirrored to Langfuse. Missing keys -> LANGFUSE_ENABLED False, no-op sink.
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_BASE_URL: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()
LANGFUSE_ENABLED: bool = bool(LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY)

# Which LLM backend produces prose/answers. "offline" (default) uses deterministic
# seeds + cached fixtures — the safe, key-free demo path. Override in backend/.env.
#   offline | codex | openai | anthropic
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
    if LLM_PROVIDER == "codex":
        return True  # auth is external (ChatGPT login); runtime calls fall back if not ready
    if LLM_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if LLM_PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    return False


# Offline when no usable provider. Compliance pass/fail + citations are ALWAYS
# deterministic regardless of this flag; only prose/answers change.
OFFLINE_MODE: bool = not _provider_usable()

PROJECT_NAME = "Hyperscale DC — Chennai, 48 MW, Tier III (N+1)"

# CORS. Comma-separated list; defaults to local dev only. Set in production
# (e.g. Render env var) to the deployed frontend's origin, e.g.
# ALLOWED_ORIGINS=https://sitemind.vercel.app,http://localhost:3000
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# Standalone standards/company-upload retrieval package (Phase 3,
# backend/app/retrieval/) — OFF by default. When unset/0, main.py never even
# imports the retrieval router, so none of that package's code, models, or
# dependencies (rank_bm25, sentence-transformers) are touched at all. Set to
# 1 to mount /api/retrieval/* endpoints.
RETRIEVAL_ENABLED: bool = os.getenv("RETRIEVAL_ENABLED", "0").strip() == "1"

# Codebook (standards-service/, a separate process — see
# docs/BUILD_PLAN_CODEBOOK.md) MCP client — OFF by default. When unset/0,
# main.py never imports codebook_client.py/codebook_router.py, so the `mcp`
# client package is never touched at all (same import-gating discipline as
# RETRIEVAL_ENABLED above). Set to 1 to mount /api/codebook/* endpoints,
# which proxy to Codebook's own MCP server (standards-service/app/mcp_server.py)
# over CODEBOOK_MCP_URL — this backend becomes an MCP *client*, the browser UI
# still only ever talks to this backend, never to Codebook directly.
CODEBOOK_ENABLED: bool = os.getenv("CODEBOOK_ENABLED", "0").strip() == "1"
# standards-service/run.sh's own default port (8010 — 8000/8001 are already
# spoken for by manak-dev and this backend). Not hardcoded deeper than here.
CODEBOOK_MCP_URL: str = os.getenv("CODEBOOK_MCP_URL", "http://127.0.0.1:8010/mcp").strip()
