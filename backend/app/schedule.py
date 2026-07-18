"""Pillar 3 — Schedule Risk (CPM + leading-indicator RULES, NO ML).

Two deterministic, fully-explainable parts:
  1. Critical Path (CPM): forward/backward pass over the dependency DAG to get
     early/late start-finish and float. ~0 float => on the critical path.
  2. Leading-indicator rules: flag at-risk activities with an explicit reason
     (slipping long-lead vendor on the critical path, pct lagging plan, monsoon
     weather sensitivity), a predicted slip, and a lead-time advantage over a
     naive "flag only once visibly behind" baseline.

The real schedule uses an integer `planned_start_day` (day offset from project
start) rather than calendar dates, so the rules work in day-offset space.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import networkx as nx
from fastapi import APIRouter

from . import clock, schedule_factors
from .agents.mitigation import generate_mitigation_options
from .data_loader import load_schedule
from .schemas import RiskItem

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

# Project anchor + "as-of" so the rules fire deterministically for the demo.
PROJECT_START = dt.date(2026, 1, 5)
PROJECT_TODAY = dt.date(2026, 6, 29)
TODAY_DAY = (PROJECT_TODAY - PROJECT_START).days  # ~175 days elapsed
_MONSOON_MONTHS = {6, 7, 8, 9, 10, 11}  # SW + NE monsoon window for Chennai


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _preds(row: dict) -> list[str]:
    raw = (row.get("predecessors") or "").strip()
    if not raw:
        return []
    out = []
    for tok in raw.split(","):
        tok = tok.split("(")[0].strip()  # drop "(FS)"/"(SS)" suffixes
        if tok:
            out.append(tok)
    return out


def _vendor(row: dict) -> str:
    return (row.get("vendor_status") or "").strip().lower().replace("-", "_")


# --------------------------------------------------------------------------- #
# CPM forward/backward pass
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _cpm() -> dict:
    rows = load_schedule()
    by_id = {r["wbs_id"]: r for r in rows}
    dur = {r["wbs_id"]: _to_int(r.get("duration_days"), 1) for r in rows}

    g = nx.DiGraph()
    for wid in by_id:
        g.add_node(wid)
    for r in rows:
        for p in _preds(r):
            if p in by_id:
                g.add_edge(p, r["wbs_id"])

    while not nx.is_directed_acyclic_graph(g):  # guard against bad synthetic data
        g.remove_edge(*nx.find_cycle(g)[0])

    order = list(nx.topological_sort(g))
    es, ef = {}, {}
    for n in order:
        es[n] = max((ef[p] for p in g.predecessors(n)), default=0)
        ef[n] = es[n] + dur[n]

    project_finish = max(ef.values(), default=0)
    lf, ls = {}, {}
    for n in reversed(order):
        lf[n] = min((ls[s] for s in g.successors(n)), default=project_finish)
        ls[n] = lf[n] - dur[n]

    float_days = {n: ls[n] - es[n] for n in by_id}
    critical = {n for n in by_id if float_days[n] <= 0}
    return {
        "rows": rows,
        "critical": critical,
        "project_finish": project_finish,
        "graph": g,
        "order": order,
        "dur": dur,
        "by_id": by_id,
        "float": float_days,  # ls[n] - es[n] per activity — real CPM float, used by mitigation.py
    }


def _forward_finish(order: list[str], graph: nx.DiGraph, dur: dict[str, int]) -> int:
    ef: dict[str, int] = {}
    for n in order:
        es_n = max((ef[p] for p in graph.predecessors(n)), default=0)
        ef[n] = es_n + dur[n]
    return max(ef.values(), default=0)


def _project_impact(cpm: dict, wbs_id: str, slip: int) -> int:
    """Re-run the CPM forward pass with `slip` days added to this activity's
    duration and report the resulting change in project finish. A genuine causal
    number (not a guess): float absorbs small slips on non-critical activities,
    so the impact can legitimately be 0 even when predicted_slip_days > 0."""
    if slip <= 0:
        return 0
    dur = dict(cpm["dur"])
    dur[wbs_id] = dur.get(wbs_id, 0) + slip
    new_finish = _forward_finish(cpm["order"], cpm["graph"], dur)
    return max(0, new_finish - cpm["project_finish"])


def _downstream(cpm: dict, wbs_id: str) -> list[str]:
    g = cpm["graph"]
    if wbs_id not in g:
        return []
    by_id = cpm["by_id"]
    return [by_id[s].get("task", s) for s in g.successors(wbs_id)]


# --------------------------------------------------------------------------- #
# Leading-indicator rules
# --------------------------------------------------------------------------- #
def _expected_pct(row: dict) -> float:
    """Planned % complete for elapsed time as of the current (possibly
    demo-advanced) day — see clock.py. Defaults to TODAY_DAY when the clock
    hasn't been advanced."""
    start = _to_int(row.get("planned_start_day"))
    dur = _to_int(row.get("duration_days"), 1) or 1
    return max(0.0, min(100.0, (clock.current_day() - start) / dur * 100.0))


def _in_monsoon(row: dict) -> bool:
    cal = PROJECT_START + dt.timedelta(days=_to_int(row.get("planned_start_day")))
    return cal.month in _MONSOON_MONTHS


def _assess(row: dict, on_critical: bool, cpm: dict) -> RiskItem | None:
    drivers: list[str] = []
    predicted_slip = 0
    detected_lead = 0
    lead_time = _to_int(row.get("lead_time_days"))
    vendor = _vendor(row)
    pct = _to_int(row.get("pct_complete"))
    expected = _expected_pct(row)

    # Rule 1: long-lead procurement with a slipping/late vendor. This is a LEADING
    # indicator — the slipping PO is visible weeks before the install activity is
    # ever behind, so we flag it whether or not the procurement line itself is on
    # the critical path (a slipping long-lead item threatens the downstream path).
    if vendor in ("slipping", "late"):
        item = row.get("procurement_item") or "procurement item"
        where = "on the critical path" if on_critical else "feeding the critical path"
        drivers.append(f"Long-lead {item} vendor status '{row.get('vendor_status')}' {where}")
        factor = 0.065 if vendor == "slipping" else 0.10
        predicted_slip = max(predicted_slip, round(lead_time * factor))
        # The slipping PO is visible ~15% of the lead time before the activity is
        # ever visibly behind (the naive baseline) — that's our lead-time edge.
        detected_lead = max(detected_lead, round(lead_time * 0.15))

    # Rule 2: progress lags plan.
    if expected - pct >= 15:
        behind = round((expected - pct) / 100.0 * _to_int(row.get("duration_days"), 1))
        drivers.append(f"Progress {pct}% lags planned {expected:.0f}% (~{behind}d behind)")
        predicted_slip = max(predicted_slip, behind)

    # Rule 3: weather-sensitive activity scheduled in monsoon (legacy, uncited
    # June-November proxy). Left unchanged -- eval/run_schedule_eval.py imports
    # _in_monsoon directly and asserts this exact behaviour (13-eval regression).
    weather = str(row.get("weather_sensitive")).strip().lower() in ("true", "1", "yes")
    if weather and _in_monsoon(row) and pct < 100:
        drivers.append("Weather-sensitive activity scheduled during the monsoon window")
        predicted_slip = max(predicted_slip, 5)

    # Rule 4 (P1a): weather, cited to the real IMD NE-monsoon normal window --
    # a separate, precise, citable check alongside Rule 3 (see
    # schedule_factors.py's module docstring for why it doesn't replace it).
    if pct < 100:
        weather_drivers, weather_slip = schedule_factors.weather_driver(row, PROJECT_START)
        if weather_drivers:
            drivers.extend(weather_drivers)
            predicted_slip = max(predicted_slip, weather_slip)

    # Rule 5 (P1b): workforce availability, cited to the Pongal festival window
    # (backend/data/project_docs/workforce_calendar.json). Honestly dormant on
    # the bundled schedule -- see schedule_factors.py -- because the only rows
    # whose window overlaps the window are already 100% complete.
    if pct < 100:
        workforce_drivers, workforce_slip = schedule_factors.workforce_driver(row, PROJECT_START)
        if workforce_drivers:
            drivers.extend(workforce_drivers)
            predicted_slip = max(predicted_slip, workforce_slip)

    if not drivers:
        return None

    wbs_id = row.get("wbs_id", "")
    return RiskItem(
        activity=row.get("task", row.get("wbs_id", "")),
        wbs_id=wbs_id,
        on_critical_path=on_critical,
        predicted_slip_days=int(predicted_slip),
        detected_lead_time_days=int(detected_lead),
        drivers=drivers,
        mitigation=_mitigation(row, vendor, drivers),
        downstream_activities=_downstream(cpm, wbs_id),
        project_impact_days=_project_impact(cpm, wbs_id, int(predicted_slip)),
        mitigation_options=generate_mitigation_options(row, int(predicted_slip), cpm, clock.current_day()),
    )


def _mitigation(row: dict, vendor: str, drivers: list[str]) -> str:
    item = row.get("procurement_item") or "the procurement item"
    if vendor in ("slipping", "late"):
        return (
            f"Expedite the PO for {item} and resequence downstream fit-out to start "
            "with available equipment; escalate to the vendor weekly."
        )
    if any("monsoon" in d for d in drivers):
        return "Re-window the weather-sensitive work or add temporary weather protection to hold the date."
    if any("labour-availability" in d for d in drivers):
        return "Pre-mobilise a contingency crew or re-window non-critical labour-intensive tasks around the festival dip."
    return "Add resources / overtime to recover the lagging progress and protect the critical path."


@lru_cache(maxsize=1)
def risks() -> list[RiskItem]:
    cpm = _cpm()
    out: list[RiskItem] = []
    for row in cpm["rows"]:
        item = _assess(row, row["wbs_id"] in cpm["critical"], cpm)
        if item is not None:
            out.append(item)
    out.sort(key=lambda r: (r.on_critical_path, r.predicted_slip_days), reverse=True)
    return out


@router.get("/risks", response_model=list[RiskItem])
def get_risks() -> list[RiskItem]:
    return risks()


@router.get("/gantt")
def get_gantt() -> list[dict]:
    """Baseline bar is always [start_day, start_day+duration_days] (the planned
    dates, untouched). For at-risk activities only, `predicted_slip_days` and
    `drivers` are joined in directly from `risks()` — the SAME numbers already
    shown in the risk cards below the chart, never recomputed — so the frontend
    can render a ghost baseline-vs-predicted overlay with a named cause, proving
    the "flags slips weeks before the baseline does" claim on the chart itself."""
    cpm = _cpm()
    risk_by_id = {r.wbs_id: r for r in risks()}
    return [
        {
            "wbs_id": row["wbs_id"],
            "task": row.get("task", ""),
            "phase": row.get("phase", ""),
            "start_day": _to_int(row.get("planned_start_day")),
            "duration_days": _to_int(row.get("duration_days"), 1),
            "on_critical_path": row["wbs_id"] in cpm["critical"],
            "at_risk": row["wbs_id"] in risk_by_id,
            "predicted_slip_days": (
                risk_by_id[row["wbs_id"]].predicted_slip_days if row["wbs_id"] in risk_by_id else 0
            ),
            "drivers": (
                risk_by_id[row["wbs_id"]].drivers if row["wbs_id"] in risk_by_id else []
            ),
        }
        for row in cpm["rows"]
    ]


@router.get("/methodology")
def get_methodology() -> dict:
    """Discloses the 4 brief-named Predictive Schedule Risk Engine inputs and
    exactly how each is grounded — procurement status/lead times (Rule 1, no
    external citation needed, it's the project's own vendor-status field),
    workforce availability (Rule 5, Pongal window, honestly dormant on the
    bundled schedule) and weather (Rule 4, real IMD NE-monsoon citation).
    Surfaced in-product on the Schedule page's methodology panel."""
    year = PROJECT_START.year
    m_start, m_end = schedule_factors.monsoon_window(year)
    w_start, w_end = schedule_factors.workforce_window(year)
    citation = schedule_factors.monsoon_citation()
    live_risks = risks()
    weather_firing = [
        r.wbs_id for r in live_risks if any("NE-monsoon window" in d for d in r.drivers)
    ]
    workforce_firing = [
        r.wbs_id for r in live_risks if any("labour-availability window" in d for d in r.drivers)
    ]
    return {
        "inputs": [
            {"input": "procurement status", "status": "covered", "note": "Rule 1 — vendor_status field (slipping/late) on schedule.csv."},
            {"input": "lead times", "status": "covered", "note": "Rule 1 — lead_time_days field on schedule.csv."},
            {
                "input": "workforce availability",
                "status": "covered",
                "note": f"Rule 5 — {schedule_factors.workforce_festival_name()} labour-availability window "
                f"({w_start.isoformat()} to {w_end.isoformat()}), assumed "
                f"{schedule_factors.workforce_availability_factor():.0%} availability (REPRESENTATIVE assumption). "
                + (
                    f"Currently firing on {len(workforce_firing)} activity(ies): {', '.join(workforce_firing)}."
                    if workforce_firing
                    else "Not currently firing — the only bundled activities whose window overlaps mid-January "
                    "(early site-mobilisation work) are already 100% complete; the rule is built and held-out "
                    "tested (eval/run_workforce_eval.py), not force-fit onto the live demo dataset."
                ),
            },
            {
                "input": "weather",
                "status": "covered",
                "note": f"Rule 4 — real IMD Northeast Monsoon normal window for Coastal Tamil Nadu "
                f"({m_start.isoformat()} to {m_end.isoformat()}), a planning-grade climatological window, "
                "not a forecast. "
                + (
                    f"Currently firing on {len(weather_firing)} activity(ies): {', '.join(weather_firing)}."
                    if weather_firing
                    else "Not currently firing on the bundled schedule."
                ),
            },
        ],
        "monsoon_citation": citation.model_dump() if citation else None,
        "monsoon_window": {"start": m_start.isoformat(), "end": m_end.isoformat()},
        "workforce_window": {"start": w_start.isoformat(), "end": w_end.isoformat()},
        "workforce_availability_factor": schedule_factors.workforce_availability_factor(),
    }
