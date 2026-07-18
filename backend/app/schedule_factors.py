"""Deterministic schedule-risk factor rules: weather (P1a) and workforce (P1b) --
the two brief-named Predictive Schedule Risk Engine inputs ("workforce
availability, and weather") that schedule.py's original three rules (vendor
slip, progress lag, a broad monsoon-months proxy) didn't yet cover with a real
citation.

Both rules compare a FIXED activity execution window (planned_start_day .. +
duration_days, a schedule fact) against a FIXED calendar risk window (the real
IMD NE-monsoon dates / the Pongal festival dates) -- neither depends on the
simulated clock (clock.current_day()): the windows being compared are calendar
facts about the schedule and the risk period, not "today". This mirrors the
existing progress-lag/vendor rules' shape (schedule.py::_assess), so both
compose into the SAME CPM recompute with no parallel pipeline.

schedule.py's original `_MONSOON_MONTHS`/`_in_monsoon()` (a broad June-November
proxy with no citation) is intentionally left in place, unchanged --
eval/run_schedule_eval.py imports `_in_monsoon` directly and asserts its exact
behaviour, and the 13-eval regression suite must stay green (CLAUDE.md
guardrail). The monsoon rule here is a SEPARATE, additional, precisely-cited
rule (schedule.py's Rule 4), not a replacement -- same "add, don't touch working
code" discipline already used for the hybrid-retrieval-vs-dense-floor split in
agents/copilot.py.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from typing import Optional

from .config import DATA_DIR
from .schemas import Citation

_MONSOON_PATH = DATA_DIR / "project_docs" / "monsoon_window.json"
_WORKFORCE_PATH = DATA_DIR / "project_docs" / "workforce_calendar.json"

# Conservative, documented constants (same style as impact.py's per-unit
# assumptions) -- the fraction of NORMAL productivity retained during the risk
# window. Lost days = overlap_days * (1 - factor).
MONSOON_PRODUCTIVITY_FACTOR = 0.75  # outdoor work retains ~75% output in-window
_DEFAULT_WORKFORCE_AVAILABILITY_FACTOR = 0.6  # overridden by workforce_calendar.json if present


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _flag(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


@lru_cache(maxsize=1)
def _monsoon_data() -> dict:
    try:
        return json.loads(_MONSOON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def _workforce_data() -> dict:
    try:
        return json.loads(_WORKFORCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def monsoon_window(year: int) -> tuple[dt.date, dt.date]:
    d = _monsoon_data()
    start = dt.date(year, d.get("onset_month", 10), d.get("onset_day", 20))
    end = dt.date(year, d.get("withdrawal_month", 12), d.get("withdrawal_day", 31))
    return start, end


def monsoon_citation() -> Optional[Citation]:
    d = _monsoon_data().get("citation")
    if not d:
        return None
    return Citation(**d)


def workforce_window(year: int) -> tuple[dt.date, dt.date]:
    d = _workforce_data()
    start = dt.date(year, d.get("window_month_start", 1), d.get("window_day_start", 8))
    end = dt.date(year, d.get("window_month_end", 1), d.get("window_day_end", 21))
    return start, end


def workforce_availability_factor() -> float:
    return float(_workforce_data().get("availability_factor", _DEFAULT_WORKFORCE_AVAILABILITY_FACTOR))


def workforce_festival_name() -> str:
    return str(_workforce_data().get("festival", "Pongal"))


# --------------------------------------------------------------------------- #
# Pure functions (primitives only, no I/O) -- held-out testable directly, same
# pattern as run_supply_chain_eval.py's pure-function testing.
# --------------------------------------------------------------------------- #
def monsoon_overlap_days(activity_start_day: int, activity_end_day: int, monsoon_start_day: int, monsoon_end_day: int) -> int:
    return max(0, min(activity_end_day, monsoon_end_day) - max(activity_start_day, monsoon_start_day))


def weather_predicted_slip(overlap_days: int, factor: float = MONSOON_PRODUCTIVITY_FACTOR) -> int:
    return round(overlap_days * (1 - factor))


def labour_dip_overlap_days(activity_start_day: int, activity_end_day: int, dip_start_day: int, dip_end_day: int) -> int:
    return max(0, min(activity_end_day, dip_end_day) - max(activity_start_day, dip_start_day))


def labour_dip_slip(overlap_days: int, availability_factor: float) -> int:
    return round(overlap_days * (1 - availability_factor))


# --------------------------------------------------------------------------- #
# Row-level helpers -- used by schedule.py::_assess(). Each returns
# (drivers, slip) so the caller can fold it into the existing
# `predicted_slip = max(predicted_slip, ...)` convention (same convention the
# existing 3 rules already use -- worst single driver, not summed impacts).
# --------------------------------------------------------------------------- #
def weather_driver(row: dict, project_start: dt.date) -> tuple[list[str], int]:
    if not _flag(row.get("weather_sensitive")):
        return [], 0
    a_start = _to_int(row.get("planned_start_day"))
    a_end = a_start + _to_int(row.get("duration_days"), 1)
    a_start_date = project_start + dt.timedelta(days=a_start)
    m_start, m_end = monsoon_window(a_start_date.year)
    m_start_day = (m_start - project_start).days
    m_end_day = (m_end - project_start).days
    overlap = monsoon_overlap_days(a_start, a_end, m_start_day, m_end_day)
    if overlap <= 0:
        return [], 0
    slip = weather_predicted_slip(overlap)
    if slip <= 0:
        return [], 0
    driver = (
        f"{overlap} remaining weather-sensitive workday(s) overlap the IMD-normal NE-monsoon "
        f"window ({m_start.isoformat()} to {m_end.isoformat()}) -- a planning-grade climatological "
        "window, not a forecast"
    )
    return [driver], slip


def workforce_driver(row: dict, project_start: dt.date) -> tuple[list[str], int]:
    if not _flag(row.get("labour_intensive")):
        return [], 0
    a_start = _to_int(row.get("planned_start_day"))
    a_end = a_start + _to_int(row.get("duration_days"), 1)
    a_start_date = project_start + dt.timedelta(days=a_start)
    d_start, d_end = workforce_window(a_start_date.year)
    d_start_day = (d_start - project_start).days
    d_end_day = (d_end - project_start).days
    overlap = labour_dip_overlap_days(a_start, a_end, d_start_day, d_end_day)
    if overlap <= 0:
        return [], 0
    factor = workforce_availability_factor()
    slip = labour_dip_slip(overlap, factor)
    if slip <= 0:
        return [], 0
    driver = (
        f"{workforce_festival_name()} labour-availability window ({d_start.isoformat()} to "
        f"{d_end.isoformat()}) overlaps {overlap} labour-intensive day(s) -- assumed "
        f"{factor:.0%} workforce availability during the festival window (REPRESENTATIVE assumption)"
    )
    return [driver], slip
