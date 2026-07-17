"""SiteMind SUPPLY-CHAIN ALERTING evaluation — eval #12, a separate, honest
metric from the other 11 (never blended).

What this measures and why: `app/supply_chain.py`'s `_alert_severity()` and
`_detected_at_day()` are the two pure functions behind the Evaluation Focus's
"alerting timeliness" metric. This eval verifies the severity-tiering rule
reaches the documented verdict on boundary values (exactly at each threshold,
just under, just over) and that `_detected_at_day` correctly finds the FIRST
slipped milestone (not the largest slip, not a later one) — including the
edge case of no slip at all (returns None, never a guessed day).

Cases are constructed directly against the pure functions with synthetic
Milestone objects — a genuine held-out check, not the demo data grading its
own homework.

Run:  python -m eval.run_alerts_eval   (from backend/, venv active)
      -> writes eval/alerts_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.supply_chain import (  # noqa: E402
    _ALERT_CRITICAL_DAYS,
    _ALERT_WARNING_DAYS,
    _alert_severity,
    _detected_at_day,
)
from app.schemas import Milestone  # noqa: E402


def _m(stage, tier, planned, actual) -> Milestone:
    return Milestone(stage=stage, tier=tier, planned_day=planned, actual_day=actual, projected_day=None)


SEVERITY_CASES = [
    ("info-floor", dict(days_at_risk=1, on_critical_path=False), "INFO"),
    ("info-just-under-warning", dict(days_at_risk=_ALERT_WARNING_DAYS - 1, on_critical_path=False), "INFO"),
    ("warning-at-floor", dict(days_at_risk=_ALERT_WARNING_DAYS, on_critical_path=False), "WARNING"),
    ("warning-just-under-critical", dict(days_at_risk=_ALERT_CRITICAL_DAYS, on_critical_path=False), "WARNING"),
    ("critical-just-over-threshold", dict(days_at_risk=_ALERT_CRITICAL_DAYS + 1, on_critical_path=False), "CRITICAL"),
    ("critical-on-critical-path-even-if-1-day", dict(days_at_risk=1, on_critical_path=True), "CRITICAL"),
    ("critical-zero-days-but-on-path", dict(days_at_risk=0, on_critical_path=True), "CRITICAL"),
]

DETECTED_DAY_CASES = [
    (
        "no-slip-returns-none",
        [_m("ordered", 1, 10, 10), _m("dispatched", 1, 30, 30)],
        None,
    ),
    (
        "first-slip-not-largest-slip",
        # A small slip happens first; a LARGER slip happens later — must return
        # the FIRST one's day, not the largest one's.
        [
            _m("ordered", 1, 10, 12),          # slip 2d, day 12 — this is the answer
            _m("dispatched", 1, 30, 55),        # slip 25d, day 55 — larger but later
        ],
        12,
    ),
    (
        "tier2-slip-detected-before-later-tier1-actuals",
        [
            _m("ordered", 1, 10, 10),
            _m("tier2_dispatched", 2, 20, 20),
            _m("tier2_customs_clearance", 2, 30, 55),  # first slip -> day 55
            _m("tier1_dispatched", 1, 60, None),
        ],
        55,
    ),
    (
        "ahead-of-schedule-not-a-slip",
        [_m("ordered", 1, 10, 5), _m("dispatched", 1, 30, None)],
        None,
    ),
]


def _run_severity():
    results = []
    for case_id, kwargs, expect in SEVERITY_CASES:
        got = _alert_severity(**kwargs)
        results.append({"id": case_id, "pass": got == expect, "got": got, "expected": expect})
    return results


def _run_detected_day():
    results = []
    for case_id, milestones, expect in DETECTED_DAY_CASES:
        got = _detected_at_day(milestones)
        results.append({"id": case_id, "pass": got == expect, "got": got, "expected": expect})
    return results


def main():
    severity = _run_severity()
    detected = _run_detected_day()
    all_results = severity + detected
    n_pass = sum(1 for r in all_results if r["pass"])
    n_total = len(all_results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "alert_warning_days_threshold": _ALERT_WARNING_DAYS,
        "alert_critical_days_threshold": _ALERT_CRITICAL_DAYS,
        "method": "Held-out synthetic cases constructed directly against the pure "
        "_alert_severity() and _detected_at_day() functions in app/supply_chain.py — not the "
        "live demo dataset. Verifies severity-tiering at exact threshold boundaries (not just "
        "comfortably inside each band) and that detected_at_day finds the FIRST slipped "
        "milestone, not the largest or a later one. This is a correctness check on the alerting "
        "logic; 'alerting timeliness' itself is a real computed lead-time (advance_warning_days "
        "= TODAY_DAY - detected_at_day), never asserted.",
        "severity_cases": severity,
        "detected_day_cases": detected,
    }

    (Path(__file__).resolve().parent / "alerts_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in all_results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/alerts_report.json")


if __name__ == "__main__":
    main()
