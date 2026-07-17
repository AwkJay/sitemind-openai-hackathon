"""Per-pillar impact model — extends overview.py's original Compliance-only ROI
formula to Schedule, Supply-Chain and Commissioning, each from a REAL computed
signal (NCR count / schedule risk fields / supply-chain days-at-risk / commissioning
FAIL count) with its own documented, conservative per-unit assumption — same
discipline as overview.py's original HOURS_PER_ISSUE / REWORK_INR_PER_ISSUE
constants, now shared from here so all 4 pillars use one audited module instead of
scattering assumptions. Answers the brief's "reduction in manual coordination
effort, measured in hours" metric across the whole platform, not just Compliance.

Nothing here is asserted at call time: every PillarImpact is computed from a live
pipeline result (the same `evaluate()` / `schedule.risks()` / `supply_chain.risks()`
calls the rest of the app already uses), multiplied by a constant that is stated in
`basis` so it is defensible on stage, not hidden inside a number. See
`eval/run_impact_eval.py` for a held-out check that guards this formula against
silent drift — a second, separate eval number, never blended with the other 9.
"""
from __future__ import annotations

from functools import lru_cache

from . import config
from .commissioning import build_quality_package, parse_test_log
from .schedule import risks as schedule_risks
from .schemas import PillarImpact
from .supply_chain import risks as supply_chain_risks

# --- Compliance: unchanged from the original overview.py formula. ~20 engineer-hours
# to manually cross-check a submittal against the code + write the NCR by hand; ~Rs 15
# lakh average rework/avoidance cost per structural/durability non-conformance caught
# before casting. Round, conservative, documented.
COMPLIANCE_HOURS_PER_ISSUE = 20
COMPLIANCE_REWORK_INR_PER_ISSUE = 1_500_000

# --- Schedule: hours to manually chase down a leading-indicator flag (root-cause
# investigation + stakeholder email + a mitigation plan) that SiteMind raises
# automatically, vs. a PM discovering it only once visibly behind. ~Rs 50,000
# avoided COORDINATION/overhead cost per day of CRITICAL-PATH project impact caught
# early (site-management overhead of an unplanned schedule fire-drill, not the
# project's liquidated-damages exposure — that much larger, separate number is
# covered by cost_risk.py's schedule_delay_cost so the two are never double-counted).
SCHEDULE_HOURS_PER_FLAG = 4
SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED = 50_000

# --- Supply-chain: hours to manually chase a multi-tier root cause across supplier
# tiers + evaluate alternative suppliers by hand (SiteMind does both instantly per
# shipment). ~Rs 75,000 avoided holding/coordination cost per day-at-risk caught
# early enough to still act (distinct from, and smaller than, the expedite-premium
# cost cost_risk.py computes for shipments that must actually be expedited).
SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT = 6
SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED = 75_000

# --- Commissioning: hours to manually re-test + re-commission a zone that fails the
# thermal envelope (SiteMind flags it in the same test run instead of a later,
# separate O&M audit). A within-allowable-but-outside-recommended finding gets a
# lighter touch (log + retune at next maintenance window, not an urgent re-test).
COMMISSIONING_HOURS_PER_FAIL = 8
COMMISSIONING_INR_PER_FAIL = 300_000  # re-test + CRAH re-balance labour + downtime risk
COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE = 2
COMMISSIONING_INR_PER_WITHIN_ALLOWABLE = 0  # logged for O&M review only, no urgent spend


@lru_cache(maxsize=1)
def _sample_commissioning_package():
    """Runs the bundled sample cooling test log through the REAL, unmodified
    commissioning pipeline (parse_test_log + build_quality_package) so the
    Commissioning contribution to the impact model is a genuine computed result,
    not an invented count. Same honesty tier as the rest of the demo dataset:
    the log is representative synthetic data, the pipeline over it is real."""
    path = config.DATA_DIR / "project_docs" / "sample_commissioning_log.csv"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_test_log(content)
    if not parsed.records:
        return None
    return build_quality_package(parsed.records)


def compliance_impact(issues_caught: int) -> PillarImpact:
    return PillarImpact(
        pillar="compliance",
        hours_saved=issues_caught * COMPLIANCE_HOURS_PER_ISSUE,
        inr_saved=issues_caught * COMPLIANCE_REWORK_INR_PER_ISSUE,
        basis=f"{issues_caught} open NCR(s) x {COMPLIANCE_HOURS_PER_ISSUE}h manual cross-check/write-up "
        f"avoided + Rs {COMPLIANCE_REWORK_INR_PER_ISSUE:,} rework avoided per issue caught pre-site.",
    )


def _schedule_impact_from(n_flags: int, critical_days_avoided: int) -> PillarImpact:
    """Pure arithmetic, held-out testable (see eval/run_impact_eval.py) — no I/O."""
    return PillarImpact(
        pillar="schedule",
        hours_saved=n_flags * SCHEDULE_HOURS_PER_FLAG,
        inr_saved=critical_days_avoided * SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED,
        basis=f"{n_flags} leading-indicator flag(s) x {SCHEDULE_HOURS_PER_FLAG}h manual root-cause/"
        f"escalation avoided + {critical_days_avoided}d of critical-path impact (summed across "
        f"findings, each independently CPM-recomputed) caught early x "
        f"Rs {SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED:,}/day coordination overhead avoided.",
    )


def schedule_impact() -> PillarImpact:
    risks = schedule_risks()
    n_flags = len(risks)
    critical_days_avoided = sum(r.project_impact_days for r in risks if r.on_critical_path)
    return _schedule_impact_from(n_flags, critical_days_avoided)


def _supply_chain_impact_from(n_at_risk: int, days_at_risk: int) -> PillarImpact:
    """Pure arithmetic, held-out testable (see eval/run_impact_eval.py) — no I/O."""
    return PillarImpact(
        pillar="supply_chain",
        hours_saved=n_at_risk * SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT,
        inr_saved=days_at_risk * SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED,
        basis=f"{n_at_risk} at-risk shipment(s) x {SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT}h manual "
        f"root-cause/alternative-evaluation avoided + {days_at_risk}d at-risk mitigated early x "
        f"Rs {SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED:,}/day.",
    )


def supply_chain_impact() -> PillarImpact:
    risks = supply_chain_risks()
    n_at_risk = len(risks)
    days_at_risk = sum(r.days_at_risk for r in risks)
    return _supply_chain_impact_from(n_at_risk, days_at_risk)


def _commissioning_impact_from(fail_count: int, within_allowable_count: int) -> PillarImpact:
    """Pure arithmetic, held-out testable (see eval/run_impact_eval.py) — no I/O."""
    hours = (
        fail_count * COMMISSIONING_HOURS_PER_FAIL
        + within_allowable_count * COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE
    )
    inr = (
        fail_count * COMMISSIONING_INR_PER_FAIL
        + within_allowable_count * COMMISSIONING_INR_PER_WITHIN_ALLOWABLE
    )
    return PillarImpact(
        pillar="commissioning",
        hours_saved=hours,
        inr_saved=inr,
        basis=f"{fail_count} FAIL x {COMMISSIONING_HOURS_PER_FAIL}h re-test/re-commission avoided + "
        f"{within_allowable_count} within-allowable-only x {COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE}h "
        f"O&M-review avoided (cooling slice only — see corpus-limitation banner).",
    )


def commissioning_impact() -> PillarImpact:
    pkg = _sample_commissioning_package()
    if pkg is None:
        return PillarImpact(
            pillar="commissioning",
            hours_saved=0,
            inr_saved=0,
            basis="No commissioning test log available to compute from.",
        )
    return _commissioning_impact_from(pkg.fail_count, pkg.within_allowable_count)


def all_pillar_impacts(issues_caught: int) -> list[PillarImpact]:
    return [
        compliance_impact(issues_caught),
        schedule_impact(),
        supply_chain_impact(),
        commissioning_impact(),
    ]
