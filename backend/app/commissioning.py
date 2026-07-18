"""Pillar 5 — Commissioning QA Copilot (cooling-only slice).

Same architectural pattern as the Compliance Agent (Pillar 1):
  INGEST (real uploaded test log, exact fields, no guessing)
  -> CHECK (deterministic Python threshold against a real* envelope row)
  -> NCR (only for FAIL / OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE)
  -> QUALITY PACKAGE (compiles every record + verdict into one exportable report).

*"real" here is weaker than the rest of this project: the cooling envelope
corpus (commissioning_clauses.json) is cross-source compiled, NOT fetched
verbatim from a single verified primary document (see that file's _note and
Citation.source_type). Every finding and every quality package this module
produces carries that limitation explicitly — never presented as Codebook-grade.

Scope: system == "cooling" only. power/IT records are accepted (not rejected)
but always verdict NOT_CHECKABLE — this pillar does not attempt electrical/fire
commissioning; see sitemind/docs/codes.txt for what's still needed for that.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError

from . import commissioning_standards as std
from .schemas import CommissioningFinding, NCR, QualityPackage, TestRecord

router = APIRouter(prefix="/api/commissioning", tags=["commissioning"])

_REQUIRED_FIELDS = {"test_id", "system", "parameter", "measured_value", "unit", "timestamp", "location_zone"}

# Only these (system, parameter) combinations are checkable against the cooling
# envelope corpus. Anything else -> NOT_CHECKABLE, never guessed.
_CHECKABLE_PARAMS = {"supply_air_temp": "temperature", "return_air_temp": "temperature", "room_temp": "temperature", "relative_humidity": "relative_humidity", "return_air_rh": "relative_humidity", "room_rh": "relative_humidity"}


class ParseResult:
    def __init__(self, records: list[TestRecord], errors: list[str]):
        self.records = records
        self.errors = errors


def parse_test_log(content: str) -> ParseResult:
    """Parse a CSV test log. Never crashes on a bad row — records it as an error
    and skips that row, same abstain-don't-guess discipline as ingest.py."""
    records: list[TestRecord] = []
    errors: list[str] = []
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return ParseResult([], ["Empty or unreadable CSV: no header row found."])
    missing = _REQUIRED_FIELDS - set(h.strip() for h in reader.fieldnames)
    if missing:
        return ParseResult([], [f"Missing required column(s): {sorted(missing)}"])

    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            records.append(
                TestRecord(
                    test_id=row["test_id"].strip(),
                    system=row["system"].strip().lower(),
                    parameter=row["parameter"].strip(),
                    measured_value=float(row["measured_value"]),
                    unit=row["unit"].strip(),
                    timestamp=row["timestamp"].strip(),
                    location_zone=row["location_zone"].strip(),
                    equipment_class=(row.get("equipment_class") or "A1").strip() or "A1",
                )
            )
        except (ValueError, ValidationError, KeyError) as e:
            errors.append(f"Row {i}: skipped, could not parse ({e}).")
    return ParseResult(records, errors)


# --------------------------------------------------------------------------- #
# Deterministic check
# --------------------------------------------------------------------------- #
def check_record(record: TestRecord) -> CommissioningFinding:
    base = dict(
        test_id=record.test_id,
        location_zone=record.location_zone,
        parameter=record.parameter,
        measured_value=record.measured_value,
        unit=record.unit,
    )
    if record.system != "cooling":
        return CommissioningFinding(**base, verdict="NOT_CHECKABLE")

    env_param = _CHECKABLE_PARAMS.get(record.parameter)
    if env_param is None:
        return CommissioningFinding(**base, verdict="NOT_CHECKABLE")

    rec = std.envelope(env_param, record.equipment_class, "recommended")
    allow = std.envelope(env_param, record.equipment_class, "allowable")
    if rec is None or allow is None:
        return CommissioningFinding(**base, verdict="NOT_CHECKABLE")

    rec_min, rec_max, rec_cite = rec
    allow_min, allow_max, allow_cite = allow
    v = record.measured_value

    if rec_min <= v <= rec_max:
        return CommissioningFinding(
            **base,
            verdict="PASS",
            recommended_range=f"{rec_min}-{rec_max}",
            allowable_range=f"{allow_min}-{allow_max}",
            citation=rec_cite,
        )
    if allow_min <= v <= allow_max:
        finding = CommissioningFinding(
            **base,
            verdict="OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE",
            recommended_range=f"{rec_min}-{rec_max}",
            allowable_range=f"{allow_min}-{allow_max}",
            citation=allow_cite,
        )
        finding.ncr = _to_ncr(record, finding, severity="MEDIUM")
        return finding

    finding = CommissioningFinding(
        **base,
        verdict="FAIL",
        recommended_range=f"{rec_min}-{rec_max}",
        allowable_range=f"{allow_min}-{allow_max}",
        citation=allow_cite,
    )
    finding.ncr = _to_ncr(record, finding, severity="HIGH")
    return finding


def _to_ncr(record: TestRecord, finding: CommissioningFinding, severity: str) -> NCR:
    if finding.verdict == "FAIL":
        headline = (
            f"{record.location_zone}: measured {record.parameter.replace('_', ' ')} "
            f"{record.measured_value} {record.unit} falls OUTSIDE even the allowable "
            f"envelope ({finding.allowable_range} {record.unit})."
        )
        why = (
            "Outside the allowable envelope risks IT equipment thermal shutdown or "
            "accelerated hardware failure — this is a commissioning FAIL, not a "
            "best-practice deviation."
        )
        corrective = (
            "Re-balance/re-commission the CRAH/CRAC serving this zone and re-test "
            "before sign-off; do not close this test record as passed."
        )
    else:
        headline = (
            f"{record.location_zone}: measured {record.parameter.replace('_', ' ')} "
            f"{record.measured_value} {record.unit} is within the ASHRAE allowable "
            f"envelope but OUTSIDE the recommended envelope ({finding.recommended_range} {record.unit})."
        )
        why = (
            "Outside recommended (but within allowable) is not a hard failure — "
            "ASHRAE's allowable band exists for exactly this — but sustained operation "
            "outside recommended trends toward reduced hardware reliability margin."
        )
        corrective = (
            "Log for O&M review; re-tune setpoints toward the recommended band at the "
            "next scheduled maintenance window rather than as an urgent fix."
        )
    return NCR(
        id=f"CNCR-{record.test_id}",
        item=f"{record.location_zone} ({record.test_id})",
        severity=severity,  # type: ignore[arg-type]
        finding=headline,
        citation=finding.citation,
        why_it_matters=why,
        corrective_action=corrective,
        domain="mechanical",
    )


# --------------------------------------------------------------------------- #
# Quality package
# --------------------------------------------------------------------------- #
_RUNS: dict[str, QualityPackage] = {}


def build_quality_package(records: list[TestRecord]) -> QualityPackage:
    findings = [check_record(r) for r in records]
    return QualityPackage(
        run_id=f"CQA-{uuid.uuid4().hex[:8].upper()}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        corpus_limitation=std.corpus_note() + " " + std.simplification_note(),
        total_records=len(findings),
        pass_count=sum(1 for f in findings if f.verdict == "PASS"),
        within_allowable_count=sum(1 for f in findings if f.verdict == "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"),
        fail_count=sum(1 for f in findings if f.verdict == "FAIL"),
        not_checkable_count=sum(1 for f in findings if f.verdict == "NOT_CHECKABLE"),
        findings=findings,
    )


def _to_html(pkg: QualityPackage) -> str:
    rows = "".join(
        f"<tr><td>{f.test_id}</td><td>{f.location_zone}</td><td>{f.parameter}</td>"
        f"<td>{f.measured_value} {f.unit}</td><td>{f.recommended_range or '-'}</td>"
        f"<td>{f.allowable_range or '-'}</td><td class='v-{f.verdict}'>{f.verdict}</td></tr>"
        for f in pkg.findings
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>As-Commissioned Quality Package {pkg.run_id}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#111}}
.banner{{background:#fff3cd;border:1px solid #d4a72c;padding:0.75rem 1rem;border-radius:6px;margin-bottom:1.5rem;font-size:0.9rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;font-size:0.9rem}}
th{{background:#f5f5f5}}
.v-PASS{{color:#1a7f37;font-weight:600}}
.v-OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE{{color:#9a6700;font-weight:600}}
.v-FAIL{{color:#c62828;font-weight:600}}
.v-NOT_CHECKABLE{{color:#666}}
</style></head><body>
<h1>As-Commissioned Quality Package — {pkg.run_id}</h1>
<p>Generated {pkg.generated_at}</p>
<div class="banner"><strong>Corpus limitation:</strong> {pkg.corpus_limitation}</div>
<p>{pkg.total_records} record(s) — {pkg.pass_count} PASS, {pkg.within_allowable_count} within-allowable-only,
{pkg.fail_count} FAIL, {pkg.not_checkable_count} not checkable (outside cooling/thermal scope).</p>
<table><thead><tr><th>Test ID</th><th>Zone</th><th>Parameter</th><th>Measured</th>
<th>Recommended</th><th>Allowable</th><th>Verdict</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> dict:
    content = (await file.read()).decode("utf-8", errors="replace")
    parsed = parse_test_log(content)
    if not parsed.records:
        raise HTTPException(status_code=422, detail={"message": "No valid test records parsed.", "errors": parsed.errors})
    pkg = build_quality_package(parsed.records)
    _RUNS[pkg.run_id] = pkg
    return {"run_id": pkg.run_id, "parsed": len(parsed.records), "parse_errors": parsed.errors, "package": pkg.model_dump()}


@router.get("/quality-package/{run_id}", response_model=QualityPackage)
def get_quality_package(run_id: str) -> QualityPackage:
    pkg = _RUNS.get(run_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")
    return pkg


@router.get("/quality-package/{run_id}/html")
def get_quality_package_html(run_id: str):
    from fastapi.responses import HTMLResponse

    pkg = _RUNS.get(run_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")
    return HTMLResponse(_to_html(pkg))
