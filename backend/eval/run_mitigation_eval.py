"""SiteMind MULTI-AGENT MITIGATION evaluation — eval #11, a separate, honest
metric from the other 10 (never blended).

What this measures and why: `app/agents/mitigation.py` runs three specialist
agents per flagged schedule risk (procurement-alternative, resequencing-float,
resource-recovery), each a bounded real computation — this is the brief's ONLY
explicit "multi-agent system" ask (Predictive Schedule Risk Engine: "generating
mitigation options, not just alerts"). This eval does NOT claim the recommended
options are optimal project-management advice — it IS a genuine correctness check
on each agent's ARITHMETIC and edge-case handling: given fixed synthetic inputs,
does each agent reach the right viable/non-viable verdict and the right
days-recovered number.

Cases are constructed directly against the pure agent functions with SYNTHETIC
Shipment/row/cpm objects (procurement agent takes an injected `shipments` list
specifically so this eval never touches the live demo dataset) — a genuine
held-out check, not the demo data grading its own homework.

Run:  python -m eval.run_mitigation_eval   (from backend/, venv active)
      -> writes eval/mitigation_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.agents.mitigation import (  # noqa: E402
    _OVERTIME_RECOVERABLE_THRESHOLD_PCT,
    _procurement_alternative_agent,
    _resequencing_float_agent,
    _resource_recovery_agent,
)
from app.schemas import (  # noqa: E402
    EquipmentSpecCheck,
    ProcurementAlternative,
    Shipment,
    SupplyPoint,
)

_SITE = SupplyPoint(name="t1", city="c", country="in", lat=0.0, lon=0.0)
_NA_SPEC = EquipmentSpecCheck(standard_applicable=False, status="NOT_APPLICABLE", note="n/a")


def _shipment(wbs_id, days_at_risk, alternatives) -> Shipment:
    return Shipment(
        id="SHP-TEST",
        procurement_item="Test item",
        wbs_id=wbs_id,
        tier1_supplier=_SITE,
        tier2_suppliers=[],
        milestones=[],
        current_stage="in_transit",
        required_on_site_by=100,
        projected_arrival_day=100 + days_at_risk,
        days_at_risk=days_at_risk,
        on_critical_path=False,
        alternatives=alternatives,
        equipment_spec=_NA_SPEC,
    )


def _alt(supplier, cost_premium_pct, viable, arrival=90) -> ProcurementAlternative:
    return ProcurementAlternative(
        supplier=supplier, city="c", country="in", lat=0.0, lon=0.0,
        lead_time_days=10, cost_premium_pct=cost_premium_pct, viable=viable,
        projected_arrival_day=arrival,
    )


# --------------------------------------------------------------------------- #
# Procurement-alternative agent
# --------------------------------------------------------------------------- #
PROCUREMENT_CASES = [
    (
        "no-matching-shipment",
        dict(row={"wbs_id": "WBS-X"}, predicted_slip_days=10, shipments=[]),
        {"viable": False, "days_recovered": 0},
    ),
    (
        "shipment-not-at-risk",
        dict(
            row={"wbs_id": "WBS-A"}, predicted_slip_days=10,
            shipments=[_shipment("WBS-A", days_at_risk=0, alternatives=[_alt("S1", 10, True)])],
        ),
        {"viable": False, "days_recovered": 0},
    ),
    (
        "at-risk-no-viable-alt",
        dict(
            row={"wbs_id": "WBS-B"}, predicted_slip_days=10,
            shipments=[_shipment("WBS-B", days_at_risk=5, alternatives=[_alt("S1", 10, False)])],
        ),
        {"viable": False, "days_recovered": 0},
    ),
    (
        "at-risk-viable-alt-caps-at-days-at-risk",
        dict(
            row={"wbs_id": "WBS-C"}, predicted_slip_days=20,
            shipments=[_shipment("WBS-C", days_at_risk=5, alternatives=[_alt("S1", 10, True)])],
        ),
        {"viable": True, "days_recovered": 5, "cost_premium_pct": 10},
    ),
    (
        "at-risk-viable-alt-caps-at-predicted-slip",
        dict(
            row={"wbs_id": "WBS-D"}, predicted_slip_days=3,
            shipments=[_shipment("WBS-D", days_at_risk=20, alternatives=[_alt("S1", 15, True)])],
        ),
        {"viable": True, "days_recovered": 3, "cost_premium_pct": 15},
    ),
]

# --------------------------------------------------------------------------- #
# Resequencing-float agent
# --------------------------------------------------------------------------- #
RESEQ_CASES = [
    ("zero-float-not-viable", dict(wbs_id="A", predicted_slip_days=10, cpm={"float": {"A": 0}}), {"viable": False, "days_recovered": 0}),
    ("negative-float-not-viable", dict(wbs_id="A", predicted_slip_days=10, cpm={"float": {"A": -3}}), {"viable": False, "days_recovered": 0}),
    ("float-fully-covers-slip", dict(wbs_id="A", predicted_slip_days=5, cpm={"float": {"A": 12}}), {"viable": True, "days_recovered": 5}),
    ("float-partially-covers-slip", dict(wbs_id="A", predicted_slip_days=12, cpm={"float": {"A": 5}}), {"viable": True, "days_recovered": 5}),
]

# --------------------------------------------------------------------------- #
# Resource-recovery agent
# --------------------------------------------------------------------------- #
RESOURCE_CASES = [
    ("zero-slip-not-applicable", dict(row={"duration_days": "30", "planned_start_day": "0"}, predicted_slip_days=0, today_day=10), {"viable": False, "days_recovered": 0}),
    (
        "window-already-elapsed",
        dict(row={"duration_days": "10", "planned_start_day": "0"}, predicted_slip_days=5, today_day=20),
        {"viable": False, "days_recovered": 0},
    ),
    (
        "under-threshold-viable",
        # remaining = 30 - (10-0) = 20; overtime = (4/20)*100 = 20% <= 30% threshold
        dict(row={"duration_days": "30", "planned_start_day": "0"}, predicted_slip_days=4, today_day=10),
        {"viable": True, "days_recovered": 4},
    ),
    (
        "over-threshold-not-viable-partial-recovery",
        # remaining = 30 - (10-0) = 20; overtime = (10/20)*100 = 50% > 30% threshold
        # max_realistic_days = round(20 * 0.30) = 6
        dict(row={"duration_days": "30", "planned_start_day": "0"}, predicted_slip_days=10, today_day=10),
        {"viable": False, "days_recovered": 6},
    ),
]


def _run_procurement():
    results = []
    for case_id, kwargs, expect in PROCUREMENT_CASES:
        o = _procurement_alternative_agent(**kwargs)
        checks = {
            "viable": (o.viable == expect["viable"], o.viable, expect["viable"]),
            "days_recovered": (o.days_recovered == expect["days_recovered"], o.days_recovered, expect["days_recovered"]),
        }
        if "cost_premium_pct" in expect:
            checks["cost_premium_pct"] = (o.cost_premium_pct == expect["cost_premium_pct"], o.cost_premium_pct, expect["cost_premium_pct"])
        results.append({"id": case_id, "pass": all(v[0] for v in checks.values()), "checks": checks})
    return results


def _run_reseq():
    results = []
    for case_id, kwargs, expect in RESEQ_CASES:
        o = _resequencing_float_agent(**kwargs)
        ok = o.viable == expect["viable"] and o.days_recovered == expect["days_recovered"]
        results.append({"id": case_id, "pass": ok, "got": (o.viable, o.days_recovered), "expected": (expect["viable"], expect["days_recovered"])})
    return results


def _run_resource():
    results = []
    for case_id, kwargs, expect in RESOURCE_CASES:
        o = _resource_recovery_agent(**kwargs)
        ok = o.viable == expect["viable"] and o.days_recovered == expect["days_recovered"]
        results.append({"id": case_id, "pass": ok, "got": (o.viable, o.days_recovered), "expected": (expect["viable"], expect["days_recovered"])})
    return results


def main():
    procurement = _run_procurement()
    reseq = _run_reseq()
    resource = _run_resource()
    all_results = procurement + reseq + resource
    n_pass = sum(1 for r in all_results if r["pass"])
    n_total = len(all_results)

    report = {
        "n_cases": n_total,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_total, 4) if n_total else None,
        "overtime_recoverable_threshold_pct": _OVERTIME_RECOVERABLE_THRESHOLD_PCT,
        "method": "Held-out synthetic cases constructed directly against the three pure agent "
        "functions in app/agents/mitigation.py, using synthetic Shipment/row/cpm objects (the "
        "procurement agent takes an injected shipments list specifically so this eval never "
        "touches the live demo dataset). Verifies each agent's viable/non-viable verdict and "
        "days_recovered arithmetic across edge cases (shipment not at risk, alt caps at "
        "days_at_risk vs predicted_slip, zero/negative float, elapsed planning window, "
        "over/under the overtime-recoverable threshold). This is a correctness check on each "
        "agent's grounded computation, not a claim that the RECOMMENDED action is optimal "
        "project-management advice — every option states its own real inputs so a PM can judge it.",
        "procurement_alternative_cases": procurement,
        "resequencing_float_cases": reseq,
        "resource_recovery_cases": resource,
    }

    (Path(__file__).resolve().parent / "mitigation_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_cases={n_total}  n_pass={n_pass}  accuracy={report['accuracy']}")
    for r in all_results:
        if not r["pass"]:
            print(f"  FAIL: {r}")
    print("wrote eval/mitigation_report.json")


if __name__ == "__main__":
    main()
