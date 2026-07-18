"""Provider-dispatching LLM wrapper for Codebook (standards-service).

Mirrors `backend/app/llm.py`'s shape and every one of its safety properties
(temperature 0, best-effort try/except returning "" on ANY failure, lazy
provider imports) but is a fresh, independent module — no import from
`backend/`, per the process-boundary rule. Codex is deliberately omitted
(see `config.py`'s docstring for why).

`document_check.check_document_against_corpus`'s pass/fail DECISION never
comes from this module — only prose composed AROUND a decision it is handed.
Every backend call failing (missing package, bad auth, network error, no
provider configured) returns "" so the caller always has a safe fallback to
the deterministic offline template — this module can never crash a request.
"""
from __future__ import annotations

import json
from typing import Optional

from . import config


# --------------------------------------------------------------------------- #
# OpenAI API backend
# --------------------------------------------------------------------------- #
def _openai_complete(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI  # lazy: only needed if LLM_PROVIDER == "openai"

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=0,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- #
# Anthropic backend
# --------------------------------------------------------------------------- #
def _anthropic_complete(system: str, user: str, max_tokens: int) -> str:
    import anthropic  # lazy: only needed if LLM_PROVIDER == "anthropic"

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL_SMART,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def complete_text(system: str, user: str, max_tokens: int = 800) -> str:
    """Single-turn completion (temperature 0). Returns "" on any failure
    (including LLM_PROVIDER == "offline") so the caller falls back to the
    deterministic/offline path."""
    provider = config.LLM_PROVIDER
    try:
        if provider == "openai":
            return _openai_complete(system, user, max_tokens)
        if provider == "anthropic":
            return _anthropic_complete(system, user, max_tokens)
    except Exception:
        return ""  # never let an LLM hiccup crash a request
    return ""  # offline / unknown provider


def complete_json(system: str, user: str, max_tokens: int = 800) -> Optional[dict]:
    """complete_text + parse JSON; None on failure (tolerates ```json fences)."""
    txt = complete_text(system, user, max_tokens).strip()
    if not txt:
        return None
    if txt.startswith("```"):
        txt = txt.strip("`")
        txt = txt[txt.find("{") :]
    try:
        return json.loads(txt[txt.find("{") : txt.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        return None
