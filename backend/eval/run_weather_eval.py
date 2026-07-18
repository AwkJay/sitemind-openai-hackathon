"""SiteMind WEATHER SCHEDULE-FACTOR evaluation — eval #14, a separate, honest
metric from the other 13 (never blended).

What this measures: `app/schedule_factors.py`'s pure overlap/slip functions
(`monsoon_overlap_days`, `weather_predicted_slip`) — given a fixed activity
window and a fixed IMD-cited NE-monsoon window, does the deterministic
day-overlap arithmetic and the documented productivity-factor slip formula
reach the correct number on boundary cases (no overlap, full overlap, partial
overlap, exact-boundary touch)?

Cases are constructed directly against the pure functions with synthetic
day-offset windows — a genuine held-out check, not the bundled schedule.csv
grading its own homework (that live-data behaviour is separately verified by
hand and recorded in PROGRESS.md).

Run:  python -m eval.run_weather_eval   (from backend/, venv active)
      -> writes eval/weather_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.schedule_factors import (  # noqa: E402
    MONSOON_PRODUCTIVITY_FACTOR,
    monsoon_overlap_days,
    weather_predicted_slip,
)

OVERLAP_CASES = [
    {"id": "no-overlap-before", "a_start": 0, "a_end": 20, "m_start": 100, "m_end": 150, "expect": 0},
    {"id": "no-overlap-after", "a_start": 200, "a_end": 220, "m_start": 100, "m_end": 150, "expect": 0},
    {"id": "full-overlap-activity-inside-window", "a_start": 110, "a_end": 130, "m_start": 100, "m_end": 150, "expect": 20},
    {"id": "partial-overlap-tail", "a_start": 90, "a_end": 110, "m_start": 100, "m_end": 150, "expect": 10},
    {"id": "partial-overlap-head", "a_start": 140, "a_end": 160, "m_start": 100, "m_end": 150, "expect": 10},
    {"id": "exact-boundary-touch-zero-width", "a_start": 80, "a_end": 100, "m_start": 100, "m_end": 150, "expect": 0},
    {"id": "window-fully-inside-activity", "a_start": 50, "a_end": 200, "m_start": 100, "m_end": 150, "expect": 50},
]

SLIP_CASES = [
    {"id": "slip-zero-overlap", "overlap": 0, "expect": 0},
    {"id": "slip-standard-factor", "overlap": 12, "factor": MONSOON_PRODUCTIVITY_FACTOR, "expect": round(12 * (1 - MONSOON_PRODUCTIVITY_FACTOR))},
    {"id": "slip-full-loss-factor", "overlap": 10, "factor": 0.0, "expect": 10},
    {"id": "slip-no-loss-factor", "overlap": 10, "factor": 1.0, "expect": 0},
]


def _run_overlap_cases() -> list[dict]:
    out = []
    for c in OVERLAP_CASES:
        got = monsoon_overlap_days(c["a_start"], c["a_end"], c["m_start"], c["m_end"])
        out.append({"id": c["id"], "pass": got == c["expect"], "got": got, "expected": c["expect"]})
    return out


def _run_slip_cases() -> list[dict]:
    out = []
    for c in SLIP_CASES:
        kwargs = {"factor": c["factor"]} if "factor" in c else {}
        got = weather_predicted_slip(c["overlap"], **kwargs)
        out.append({"id": c["id"], "pass": got == c["expect"], "got": got, "expected": c["expect"]})
    return out


def main():
    results = _run_overlap_cases() + _run_slip_cases()
    n_pass = sum(1 for r in results if r["pass"])
    n_total = len(results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Held-out synthetic day-offset windows constructed directly against the pure "
        "functions in app/schedule_factors.py (monsoon day-overlap arithmetic, productivity-factor "
        "slip formula) — not the bundled schedule.csv. Verifies the deterministic arithmetic behind "
        "the P1a 'weather' schedule-risk input (IMD-cited NE-monsoon normal window, planning-grade "
        "climatological, not a forecast). This is a correctness check on the logic, not a claim of "
        "predictive rainfall accuracy.",
        "overlap_cases": _run_overlap_cases(),
        "slip_cases": _run_slip_cases(),
    }

    (Path(__file__).resolve().parent / "weather_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/weather_report.json")


if __name__ == "__main__":
    main()
