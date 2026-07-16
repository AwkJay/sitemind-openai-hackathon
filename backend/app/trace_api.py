"""GET /api/trace* — read-only access to the local provenance log (see `trace.py`)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import trace

router = APIRouter(prefix="/api/trace", tags=["trace"])


@router.get("")
def list_traces(limit: int = 20) -> list[dict]:
    return trace.recent(limit)


@router.get("/{run_id}")
def get_trace(run_id: str) -> dict:
    record = trace.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown trace id: {run_id}")
    return record
