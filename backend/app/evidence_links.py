"""Shared evidence-linking resolver — generalizes the RFI/schedule-activity linking
pattern originally built for the Compliance pillar's Action Brief
(`agents/action_brief.py`) so a finding's real cross-references (which RFI already
raised this, which schedule activity it affects) are surfaced IN THE PRODUCT for
Supply-Chain (and, in future, Commissioning) — not only in DEMO_STORY.md narration
for a presenter to say out loud.

Every link is COMPUTED from a real shared key, never hardcoded:
  - `link_rfi(wbs_id=...)`: CURATED match — the wbs_id appears verbatim in an RFI's
    Ref/Subject/Question text (the strongest, most literal join; e.g. RFI-EL-112's
    Ref cites "Schedule DC1-04-EL-030" verbatim — this is exactly the SHP-002 <->
    RFI-EL-112 connection DEMO_STORY.md narrates, now derived instead of asserted).
  - Falls back to the same TF-IDF free-text retrieval `action_brief.py` already uses
    (`query_text`, e.g. a procurement_item description) when no wbs_id match exists.
  - `link_activity(wbs_id)`: CURATED exact match against the real schedule DAG
    (schedule.csv) + the real CPM critical-path flag from `schedule.py`.
Neither function guesses: if no defensible match clears the bar, it returns None.
"""
from __future__ import annotations

from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .data_loader import load_rfi_log, load_schedule
from .schedule import _cpm
from .schemas import AffectedActivity, LinkedRFI

_SIM_THRESHOLD = 0.15


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


def link_rfi(*, wbs_id: str | None = None, query_text: str = "") -> LinkedRFI | None:
    rows = _rfi_rows()
    if not rows:
        return None

    if wbs_id:
        for r in rows:
            blob = f"{r.get('Ref', '')} {r.get('Subject', '')} {r.get('Question', '')}"
            if wbs_id.lower() in blob.lower():
                return LinkedRFI(
                    id=r.get("RFI No", ""),
                    status=r.get("Status", ""),
                    match="curated",
                    subject=r.get("Subject", ""),
                    question=r.get("Question", ""),
                )

    if not query_text.strip():
        return None
    vec, matrix = _rfi_tfidf()
    if vec is None:
        return None
    sims = cosine_similarity(vec.transform([query_text]), matrix).ravel()
    i = int(sims.argmax())
    if sims[i] < _SIM_THRESHOLD:
        return None
    r = rows[i]
    return LinkedRFI(
        id=r.get("RFI No", ""),
        status=r.get("Status", ""),
        match="retrieved",
        subject=r.get("Subject", ""),
        question=r.get("Question", ""),
    )


def link_activity(wbs_id: str) -> AffectedActivity | None:
    if not wbs_id:
        return None
    rows = load_schedule()
    match = next((row for row in rows if row.get("wbs_id") == wbs_id), None)
    if match is None:
        return None
    critical = _cpm()["critical"]
    return AffectedActivity(
        id=match.get("wbs_id", ""),
        name=match.get("task", ""),
        on_critical_path=match.get("wbs_id") in critical,
    )
