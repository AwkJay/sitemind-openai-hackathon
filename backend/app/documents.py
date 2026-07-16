"""GET /api/documents — the submittal / document register."""
from __future__ import annotations

from fastapi import APIRouter

from .data_loader import load_submittals

router = APIRouter(prefix="/api", tags=["documents"])

# Real review-status codes -> human label (CONTRACT shapes).
_STATUS = {
    "A": "A – Approved",
    "B": "B – Approved as Noted",
    "C": "C – Revise & Resubmit",
    "D": "D – Rejected",
    "E": "E – For Information",
    "Pending": "Pending",
}


def _doc_type(s: dict) -> str:
    t = (s.get("Type") or "").lower()
    title = (s.get("Title") or "").lower()
    if t == "design_basis" or "design basis" in title or "dbr" in title:
        return "design_basis"
    if "mix" in title or t == "mos":
        return "mix_design"
    if t == "rfi":
        return "rfi"
    return "submittal"


@router.get("/documents")
def get_documents() -> list[dict]:
    out = []
    for s in load_submittals():
        out.append(
            {
                "id": s.get("Submittal No"),
                "title": s.get("Title", ""),
                "type": _doc_type(s),
                "status": _STATUS.get((s.get("Status") or "").strip(), s.get("Status", "")),
                "discipline": s.get("Discipline", ""),
            }
        )
    return out
