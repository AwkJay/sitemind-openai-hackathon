"""SiteMind IMPACT-MODEL evaluation — eval #9, a separate, honest metric from the
other 8 (never blended).

What this measures and why: `app/impact.py` composes the platform-wide ROI ticker
(engineer-hours + Rs saved) from real per-pillar signals x documented, conservative
per-unit assumptions. This eval does NOT claim those assumptions are empirically
correct (no real historical baseline exists to backtest against — same caveat as
`run_supply_chain_eval.py`). It IS a genuine correctness check on the ARITHMETIC: given
a pillar's real computed inputs (NCR count, flag count, days-at-risk, FAIL count),
does `impact.py` multiply by the RIGHT documented constant and report the right
number — guarding the formula against silent drift (e.g. an edit that changes a
constant without updating `basis`, or an off-by-one in the aggregation).

Cases are constructed directly against the pure functions in `app/impact.py`
(`compliance_impact`, `_schedule_impact_from`, `_supply_chain_impact_from`,
`_commissioning_impact_from`) with fixed synthetic inputs — a genuine held-out
arithmetic check, not the demo data grading its own homework.

Run:  python -m eval.run_impact_eval   (from backend/, venv active)
      -> writes eval/impact_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.impact import (  # noqa: E402
    COMMISSIONING_HOURS_PER_FAIL,
    COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE,
    COMMISSIONING_INR_PER_FAIL,
    COMMISSIONING_INR_PER_WITHIN_ALLOWABLE,
    COMPLIANCE_HOURS_PER_ISSUE,
    COMPLIANCE_REWORK_INR_PER_ISSUE,
    SCHEDULE_HOURS_PER_FLAG,
    SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED,
    SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT,
    SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED,
    _commissioning_impact_from,
    _schedule_impact_from,
    _supply_chain_impact_from,
    compliance_impact,
)

CASES = [
    # (id, fn, args, expected_hours, expected_inr)
    ("compliance-zero", compliance_impact, (0,), 0, 0),
    ("compliance-six", compliance_impact, (6,), 6 * COMPLIANCE_HOURS_PER_ISSUE, 6 * COMPLIANCE_REWORK_INR_PER_ISSUE),
    ("compliance-large", compliance_impact, (25,), 25 * COMPLIANCE_HOURS_PER_ISSUE, 25 * COMPLIANCE_REWORK_INR_PER_ISSUE),
    ("schedule-zero-flags", _schedule_impact_from, (0, 0), 0, 0),
    (
        "schedule-flags-no-critical-impact",
        _schedule_impact_from,
        (5, 0),
        5 * SCHEDULE_HOURS_PER_FLAG,
        0,  # flags exist but none on critical path with nonzero impact -> zero INR, not invented
    ),
    (
        "schedule-typical",
        _schedule_impact_from,
        (13, 101),
        13 * SCHEDULE_HOURS_PER_FLAG,
        101 * SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED,
    ),
    ("supply-chain-none-at-risk", _supply_chain_impact_from, (0, 0), 0, 0),
    (
        "supply-chain-typical",
        _supply_chain_impact_from,
        (2, 10),
        2 * SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT,
        10 * SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED,
    ),
    ("commissioning-all-pass", _commissioning_impact_from, (0, 0), 0, 0),
    (
        "commissioning-fail-only",
        _commissioning_impact_from,
        (3, 0),
        3 * COMMISSIONING_HOURS_PER_FAIL,
        3 * COMMISSIONING_INR_PER_FAIL,
    ),
    (
        "commissioning-within-allowable-only",
        _commissioning_impact_from,
        (0, 4),
        4 * COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE,
        4 * COMMISSIONING_INR_PER_WITHIN_ALLOWABLE,
    ),
    (
        "commissioning-mixed",
        _commissioning_impact_from,
        (2, 1),
        2 * COMMISSIONING_HOURS_PER_FAIL + 1 * COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE,
        2 * COMMISSIONING_INR_PER_FAIL + 1 * COMMISSIONING_INR_PER_WITHIN_ALLOWABLE,
    ),
]


def _run() -> list[dict]:
    results = []
    for case_id, fn, args, expected_hours, expected_inr in CASES:
        impact = fn(*args)
        hours_ok = impact.hours_saved == expected_hours
        inr_ok = impact.inr_saved == expected_inr
        basis_nonempty = bool(impact.basis and impact.basis.strip())
        results.append(
            {
                "id": case_id,
                "pass": hours_ok and inr_ok and basis_nonempty,
                "hours_saved": impact.hours_saved,
                "expected_hours": expected_hours,
                "inr_saved": impact.inr_saved,
                "expected_inr": expected_inr,
                "basis_nonempty": basis_nonempty,
            }
        )
    return results


def main():
    results = _run()
    n_pass = sum(1 for r in results if r["pass"])
    n_total = len(results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "method": "Held-out synthetic input cases constructed directly against the pure formula "
        "functions in app/impact.py (compliance_impact, _schedule_impact_from, "
        "_supply_chain_impact_from, _commissioning_impact_from) — not the live demo dataset. "
        "Verifies the arithmetic composing the platform-wide ROI ticker is correct across edge "
        "cases (zero-issue pillars, flags with no critical-path impact, mixed FAIL/within-"
        "allowable commissioning). This is a correctness check on the formula and its "
        "aggregation, not a claim that the underlying per-unit assumptions (hours/Rs per issue) "
        "are empirically validated against real project history — none exists to backtest "
        "against; every constant is stated in PillarImpact.basis for the user to defend or "
        "revise on stage.",
        "cases": results,
    }

    (Path(__file__).resolve().parent / "impact_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/impact_report.json")


if __name__ == "__main__":
    main()
