"""SiteMind SCHEDULE-RISK LOGIC evaluation — a separate, honest metric from the
other evals, and honest about what it does NOT claim.

What this measures: given a schedule row (or a small synthetic dependency graph),
does `app/schedule.py`'s deterministic rule arithmetic and CPM re-computation
produce the CORRECT number — the vendor-slip predicted-slip/detected-lead-time
formulas, the progress-lag threshold, the monsoon-window check, and the CPM
forward-pass re-run used for `project_impact_days` (float correctly absorbs a
slip on a non-critical activity; a critical-path slip correctly pushes the
project finish date by the same amount).

What this explicitly does NOT claim: SiteMind has no real historical project to
backtest "detected_lead_time_days" against real actual delays — the schedule and
its "slipping vendor" scenarios are representative synthetic data (stated as such
throughout the project), not measured outcomes. This eval verifies the FORMULA
implementation is correct and bug-free, the same way `run_supply_chain_eval.py`
verifies that module's arithmetic — it is a correctness check on deterministic
Python, not a predictive-accuracy claim.

Run:  python -m eval.run_schedule_eval   (from backend/, venv active)
      -> writes eval/schedule_report.json
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import networkx as nx

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.schedule import (  # noqa: E402
    PROJECT_START,
    TODAY_DAY,
    _assess,
    _downstream,
    _expected_pct,
    _forward_finish,
    _in_monsoon,
    _project_impact,
)


def _row(**kw) -> dict:
    # Default start is FAR in the future (relative to the real TODAY_DAY) so
    # rule 2 (progress-lag) never fires by accident in tests targeting a
    # different rule — expected_pct clamps to 0 and pct_complete is 0, so the
    # gap is 0 unless a test deliberately overrides start/duration/pct.
    base = {
        "wbs_id": "T-1", "task": "Test activity", "phase": "Test",
        "planned_start_day": str(TODAY_DAY + 100), "duration_days": "10", "predecessors": "",
        "pct_complete": "0", "procurement_item": "", "lead_time_days": "0",
        "vendor_status": "na", "weather_sensitive": "false",
    }
    base.update(kw)
    return base


def _rule_cases() -> list[dict]:
    results = []

    # -- Rule 1: vendor slip formulas --
    for status, factor in (("slipping", 0.065), ("late", 0.10)):
        row = _row(lead_time_days="200", vendor_status=status)
        item = _assess(row, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
        expected_slip = round(200 * factor)
        expected_lead = round(200 * 0.15)
        ok = item is not None and item.predicted_slip_days == expected_slip and item.detected_lead_time_days == expected_lead
        results.append({"id": f"vendor-{status}", "pass": ok, "got": None if item is None else (item.predicted_slip_days, item.detected_lead_time_days), "expected": (expected_slip, expected_lead)})

    # -- Rule 1: on-track vendor must NOT fire --
    row = _row(lead_time_days="200", vendor_status="on-track")
    item = _assess(row, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
    results.append({"id": "vendor-on-track-no-fire", "pass": item is None, "got": (item.predicted_slip_days if item else None), "expected": None})

    # -- Rule 2: progress-lag threshold, using the REAL TODAY_DAY so this is a
    # genuine check of the module's live behaviour, not a mocked clock. --
    start, dur = 100, 100
    expected_pct_val = (TODAY_DAY - start) / dur * 100.0
    # Fires at >=15 pts behind:
    row_fires = _row(planned_start_day=str(start), duration_days=str(dur), pct_complete=str(round(expected_pct_val - 20)))
    item = _assess(row_fires, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
    results.append({"id": "progress-lag-fires-at-20pts", "pass": item is not None and item.predicted_slip_days > 0, "got": item and item.predicted_slip_days, "expected": "> 0"})
    # Does NOT fire just under the 15-pt threshold:
    row_no_fire = _row(planned_start_day=str(start), duration_days=str(dur), pct_complete=str(round(expected_pct_val - 14)), lead_time_days="0")
    item = _assess(row_no_fire, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
    results.append({"id": "progress-lag-no-fire-under-threshold", "pass": item is None, "got": (item.predicted_slip_days if item else None), "expected": None})

    # -- Rule 3: monsoon window, using the real PROJECT_START calendar anchor --
    # Find a real planned_start_day that lands in August (a monsoon month) by
    # construction, so the test is honest about what "_in_monsoon" checks.
    aug_date = dt.date(PROJECT_START.year, 8, 15)
    aug_offset = (aug_date - PROJECT_START).days
    row_monsoon = _row(planned_start_day=str(aug_offset), weather_sensitive="true", pct_complete="0", duration_days="10")
    monsoon_flag = _in_monsoon(row_monsoon)
    item = _assess(row_monsoon, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
    results.append({
        "id": "monsoon-window-fires",
        "pass": monsoon_flag is True and item is not None and any("monsoon" in d for d in item.drivers),
        "got": (monsoon_flag, item.drivers if item else None),
        "expected": (True, "a monsoon driver present"),
    })
    # A January date must NOT be flagged as monsoon.
    jan_offset = 5  # PROJECT_START itself is Jan 5
    row_not_monsoon = _row(planned_start_day=str(jan_offset), weather_sensitive="true", pct_complete="0")
    results.append({"id": "non-monsoon-month-not-flagged", "pass": _in_monsoon(row_not_monsoon) is False, "got": _in_monsoon(row_not_monsoon), "expected": False})

    # -- No drivers at all -> must return None, never a hallucinated risk --
    row_clean = _row()
    item = _assess(row_clean, on_critical=False, cpm={"graph": nx.DiGraph(), "by_id": {}, "dur": {}, "order": [], "project_finish": 0})
    results.append({"id": "no-drivers-returns-none", "pass": item is None, "got": (item.predicted_slip_days if item else None), "expected": None})

    return results


def _cpm_cases() -> list[dict]:
    """Small synthetic dependency graphs, independent of the real schedule.csv,
    to verify the CPM re-run used for project_impact_days and _downstream."""
    results = []

    # A -> B -> C (linear chain, everything critical). Slipping A by 5 must push
    # the whole chain's finish by exactly 5 (no float anywhere to absorb it).
    g = nx.DiGraph()
    g.add_edges_from([("A", "B"), ("B", "C")])
    dur = {"A": 10, "B": 10, "C": 10}
    order = list(nx.topological_sort(g))
    baseline = _forward_finish(order, g, dur)
    cpm = {"graph": g, "order": order, "dur": dur, "project_finish": baseline, "by_id": {"A": {"task": "Task A"}, "B": {"task": "Task B"}, "C": {"task": "Task C"}}}
    impact = _project_impact(cpm, "A", 5)
    results.append({"id": "linear-chain-critical-slip-passes-through", "pass": impact == 5, "got": impact, "expected": 5})

    # A -> C and B -> C, where A is much shorter than B (A has float). Slipping A
    # by an amount smaller than its float must NOT move project finish at all.
    g2 = nx.DiGraph()
    g2.add_edges_from([("A", "C"), ("B", "C")])
    dur2 = {"A": 5, "B": 30, "C": 10}
    order2 = list(nx.topological_sort(g2))
    baseline2 = _forward_finish(order2, g2, dur2)  # driven by B (30+10=40), A has 25d float
    cpm2 = {"graph": g2, "order": order2, "dur": dur2, "project_finish": baseline2, "by_id": {"A": {"task": "Task A"}, "B": {"task": "Task B"}, "C": {"task": "Task C"}}}
    impact2 = _project_impact(cpm2, "A", 10)  # 10d slip on A, well within its 25d float
    results.append({"id": "float-absorbs-noncritical-slip", "pass": impact2 == 0, "got": impact2, "expected": 0})
    # A slip on A large enough to exceed its float DOES move the finish, by the excess.
    impact3 = _project_impact(cpm2, "A", 30)  # 25d float + 5d overrun
    results.append({"id": "slip-exceeding-float-moves-finish-by-excess", "pass": impact3 == 5, "got": impact3, "expected": 5})

    # _downstream reads direct successors correctly off the same graph.
    down = _downstream(cpm, "A")
    results.append({"id": "downstream-direct-successors", "pass": down == ["Task B"], "got": down, "expected": ["Task B"]})

    return results


def main():
    results = _rule_cases() + _cpm_cases()
    n_pass = sum(1 for r in results if r["pass"])
    n_total = len(results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Held-out synthetic rows and small synthetic dependency graphs, independent of "
        "the real schedule.csv, verifying the deterministic rule arithmetic (vendor-slip "
        "formulas, progress-lag threshold, monsoon-window check) and the CPM re-computation used "
        "for project_impact_days (float correctly absorbs a non-critical slip; a critical-path "
        "slip passes through 1:1; a slip exceeding available float moves the finish by exactly "
        "the excess). This is a correctness check on the logic, NOT a claim that the schedule "
        "pillar's predictions have been validated against real historical project delays — "
        "SiteMind has no real historical delivery data to backtest against (same limitation "
        "stated in run_supply_chain_eval.py).",
        "cases": results,
    }

    (Path(__file__).resolve().parent / "schedule_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/schedule_report.json")


if __name__ == "__main__":
    main()
