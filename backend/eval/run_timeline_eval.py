"""SiteMind PROJECT TIMELINE evaluation — eval #16, a separate, honest metric
from the other 15 (never blended).

What this measures: `app/timeline.py` is a pure AGGREGATION layer — it invents
no new judgment, only combines outputs that already exist elsewhere. So this
eval is a CONSISTENCY check, not an arithmetic check (unlike run_weather_eval
/run_workforce_eval's pure-function boundary cases): does every event on the
timeline actually trace back to a real record in its source pillar, do the
per-pillar counts match, do phase-band boundaries match an independently
recomputed min/max, and is every linked_event_ids entry symmetric and
resolvable to a real event id on the timeline. A timeline event that doesn't
trace to a real source record would be exactly the "invented event" the
project's non-negotiable integrity rules forbid — this eval exists to catch
that class of bug specifically.

Run:  python -m eval.run_timeline_eval   (from backend/, venv active)
      -> writes eval/timeline_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.agents.compliance import evaluate  # noqa: E402
from app.data_loader import load_rfi_log, load_schedule, load_submittals  # noqa: E402
from app.schedule import risks as schedule_risks  # noqa: E402
from app.supply_chain import alerts as sc_alerts, shipments as sc_shipments  # noqa: E402
from app.timeline import _phase_bands, _to_int, all_events  # noqa: E402


def _check(id_: str, ok: bool, detail: str = "") -> dict:
    return {"id": id_, "pass": bool(ok), "detail": detail}


def _source_id_checks() -> list[dict]:
    """(a) every timeline event's source id exists in its source pillar's output."""
    events = all_events()
    checks = []

    ncr_events = [e for e in events if e.kind == "ncr"]
    dbr = next(s for s in load_submittals() if "dbr" in (s.get("Submittal No") or "").lower())
    real_ncr_ids = {n.id for n in evaluate(dbr["Submittal No"]).ncrs}
    ok = all(e.id.removeprefix("tl-ncr-") in real_ncr_ids for e in ncr_events)
    checks.append(_check("ncr-ids-resolve", ok, f"{len(ncr_events)} NCR events, {len(real_ncr_ids)} real NCRs"))

    rfi_events = [e for e in events if e.kind == "rfi"]
    real_rfi_ids = {r.get("RFI No") for r in load_rfi_log()}
    ok = all(e.id.removeprefix("tl-rfi-") in real_rfi_ids for e in rfi_events)
    checks.append(_check("rfi-ids-resolve", ok, f"{len(rfi_events)} RFI events"))

    risk_events = [e for e in events if e.kind == "risk"]
    real_wbs_ids = {r.wbs_id for r in schedule_risks()}
    ok = all(e.id.removeprefix("tl-risk-") in real_wbs_ids for e in risk_events)
    checks.append(_check("schedule-risk-ids-resolve", ok, f"{len(risk_events)} schedule-risk events"))

    alert_events = [e for e in events if e.kind == "alert"]
    real_alert_ids = {a.id for a in sc_alerts()}
    ok = all(e.id.removeprefix("tl-alert-") in real_alert_ids for e in alert_events)
    checks.append(_check("alert-ids-resolve", ok, f"{len(alert_events)} alert events"))

    miss_events = [e for e in events if e.kind == "projected_miss"]
    real_shipment_ids = {s.id for s in sc_shipments() if s.days_at_risk > 0}
    ok = all(e.id.removeprefix("tl-miss-") in real_shipment_ids for e in miss_events)
    checks.append(_check("projected-miss-ids-resolve", ok, f"{len(miss_events)} projected-miss events"))

    return checks


def _count_checks() -> list[dict]:
    """(b) counts match: n events per pillar == n real records from that pillar."""
    events = all_events()
    checks = []

    dbr = next(s for s in load_submittals() if "dbr" in (s.get("Submittal No") or "").lower())
    real_ncr_count = len(evaluate(dbr["Submittal No"]).ncrs)
    tl_ncr_count = sum(1 for e in events if e.kind == "ncr")
    checks.append(_check("ncr-count-matches", tl_ncr_count == real_ncr_count, f"{tl_ncr_count} vs {real_ncr_count}"))

    tl_risk_count = sum(1 for e in events if e.kind == "risk")
    checks.append(_check("schedule-risk-count-matches", tl_risk_count == len(schedule_risks()), f"{tl_risk_count} vs {len(schedule_risks())}"))

    tl_alert_count = sum(1 for e in events if e.kind == "alert")
    checks.append(_check("alert-count-matches", tl_alert_count == len(sc_alerts()), f"{tl_alert_count} vs {len(sc_alerts())}"))

    real_at_risk_shipments = sum(1 for s in sc_shipments() if s.days_at_risk > 0)
    tl_miss_count = sum(1 for e in events if e.kind == "projected_miss")
    checks.append(_check("projected-miss-count-matches", tl_miss_count == real_at_risk_shipments, f"{tl_miss_count} vs {real_at_risk_shipments}"))

    return checks


def _phase_band_checks() -> list[dict]:
    """(c) phase band boundaries equal the min/max computed from a primitive
    activity list — recomputed independently here, not by calling _phase_bands
    twice, so this genuinely checks the aggregation logic against ground truth."""
    rows = load_schedule()
    expected: dict[str, list[int]] = {}
    for row in rows:
        phase = row.get("phase") or "Unphased"
        start = _to_int(row.get("planned_start_day"))
        end = start + _to_int(row.get("duration_days"), 1)
        if phase not in expected:
            expected[phase] = [start, end]
        else:
            expected[phase][0] = min(expected[phase][0], start)
            expected[phase][1] = max(expected[phase][1], end)

    bands = {b.phase: (b.start_day, b.end_day) for b in _phase_bands()}
    checks = []
    ok = set(bands) == set(expected)
    checks.append(_check("phase-set-matches", ok, f"{sorted(bands)} vs {sorted(expected)}"))
    for phase, (s, e) in expected.items():
        got = bands.get(phase)
        checks.append(_check(f"phase-bounds-{phase}", got == (s, e), f"got {got} expected {(s, e)}"))
    return checks


def _link_symmetry_checks() -> list[dict]:
    """(d) linked_event_ids are symmetric and resolve to a real event id."""
    events = all_events()
    by_id = {e.id: e for e in events}
    checks = []
    n_links = 0
    all_resolve = True
    all_symmetric = True
    for e in events:
        for target_id in e.linked_event_ids:
            n_links += 1
            if target_id not in by_id:
                all_resolve = False
                continue
            if e.id not in by_id[target_id].linked_event_ids:
                all_symmetric = False
    checks.append(_check("links-resolve", all_resolve, f"{n_links} link edges checked"))
    checks.append(_check("links-symmetric", all_symmetric, f"{n_links} link edges checked"))
    checks.append(_check("at-least-one-cross-pillar-link", n_links > 0, f"{n_links} link edges found"))
    return checks


def main():
    results = _source_id_checks() + _count_checks() + _phase_band_checks() + _link_symmetry_checks()
    n_pass = sum(1 for r in results if r["pass"])
    n_total = len(results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Consistency checks (not arithmetic checks) against the LIVE aggregation in "
        "app/timeline.py: every event id resolves to a real record in its source pillar's live "
        "output, per-pillar event counts match the source pillar's real counts, phase-band "
        "boundaries match an independently-recomputed min/max over schedule.csv's real phase "
        "column, and every linked_event_ids entry is symmetric and resolves to a real timeline "
        "event id. This catches the specific failure mode timeline.py's docstring forbids: an "
        "event that doesn't trace to a real source record.",
        "cases": results,
    }

    (Path(__file__).resolve().parent / "timeline_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/timeline_report.json")


if __name__ == "__main__":
    main()
