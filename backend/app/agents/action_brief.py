"""Action Brief — GET /api/compliance/action-brief/{document_id}.

Per the cross-agent-reviewed contract in `update_plan_draft.md`: every field is
either extracted-with-span, cited, or a deterministic result. `confidence` is an
enum tied to explicit conditions, never a fabricated percentage. `computed_impact`
stays null unless a transparent formula with visible assumptions exists (it does
not, yet — so it is always null here; do not add a number without one).

One Action Brief is produced per NCR (a conforming param has no finding to brief).
It links the finding to: (a) a real RFI if one plausibly concerns the same
element/parameter (curated = element code matches; retrieved = TF-IDF similarity
over subject/question text), and (b) a real schedule activity for the same
element, with its real on-critical-path flag from the CPM pass in `schedule.py`.
Neither link is guessed if no defensible match exists — the field is simply
omitted (`None`), never populated with a plausible-looking fake.
"""
from __future__ import annotations

import re
from functools import lru_cache

from fastapi import APIRouter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .. import trace
from ..data_loader import load_rfi_log, load_schedule
from ..schedule import _cpm
from ..schemas import (
    ActionBrief,
    AffectedActivity,
    BriefCheck,
    BriefParameter,
    Confidence,
    LinkedRFI,
    RecommendedAction,
)
from .compliance import evaluate_with_params

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

_CODE_RE = re.compile(r"\b([A-Za-z]{1,3}-\d{1,3})\b")
_RFI_SIM_THRESHOLD = 0.15


def _element_code(element: str) -> str | None:
    m = _CODE_RE.search(element or "")
    return m.group(1).lower() if m else None


# --------------------------------------------------------------------------- #
# RFI linking
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _rfi_rows() -> list[dict]:
    return load_rfi_log()


@lru_cache(maxsize=1)
def _rfi_tfidf():
    rows = _rfi_rows()
    if not rows:
        return None, None
    texts = [f"{r.get('Subject', '')} {r.get('Question', '')} {r.get('Ref', '')}" for r in rows]
    vec = TfidfVectorizer(stop_words="english")
    return vec, vec.fit_transform(texts)


def _link_rfi(param: dict) -> LinkedRFI | None:
    rows = _rfi_rows()
    if not rows:
        return None
    code = _element_code(param.get("element", ""))

    # Curated: the element code (e.g. F-12) appears in the RFI's Ref/Subject/Question.
    if code:
        for r in rows:
            blob = f"{r.get('Ref', '')} {r.get('Subject', '')} {r.get('Question', '')}".lower()
            if code in blob:
                return LinkedRFI(
                    id=r.get("RFI No", ""),
                    status=r.get("Status", ""),
                    match="curated",
                    subject=r.get("Subject", ""),
                    question=r.get("Question", ""),
                )

    # Retrieved: TF-IDF similarity between the parameter and RFI text.
    vec, matrix = _rfi_tfidf()
    if vec is None:
        return None
    query = f"{param.get('element', '')} {param.get('param', '').replace('_', ' ')}"
    sims = cosine_similarity(vec.transform([query]), matrix).ravel()
    i = int(sims.argmax())
    if sims[i] < _RFI_SIM_THRESHOLD:
        return None
    r = rows[i]
    return LinkedRFI(
        id=r.get("RFI No", ""),
        status=r.get("Status", ""),
        match="retrieved",
        subject=r.get("Subject", ""),
        question=r.get("Question", ""),
    )


# --------------------------------------------------------------------------- #
# Schedule activity linking
# --------------------------------------------------------------------------- #
_ELEMENT_TYPE_KEYWORDS = {"footing": ["footing"], "column": ["column"]}


def _link_activity(param: dict) -> AffectedActivity | None:
    rows = load_schedule()
    if not rows:
        return None
    code = _element_code(param.get("element", ""))
    et = (param.get("element_type") or "").lower()
    kws = _ELEMENT_TYPE_KEYWORDS.get(et, [])

    match = None
    for row in rows:
        task = (row.get("task") or "").lower()
        if code and code in task:
            match = row
            break
    if match is None and kws:
        for row in rows:
            task = (row.get("task") or "").lower()
            if any(k in task for k in kws):
                match = row
                break
    if match is None:
        return None

    critical = _cpm()["critical"]
    return AffectedActivity(
        id=match.get("wbs_id", ""),
        name=match.get("task", ""),
        on_critical_path=match.get("wbs_id") in critical,
    )


# --------------------------------------------------------------------------- #
# Confidence + status (deterministic rule, per the agreed contract)
# --------------------------------------------------------------------------- #
def _confidence_and_status(ncr) -> tuple[Confidence, str]:
    if ncr.severity == "ADVISORY":
        return (
            Confidence(
                level="medium",
                basis="cited judgment call — requires EOR confirmation, not a binary "
                "deterministic threshold",
            ),
            "NCR",
        )
    if ncr.source is not None and ncr.citation is not None:
        return (
            Confidence(
                level="high",
                basis="exact-span extraction + exact clause match + deterministic result",
            ),
            "NCR",
        )
    return (
        Confidence(level="low", basis="missing source span or citation — insufficient evidence"),
        "REVIEW_REQUIRED",
    )


def _recommended_action(ncr, status: str) -> RecommendedAction | None:
    # Low confidence: escalate, no prescriptive action (per the contract refinement).
    if status == "REVIEW_REQUIRED":
        return None
    if ncr.severity == "ADVISORY":
        return RecommendedAction(
            owner_role="Design Manager",
            action=ncr.corrective_action,
            note="System raises a design clarification for EOR confirmation; it does not redesign.",
        )
    return RecommendedAction(
        owner_role="Design Manager",
        action=ncr.corrective_action,
        note="System raises a design clarification; it does not redesign.",
    )


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build(document_id: str) -> list[ActionBrief]:
    run = trace.start("action_brief.build", {"document_id": document_id})
    with run.step("evaluate_document"):
        result, param_by_ncr = evaluate_with_params(document_id)
    briefs: list[ActionBrief] = []
    rfi_links = activity_links = 0

    for ncr in result.ncrs:
        param = param_by_ncr.get(ncr.id, {})
        confidence, status = _confidence_and_status(ncr)
        linked_rfi = _link_rfi(param) if param else None
        activity = _link_activity(param) if param else None
        rfi_links += 1 if linked_rfi else 0
        activity_links += 1 if activity else 0

        evidence: list[str] = []
        if ncr.source:
            evidence.append(ncr.source.location)
        if ncr.citation:
            evidence.append(f"{ncr.citation.standard} Cl {ncr.citation.clause}")
        if activity:
            evidence.append(f"Activity {activity.id}")
        if linked_rfi:
            evidence.append(f"RFI {linked_rfi.id}")

        briefs.append(
            ActionBrief(
                finding_id=ncr.id,
                parameter=BriefParameter(
                    name=param.get("param", "unknown"),
                    value=f"{param.get('value', '?')} {param.get('unit', '')}".strip(),
                    source=ncr.source,
                ),
                check=BriefCheck(
                    clause=ncr.citation,
                    requirement=ncr.finding,
                    result="ADVISORY" if ncr.severity == "ADVISORY" else "FAIL",
                ),
                status=status,
                linked_rfi=linked_rfi,
                affected_activity=activity,
                recommended_action=_recommended_action(ncr, status),
                confidence=confidence,
                evidence=evidence,
                computed_impact=None,
            )
        )
    run.finish(
        {
            "brief_count": len(briefs),
            "rfi_links": rfi_links,
            "activity_links": activity_links,
            "review_required": sum(1 for b in briefs if b.status == "REVIEW_REQUIRED"),
        }
    )
    return briefs


@router.get("/action-brief/{document_id}", response_model=list[ActionBrief])
def get_action_brief(document_id: str) -> list[ActionBrief]:
    return build(document_id)
