"""Real document ingestion for Pillar 1 — POST /api/compliance/ingest.

This is the honesty-critical module: it reads an ACTUAL uploaded PDF/DOCX/text
file (not a pre-stored fixture) and extracts ONLY the parameter types the
CHECK REGISTRY (`agents/checks.py`) knows how to evaluate. For every parameter
type it does not confidently find with an exact source sentence, it emits an
explicit ABSTENTION rather than guessing — never presented as a conforming or
non-conforming result. Extraction is regex/heuristic, not an LLM: a wrong regex
match is instantly auditable against the shown source_quote, so it cannot
launder a hallucination the way a free-form LLM extraction could.

Extracted params share the exact shape of design_basis_params.json entries, so
they can be checked through the existing deterministic pipeline unchanged.
"""
from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Text extraction — dispatch by file type. Real parsing, not a stub.
# --------------------------------------------------------------------------- #
class UnsupportedFileType(ValueError):
    pass


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    if name.endswith(".docx"):
        return _extract_docx(content)
    if name.endswith((".txt", ".md")):
        return content.decode("utf-8", errors="replace")
    raise UnsupportedFileType(
        f"Unsupported file type for '{filename}'. Accepted: .pdf, .docx, .txt, .md"
    )


def _extract_pdf(content: bytes) -> str:
    import pdfplumber  # imported lazily so offline/no-upload paths never need it

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(content: bytes) -> str:
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


# --------------------------------------------------------------------------- #
# Sentence splitting
# --------------------------------------------------------------------------- #
_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9])")
_BLOCK_SPLIT = re.compile(r"\n\s*\n|\n(?=[A-Z][a-zA-Z ]{0,30}\s*(?:Note)?\s*\d*\s*:)")


def _sentences(text: str) -> list[str]:
    # Split on blank lines / "Label N:" line starts first (so a heading or note
    # number doesn't get glued onto the next paragraph's sentence), THEN split
    # each block into sentences. A line wrap inside one sentence still collapses.
    blocks = [b.strip() for b in _BLOCK_SPLIT.split(text) if b.strip()]
    out: list[str] = []
    for block in blocks:
        flat = re.sub(r"\s+", " ", block).strip()
        if not flat:
            continue
        out.extend(s.strip() for s in _SENTENCE_SPLIT.split(flat) if s.strip())
    return out


# --------------------------------------------------------------------------- #
# Narrow extractors — one per parameter type the CHECK REGISTRY consumes.
# Each returns a list of hits: (element_hint, element_type, value, unit, context, sentence)
# --------------------------------------------------------------------------- #
@dataclass
class ExtractedParam:
    param: str
    element: str
    element_type: str
    value: float
    unit: str
    context: dict = field(default_factory=dict)
    source_quote: str = ""
    source_location: str = "uploaded document"


@dataclass
class Abstention:
    param: str
    reason: str


_COVER_RE = re.compile(
    r"(?i)\bcover\b(?:[^.;]{0,120}?)(\d+(?:\.\d+)?)\s*mm"
    r"|(\d+(?:\.\d+)?)\s*mm(?:[^.;]{0,60}?)\bcover\b"
)


def _cover_value(m: "re.Match") -> float:
    return float(m.group(1) if m.group(1) is not None else m.group(2))
_ELEMENT_CODE_RE = re.compile(r"\b([A-Za-z]{1,3}-\d{1,3})\b")


def _extract_cover(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _COVER_RE.search(s)
        if not m:
            continue
        low = s.lower()
        if "footing" in low:
            element_type = "footing"
        elif "column" in low:
            element_type = "column"
        else:
            continue  # cover mentioned but element type unrecoverable — skip, don't guess
        code = _ELEMENT_CODE_RE.search(s)
        element = f"{element_type.title()} {code.group(1)}" if code else element_type.title()
        exposure = None
        for word in ("very severe", "extreme", "severe", "moderate", "mild"):
            if word in low:
                exposure = word
                break
        hits.append(
            ExtractedParam(
                param="nominal_cover",
                element=element,
                element_type=element_type,
                value=_cover_value(m),
                unit="mm",
                context={"exposure": exposure} if exposure else {},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_GRADE_RE = re.compile(r"(?i)\bM\s?-?(\d{2,3})\b")


def _extract_concrete_grade(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        low = s.lower()
        if "concrete" not in low and "grade" not in low and "rcc" not in low:
            continue
        m = _GRADE_RE.search(s)
        if not m:
            continue
        marine = any(w in low for w in ("marine", "sea-water", "sea water", "coastal", "transformer-yard", "transformer yard"))
        hits.append(
            ExtractedParam(
                param="concrete_grade",
                element="Concrete (from uploaded document)",
                element_type="general",
                value=float(m.group(1)),
                unit="MPa",
                context={"marine": marine},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_WC_RE = re.compile(r"(?i)water[-\s]?cement\s+ratio[^.;]{0,100}?(\d\.\d+)")


def _extract_wc_ratio(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _WC_RE.search(s)
        if not m:
            continue
        low = s.lower()
        exposure = None
        for word in ("very severe", "extreme", "severe", "moderate", "mild"):
            if word in low:
                exposure = word
                break
        hits.append(
            ExtractedParam(
                param="wc_ratio",
                element="Structural concrete (from uploaded document)",
                element_type="general",
                value=float(m.group(1)),
                unit="ratio",
                context={"exposure": exposure} if exposure else {},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_STEEL_PCT_RE = re.compile(
    r"(?i)longitudinal[^.;]{0,60}?(\d+(?:\.\d+)?)\s*(?:percent|%)"
)


def _extract_long_steel_pct(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        low = s.lower()
        if "column" not in low:
            continue
        m = _STEEL_PCT_RE.search(s)
        if not m:
            continue
        code = _ELEMENT_CODE_RE.search(s)
        element = f"Column {code.group(1)}" if code else "Column"
        hits.append(
            ExtractedParam(
                param="long_steel_pct",
                element=element,
                element_type="column",
                value=float(m.group(1)),
                unit="%",
                context={},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_IMPORTANCE_RE = re.compile(
    r"(?i)importance\s+factor[^.;]{0,100}?(?:I\s*=?\s*)?(\d(?:\.\d+)?)"
)


def _extract_importance_factor(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        if "importance factor" not in s.lower():
            continue
        m = _IMPORTANCE_RE.search(s)
        if not m:
            continue
        hits.append(
            ExtractedParam(
                param="importance_factor",
                element="Primary structure (seismic basis)",
                element_type="general",
                value=float(m.group(1)),
                unit="factor",
                context={},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_RCD_RE = re.compile(
    r"(?i)residual current device[^.;]{0,80}?(\d+(?:\.\d+)?)\s*mA"
)

_EARTH_RESISTANCE_RE = re.compile(
    r"(?i)earth[^.;]{0,40}resistance[^.;]{0,60}?(\d+(?:\.\d+)?)\s*\bohm\b"
)


def _extract_earth_grid_resistance(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _EARTH_RESISTANCE_RE.search(s)
        if not m:
            continue
        low = s.lower()
        if "grid" not in low:
            continue  # the checked rule is specifically the earth GRID's continuity resistance
        hits.append(
            ExtractedParam(
                param="earth_grid_resistance_ohm",
                element="Earth grid (from uploaded document)",
                element_type="general",
                value=float(m.group(1)),
                unit="ohm",
                context={},
                source_quote=s,
            )
        )
    return hits, bool(hits)


def _extract_rcd_rated_current(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _RCD_RE.search(s)
        if not m:
            continue
        low = s.lower()
        if "socket" not in low:
            continue  # the checked rule is specifically socket-outlet circuits; don't guess scope
        hits.append(
            ExtractedParam(
                param="rcd_rated_current_ma",
                element="Socket-outlet circuit (from uploaded document)",
                element_type="socket_outlet",
                value=float(m.group(1)),
                unit="mA",
                context={"circuit_type": "socket_outlet"},
                source_quote=s,
            )
        )
    return hits, bool(hits)


_FRAME_EARTH_RE = re.compile(
    r"(?i)(generator|transformer)[^.;]{0,40}frame[^.;]{0,60}?earthed[^.;]{0,30}?(\d+)\s*(?:separate|distinct)"
)
_NEUTRAL_EARTH_RE = re.compile(
    r"(?i)neutral[^.;]{0,40}?earthed[^.;]{0,30}?(\d+)\s*(?:separate|distinct)"
)


def _extract_frame_earthing(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _FRAME_EARTH_RE.search(s)
        if not m:
            continue
        hits.append(
            ExtractedParam(
                param="frame_earth_connections_count",
                element=f"{m.group(1).title()} frame (from uploaded document)",
                element_type="general",
                value=float(m.group(2)),
                unit="connections",
                context={},
                source_quote=s,
            )
        )
    return hits, bool(hits)


def _extract_neutral_earthing(sentences: list[str]) -> tuple[list[ExtractedParam], bool]:
    hits: list[ExtractedParam] = []
    for s in sentences:
        m = _NEUTRAL_EARTH_RE.search(s)
        if not m:
            continue
        hits.append(
            ExtractedParam(
                param="neutral_earth_connections_count",
                element="Generator/transformer neutral point (from uploaded document)",
                element_type="general",
                value=float(m.group(1)),
                unit="connections",
                context={},
                source_quote=s,
            )
        )
    return hits, bool(hits)


# Parameter types the CHECK REGISTRY can evaluate but this extractor deliberately
# does NOT attempt, because a reliable value needs numeric context (e.g. site
# basic wind speed, longitudinal bar diameter) that free text rarely states
# unambiguously next to the target number. Guessing here would be exactly the
# kind of extraction hallucination the product promises never to produce.
_ALWAYS_ABSTAIN = {
    "design_wind_speed": "requires the site's code basic wind speed Vb for comparison; not reliably separable from prose without structured input.",
    "design_wind_pressure": "requires the corresponding design wind speed Vz to validate pz = 0.6*Vz^2; provide via structured submission.",
    "tie_spacing": "requires the column's least lateral dimension and longitudinal bar diameter to evaluate the governing limit; provide via structured submission.",
    "insulation_resistance_megohm": "requires the number of points on the circuit (the required minimum is 50/N, capped at 1 megohm) — free text rarely states both the measured value and the point count unambiguously in one sentence; provide via structured submission.",
    "rcd_touch_voltage_check": "requires BOTH the earth electrode resistance (ohm) and the RCD's rated residual current (A) unambiguously paired to the same circuit in one sentence, to compute RA x I(delta n) against the 50V limit — too easy to misattribute two separately-stated numbers to the wrong circuit from free text; provide via structured submission.",
    "insulation_resistance_voltage_class_megohm": "requires the circuit's nominal voltage class (SELV/PELV, up to 500V, or above 500V) unambiguously paired with the measured megohm value per IS 732:2019 Table 15 — classifying voltage class from free prose risks misreading which threshold tier applies; provide via structured submission.",
}

_EXTRACTORS = [
    ("nominal_cover", _extract_cover),
    ("concrete_grade", _extract_concrete_grade),
    ("wc_ratio", _extract_wc_ratio),
    ("long_steel_pct", _extract_long_steel_pct),
    ("importance_factor", _extract_importance_factor),
    ("rcd_rated_current_ma", _extract_rcd_rated_current),
    ("earth_grid_resistance_ohm", _extract_earth_grid_resistance),
    ("frame_earth_connections_count", _extract_frame_earthing),
    ("neutral_earth_connections_count", _extract_neutral_earthing),
]


def extract_params(text: str) -> tuple[list[ExtractedParam], list[Abstention]]:
    """Run every narrow extractor; return (found, abstained). Never guesses."""
    sentences = _sentences(text)
    found: list[ExtractedParam] = []
    abstained: list[Abstention] = []

    for param_name, fn in _EXTRACTORS:
        hits, ok = fn(sentences)
        if ok:
            found.extend(hits)
        else:
            abstained.append(
                Abstention(
                    param=param_name,
                    reason="No sentence in the document matched this parameter with high "
                    "enough confidence to extract a value and element — abstaining rather "
                    "than guessing.",
                )
            )

    for param_name, reason in _ALWAYS_ABSTAIN.items():
        abstained.append(Abstention(param=param_name, reason=reason))

    return found, abstained


def to_param_dicts(found: list[ExtractedParam]) -> list[dict]:
    """Shape extracted params exactly like design_basis_params.json entries — and
    flatten `context` onto the top level the same way data_loader._flatten() does
    — so they flow through the existing deterministic check pipeline unchanged."""
    from .data_loader import _flatten  # local import: avoid a module cycle at import time

    out = []
    for i, p in enumerate(found, start=1):
        raw = {
            "id": f"UP-{i:02d}",
            "element": p.element,
            "element_type": p.element_type,
            "param": p.param,
            "value": p.value,
            "unit": p.unit,
            "context": p.context,
            "source_quote": p.source_quote,
            "source_location": p.source_location,
        }
        out.append(_flatten(raw))
    return out


# --------------------------------------------------------------------------- #
# In-memory store for uploaded-document params, keyed by a generated document_id.
# The demo server is single-process; this is intentionally not persisted.
# --------------------------------------------------------------------------- #
_UPLOADS: dict[str, dict] = {}


def register_upload(title: str, params: list[dict], abstained: list[Abstention]) -> str:
    document_id = f"UPLOAD-{uuid.uuid4().hex[:8].upper()}"
    _UPLOADS[document_id] = {
        "title": title,
        "params": params,
        "abstained": [{"param": a.param, "reason": a.reason} for a in abstained],
    }
    return document_id


def get_upload(document_id: str) -> Optional[dict]:
    return _UPLOADS.get(document_id)
