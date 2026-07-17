"""Multi-agent mitigation-option generation (Schedule pillar) — the brief's ONLY
explicit "multi-agent system" ask (Predictive Schedule Risk Engine bullet:
"generating mitigation options, not just alerts"). Three specialist agents, each
a bounded, real computation (never open-ended LLM reasoning) — grounded the same
way every other decision in this project is grounded, just applied to a
naturally multiple-valid-answers question (there isn't one right mitigation,
there are several real options worth surfacing) rather than a single verifiable
yes/no. A plain-Python coordinator collects all three (including non-viable
ones, transparently) — no LLM synthesis, no hidden ranking beyond each option's
own numbers.

Why not a framework (LangGraph/CrewAI/etc.)? Each agent here is one bounded
tool-call over data already loaded in this process — no planning loop, no
inter-agent negotiation, no retries against an uncertain environment. A
framework's state/replanning machinery would add complexity this scoped task
doesn't need. See docs/ARCHITECTURE.md's "why not fully agentic" section for the
fuller reasoning and where the line is drawn between this and the pass/fail
pillars, which stay plain deterministic Python with no agents at all.
"""
from __future__ import annotations

from ..schemas import MitigationOption

# Above this required-productivity-increase, resourcing alone is not realistically
# considered a recoverable option (documented, conservative — a construction crew
# running >30% above baseline pace for a sustained stretch is not a safe assumption).
_OVERTIME_RECOVERABLE_THRESHOLD_PCT = 30.0


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _procurement_alternative_agent(
    row: dict, predicted_slip_days: int, shipments: list | None = None
) -> MitigationOption:
    """`shipments`: injected for held-out testing (eval/run_mitigation_eval.py)
    against synthetic Shipment-like objects, never the live demo dataset. When
    None (the real call path from schedule.py), lazily loads the real data —
    lazy because supply_chain.py imports schedule.py's TODAY_DAY/_cpm at module
    load time; a top-level import here would create a schedule -> mitigation ->
    supply_chain -> schedule cycle."""
    wbs_id = row.get("wbs_id", "")
    if shipments is None:
        from ..supply_chain import shipments as sc_shipments

        shipments = sc_shipments()

    match = next((s for s in shipments if s.wbs_id == wbs_id), None)
    if match is None:
        return MitigationOption(
            agent="procurement_alternative",
            viable=False,
            days_recovered=0,
            summary="No tracked shipment feeds this activity.",
            detail=f"wbs_id {wbs_id} has no matching entry in Supply Chain's shipment tracking — "
            "this activity isn't a procurement/delivery item, so an alternative-supplier option "
            "doesn't apply.",
        )
    if match.days_at_risk <= 0:
        return MitigationOption(
            agent="procurement_alternative",
            viable=False,
            days_recovered=0,
            summary=f"{match.procurement_item} shipment is on track — this risk isn't procurement-driven.",
            detail=f"{match.id} ({match.procurement_item}) has 0 days at risk in Supply Chain "
            "tracking — the predicted slip on this activity comes from a different driver "
            "(progress lag / weather), not a delivery delay, so switching suppliers wouldn't "
            "address it even though alternatives exist.",
        )
    viable_alts = [a for a in match.alternatives if a.viable]
    if not viable_alts:
        return MitigationOption(
            agent="procurement_alternative",
            viable=False,
            days_recovered=0,
            summary=f"No viable alternative supplier for {match.procurement_item}.",
            detail=f"{match.id} ({match.procurement_item}) has {len(match.alternatives)} tracked "
            "alternative(s), none arriving by the required-on-site date — a procurement swap "
            "won't recover this slip; escalate for a schedule replan instead.",
        )
    best = min(viable_alts, key=lambda a: a.projected_arrival_day)
    days_recovered = min(max(0, predicted_slip_days), match.days_at_risk)
    return MitigationOption(
        agent="procurement_alternative",
        viable=True,
        days_recovered=days_recovered,
        cost_premium_pct=best.cost_premium_pct,
        summary=f"Switch to {best.supplier} — arrives day {best.projected_arrival_day}, "
        f"+{best.cost_premium_pct:g}% cost.",
        detail=f"{match.id} ({match.procurement_item}): {best.supplier} ({best.city}) has a "
        f"{best.lead_time_days}d lead time and would arrive by day {best.projected_arrival_day}, "
        f"on or before the required-on-site date — recovers the shipment's {match.days_at_risk}d "
        f"at-risk gap at a {best.cost_premium_pct:g}% cost premium.",
    )


def _resequencing_float_agent(wbs_id: str, predicted_slip_days: int, cpm: dict) -> MitigationOption:
    float_days = cpm.get("float", {}).get(wbs_id, 0)
    if float_days <= 0:
        return MitigationOption(
            agent="resequencing_float",
            viable=False,
            days_recovered=0,
            summary="No schedule float — this activity is on (or at) the critical path.",
            detail=f"CPM float for {wbs_id} is {float_days}d — the predicted {predicted_slip_days}d "
            "slip has no slack to absorb; it will push the project finish date unless mitigated "
            "another way.",
        )
    recovered = min(float_days, max(0, predicted_slip_days))
    fully = recovered >= predicted_slip_days
    return MitigationOption(
        agent="resequencing_float",
        viable=True,
        days_recovered=recovered,
        summary=f"{recovered}d absorbed by existing schedule float"
        + (" — fully covers the predicted slip." if fully else f" ({predicted_slip_days - recovered}d still exposed)."),
        detail=f"CPM float for {wbs_id} is {float_days}d (real forward/backward pass over the "
        "dependency DAG, see schedule.py::_cpm). This is EXISTING slack already in the network, "
        "not a proposed resequencing plan — a deeper resequencing recommendation would need "
        "resource-loading data this project doesn't have.",
    )


def _resource_recovery_agent(row: dict, predicted_slip_days: int, today_day: int) -> MitigationOption:
    duration = _to_int(row.get("duration_days"), 1) or 1
    start = _to_int(row.get("planned_start_day"))
    if predicted_slip_days <= 0:
        return MitigationOption(
            agent="resource_recovery",
            viable=False,
            days_recovered=0,
            summary="No slip to recover.",
            detail="predicted_slip_days is 0 — resourcing/overtime is not applicable.",
        )
    remaining = duration - (today_day - start)
    if remaining <= 0:
        return MitigationOption(
            agent="resource_recovery",
            viable=False,
            days_recovered=0,
            summary="Planned duration window has already elapsed — a faster-execution recovery no longer applies.",
            detail=f"planned_start_day {start} + duration_days {duration} is at or before today "
            f"(day {today_day}) — there is no remaining time left in the ORIGINAL window to run "
            "faster within; a productivity-increase recovery isn't a meaningful lever here. "
            "Consider the procurement-alternative or resequencing-float options instead.",
        )
    overtime_pct_needed = round((predicted_slip_days / remaining) * 100, 1)
    viable = overtime_pct_needed <= _OVERTIME_RECOVERABLE_THRESHOLD_PCT
    if viable:
        return MitigationOption(
            agent="resource_recovery",
            viable=True,
            days_recovered=predicted_slip_days,
            summary=f"Recoverable with ~{overtime_pct_needed:g}% added crew/overtime capacity.",
            detail=f"Clawing back {predicted_slip_days}d within the {remaining}d remaining in the "
            f"planned duration requires running ~{overtime_pct_needed:g}% above baseline pace — "
            f"under the {_OVERTIME_RECOVERABLE_THRESHOLD_PCT:g}% documented threshold for a "
            "realistic sustained crew/overtime increase.",
        )
    max_realistic_days = round(remaining * (_OVERTIME_RECOVERABLE_THRESHOLD_PCT / 100))
    return MitigationOption(
        agent="resource_recovery",
        viable=False,
        days_recovered=max_realistic_days,
        summary=f"Would need ~{overtime_pct_needed:g}% added capacity — not realistically "
        "recoverable via resourcing alone.",
        detail=f"Clawing back the full {predicted_slip_days}d within {remaining}d remaining needs "
        f"~{overtime_pct_needed:g}% above baseline pace, over the "
        f"{_OVERTIME_RECOVERABLE_THRESHOLD_PCT:g}% documented realistic threshold. At the "
        f"threshold rate, at most ~{max_realistic_days}d could realistically be recovered this way "
        "— the rest needs another lever.",
    )


def generate_mitigation_options(
    row: dict, predicted_slip_days: int, cpm: dict, today_day: int
) -> list[MitigationOption]:
    """Coordinator: runs all three specialist agents, returns every result
    (including non-viable ones) — no hidden ranking, no LLM synthesis."""
    return [
        _procurement_alternative_agent(row, predicted_slip_days),
        _resequencing_float_agent(row.get("wbs_id", ""), predicted_slip_days, cpm),
        _resource_recovery_agent(row, predicted_slip_days, today_day),
    ]
