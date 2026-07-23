"""Pillar 1 — the Spec & Quality Compliance Agent (THE HERO).

Flow per parameter:
  EXTRACT (pre-stored params)  ->  RETRIEVE (CHECK REGISTRY + real clause)
  ->  DECIDE (deterministic Python threshold)  ->  EXPLAIN (prose).

The pass/fail decision and the Citation are ALWAYS deterministic (Python +
clauses.json). Only the prose (finding / why / corrective) is LLM-assisted when
a key is present; otherwise it comes from deterministic seeds / fixtures.
"""
from __future__ import annotations

import json
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import config, ingest, llm, llm_extract, trace
from ..data_loader import fixture, load_submittals, params_for
from ..schemas import NCR, ComplianceResult, Citation, CoverageStat, OverlapNote, SourceSpan
from ..standards import all_clauses, get_clause
from .checks import applicable_checks


# IS 456 Table 16 — nominal durability cover floor by exposure (mm). Real values
# from the digitised clause IS456_26.5.1.1. Used only to resolve cover overlaps.
_TABLE16_COVER = {
    "mild": 20,
    "moderate": 30,
    "severe": 45,
    "very severe": 50,
    "extreme": 75,
}
# Primary per-element cover floor (mm), keyed by the binary check id.
_PRIMARY_COVER_FLOOR = {"COVER_FOOTING": 50, "COVER_COLUMN": 40}


def _ref(citation: Optional[Citation]) -> str:
    """Compact human-readable clause ref, e.g. 'IS 456:2000 Cl 26.4.2.2'."""
    if not citation:
        return "?"
    return f"{citation.standard} Cl {citation.clause}"

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class CheckRequest(BaseModel):
    document_id: str


# --------------------------------------------------------------------------- #
# Prose (LLM-assisted online, deterministic offline)
# --------------------------------------------------------------------------- #
_EXPLAIN_SYSTEM = (
    "You are a structural QA engineer writing a Non-Conformance Report for a "
    "data-centre construction project. You are GIVEN the governing standard "
    "clause verbatim — never alter or invent clause numbers or text. Reply with "
    "ONLY a JSON object with keys finding, why_it_matters, corrective_action. "
    "Temperature 0."
)


def _explain_prompt(param: dict, check, citation: Citation) -> str:
    return (
        f"Element: {param.get('element')}\n"
        f"Specified: {param.get('param')} = {param.get('value')} {param.get('unit', '')}\n"
        f"Context: exposure={param.get('exposure')}, type={param.get('element_type')}\n"
        f"Required by standard: {check['rule_text']}\n"
        f"Governing clause (cite exactly): {citation.standard} Cl. {citation.clause}: "
        f'"{citation.text}"\n\n'
        "Write finding (1 sentence on what was specified), why_it_matters (1-2 "
        "sentences tying it to data-centre reliability/uptime), corrective_action "
        "(1 concrete step)."
    )


def _offline_prose(param: dict, check) -> dict:
    """Deterministic prose: prefer the fixture (keyed by param id), else seeds."""
    fx = fixture("compliance_prose.json") or {}
    pid = param.get("id")
    if pid and pid in fx:
        return fx[pid]
    if check and check["id"] in fx:
        return fx[check["id"]]
    return {
        "finding": (
            f"{param.get('source_location', 'The submittal')} specifies "
            f"{param.get('param', 'a parameter').replace('_', ' ')} = "
            f"{param.get('value')} {param.get('unit', '')}".strip() + "."
        ),
        "why_it_matters": check["why"],
        "corrective_action": check["corrective"],
    }


def _prose(param: dict, check, citation: Citation) -> dict:
    """Online: Claude writes prose handed the real clause. Offline: deterministic."""
    if config.OFFLINE_MODE:
        return _offline_prose(param, check)
    out = llm.complete_json(_EXPLAIN_SYSTEM, _explain_prompt(param, check, citation))
    if not out or not all(k in out for k in ("finding", "why_it_matters", "corrective_action")):
        return _offline_prose(param, check)  # robust fallback
    return out


# --------------------------------------------------------------------------- #
# NCR construction
# --------------------------------------------------------------------------- #
def _source(param: dict) -> Optional[SourceSpan]:
    q = param.get("source_quote")
    if not q:
        return None
    return SourceSpan(quote=q, location=param.get("source_location", "unknown"))


def _advisory_ncr(param: dict, ncr_id: str) -> Optional[NCR]:
    """The IS 1893 I=1.5 judgment-catch (the memorable demo beat)."""
    if param.get("param") != "importance_factor" or param.get("value", 1.5) >= 1.5:
        return None
    citation = get_clause("IS1893_7.2.3")
    fx = (fixture("compliance_prose.json") or {}).get(param.get("id"), {})
    finding = fx.get(
        "finding",
        f"Design uses seismic Importance Factor I={param.get('value')} "
        "(treated as an ordinary building).",
    )
    return NCR(
        id=ncr_id,
        item=param.get("element", "Primary structure"),
        severity="ADVISORY",
        finding=finding,
        source=_source(param),
        citation=citation,
        why_it_matters=fx.get(
            "why_it_matters",
            "A Tier-III/IV data centre is a textbook modern lifeline facility. "
            "Per IS 1893 Pt1:2016 Cl 7.2.3 / Table 8, lifeline and emergency "
            "buildings (power stations, telephone exchanges) take I=1.5; using "
            "I=1.0 may under-design the lateral system for a mission-critical asset.",
        )
        + " IS 1893 Cl 6.4.2 reinforces this: where I is not otherwise specified, "
        "the minimum for critical and lifeline structures is 1.5, and I feeds the "
        "design seismic coefficient Ah = (Z/2)(Sa/g)/(R/I) — so I=1.0 lowers the "
        "design base shear by a third versus I=1.5.",
        corrective_action=fx.get(
            "corrective_action",
            "Re-run the seismic design basis with I=1.5 and compare base shear.",
        ),
        recommendation=fx.get(
            "recommendation",
            "Adopt I=1.5. Table 8 does not name data centres, but Note 1 lets the "
            "owner adopt a higher I, and a Tier-III/IV DC is arguably a lifeline facility.",
        ),
        confirm_with=fx.get("confirm_with", "EOR"),
    )


def _violation_ncr(param: dict, check, ncr_id: str) -> NCR:
    citation = get_clause(check["clause_key"])
    prose = _prose(param, check, citation) if citation else _offline_prose(param, check)
    return NCR(
        id=ncr_id,
        item=param.get("element", "Unknown element"),
        severity=check["severity"],  # type: ignore[arg-type]
        finding=prose["finding"],
        source=_source(param),
        citation=citation,
        why_it_matters=prose["why_it_matters"],
        corrective_action=prose["corrective_action"],
        domain=check.get("domain", "structural"),  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# Core evaluation
# --------------------------------------------------------------------------- #
def _document_title(document_id: str) -> str:
    upload = ingest.get_upload(document_id)
    if upload:
        return f"{document_id} — {upload['title']} (uploaded)"
    for s in load_submittals():
        if s.get("Submittal No") == document_id:
            rev = s.get("Rev", "")
            return f"{document_id} {rev} — {s.get('Title', '')}".strip()
    return document_id


def _params_for(document_id: str) -> list[dict]:
    """Uploaded documents first (real extraction), then the pre-structured set."""
    upload = ingest.get_upload(document_id)
    if upload:
        return upload["params"]
    return params_for(document_id)


def _cover_overlap(param: dict, check) -> Optional[OverlapNote]:
    """For a cover check governed by >1 clause, resolve the binding requirement.

    Returns an OverlapNote naming every governing clause and the strictest one,
    or None when the overlap doesn't apply (e.g. no recognised exposure)."""
    primary = get_clause(check["clause_key"])
    floor_primary = _PRIMARY_COVER_FLOOR.get(check["id"])
    exposure = (param.get("exposure") or "").lower()
    floor_table16 = _TABLE16_COVER.get(exposure)
    if not primary or floor_primary is None or floor_table16 is None:
        return None
    t16 = get_clause("IS456_26.5.1.1")
    primary_lbl = f"{_ref(primary)} ({param.get('element_type')} min {floor_primary} mm)"
    t16_lbl = f"{_ref(t16)} / Table 16 ({exposure} exposure {floor_table16} mm)"
    if floor_primary >= floor_table16:
        governing, gov_val = primary_lbl, floor_primary
    else:
        governing, gov_val = t16_lbl, floor_table16
    return OverlapNote(
        item=param.get("element", "element"),
        param="nominal_cover",
        clauses=[primary_lbl, t16_lbl],
        governing=governing,
        note=(
            f"Two clauses govern cover for {param.get('element')}: the "
            f"{param.get('element_type')} minimum ({floor_primary} mm) and the "
            f"{exposure}-exposure durability floor (Table 16, {floor_table16} mm). "
            f"The binding requirement is {gov_val} mm."
        ),
    )


def evaluate(document_id: str) -> ComplianceResult:
    """Run every applicable check on the document and assemble a ComplianceResult."""
    return evaluate_with_params(document_id)[0]


def evaluate_with_params(document_id: str) -> tuple[ComplianceResult, dict[str, dict]]:
    """Same as evaluate(), plus a {ncr_id: raw_param_dict} side-channel the Action
    Brief needs (element/param/value/unit) without changing the stable NCR schema."""
    run = trace.start(
        "compliance.evaluate",
        {"document_id": document_id, "llm_provider": config.LLM_PROVIDER, "offline_mode": config.OFFLINE_MODE},
    )
    with run.step("load_params"):
        params = _params_for(document_id)
        known_ids = {s.get("Submittal No") for s in load_submittals()}
        if not params and document_id not in known_ids and not ingest.get_upload(document_id):
            raise HTTPException(status_code=404, detail=f"Unknown document_id: {document_id}")

    ncrs: list[NCR] = []
    conforming: list[str] = []
    overlaps: list[OverlapNote] = []
    cited_keys: set[str] = set()
    standards: set[str] = set()
    standards_by_domain: dict[str, set[str]] = {}
    checks_run = 0
    checked = 0
    seq = 1
    param_by_ncr: dict[str, dict] = {}

    def _register(key: str, domain: str = "structural") -> None:
        c = get_clause(key)
        if c:
            cited_keys.add(key)
            standards.add(c.standard)
            standards_by_domain.setdefault(domain, set()).add(c.standard)

    _checks_t0 = time.time()
    for param in params:
        # Special ADVISORY (judgment call) — not a binary pass/fail.
        adv = _advisory_ncr(param, f"NCR-{seq:04d}")
        if adv is not None:
            ncrs.append(adv)
            param_by_ncr[adv.id] = param
            _register("IS1893_7.2.3")
            _register("IS1893_6.4.2")  # second clause backing the I=1.5 catch
            seq += 1
            checked += 1
            checks_run += 1
            continue

        applied = applicable_checks(param)
        if not applied:
            continue
        for check in applied:
            checked += 1
            checks_run += 1
            check_domain = check.get("domain", "structural")
            _register(check["clause_key"], check_domain)

            # Multi-clause governance: surface overlap + name the binding clause.
            overlap = None
            if check.get("also_governed_by"):
                for k in check["also_governed_by"]:
                    _register(k, check_domain)
                if check["id"] in _PRIMARY_COVER_FLOOR:
                    overlap = _cover_overlap(param, check)
                    if overlap:
                        overlaps.append(overlap)

            label = f"{param.get('element')}: {param.get('param', '').replace('_', ' ')}"
            if check["rule"](param):
                conforming.append(f"{label} — conforms to {check['clause_key']}")
            else:
                ncr = _violation_ncr(param, check, f"NCR-{seq:04d}")
                if overlap:
                    ncr.governing_note = overlap.note
                ncrs.append(ncr)
                param_by_ncr[ncr.id] = param
                seq += 1

    run.steps.append(
        {
            "name": "run_checks",
            "duration_ms": round((time.time() - _checks_t0) * 1000, 1),
            "meta": {"params": len(params), "checks_run": checks_run, "ncrs": len(ncrs)},
        }
    )

    coverage = CoverageStat(
        standards=sorted(standards),
        clauses_cited=len(cited_keys),
        checks_run=checks_run,
        library_clauses=len(all_clauses()),
        standards_by_domain={d: sorted(s) for d, s in standards_by_domain.items() if s},
    )
    result = ComplianceResult(
        document=_document_title(document_id),
        checked_params=checked,
        ncrs=ncrs,
        conforming=conforming,
        overlaps=overlaps,
        coverage=coverage,
    )
    run.finish(
        {
            "checked_params": checked,
            "ncr_count": len(ncrs),
            "conforming_count": len(conforming),
            "clauses_cited": len(cited_keys),
        }
    )
    return result, param_by_ncr


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/check", response_model=ComplianceResult)
def check(req: CheckRequest) -> ComplianceResult:
    return evaluate(req.document_id)


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)) -> dict:
    """Real document upload: reads the actual PDF/DOCX/text file, extracts ONLY
    the narrow parameter set the CHECK REGISTRY can evaluate, and explicitly
    abstains (never guesses) on anything it can't confidently find. Returns a
    document_id that /compliance/check and /compliance/check/stream accept
    exactly like any pre-loaded document."""
    content = await file.read()
    try:
        text = ingest.extract_text(file.filename or "upload", content)
    except ingest.UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this file (scanned/image-only PDFs are "
            "not supported by this text-first pipeline).",
        )

    # PERCEIVE: LLM-first extraction behind a span-verification gate when enabled
    # (app/llm_extract.py), else pure regex. Either way, DECIDE stays in checks.py.
    found, abstained = await llm_extract.extract_params(text)
    param_dicts = ingest.to_param_dicts(found)
    document_id = ingest.register_upload(file.filename or "upload", param_dicts, abstained)

    return {
        "document_id": document_id,
        "title": file.filename,
        "extracted": [
            {
                "param": p["param"],
                "element": p["element"],
                "value": p["value"],
                "unit": p["unit"],
                "source_quote": p["source_quote"],
            }
            for p in param_dicts
        ],
        "abstained": [{"param": a.param, "reason": a.reason} for a in abstained],
        "checkable_params": len(param_dicts),
    }


def _reasoning_trace(document_id: str) -> list[str]:
    """Human-readable agent trace for the live SSE panel."""
    params = _params_for(document_id)
    upload = ingest.get_upload(document_id)
    lines = [
        "Extracting parameters from the document…",
        f"Found {len(params)} checkable parameter(s).",
    ]
    if upload and upload.get("abstained"):
        lines.append(
            f"Abstained on {len(upload['abstained'])} parameter type(s) — no confident match "
            "in the uploaded text (see abstained list)."
        )
    for param in params:
        p = param.get("param", "")
        if p == "importance_factor":
            lines.append("Reviewing seismic Importance Factor against IS 1893 Table 8…")
        elif p == "nominal_cover":
            lines.append(f"Checking {param.get('element_type')} cover against IS 456…")
        elif p == "wc_ratio":
            lines.append("Checking free water-cement ratio against IS 456 Table 5…")
        elif p == "design_wind_speed":
            lines.append("Checking design wind speed against IS 875 Pt3…")
        elif p == "concrete_grade":
            lines.append("Checking marine concrete grade against IS 456 8.2.8…")
        elif p == "long_steel_pct":
            lines.append("Checking column steel percentage against IS 456 26.5.3.1…")
        elif p == "tie_spacing":
            lines.append("Checking lateral-tie pitch against IS 456 26.5.3.2…")
        elif p == "design_wind_pressure":
            lines.append("Checking design wind pressure pz against IS 875 Pt3 5.4…")
    return lines


async def _sse_stream(document_id: str) -> AsyncGenerator[bytes, None]:
    for line in _reasoning_trace(document_id):
        yield f"data: {json.dumps({'type': 'reasoning', 'text': line})}\n\n".encode()
    result = evaluate(document_id)
    n = len(result.ncrs)
    yield (
        "data: "
        + json.dumps(
            {"type": "reasoning", "text": f"Found {n} non-conformance(s). Compiling NCRs…"}
        )
        + "\n\n"
    ).encode()
    yield (
        "data: " + json.dumps({"type": "result", "data": result.model_dump()}) + "\n\n"
    ).encode()


@router.post("/check/stream")
def check_stream(req: CheckRequest) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(req.document_id), media_type="text/event-stream"
    )
