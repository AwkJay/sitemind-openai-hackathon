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
from .schemas import OverviewStats

router = APIRouter(prefix="/api", tags=["overview"])

# Back-compat aliases (Compliance's original ROI assumptions now live in impact.py,
# shared with the other 3 pillars' assumptions in one audited module).
HOURS_PER_ISSUE = COMPLIANCE_HOURS_PER_ISSUE
REWORK_INR_PER_ISSUE = COMPLIANCE_REWORK_INR_PER_ISSUE


def _all_ncrs():
    """NCRs from the canonical Design Basis Report (holds the full param set).

    Counting the DBR avoids double-counting the same finding that is also mirrored
    onto an individual submittal. Falls back to scanning every document if no DBR.
    """
    subs = load_submittals()
    dbr = [
        s.get("Submittal No")
        for s in subs
        if "dbr" in (s.get("Submittal No") or "").lower()
        or "design basis" in (s.get("Title") or "").lower()
    ]
    targets = dbr or [s.get("Submittal No") for s in subs]
    ncrs = []
    for doc_id in targets:
        if not doc_id:
            continue
        try:
            ncrs.extend(evaluate(doc_id).ncrs)
        except Exception:
            continue
    return ncrs


@router.get("/overview", response_model=OverviewStats)
def get_overview() -> OverviewStats:
    ncrs = _all_ncrs()
    issues = len(ncrs)
    by_sev: dict[str, int] = {}
    for n in ncrs:
        if n.status == "OPEN":
            by_sev[n.severity] = by_sev.get(n.severity, 0) + 1
    pillar_impacts = all_pillar_impacts(issues)
    return OverviewStats(
        project=config.PROJECT_NAME,
        issues_caught=issues,
        engineer_hours_saved=sum(p.hours_saved for p in pillar_impacts),
        rework_avoided_inr=sum(p.inr_saved for p in pillar_impacts),
        open_ncrs_by_severity=by_sev,
        schedule_at_risk=len(risks()),
        by_pillar=pillar_impacts,
    )
