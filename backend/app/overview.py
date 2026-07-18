"""GET /api/overview — ROI ticker stats derived from real NCRs + schedule risks.

engineer_hours_saved / rework_avoided_inr are now PLATFORM-WIDE totals (Compliance +
Schedule + Supply-Chain + Commissioning), composed from `impact.py`'s per-pillar,
documented-assumption model — see `by_pillar` for the breakdown with each pillar's
exact computed inputs. Previously (pre-2026-07-03) this endpoint counted Compliance
NCRs only; extending it answers the brief's "reduction in manual coordination effort,
measured in hours" metric across the whole platform, not one pillar.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import config
from .agents.compliance import evaluate
from .data_loader import load_submittals
from .impact import COMPLIANCE_HOURS_PER_ISSUE, COMPLIANCE_REWORK_INR_PER_ISSUE, all_pillar_impacts
from .schedule import risks
from .schemas import MachineScaleStats, OverviewStats
from .supply_chain import shipments as supply_chain_shipments

router = APIRouter(prefix="/api", tags=["overview"])

# Back-compat aliases (Compliance's original ROI assumptions now live in impact.py,
# shared with the other 3 pillars' assumptions in one audited module).
HOURS_PER_ISSUE = COMPLIANCE_HOURS_PER_ISSUE
REWORK_INR_PER_ISSUE = COMPLIANCE_REWORK_INR_PER_ISSUE


def _evaluate_all():
    """Runs the real Compliance evaluate() over the canonical Design Basis Report
    (falls back to every document if no DBR is found) and returns the full
    ComplianceResult list — NCRs, coverage, and overlaps all come from these same
    runs, so the machine-scale counts below can never drift from what the
    Compliance page itself would show for the same documents."""
    subs = load_submittals()
    dbr = [
        s.get("Submittal No")
        for s in subs
        if "dbr" in (s.get("Submittal No") or "").lower()
        or "design basis" in (s.get("Title") or "").lower()
    ]
    targets = dbr or [s.get("Submittal No") for s in subs]
    results = []
    for doc_id in targets:
        if not doc_id:
            continue
        try:
            results.append(evaluate(doc_id))
        except Exception:
            continue
    return results


@router.get("/overview", response_model=OverviewStats)
def get_overview() -> OverviewStats:
    results = _evaluate_all()
    ncrs = [n for r in results for n in r.ncrs]
    issues = len(ncrs)
    by_sev: dict[str, int] = {}
    for n in ncrs:
        if n.status == "OPEN":
            by_sev[n.severity] = by_sev.get(n.severity, 0) + 1
    pillar_impacts = all_pillar_impacts(issues)

    clauses_checked = sum(r.coverage.clauses_cited for r in results if r.coverage)
    conflicts_surfaced = sum(len(r.overlaps) for r in results)
    # Counts real RFI links only, not the near-automatic schedule-activity join
    # (every shipment declares a wbs_id, so linked_activity resolves for almost
    # all of them regardless of any real evidence work — linked_rfi is the
    # genuinely selective match, curated or TF-IDF-retrieved against RFI text).
    cross_references_found = sum(1 for s in supply_chain_shipments() if s.linked_rfi is not None)

    return OverviewStats(
        project=config.PROJECT_NAME,
        issues_caught=issues,
        engineer_hours_saved=sum(p.hours_saved for p in pillar_impacts),
        rework_avoided_inr=sum(p.inr_saved for p in pillar_impacts),
        open_ncrs_by_severity=by_sev,
        schedule_at_risk=len(risks()),
        by_pillar=pillar_impacts,
        machine_scale=MachineScaleStats(
            documents_read=len(load_submittals()),
            clauses_checked=clauses_checked,
            cross_references_found=cross_references_found,
            conflicts_surfaced=conflicts_surfaced,
        ),
    )
