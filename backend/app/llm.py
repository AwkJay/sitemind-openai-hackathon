"""Provider-dispatching LLM wrapper.

SiteMind's compliance pass/fail + citations are ALWAYS deterministic (Python +
clauses.json) — this module only produces *prose* (NCR wording) and *copilot
answers*, and only when a provider is configured (OFFLINE_MODE is False).

Providers (set LLM_PROVIDER in backend/.env):
  offline   — never calls out; callers use deterministic seeds / cached fixtures.
  codex     — OpenAI Codex SDK via local ChatGPT login (no API key). See docs/CODEX_SETUP.md.
  openai    — OpenAI API (needs OPENAI_API_KEY).
  anthropic — Anthropic API (needs ANTHROPIC_API_KEY).

Every backend is best-effort: on import error, auth failure, or any exception we
return "" so the caller falls back to the offline path. Nothing here can crash a
request — important for a live demo. The clause TEXT is always handed to the model
and the Citation is filled programmatically from the cache, so citations are real
regardless of which provider (or none) writes the prose.
"""
from __future__ import annotations

import atexit
import json
from typing import Optional

from . import config


# --------------------------------------------------------------------------- #
# Codex backend (OpenAI Codex SDK, ChatGPT login). Reuse one app-server.
# --------------------------------------------------------------------------- #
_codex_cm = None  # the Codex() context manager
_codex = None     # the entered Codex instance


def _get_codex():
    global _codex_cm, _codex
    if _codex is None:
        from openai_codex import Codex  # lazy: only needed for this provider

        _codex_cm = Codex()
        _codex = _codex_cm.__enter__()

        @atexit.register
        def _close():  # pragma: no cover - process teardown
            try:
                _codex_cm.__exit__(None, None, None)
            except Exception:
                pass

    return _codex


def _codex_complete(system: str, user: str) -> str:
    from openai_codex import Sandbox

    codex = _get_codex()
    # read_only sandbox => the coding agent cannot edit files or mutate the repo;
    # we only want pure text generation.
    thread = codex.thread_start(model=config.CODEX_MODEL, sandbox=Sandbox.read_only)
    prompt = (
        f"{system}\n\n{user}\n\n"
        "Respond with ONLY the requested content (text or JSON). Do not run "
        "commands, do not edit files, do not explain your process."
    )
    result = thread.run(prompt)
    return (getattr(result, "final_response", "") or "").strip()


# --------------------------------------------------------------------------- #
# OpenAI API backend
# --------------------------------------------------------------------------- #
def _openai_complete(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI

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
    import anthropic

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
    """Single-turn completion (temperature 0). Returns "" on any failure so the
    caller can fall back to the deterministic/offline path."""
    provider = config.LLM_PROVIDER
    try:
        if provider == "codex":
            return _codex_complete(system, user)
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
