"""Project Timeline (P0, the centerpiece) — pure aggregation of computations
that already exist elsewhere: compliance NCRs, RFIs, supply-chain alerts,
schedule at-risk activities, and commissioning findings, plotted as one
sorted event list against real phase bands derived straight from
schedule.csv's own `phase` column (min/max of that phase's activities'
planned windows).

Hard rule: zero new fabricated events. Every event's `day`, severity, and
detail come from a real field another pillar's module already computed. If a
day genuinely can't be derived (no date field on the source record), the
event is skipped rather than assigned an invented day.

Cross-pillar `linked_event_ids` reuse evidence_links.py's real shared-key
matches (Shipment.linked_rfi / Shipment.linked_activity) — e.g. SHP-002's
match to RFI-EL-112 (the RFI's own Ref text cites the shipment's wbs_id
verbatim) now lights up on the Timeline too, not only in supply-chain's own
LinkedEvidence chips.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter

from . import clock
from .agents.compliance import evaluate
from .commissioning import build_quality_package, parse_test_log
from .config import DATA_DIR
from .data_loader import load_rfi_log, load_schedule, load_submittals
from .schedule import PROJECT_START, _cpm
from .schedule import risks as schedule_risks
from .schemas import PhaseBand, TimelineEvent
from .supply_chain import alerts as sc_alerts
from .supply_chain import shipments as sc_shipments

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _date_to_day(date_str: Optional[str]) -> Optional[int]:
    """Real calendar date -> project day offset. Returns None (never a guessed
    day) if the string is missing or unparseable."""
    if not date_str:
        return None
    try:
        d = dt.date.fromisoformat(date_str.strip()[:10])
    except ValueError:
        return None
    return (d - PROJECT_START).days


# --------------------------------------------------------------------------- #
# Phase bands -- straight from schedule.csv's own `phase` column, never a
# hardcoded WBS-prefix map (the real column already carries human phase names).
# --------------------------------------------------------------------------- #
def _phase_bands() -> list[PhaseBand]:
    rows = _cpm()["rows"]
    order: list[str] = []
    spans: dict[str, list[int]] = {}
    for row in rows:
        phase = row.get("phase") or "Unphased"
        start = _to_int(row.get("planned_start_day"))
        end = start + _to_int(row.get("duration_days"), 1)
        if phase not in spans:
            spans[phase] = [start, end]
            order.append(phase)
        else:
            spans[phase][0] = min(spans[phase][0], start)
            spans[phase][1] = max(spans[phase][1], end)
    return [PhaseBand(phase=p, start_day=spans[p][0], end_day=spans[p][1]) for p in order]


# --------------------------------------------------------------------------- #
# Per-pillar event sources
# --------------------------------------------------------------------------- #
def _ncr_severity(sev: str) -> str:
    return {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW", "ADVISORY": "MEDIUM"}.get(sev, "MEDIUM")


def _compliance_events() -> list[TimelineEvent]:
    subs = load_submittals()
    dbr = next(
        (s for s in subs if "dbr" in (s.get("Submittal No") or "").lower() or "design basis" in (s.get("Title") or "").lower()),
        None,
    )
    if dbr is None:
        return []
    doc_id = dbr.get("Submittal No")
    day = _date_to_day(dbr.get("Date Submitted"))
    if day is None or not doc_id:
        return []
    result = evaluate(doc_id)
    events = []
    for ncr in result.ncrs:
        events.append(
            TimelineEvent(
                id=f"tl-ncr-{ncr.id}",
                day=day,
                pillar="compliance",
                kind="ncr",
                severity=_ncr_severity(ncr.severity),
                title=f"{ncr.item} — {ncr.severity} NCR",
                detail=ncr.finding,
                link_route="/compliance",
            )
        )
    return events


def _rfi_events() -> list[TimelineEvent]:
    events = []
    for r in load_rfi_log():
        day = _date_to_day(r.get("Date"))
        rfi_no = r.get("RFI No")
        if day is None or not rfi_no:
            continue
        status = (r.get("Status") or "").strip().lower()
        events.append(
            TimelineEvent(
                id=f"tl-rfi-{rfi_no}",
                day=day,
                pillar="copilot",
                kind="rfi",
                severity="INFO" if status in ("closed", "answered") else "MEDIUM",
                title=f"{rfi_no} — {r.get('Subject', '')}",
                detail=r.get("Question", ""),
                link_route="/copilot",
            )
        )
    return events


@lru_cache(maxsize=1)
def _schedule_rows_by_wbs() -> dict[str, dict]:
    return {r["wbs_id"]: r for r in load_schedule()}


def _schedule_events() -> list[TimelineEvent]:
    rows = _schedule_rows_by_wbs()
    events = []
    for r in schedule_risks():
        row = rows.get(r.wbs_id)
        if row is None:
            continue
        day = _to_int(row.get("planned_start_day"))
        events.append(
            TimelineEvent(
                id=f"tl-risk-{r.wbs_id}",
                day=day,
                pillar="schedule",
                kind="risk",
                severity="HIGH" if r.on_critical_path else "MEDIUM",
                title=f"{r.activity} — predicted {r.predicted_slip_days}d slip",
                detail="; ".join(r.drivers),
                link_route="/schedule",
            )
        )
    return events


_ALERT_SEVERITY = {"CRITICAL": "CRITICAL", "WARNING": "MEDIUM", "INFO": "INFO"}


def _supply_chain_events() -> list[TimelineEvent]:
    events = []
    for a in sc_alerts():
        events.append(
            TimelineEvent(
                id=f"tl-alert-{a.id}",
                day=a.detected_at_day,
                pillar="supply_chain",
                kind="alert",
                severity=_ALERT_SEVERITY.get(a.severity, "MEDIUM"),
                title=f"{a.procurement_item} — {a.severity} alert",
                detail=a.message,
                link_route="/supply-chain",
            )
        )
    for s in sc_shipments():
        if s.days_at_risk <= 0:
            continue
        events.append(
            TimelineEvent(
                id=f"tl-miss-{s.id}",
                day=s.projected_arrival_day,
                pillar="supply_chain",
                kind="projected_miss",
                severity="HIGH" if s.on_critical_path else "MEDIUM",
                title=f"{s.procurement_item} — projected to miss required-on-site date",
                detail=f"Projected arrival day {s.projected_arrival_day}, required by day "
                f"{s.required_on_site_by} ({s.days_at_risk}d at risk).",
                link_route="/supply-chain",
            )
        )
    return events


@lru_cache(maxsize=1)
def _sample_commissioning():
    path = DATA_DIR / "project_docs" / "sample_commissioning_log.csv"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_test_log(content)
    if not parsed.records:
        return None
    pkg = build_quality_package(parsed.records)
    return parsed.records, pkg


def _commissioning_events() -> list[TimelineEvent]:
    data = _sample_commissioning()
    if data is None:
        return []
    records, pkg = data
    events = []
    for record, finding in zip(records, pkg.findings):
        if finding.verdict not in ("FAIL", "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"):
            continue
        day = _date_to_day(record.timestamp)
        if day is None:
            continue
        events.append(
            TimelineEvent(
                id=f"tl-cqa-{record.test_id}",
                day=day,
                pillar="commissioning",
                kind="finding",
                severity="HIGH" if finding.verdict == "FAIL" else "MEDIUM",
                title=f"{finding.location_zone} — {finding.verdict.replace('_', ' ').title()}",
                detail=f"{finding.parameter.replace('_', ' ')}: {finding.measured_value} {finding.unit}",
                link_route="/commissioning",
            )
        )
    return events


# --------------------------------------------------------------------------- #
# Cross-pillar linking -- reuses Shipment.linked_rfi / .linked_activity
# (evidence_links.py's real shared-key matches), never a new match here.
# --------------------------------------------------------------------------- #
def _add_symmetric_link(a: TimelineEvent, b: TimelineEvent) -> None:
    if b.id not in a.linked_event_ids:
        a.linked_event_ids.append(b.id)
    if a.id not in b.linked_event_ids:
        b.linked_event_ids.append(a.id)


def _link_pairs(events: list[TimelineEvent]) -> None:
    by_id = {e.id: e for e in events}
    for s in sc_shipments():
        sources = [eid for eid in (f"tl-alert-ALERT-{s.id}", f"tl-miss-{s.id}") if eid in by_id]
        if not sources:
            continue
        targets = []
        if s.linked_rfi is not None:
            rfi_id = f"tl-rfi-{s.linked_rfi.id}"
            if rfi_id in by_id:
                targets.append(rfi_id)
        if s.linked_activity is not None:
            risk_id = f"tl-risk-{s.linked_activity.id}"
            if risk_id in by_id:
                targets.append(risk_id)
        for sid in sources:
            for tid in targets:
                _add_symmetric_link(by_id[sid], by_id[tid])


@lru_cache(maxsize=1)
def all_events() -> list[TimelineEvent]:
    events = (
        _compliance_events()
        + _rfi_events()
        + _schedule_events()
        + _supply_chain_events()
        + _commissioning_events()
    )
    _link_pairs(events)
    events.sort(key=lambda e: e.day)
    return events


def phase_bands() -> list[PhaseBand]:
    return _phase_bands()


@router.get("")
def get_timeline() -> dict:
    return {
        "project_start": PROJECT_START.isoformat(),
        "today_day": clock.current_day(),
        "phase_bands": [b.model_dump() for b in phase_bands()],
        "events": [e.model_dump() for e in all_events()],
    }
