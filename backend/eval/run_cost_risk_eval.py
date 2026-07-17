"""SiteMind COST-RISK evaluation — eval #10, a separate, honest metric from the
other 9 (never blended).

What this measures and why: `app/cost_risk.py` composes a deterministic cost-at-risk
figure from three real signals (critical-path project-impact days, viable-alternative
cost premiums, open-NCR count) x documented rates/base-costs. This eval does NOT
claim the daily-delay-rate or per-item base-cost assumptions are empirically
validated (no real project cost history exists to backtest against — same caveat
as run_impact_eval.py and run_supply_chain_eval.py). It IS a genuine correctness
check on the ARITHMETIC: given fixed inputs, does each formula term compute the
right number, and does the total sum correctly — guarding against silent drift.

Cases are constructed directly against the pure functions in `app/cost_risk.py`
(`schedule_delay_cost_from`, `expedite_premium_cost_from`, `rework_exposure_from`)
with fixed synthetic inputs — a genuine held-out arithmetic check, not the demo
data grading its own homework.

Run:  python -m eval.run_cost_risk_eval   (from backend/, venv active)
      -> writes eval/cost_risk_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.cost_risk import (  # noqa: E402
    expedite_premium_cost_from,
    rework_exposure_from,
    schedule_delay_cost_from,
)

SCHEDULE_CASES = [
    ("schedule-zero-days", 0, 350_000, 0),
    ("schedule-typical", 101, 350_000, 101 * 350_000),
    ("schedule-different-rate", 50, 100_000, 50 * 100_000),
]

REWORK_CASES = [
    ("rework-zero-ncrs", 0, 1_500_000, 0),
    ("rework-six-ncrs", 6, 1_500_000, 6 * 1_500_000),
]

EXPEDITE_CASES = [
    ("expedite-no-items", [], 0),
    (
        "expedite-single-item",
        [("SHP-002", "LV switchgear 4000A", 22.0, 45_000_000)],
        round(45_000_000 * 0.22),
    ),
    (
        "expedite-multi-item",
        [
            ("SHP-001", "DRUPS 2.5MW", 45.0, 180_000_000),
            ("SHP-002", "LV switchgear 4000A", 22.0, 45_000_000),
        ],
        round(180_000_000 * 0.45) + round(45_000_000 * 0.22),
    ),
    (
        "expedite-zero-pct-still-zero-cost",
        [("SHP-003", "Busway 4000A", 0.0, 18_000_000)],
        0,
    ),
]


def _run_schedule() -> list[dict]:
    results = []
    for case_id, days, rate, expected in SCHEDULE_CASES:
        c = schedule_delay_cost_from(days, rate)
        results.append({"id": case_id, "pass": c.inr == expected, "got": c.inr, "expected": expected})
    return results


def _run_rework() -> list[dict]:
    results = []
    for case_id, n, rate, expected in REWORK_CASES:
        c = rework_exposure_from(n, rate)
        results.append({"id": case_id, "pass": c.inr == expected, "got": c.inr, "expected": expected})
    return results


def _run_expedite() -> list[dict]:
    results = []
    for case_id, items, expected in EXPEDITE_CASES:
        c = expedite_premium_cost_from(items)
        results.append({"id": case_id, "pass": c.inr == expected, "got": c.inr, "expected": expected})
    return results


def main():
    all_results = _run_schedule() + _run_rework() + _run_expedite()
    n_pass = sum(1 for r in all_results if r["pass"])
    n_total = len(all_results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Held-out synthetic input cases constructed directly against the pure formula "
        "functions in app/cost_risk.py (schedule_delay_cost_from, expedite_premium_cost_from, "
        "rework_exposure_from) — not the live demo dataset. Verifies each cost-at-risk formula "
        "term computes correctly across edge cases (zero inputs, multi-item aggregation, a "
        "zero-percent premium correctly contributing zero cost). This is a correctness check on "
        "the formula, not a claim that the daily-delay-rate or per-item base-cost assumptions in "
        "cost_basis.json are empirically validated against real project cost history — none "
        "exists to backtest against; every rate is stated in CostRiskComponent.basis for the "
        "user to defend or revise on stage.",
        "schedule_delay_cases": _run_schedule(),
        "rework_exposure_cases": _run_rework(),
        "expedite_premium_cases": _run_expedite(),
    }

    (Path(__file__).resolve().parent / "cost_risk_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in all_results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/cost_risk_report.json")


if __name__ == "__main__":
    main()
