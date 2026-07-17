"""Cost-at-Risk — the brief's "schedule AND cost risk modelling" ask (only schedule
risk existed before this module).

Deterministic, transparent formula (NOT ML / Monte-Carlo — a black-box cost
distribution would contradict the project's no-ML, explainable-decisions thesis):

    cost_at_risk = schedule_delay_cost + expedite_premium_cost + rework_exposure

  schedule_delay_cost   = sum of `project_impact_days` (a REAL CPM re-run, see
                           schedule.py) across on-critical-path schedule risks, x a
                           documented daily delay/liquidated-damages rate.
  expedite_premium_cost = for each at-risk shipment that has a viable recommended
                           alternative (supply_chain.py), that alternative's real
                           `cost_premium_pct` x a documented per-item base equipment
                           cost. Shipments with no viable alternative contribute 0
                           here (never invented) — that honest gap is itself the
                           argument for earlier detection.
  rework_exposure        = open Compliance NCR count x the SAME
                           REWORK_INR_PER_ISSUE constant impact.py's ROI ticker uses
                           — reused, never duplicated, so the two numbers can't
                           silently diverge on one assumption.

`cost_basis.json` (backend/data/project_docs/) is REPRESENTATIVE synthetic data
(order-of-magnitude BOQ figures, not any real project's actual costs) — same
honesty tier as the rest of the demo dataset, disclosed via `CostRisk.data_note`.
The formula and its live inputs (project_impact_days, cost_premium_pct, NCR count)
are real. See eval/run_cost_risk_eval.py for a held-out arithmetic check (eval #10,
never blended with the other 9).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter

from . import config
from .impact import COMPLIANCE_REWORK_INR_PER_ISSUE
from .overview import _all_ncrs
from .schedule import risks as schedule_risks
from .schemas import CostRisk, CostRiskComponent
from .supply_chain import shipments as supply_chain_shipments

router = APIRouter(prefix="/api", tags=["cost-risk"])


@lru_cache(maxsize=1)
def _cost_basis() -> dict:
    import json

    path = config.DATA_DIR / "project_docs" / "cost_basis.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"daily_delay_rate_inr": 0, "equipment_base_cost_inr": {}, "default_equipment_base_cost_inr": 0}


# --------------------------------------------------------------------------- #
# Pure formula functions — held-out testable (eval/run_cost_risk_eval.py), no I/O.
# --------------------------------------------------------------------------- #
def schedule_delay_cost_from(critical_days: int, daily_rate: int) -> CostRiskComponent:
    return CostRiskComponent(
        label="Schedule delay exposure",
        inr=critical_days * daily_rate,
        basis=f"{critical_days}d of critical-path project impact (CPM-recomputed, summed across "
        f"findings) x Rs {daily_rate:,}/day documented delay/liquidated-damages rate.",
    )


def expedite_premium_cost_from(items: list[tuple[str, str, float, int]]) -> CostRiskComponent:
    """items: (shipment_id, procurement_item, cost_premium_pct, base_cost_inr) for
    each at-risk shipment that has a viable recommended alternative."""
    total = 0.0
    lines: list[str] = []
    for shipment_id, procurement_item, pct, base_cost in items:
        premium = base_cost * (pct / 100.0)
        total += premium
        lines.append(f"{shipment_id} ({procurement_item}): {pct:g}% premium on Rs {base_cost:,} base = Rs {round(premium):,}")
    return CostRiskComponent(
        label="Expedite-premium exposure",
        inr=round(total),
        basis="; ".join(lines) if lines else "No at-risk shipment currently has a viable alternative requiring an expedite premium.",
    )


def rework_exposure_from(open_ncr_count: int, rate: int) -> CostRiskComponent:
    return CostRiskComponent(
        label="Rework exposure (open NCRs)",
        inr=open_ncr_count * rate,
        basis=f"{open_ncr_count} open NCR(s) x Rs {rate:,} avg rework cost per issue "
        "(same assumption the ROI ticker's Compliance pillar uses).",
    )


# --------------------------------------------------------------------------- #
# Live composition
# --------------------------------------------------------------------------- #
def compute_cost_risk() -> CostRisk:
    basis = _cost_basis()
    daily_rate = basis.get("daily_delay_rate_inr", 0)
    base_costs = basis.get("equipment_base_cost_inr", {})
    default_cost = basis.get("default_equipment_base_cost_inr", 0)

    critical_days = sum(r.project_impact_days for r in schedule_risks() if r.on_critical_path)

    expedite_items: list[tuple[str, str, float, int]] = []
    for s in supply_chain_shipments():
        if s.days_at_risk <= 0:
            continue
        viable = [a for a in s.alternatives if a.viable]
        if not viable:
            continue
        best = min(viable, key=lambda a: a.projected_arrival_day)
        base_cost = base_costs.get(s.procurement_item, default_cost)
        expedite_items.append((s.id, s.procurement_item, best.cost_premium_pct, base_cost))

    open_ncr_count = len(_all_ncrs())

    components = [
        schedule_delay_cost_from(critical_days, daily_rate),
        expedite_premium_cost_from(expedite_items),
        rework_exposure_from(open_ncr_count, COMPLIANCE_REWORK_INR_PER_ISSUE),
    ]
    return CostRisk(
        total_inr=sum(c.inr for c in components),
        components=components,
        data_note=basis.get("_note", ""),
    )


@router.get("/cost-risk", response_model=CostRisk)
def get_cost_risk() -> CostRisk:
    return compute_cost_risk()
