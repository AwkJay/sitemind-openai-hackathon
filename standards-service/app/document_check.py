"""`check_document_against_corpus` — Codebook's own reasoning primitive
(docs/BUILD_PLAN_CODEBOOK.md step 4). The one genuinely new piece of logic
in the whole Codebook build; everything else in this service is relocation.

Generalizes `backend/app/agents/checks.py` + `backend/app/ingest.py`'s
pattern (deterministic Python decision against a REAL fetched clause, LLM
only ever composes prose around a decision it is handed) into a reusable
primitive that works against ANY uploaded document + ANY corpus Codebook has
indexed — not hardcoded to the ~9 design-basis-params SiteMind's Compliance
Agent already knows about.

Pipeline, mirroring `agents/compliance.py`'s EXTRACT -> RETRIEVE -> DECIDE ->
EXPLAIN shape exactly, generalized:

  1. EXTRACT TEXT   — `retrieval.ingest.extract_text` (PDF/DOCX/txt/md;
     already-relocated, self-contained code — no import from `backend/`).
  2. CANDIDATE SENTENCES — split into sentences (reusing chunker.py's own
     paragraph/sentence-splitting + fuzzy raw-offset-locate helpers, so each
     candidate carries a real start_char/end_char into the original text,
     the same "verbatim + offsets, never re-typeset" discipline as every
     other extractor in this codebase), then keep only sentences that LOOK
     like a checkable numeric/threshold requirement: a number adjacent to a
     recognized engineering unit, OR a modal word ("shall"/"must"/
     "minimum"/"maximum"/"at least"/etc.) co-occurring with a number.
  3. RETRIEVE — call `Corpus.query` (the SAME hybrid BM25+dense+RRF index
     `search_standards` uses) directly, in-process — no MCP round-trip, per
     the spec ("call the underlying Python function directly").
  4. DECIDE — deterministic Python. The document sentence's value is
     compared against the MATCHED CLAUSE'S OWN stated threshold, IF AND
     ONLY IF: (a) the clause text itself yields a number+unit via the exact
     same extractor, (b) that clause's requirement has a determinable
     direction (a "not less than"/"minimum"/... or "not exceed"/
     "maximum"/... marker), and (c) the document's and the clause's units
     resolve to the same canonical unit. Any of those failing is a hard
     abstention (`NEEDS_REVIEW`) citing the real clause, never a guessed
     pass/fail — mirrors `ingest.py`'s `Abstention` pattern exactly, and is
     deliberately conservative: e.g. IS 3043:1987 Cl 22.2.3 states its earth
     grid resistance limit as the WORD "one ohm", not the digit "1" — this
     extractor does not parse number-words, so that real clause correctly
     abstains rather than fabricating a match, even though a human (and
     `agents/checks.py`'s hardcoded rule) knows the threshold is 1.0 ohm.
  5. EXPLAIN — `_compose_prose`: an LLM-composed explanation when a provider
     is configured (handed the decision + real clause text, never allowed
     to invent either), else a deterministic string template — exactly
     `agents/compliance.py`'s `_prose`/`_offline_prose` split, reimplemented
     here rather than imported (process-boundary rule).

KNOWN LIMITATIONS (stated plainly, not papered over):
  - Only digit-form numbers are extracted (no "one"/"two"/... word-numbers).
  - When a clause contains MULTIPLE number+unit pairs (e.g. a table with one
    row per exposure class), only the FIRST is used as "the" threshold —
    this is a real simplification vs. `agents/checks.py`'s exposure-aware
    logic, appropriate for a general primitive but not a full replacement
    for a hand-written check. Prefer simple, single-threshold clauses.
  - Unit compatibility is a canonical-string match, not a unit-conversion
    engine (e.g. it will NOT convert "cm" to "mm" for comparison) — a
    mismatch abstains rather than silently misconverting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from . import config, llm
from .retrieval import router as retrieval_router
from .retrieval.chunker import _SENTENCE_SPLIT, _iter_paragraphs, _locate_in_raw, _normalize
from .retrieval.index import Corpus, get_corpus, list_corpora
from .retrieval.ingest import extract_text

# --------------------------------------------------------------------------- #
# Sentence splitting with real char offsets into the ORIGINAL document text.
# Reuses chunker.py's own paragraph-iteration + fuzzy raw-locate helpers (the
# same technique `_fallback_chunks` uses for oversized paragraphs) — applied
# uniformly here since this module needs sentence-level granularity
# regardless of paragraph size, unlike the corpus chunker's own size gate.
# --------------------------------------------------------------------------- #
def _sentences_with_offsets(text: str) -> list[dict]:
    out: list[dict] = []
    for p_start, p_end, raw_para in _iter_paragraphs(text):
        norm_para = _normalize(raw_para)
        if not norm_para:
            continue
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(norm_para) if s.strip()]
        cursor = 0
        for sent in sentences:
            s_rel, e_rel = _locate_in_raw(raw_para, sent, cursor)
            cursor = e_rel
            out.append({"text": sent, "start_char": p_start + s_rel, "end_char": p_start + e_rel})
    return out


# --------------------------------------------------------------------------- #
# Generalized number+unit extraction — the shape of SiteMind's existing
# regex extractors (backend/app/ingest.py: _COVER_RE, _WC_RE, _RCD_RE,
# _EARTH_RESISTANCE_RE, ...), generalized to a single unit-alias table
# instead of ~9 hand-named patterns, so it works on requirements this
# service has never seen named before.
# --------------------------------------------------------------------------- #
_UNIT_ALIASES: dict[str, str] = {
    # length
    "mm": "mm", "millimeter": "mm", "millimetre": "mm", "millimeters": "mm", "millimetres": "mm",
    "cm": "cm", "centimeter": "cm", "centimetre": "cm",
    "km": "km",
    "m": "m", "meter": "m", "metre": "m", "meters": "m", "metres": "m",
    # pressure / stress
    "mpa": "mpa", "kpa": "kpa", "pa": "pa",
    # electrical resistance
    "megohm": "megohm", "megohms": "megohm", "mohm": "megohm", "mΩ": "megohm",
    "ohm": "ohm", "ohms": "ohm", "Ω": "ohm",
    # electrical current
    "ma": "ma", "milliamp": "ma", "milliamps": "ma", "milliampere": "ma", "milliamperes": "ma",
    "a": "a", "amp": "a", "amps": "a", "ampere": "a", "amperes": "a",
    # electrical voltage
    "kv": "kv", "kilovolt": "kv", "kilovolts": "kv",
    "v": "v", "volt": "v", "volts": "v",
    # force
    "kn": "kn", "n": "n", "newton": "n", "newtons": "n",
    # mass
    "kg": "kg",
    # temperature
    "c": "c", "°c": "c", "degc": "c", "celsius": "c",
    # frequency
    "hz": "hz",
    # time
    "hour": "hour", "hours": "hour", "hr": "hour", "hrs": "hour",
    "day": "day", "days": "day",
    "minute": "minute", "minutes": "minute", "min": "minute",
    # dimensionless / percentage
    "%": "%", "percent": "%",
    # discrete counts (e.g. "two separate connections")
    "connection": "count", "connections": "count",
    "point": "count", "points": "count",
    "way": "count", "ways": "count",
}
# Longest tokens first so a symbol/word alternative that is a PREFIX of
# another (e.g. "ohm" vs "ohms" vs "megohm") doesn't win by accident — though
# the trailing `(?![A-Za-z])` guard below already rejects a partial-token
# match on its own, this ordering keeps the pattern readable and is a second
# line of defense.
_UNIT_TOKENS = sorted(_UNIT_ALIASES.keys(), key=len, reverse=True)
_UNIT_ALT = "|".join(re.escape(u) for u in _UNIT_TOKENS)
# Number immediately (optional whitespace) followed by a recognized unit,
# rejected if the "unit" is actually a prefix of a longer word (e.g. "50 mm2"
# vs the bare "50 m" reading — `(?![A-Za-z])` blocks matching "m" out of "mm").
_NUMBER_UNIT_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNIT_ALT})(?![A-Za-z])", re.IGNORECASE)

# Modal/comparison-direction markers. ">=": the extracted value is a FLOOR
# (document/clause value must be at least this). "<=": a CEILING (must not
# exceed this). Order doesn't matter (see _direction_for — nearest marker by
# character distance to the number wins), but longer/more specific patterns
# are listed first for readability.
_GE_PATTERNS = [
    r"not\s+be\s+less\s+than", r"not\s+less\s+than", r"no\s+less\s+than",
    r"not\s+lower\s+than", r"not\s+below", r"at\s+least",
    r"minimum\s+of", r"minimum", r"or\s+more", r"or\s+greater", r">=",
]
_LE_PATTERNS = [
    r"shall\s+not\s+exceed", r"not\s+exceed(?:ing)?", r"not\s+more\s+than",
    r"no\s+more\s+than", r"not\s+above",
    r"maximum\s+of", r"maximum", r"or\s+less", r"<=",
]
_GE_RE = [re.compile(p, re.IGNORECASE) for p in _GE_PATTERNS]
_LE_RE = [re.compile(p, re.IGNORECASE) for p in _LE_PATTERNS]

# Broader modal-word check used ONLY to decide whether a sentence with a
# number but NO recognized unit still qualifies as a "candidate requirement
# sentence" per spec step 2 (it will still get searched + cited; it just
# cannot contribute a comparable value — see ExtractedValue's absence -> a
# NEEDS_REVIEW decision, never a guess).
_MODAL_RE = re.compile(
    r"\b(shall|must|required|minimum|maximum|at least|not less than|not more than|"
    r"not exceed|no more than|no less than|not below|not above)\b",
    re.IGNORECASE,
)
_ANY_DIGIT_RE = re.compile(r"\d")


def _direction_for(text: str, number_start: int) -> Optional[str]:
    """The comparison direction (">="/"<="/None) implied by the marker
    nearest (by character distance) to the number at `number_start` in
    `text`. None means no recognizable direction marker was found anywhere
    in the sentence — an honest "can't tell" rather than a default guess."""
    best_dist: Optional[int] = None
    best_dir: Optional[str] = None
    for rx, direction in [(r, ">=") for r in _GE_RE] + [(r, "<=") for r in _LE_RE]:
        for m in rx.finditer(text):
            dist = abs(m.start() - number_start)
            if best_dist is None or dist < best_dist:
                best_dist, best_dir = dist, direction
    return best_dir


@dataclass
class ExtractedValue:
    value: float
    unit: str  # canonical unit string
    raw_unit: str  # unit exactly as it appeared in the text
    direction: Optional[str]  # ">=" | "<=" | None
    match_text: str
    match_start: int
    match_end: int


def _extract_value(text: str) -> Optional[ExtractedValue]:
    """The FIRST number+recognized-unit pair in `text`, with its comparison
    direction (if any marker is present). Deliberately does NOT fall back to
    a bare unitless number: a clause's own prose commonly contains several
    numbers (table row labels, cross-references, other clause numbers) with
    no unit attached, and guessing "the" value among them would be exactly
    the fabrication risk this project exists to eliminate — abstain
    (return None) instead. See module docstring's "KNOWN LIMITATIONS"."""
    m = _NUMBER_UNIT_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    raw_unit = m.group(2)
    unit = _UNIT_ALIASES.get(raw_unit.lower(), raw_unit.lower())
    direction = _direction_for(text, m.start(1))
    return ExtractedValue(value, unit, raw_unit, direction, m.group(0), m.start(), m.end())


def _is_candidate(text: str) -> bool:
    """Step 2's filter: a number+unit anywhere, OR a modal word co-occurring
    with any digit (even without a recognized unit — kept as a candidate so
    it still gets searched + cited, per spec step 2's "or a modal ... and a
    value" clause; it just can't contribute a comparable value at step 4)."""
    if _NUMBER_UNIT_RE.search(text):
        return True
    return bool(_MODAL_RE.search(text)) and bool(_ANY_DIGIT_RE.search(text))


# --------------------------------------------------------------------------- #
# Retrieval — calls straight into the SAME Corpus.query hybrid index
# search_standards uses (app/mcp_server.py), in-process, no MCP round-trip.
# --------------------------------------------------------------------------- #
def _search(corpus_name: str, query: str, k: int) -> list[dict]:
    retrieval_router._ensure_loaded()
    corpus: Optional[Corpus] = get_corpus(corpus_name)
    if corpus is None:
        known = ", ".join(sorted(c.name for c in list_corpora())) or "(none loaded)"
        raise ValueError(f"No corpus named {corpus_name!r}. Known corpora: {known}.")
    return corpus.query(query, k=k)


# --------------------------------------------------------------------------- #
# Deterministic decision — the credibility-critical boundary. Never an LLM
# judgment call; a plain Python comparison, or an explicit abstention.
# --------------------------------------------------------------------------- #
def _decide(
    doc_val: Optional[ExtractedValue], clause_val: Optional[ExtractedValue]
) -> tuple[str, Optional[str]]:
    if doc_val is None:
        return "NEEDS_REVIEW", (
            "No comparable number+unit could be extracted from the document sentence "
            "(it matched only on a modal keyword) — abstaining rather than guessing a value."
        )
    if clause_val is None:
        return "NEEDS_REVIEW", (
            "The matched clause's own text does not contain a cleanly extractable "
            "comparable number+unit — abstaining rather than guessing a pass/fail decision "
            "against a threshold the clause doesn't actually state in extractable form."
        )
    if clause_val.direction is None:
        return "NEEDS_REVIEW", (
            "The matched clause states a number but no minimum/maximum direction marker "
            "(\"not less than\"/\"minimum\"/\"not exceed\"/\"maximum\"/...) could be found near "
            "it — abstaining rather than guessing which way the comparison should go."
        )
    if doc_val.unit != clause_val.unit:
        return "NEEDS_REVIEW", (
            f"Unit mismatch: the document states a value in {doc_val.unit!r} but the "
            f"matched clause's threshold is in {clause_val.unit!r} — abstaining rather than "
            "comparing incompatible quantities (no unit-conversion is performed)."
        )
    if clause_val.direction == ">=":
        conforms = doc_val.value >= clause_val.value
    else:
        conforms = doc_val.value <= clause_val.value
    return ("CONFORMS" if conforms else "NON_CONFORM"), None


# --------------------------------------------------------------------------- #
# Prose composition — LLM online (handed the decision, never deciding),
# deterministic string template offline. Mirrors
# backend/app/agents/compliance.py's _prose/_offline_prose split exactly.
# --------------------------------------------------------------------------- #
_EXPLAIN_SYSTEM = (
    "You are a compliance reviewer preparing a finding note for a data-centre "
    "construction project. You are GIVEN a sentence from an uploaded document, "
    "a REAL clause fetched verbatim from a standards corpus, and a decision "
    "(CONFORMS / NON_CONFORM / NEEDS_REVIEW) that has ALREADY been made "
    "deterministically in Python — it is not yours to make, question, or change. "
    "Never alter, invent, or paraphrase the clause text; quote it exactly as "
    "given if you quote it at all. Reply with ONLY a JSON object with keys "
    "finding, detail, action. Temperature 0."
)


def _fmt_val(v: Optional[ExtractedValue]) -> str:
    if v is None:
        return "(no comparable value extracted)"
    return f"{v.value} {v.unit}"


def _clause_ref(best: dict) -> str:
    return f"{best.get('corpus_name')}::{best.get('document_id')}::{best.get('chunk_id')}"


def _offline_prose(
    sentence: str,
    best: Optional[dict],
    doc_val: Optional[ExtractedValue],
    clause_val: Optional[ExtractedValue],
    decision: str,
    reason: Optional[str],
) -> dict:
    if best is None:
        return {
            "finding": f'Document states: "{sentence}"',
            "detail": reason or "No clause in this corpus cleared the retrieval floor for this sentence.",
            "action": "Route to a qualified reviewer for manual comparison against the relevant standard.",
        }
    clause_text = best.get("raw_text", best.get("text", ""))
    ref = _clause_ref(best)
    if decision in ("CONFORMS", "NON_CONFORM"):
        dir_word = "at least" if clause_val.direction == ">=" else "at most"
        verdict = "conforms to" if decision == "CONFORMS" else "does NOT conform to"
        return {
            "finding": f'Document states: "{sentence}" (extracted value {_fmt_val(doc_val)}).',
            "detail": (
                f"Matched clause {ref} requires {dir_word} {_fmt_val(clause_val)}: "
                f'"{clause_text}". The stated value {verdict} this requirement.'
            ),
            "action": (
                "No corrective action required for this requirement."
                if decision == "CONFORMS"
                else f"Revise the document's stated value to be {dir_word} {_fmt_val(clause_val)} and re-submit."
            ),
        }
    # NEEDS_REVIEW with a real matched clause
    return {
        "finding": f'Document states: "{sentence}".',
        "detail": f'Most relevant matched clause {ref}: "{clause_text}". {reason}',
        "action": "Route to a qualified reviewer for manual comparison against this clause.",
    }


def _compose_prose(
    sentence: str,
    best: Optional[dict],
    doc_val: Optional[ExtractedValue],
    clause_val: Optional[ExtractedValue],
    decision: str,
    reason: Optional[str],
) -> dict:
    offline_result = _offline_prose(sentence, best, doc_val, clause_val, decision, reason)
    if config.OFFLINE_MODE:
        return offline_result
    clause_text = best.get("raw_text", best.get("text", "")) if best else ""
    user = (
        f"Document sentence: {sentence!r}\n"
        f"Extracted document value: {_fmt_val(doc_val)}\n"
        f"Matched clause ({_clause_ref(best) if best else 'none'}): {clause_text!r}\n"
        f"Extracted clause threshold: {_fmt_val(clause_val)} "
        f"(direction: {clause_val.direction if clause_val else 'n/a'})\n"
        f"DECISION (already made, do not change): {decision}\n"
        f"Reason (if abstained): {reason or 'n/a'}\n\n"
        "Write finding (1 sentence restating what the document states), "
        "detail (1-2 sentences citing the clause and explaining the decision), "
        "action (1 concrete next step)."
    )
    out = llm.complete_json(_EXPLAIN_SYSTEM, user)
    if not out or not all(k in out for k in ("finding", "detail", "action")):
        return offline_result  # robust fallback — an LLM hiccup never blocks a result
    return out


# --------------------------------------------------------------------------- #
# Finding assembly
# --------------------------------------------------------------------------- #
def _val_dict(v: Optional[ExtractedValue]) -> Optional[dict]:
    if v is None:
        return None
    return {
        "value": v.value,
        "unit": v.unit,
        "raw_unit": v.raw_unit,
        "direction": v.direction,
        "matched_text": v.match_text,
    }


def _build_finding(
    cand: dict,
    best: Optional[dict],
    doc_val: Optional[ExtractedValue],
    clause_val: Optional[ExtractedValue],
    decision: str,
    reason: Optional[str],
) -> dict:
    prose = _compose_prose(cand["text"], best, doc_val, clause_val, decision, reason)
    finding = {
        "source_sentence": cand["text"],
        "source_start_char": cand["start_char"],
        "source_end_char": cand["end_char"],
        "extracted_document_value": _val_dict(doc_val),
        "decision": decision,
        "abstain_reason": reason if decision == "NEEDS_REVIEW" else None,
        "matched_clause": None,
        "prose": prose,
    }
    if best is not None:
        finding["matched_clause"] = {
            "corpus_name": best.get("corpus_name"),
            "document_id": best.get("document_id"),
            "chunk_id": best.get("chunk_id"),
            "filename": best.get("filename"),
            "heading": best.get("heading"),
            "breadcrumb": best.get("breadcrumb"),
            "text": best.get("raw_text", best.get("text", "")),  # verbatim — never re-typeset
            "provenance_tag": best.get("provenance_tag"),
            "score": best.get("score"),
            "extracted_clause_value": _val_dict(clause_val),
        }
    return finding


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def check_document_against_corpus(
    document_path: Union[str, Path], corpus_name: str, k: int = 3
) -> list[dict]:
    """Extract candidate requirement sentences from the document at
    `document_path`, search `corpus_name` for the most relevant real clause
    per sentence, and deterministically decide CONFORMS / NON_CONFORM /
    NEEDS_REVIEW for each — never inventing or paraphrasing clause text,
    never letting an LLM decide. See module docstring for the full pipeline
    and its stated limitations.

    Raises FileNotFoundError if `document_path` doesn't exist, ValueError if
    `corpus_name` isn't a currently-loaded corpus, and propagates
    `retrieval.ingest.UnsupportedFileType` for an unsupported extension —
    same hard-error discipline as the rest of this service's MCP tools."""
    path = Path(document_path)
    if not path.exists():
        raise FileNotFoundError(f"No file at {path}")
    content = path.read_bytes()
    text = extract_text(path.name, content)
    if not text.strip():
        return []

    candidates = [s for s in _sentences_with_offsets(text) if _is_candidate(s["text"])]

    findings: list[dict] = []
    for cand in candidates:
        hits = _search(corpus_name, cand["text"], k=k)
        doc_val = _extract_value(cand["text"])
        if not hits:
            findings.append(
                _build_finding(
                    cand,
                    None,
                    doc_val,
                    None,
                    "NEEDS_REVIEW",
                    "No clause in this corpus cleared the retrieval floor for this sentence "
                    "— abstaining rather than citing an irrelevant match.",
                )
            )
            continue
        best = hits[0]
        clause_val = _extract_value(best.get("raw_text", best.get("text", "")))
        decision, reason = _decide(doc_val, clause_val)
        findings.append(_build_finding(cand, best, doc_val, clause_val, decision, reason))
    return findings
