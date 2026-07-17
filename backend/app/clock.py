"""Simulated project clock — the "prove it's not hardcoded" demo control.

Every risk/alert/alternative-viability number elsewhere in the app is a REAL
function of "today" (schedule.TODAY_DAY): how far an activity's planned window
has elapsed, how many days of runway remain before a shipment's required-on-site
date, how much advance warning an alert has accumulated. This module lets a demo
advance that "today" at runtime and watch those same real computations produce
different, still-correct output — instead of asking a judge to take "derived,
not hardcoded" on faith.

`_offset_days` is the ONLY mutable state in this module (server-process-lifetime,
resets on restart, exactly like the in-memory upload store in ingest.py). Nothing
in schedule.csv / supply_chain.json changes — advancing the clock does not
simulate new work being done, only time passing, which is itself a real and
useful thing to demonstrate (undone work looks progressively more at-risk the
longer it goes unaddressed).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/clock", tags=["clock"])

MAX_OFFSET_DAYS = 60

_offset_days = 0


def get_offset() -> int:
    return _offset_days


def current_day() -> int:
    from .schedule import TODAY_DAY  # local import: schedule.py imports this module

    return TODAY_DAY + _offset_days


def _clear_downstream_caches() -> None:
    """Every lru_cache(maxsize=1) whose result depends on 'today'. Lazy imports
    only — schedule.py and supply_chain.py both import current_day() from here,
    so a top-level import back into them would be circular."""
    from . import schedule, supply_chain

    schedule.risks.cache_clear()
    supply_chain.shipments.cache_clear()
    supply_chain.risks.cache_clear()
    supply_chain.alerts.cache_clear()


def set_offset(days: int) -> int:
    global _offset_days
    _offset_days = max(0, min(MAX_OFFSET_DAYS, days))
    _clear_downstream_caches()
    return _offset_days


def reset() -> int:
    return set_offset(0)


def _state() -> dict:
    from .schedule import TODAY_DAY

    return {
        "base_day": TODAY_DAY,
        "offset_days": _offset_days,
        "current_day": TODAY_DAY + _offset_days,
        "max_offset_days": MAX_OFFSET_DAYS,
    }


class AdvanceRequest(BaseModel):
    days: int = 7


@router.get("")
def get_clock() -> dict:
    return _state()


@router.post("/advance")
def advance_clock(body: AdvanceRequest) -> dict:
    set_offset(_offset_days + body.days)
    return _state()


@router.post("/reset")
def reset_clock() -> dict:
    reset()
    return _state()
