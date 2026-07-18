"""SiteMind WORKFORCE SCHEDULE-FACTOR evaluation — eval #15, a separate,
honest metric from the other 14 (never blended).

What this measures: `app/schedule_factors.py`'s pure overlap/slip functions
(`labour_dip_overlap_days`, `labour_dip_slip`) — given a fixed activity window
and a fixed Pongal festival window, does the deterministic day-overlap
arithmetic and the documented availability-factor slip formula reach the
correct number on boundary cases.

Cases are constructed directly against the pure functions with synthetic
day-offset windows — a genuine held-out check. On the BUNDLED schedule.csv this
rule is honestly dormant (the only activities whose window overlaps the real
mid-January Pongal dates are already 100% complete by the demo's TODAY_DAY —
see PROGRESS.md) — that live-data behaviour is deliberately NOT what this eval
tests; this eval proves the rule's arithmetic is correct and would fire on any
project whose labour-intensive work actually spans the window.

Run:  python -m eval.run_workforce_eval   (from backend/, venv active)
      -> writes eval/workforce_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.schedule_factors import labour_dip_overlap_days, labour_dip_slip  # noqa: E402

OVERLAP_CASES = [
    {"id": "no-overlap-before", "a_start": 0, "a_end": 5, "d_start": 8, "d_end": 21, "expect": 0},
    {"id": "no-overlap-after", "a_start": 25, "a_end": 40, "d_start": 8, "d_end": 21, "expect": 0},
    {"id": "full-overlap-activity-inside-window", "a_start": 10, "a_end": 15, "d_start": 8, "d_end": 21, "expect": 5},
    {"id": "partial-overlap-tail", "a_start": 3, "a_end": 12, "d_start": 8, "d_end": 21, "expect": 4},
    {"id": "partial-overlap-head", "a_start": 18, "a_end": 30, "d_start": 8, "d_end": 21, "expect": 3},
    {"id": "exact-boundary-touch-zero-width", "a_start": 0, "a_end": 8, "d_start": 8, "d_end": 21, "expect": 0},
]

SLIP_CASES = [
    {"id": "slip-zero-overlap", "overlap": 0, "factor": 0.6, "expect": 0},
    {"id": "slip-standard-factor", "overlap": 8, "factor": 0.6, "expect": round(8 * (1 - 0.6))},
    {"id": "slip-full-loss-factor", "overlap": 10, "factor": 0.0, "expect": 10},
    {"id": "slip-no-loss-factor", "overlap": 10, "factor": 1.0, "expect": 0},
]


def _run_overlap_cases() -> list[dict]:
    out = []
    for c in OVERLAP_CASES:
        got = labour_dip_overlap_days(c["a_start"], c["a_end"], c["d_start"], c["d_end"])
        out.append({"id": c["id"], "pass": got == c["expect"], "got": got, "expected": c["expect"]})
    return out


def _run_slip_cases() -> list[dict]:
    out = []
    for c in SLIP_CASES:
        got = labour_dip_slip(c["overlap"], c["factor"])
        out.append({"id": c["id"], "pass": got == c["expect"], "got": got, "expected": c["expect"]})
    return out


def main():
    overlap_results = _run_overlap_cases()
    slip_results = _run_slip_cases()
    results = overlap_results + slip_results
    n_pass = sum(1 for r in results if r["pass"])
    n_total = len(results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Held-out synthetic day-offset windows constructed directly against the pure "
        "functions in app/schedule_factors.py (Pongal-window day-overlap arithmetic, "
        "availability-factor slip formula) — not the bundled schedule.csv. Verifies the "
        "deterministic arithmetic behind the P1b 'workforce availability' schedule-risk input. "
        "This rule is honestly dormant on the bundled demo dataset (documented in PROGRESS.md and "
        "the Schedule page's methodology panel, GET /api/schedule/methodology) — this eval proves "
        "the formula is correct, independent of whether the live demo happens to exercise it.",
        "overlap_cases": overlap_results,
        "slip_cases": slip_results,
    }

    (Path(__file__).resolve().parent / "workforce_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/workforce_report.json")


if __name__ == "__main__":
    main()
