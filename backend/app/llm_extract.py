"""LLM-powered PERCEIVE step for Pillar 1 — the "intelligent" upload path.

This is what the deck/PDF mean by *"Claude Sonnet 4.6, via the Claude Agent SDK,
extracts each parameter behind a span-verification gate."* It replaces the brittle
regex reader (`ingest.py`) with a Claude call **only for perception**, then hands
every candidate through a deterministic, pure-Python **span-verification gate**
before anything reaches the check registry. The model never decides pass/fail and
can never launder a hallucinated number: a value only survives if its verbatim
source span is literally present in the uploaded document.

Design (integrity core — read `docs/later_changes.md` §P0.1):
  1. Claude returns a JSON array, one object per parameter it can quote verbatim.
  2. `verify_spans()` (NO LLM) drops anything whose span is not literally in the
     document, whose value is not inside that span, or whose type is not a
     checkable type. Survivors become the SAME `ExtractedParam` dataclass the regex
     path emits, so they flow through `to_param_dicts -> evaluate -> checks.py`
     unchanged.
  3. Regex extraction runs too and acts as a **floor**: results are unioned so the
     LLM path can only ever do *better* than today, never worse. On any LLM error,
     missing auth, or OFFLINE_MODE, we fall back to pure regex — an upload never
     fails because the model was unavailable.

Auth: the Claude Agent SDK uses your Claude Code login (a subscription token via
`claude setup-token` -> CLAUDE_CODE_OAUTH_TOKEN in backend/.env). No API key.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from . import config, ingest
from .ingest import Abstention, ExtractedParam

# --------------------------------------------------------------------------- #
# The checkable parameter enum — MUST match agents/checks.py. The model is given
# this list + a one-line definition; anything it returns outside it is dropped.
# --------------------------------------------------------------------------- #
CHECKABLE_TYPES: dict[str, str] = {
    "nominal_cover": "clear/nominal concrete cover to reinforcement, in mm (element must be a footing or a column).",
    "concrete_grade": "concrete grade as the number after 'M' (e.g. M30 -> 30), in MPa.",
    "wc_ratio": "free water-cement ratio, a decimal like 0.45.",
    "long_steel_pct": "longitudinal reinforcement steel as a percentage of a column's gross area.",
    "importance_factor": "seismic importance factor I (e.g. 1.0, 1.5).",
    "rcd_rated_current_ma": "rated residual operating current of an RCD on a socket-outlet circuit, in mA.",
    "earth_grid_resistance_ohm": "measured continuity/earth resistance of the earth GRID, in ohm.",
    "frame_earth_connections_count": "number of separate earth connections to a generator/transformer FRAME.",
    "neutral_earth_connections_count": "number of separate earth connections to a generator/transformer NEUTRAL point.",
}

# Deterministic unit normalisation (the model's unit string is advisory only).
_UNIT_BY_TYPE: dict[str, str] = {
    "nominal_cover": "mm",
    "concrete_grade": "MPa",
    "wc_ratio": "ratio",
    "long_steel_pct": "%",
    "importance_factor": "factor",
    "rcd_rated_current_ma": "mA",
    "earth_grid_resistance_ohm": "ohm",
    "frame_earth_connections_count": "connections",
    "neutral_earth_connections_count": "connections",
}

_EXPOSURE_WORDS = ("very severe", "extreme", "severe", "moderate", "mild")
_MARINE_WORDS = ("marine", "sea-water", "sea water", "coastal", "transformer-yard", "transformer yard")


# --------------------------------------------------------------------------- #
# Deterministic span-verification gate — the integrity core. NO LLM in here.
# Independently unit-testable with hand-written `raw_items` (no key needed).
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    """Collapse all whitespace and strip. Used for verbatim-substring checks so a
    line-wrapped span still matches the source, but nothing else is altered."""
    return re.sub(r"\s+", " ", s or "").strip()


def _value_str_variants(value: float) -> list[str]:
    """String forms a written number might take: '30', '30.0', '0.45', '1.8'."""
    out = {repr(value), str(value)}
    if float(value).is_integer():
        out.add(str(int(value)))
    else:
        out.add(f"{value:g}")
    return [v for v in out if v]


def _element_type_for(param_type: str, element_type: str, span_low: str) -> Optional[str]:
    if param_type == "nominal_cover":
        # cover is only checkable for a footing or a column (checks.py contract).
        if "footing" in span_low or (element_type or "").lower() == "footing":
            return "footing"
        if "column" in span_low or (element_type or "").lower() == "column":
            return "column"
        return None  # cover with no recoverable element -> drop, don't guess
    return element_type or "general"


def _verified_context(param_type: str, context: dict, span_low: str) -> dict:
    """Keep only context flags that are themselves grounded in the span — a
    severity-driving flag (marine, exposure) must be quotable, not inferred."""
    out: dict = {}
    ctx = context or {}
    if param_type in ("nominal_cover", "wc_ratio"):
        for w in _EXPOSURE_WORDS:
            if w in span_low:
                out["exposure"] = w
                break
    if param_type == "concrete_grade":
        out["marine"] = any(w in span_low for w in _MARINE_WORDS)
    if param_type == "rcd_rated_current_ma" and "socket" in span_low:
        out["circuit_type"] = "socket_outlet"
    return out


def verify_spans(raw_items: list[dict], text: str) -> tuple[list[ExtractedParam], list[Abstention]]:
    """Pure-Python gate. `raw_items` is whatever the model proposed (list of dicts).
    Returns (verified ExtractedParams, abstentions for everything dropped)."""
    doc_norm = _norm(text)
    doc_low = doc_norm.lower()
    found: list[ExtractedParam] = []
    abstained: list[Abstention] = []

    def drop(pt: str, why: str) -> None:
        abstained.append(Abstention(param=pt or "unknown", reason=why))

    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        param_type = str(item.get("param_type") or item.get("param") or "").strip()
        span = str(item.get("verbatim_source_span") or item.get("source_quote") or "").strip()
        raw_value = item.get("value")

        # (d) type must be a checkable type
        if param_type not in CHECKABLE_TYPES:
            drop(param_type, f"'{param_type}' is not a check-registry parameter type — dropped.")
            continue
        # value must be numeric
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            drop(param_type, "model returned a non-numeric value — dropped, not guessed.")
            continue
        if not span:
            drop(param_type, "model returned no verbatim source span — dropped.")
            continue

        span_norm = _norm(span)
        # (a) span must appear literally in the document
        if span_norm.lower() not in doc_low:
            drop(param_type, "the quoted source span is not verbatim in the document — dropped as a possible hallucination.")
            continue
        # (b) the value must appear inside that span
        if not any(v in span_norm for v in _value_str_variants(value)):
            drop(param_type, "the value is not written inside its own quoted span — dropped.")
            continue

        span_low = span_norm.lower()
        element_type = _element_type_for(param_type, str(item.get("element_type") or ""), span_low)
        if element_type is None:
            drop(param_type, "cover found but the element (footing/column) was not recoverable from the span — dropped.")
            continue

        element = str(item.get("element") or "").strip() or f"{element_type.title()} (from uploaded document)"
        found.append(
            ExtractedParam(
                param=param_type,
                element=element,
                element_type=element_type,
                value=value,
                unit=_UNIT_BY_TYPE[param_type],
                context=_verified_context(param_type, item.get("context") or {}, span_low),
                source_quote=span_norm,
                source_location="uploaded document (LLM-extracted, span-verified)",
            )
        )
    return found, abstained


# --------------------------------------------------------------------------- #
# The Claude Agent SDK call — PERCEIVE only. Returns raw dicts (unverified).
# --------------------------------------------------------------------------- #
def _build_prompt(text: str) -> tuple[str, str]:
    enum_lines = "\n".join(f"  - {k}: {v}" for k, v in CHECKABLE_TYPES.items())
    system = (
        "You are a structural/electrical parameter EXTRACTOR for an Indian-code compliance engine. "
        "You do NOT judge compliance; you only quote what the document states.\n"
        "Return ONLY a JSON array. Each element is an object with keys: "
        '"param_type", "element", "element_type", "value" (a number), "unit", '
        '"verbatim_source_span", "context" (object; may be empty).\n'
        "Hard rules:\n"
        "  1. param_type MUST be exactly one of these; ignore anything else:\n"
        f"{enum_lines}\n"
        "  2. verbatim_source_span MUST be an EXACT substring of the document text, copied "
        "character-for-character (a sentence or clause containing the value). If you cannot quote "
        "it verbatim, OMIT the parameter.\n"
        "  3. The numeric value MUST appear literally inside verbatim_source_span.\n"
        "  4. Never infer, convert, or compute a value that is not written in the document.\n"
        "  5. For context, you may add {\"exposure\": \"severe|very severe|...\"}, {\"marine\": true}, "
        "or {\"circuit_type\": \"socket_outlet\"} ONLY when those words appear in the span.\n"
        "Output the JSON array and nothing else — no prose, no markdown fences."
    )
    user = f"Extract every checkable parameter from this document:\n\n{text}"
    return system, user


async def _call_claude_agent_sdk(text: str) -> Optional[list[dict]]:
    """One-shot extraction via the Claude Agent SDK (Claude Code subscription auth).
    Returns a list of raw dicts, or None on any failure so the caller falls back."""
    try:
        from claude_agent_sdk import (  # lazy: only imported on the LLM path
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )
    except Exception:
        return None

    system, user = _build_prompt(text)
    options = ClaudeAgentOptions(
        system_prompt=system,
        model=config.ANTHROPIC_MODEL_SMART,  # "claude-sonnet-4-6"
        max_turns=1,
        allowed_tools=[],          # pure text-in/JSON-out; no file/bash tools
        setting_sources=None,      # do NOT load project CLAUDE.md / settings
        permission_mode="default",
    )
    parts: list[str] = []
    try:
        async for msg in query(prompt=user, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
    except Exception:
        return None

    raw = "".join(parts).strip()
    return _parse_json_array(raw)


def _parse_json_array(raw: str) -> Optional[list[dict]]:
    """Tolerant JSON-array parse (handles ```json fences and leading prose)."""
    if not raw:
        return None
    if "```" in raw:
        raw = raw.split("```")[1] if raw.count("```") >= 2 else raw
        raw = raw[raw.find("[") if "[" in raw else 0:]
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, list) else None


# --------------------------------------------------------------------------- #
# Public entry point — LLM-first with a deterministic regex floor + fallback.
# --------------------------------------------------------------------------- #
def _dedup_union(regex_found: list[ExtractedParam], llm_found: list[ExtractedParam]) -> list[ExtractedParam]:
    """Regex is the floor: keep every regex hit, then add LLM hits that name a
    genuinely different (param_type, element_type, value). On a tie, the regex
    result wins (it carries the hand-tuned context that the demo baseline needs)."""
    def key(p: ExtractedParam) -> tuple:
        return (p.param, p.element_type, round(float(p.value), 4))

    out = list(regex_found)
    seen = {key(p) for p in regex_found}
    for p in llm_found:
        if key(p) not in seen:
            out.append(p)
            seen.add(key(p))
    return out


def llm_enabled() -> bool:
    """LLM extraction is used only when explicitly enabled by its own flag.

    Deliberately NOT gated on config.OFFLINE_MODE: OFFLINE_MODE tracks whether a
    metered *API key* is present for prose generation, but LLM extraction runs on
    the Claude Code *subscription* (CLAUDE_CODE_OAUTH_TOKEN / a logged-in CLI) —
    the whole point of this path is that there is no API key. Auth failures are
    handled at call time by falling back to regex, so this gate stays simple."""
    return config.LLM_EXTRACTION_ENABLED


async def extract_params(text: str) -> tuple[list[ExtractedParam], list[Abstention]]:
    """The smart PERCEIVE entry point used by POST /api/compliance/ingest.

    Always computes the regex result (the floor). When LLM extraction is enabled
    and succeeds, unions in the span-verified LLM finds. On any failure it returns
    exactly the regex result — identical to the pre-LLM behaviour."""
    regex_found, regex_abstained = ingest.extract_params(text)

    if not llm_enabled():
        return regex_found, regex_abstained

    raw_items = await _call_claude_agent_sdk(text)
    if raw_items is None:  # no auth / SDK missing / model error -> safe fallback
        return regex_found, regex_abstained

    llm_found, _llm_dropped = verify_spans(raw_items, text)
    merged = _dedup_union(regex_found, llm_found)

    # Any always-abstain / regex-missed type the LLM did surface is no longer an
    # abstention; drop those entries from the regex abstention list.
    surfaced = {p.param for p in merged}
    abstained = [a for a in regex_abstained if a.param not in surfaced]
    return merged, abstained
