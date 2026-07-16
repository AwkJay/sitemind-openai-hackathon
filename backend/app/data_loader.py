"""Defensive loaders for the synthetic project data.

The data agent owns backend/data/. We read the real files when present and fall
back to small built-in samples otherwise, so the server always boots and the
demo always works. Column/field names match 04_DATA_PLAN.md and the real files
the data agent shipped (submittals.csv, design_basis_params.json, rfi_log.csv,
schedule/schedule.csv, fixtures/*.json).

The checkable parameters live in design_basis_params.json (a flat list, each with
a nested `context`). We flatten them and assign each to the Design Basis Report
plus any submittal whose title references the same element — so every demo doc is
meaningful while the DBR remains the canonical full set.
"""
from __future__ import annotations

import csv
import io
import json
import re
from functools import lru_cache
from typing import Any, Optional

from .config import DATA_DIR


# --------------------------------------------------------------------------- #
# tiny IO helpers (read-only; we never write into backend/data/)
# --------------------------------------------------------------------------- #
def _read_json(rel: str) -> Optional[Any]:
    try:
        return json.loads((DATA_DIR / rel).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv(rel: str) -> Optional[list[dict]]:
    try:
        text = (DATA_DIR / rel).read_text(encoding="utf-8")
    except OSError:
        return None
    return list(csv.DictReader(io.StringIO(text)))


def _find(*rel_candidates: str) -> Optional[Any]:
    for rel in rel_candidates:
        v = _read_json(rel) if rel.endswith(".json") else _read_csv(rel)
        if v:
            return v
    return None


# --------------------------------------------------------------------------- #
# Built-in samples (used only when the real files are absent)
# --------------------------------------------------------------------------- #
_SAMPLE_SUBMITTALS: list[dict] = [
    {"Submittal No": "DC1-02-DBR-0001-R2", "Rev": "R2", "Title": "Structural Design Basis Report", "Discipline": "Structural", "Type": "PD", "Status": "A – Approved"},
    {"Submittal No": "DC1-02-SD-0142-R1", "Rev": "R1", "Title": "Foundation shop drawing — footing F-12 transformer yard (cover 30mm, M25, severe)", "Discipline": "Structural", "Type": "SD", "Status": "C – Revise & Resubmit"},
    {"Submittal No": "DC1-02-MOS-0210-R0", "Rev": "R0", "Title": "Method statement — concrete mix for severe-exposure raft (w/c 0.55)", "Discipline": "Structural", "Type": "MOS", "Status": "C – Revise & Resubmit"},
    {"Submittal No": "DC1-02-SD-0156-R0", "Rev": "R0", "Title": "Reinforcement detailing — column C-08 (0.6% long. steel, cover 45mm)", "Discipline": "Structural", "Type": "SD", "Status": "Pending"},
    {"Submittal No": "DC1-01-SD-0301-R0", "Rev": "R0", "Title": "Roof cladding — design wind pressure & fastener schedule", "Discipline": "Architecture", "Type": "SD", "Status": "B – Approved as Noted"},
]

# Flat param list mirroring design_basis_params.json structure (with `context`).
_SAMPLE_DB_PARAMS: list[dict] = [
    {"id": "DBP-01", "element": "Footing F-12", "element_type": "footing", "param": "nominal_cover", "value": 30, "unit": "mm", "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50}, "source_quote": "Nominal cover to reinforcement for transformer-yard footing F-12 is specified as 30 mm.", "source_location": "General Note 5"},
    {"id": "DBP-03", "element": "Transformer-yard RCC", "element_type": "general", "param": "concrete_grade", "value": 25, "unit": "MPa", "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50}, "source_quote": "Concrete grade for marine/transformer-yard RCC is specified as M25.", "source_location": "General Note 7"},
    {"id": "DBP-04", "element": "Severe-exposure concrete", "element_type": "general", "param": "wc_ratio", "value": 0.55, "unit": "ratio", "context": {"exposure": "severe", "marine": True}, "source_quote": "The free water-cement ratio for severe-exposure structural concrete is specified as 0.55.", "source_location": "General Note 8"},
    {"id": "DBP-05", "element": "Column C-08", "element_type": "column", "param": "long_steel_pct", "value": 0.6, "unit": "%", "context": {"exposure": "severe", "marine": False}, "source_quote": "Longitudinal reinforcement for column C-08 is provided at 0.6 percent.", "source_location": "General Note 9"},
    {"id": "DBP-06", "element": "Data-centre buildings (global seismic basis)", "element_type": "general", "param": "importance_factor", "value": 1.0, "unit": "factor", "context": {}, "source_quote": "The seismic Importance Factor I is adopted as 1.0 for the data-centre buildings.", "source_location": "General Note 11"},
    {"id": "DBP-07", "element": "Roof cladding (wind basis)", "element_type": "general", "param": "design_wind_speed", "value": 50, "unit": "m/s", "context": {"city_basic_vb": 50}, "source_quote": "Design wind speed for the Chennai site is taken as 50 m/s basic wind speed.", "source_location": "General Note 13"},
]

_SAMPLE_RFI: list[dict] = [
    {"RFI No": "RFI-CIV-061", "Date": "2026-02-11", "Discipline": "Civil/Structural", "Subject": "M30 vs M35 for severe exposure raft", "Question": "Should we upgrade the severe-exposure raft from M30 to M35?", "Ref": "DBR-0001 Note 4 / IS456 8.2.4.1", "Status": "Closed"},
    {"RFI No": "RFI-CIV-072", "Date": "2026-04-26", "Discipline": "Civil/Structural", "Subject": "M25 vs M30 for marine/transformer-yard RCC", "Question": "Note 7 specifies M25; IS 456 8.2.8 requires M30 near sea-water. Confirm grade for footing F-12.", "Ref": "DBR-0001 Note 7 / IS456 8.2.8 / SUB-0142", "Status": "Open"},
]

_SAMPLE_SCHEDULE: list[dict] = [
    {"wbs_id": "DC1-01-EN-010", "task": "Site enabling works", "phase": "Enabling", "planned_start_day": "0", "duration_days": "15", "predecessors": "", "pct_complete": "100", "procurement_item": "", "lead_time_days": "0", "vendor_status": "na", "weather_sensitive": "false"},
    {"wbs_id": "DC1-02-CS-030", "task": "Transformer-yard footings", "phase": "Civil/Structural", "planned_start_day": "78", "duration_days": "18", "predecessors": "DC1-01-EN-010", "pct_complete": "40", "procurement_item": "", "lead_time_days": "0", "vendor_status": "na", "weather_sensitive": "true"},
    {"wbs_id": "DC1-04-EL-030", "task": "LV switchgear procurement & delivery", "phase": "MEP", "planned_start_day": "130", "duration_days": "25", "predecessors": "DC1-02-CS-030", "pct_complete": "0", "procurement_item": "LV switchgear 4000A", "lead_time_days": "150", "vendor_status": "slipping", "weather_sensitive": "false"},
    {"wbs_id": "DC1-06-CX-050", "task": "L5 integrated systems test", "phase": "Commissioning L1-L5", "planned_start_day": "299", "duration_days": "14", "predecessors": "DC1-04-EL-030", "pct_complete": "0", "procurement_item": "", "lead_time_days": "0", "vendor_status": "na", "weather_sensitive": "false"},
]


# --------------------------------------------------------------------------- #
# Raw loaders (cached): real file first, then built-in sample
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_submittals() -> list[dict]:
    return _find("project_docs/submittals.csv", "submittals.csv") or _SAMPLE_SUBMITTALS


@lru_cache(maxsize=1)
def load_design_basis_params() -> list[dict]:
    data = _find("project_docs/design_basis_params.json", "design_basis_params.json")
    return data if isinstance(data, list) and data else _SAMPLE_DB_PARAMS


@lru_cache(maxsize=1)
def load_rfi_log() -> list[dict]:
    return _find("project_docs/rfi_log.csv", "rfi_log.csv") or _SAMPLE_RFI


@lru_cache(maxsize=1)
def load_schedule() -> list[dict]:
    return _find("schedule/schedule.csv", "schedule.csv", "project_docs/schedule.csv") or _SAMPLE_SCHEDULE


@lru_cache(maxsize=1)
def load_supply_chain() -> list[dict]:
    data = _read_json("project_docs/supply_chain.json")
    if isinstance(data, dict) and data.get("shipments"):
        return data["shipments"]
    return []


# --------------------------------------------------------------------------- #
# Parameter assembly: flatten context + assign each param to documents
# --------------------------------------------------------------------------- #
def _flatten(param: dict) -> dict:
    """Lift the nested `context` onto the param and normalise check inputs."""
    p = {k: v for k, v in param.items() if k != "context"}
    p.update(param.get("context") or {})
    # The concrete-grade check reads grade_mpa; the value carries the MPa grade.
    if p.get("param") == "concrete_grade" and "grade_mpa" not in p:
        try:
            p["grade_mpa"] = float(p.get("value"))
        except (TypeError, ValueError):
            pass
    return p


def _code_tokens(text: str) -> list[str]:
    """Element codes like 'F-12' / 'C-08' (lowercased) for title matching."""
    return [m.lower() for m in re.findall(r"[A-Za-z]+-?\d+", text or "")]


# Extra title keywords for params whose element_type is "general" (no code token
# to anchor on). Kept narrow so a param attaches to exactly the right submittal —
# cover/steel params anchor on element_type + code token instead (see below).
_PARAM_KEYWORDS = {
    "concrete_grade": ["transformer"],
    "wc_ratio": ["mix", "w/c", "raft"],
    "design_wind_speed": ["wind", "cladding", "roof"],
}


def _is_dbr(s: dict) -> bool:
    sid = (s.get("Submittal No") or "").lower()
    title = (s.get("Title") or "").lower()
    return "dbr" in sid or "design basis" in title


@lru_cache(maxsize=1)
def load_submittal_params() -> dict[str, list[dict]]:
    """Build {document_id: [flattened params]} from design_basis_params.json.

    Honours a real submittal_params.json if the data agent ever ships one.
    """
    override = _find("project_docs/submittal_params.json", "submittal_params.json")
    if isinstance(override, dict) and override:
        return override

    params = [_flatten(p) for p in load_design_basis_params()]
    submittals = load_submittals()
    dbr_ids = [s.get("Submittal No") for s in submittals if _is_dbr(s)]

    mapping: dict[str, list[dict]] = {sid: [] for sid in dbr_ids}
    for p in params:
        # Canonical: every param belongs to the Design Basis Report.
        for sid in dbr_ids:
            mapping[sid].append(p)
        # Mirror onto the specific submittal that references the same element.
        tokens = set(_code_tokens(p.get("element", "")))
        et = (p.get("element_type") or "").lower()
        kw = _PARAM_KEYWORDS.get(p.get("param"), [])
        for s in submittals:
            if _is_dbr(s):
                continue
            title = (s.get("Title") or "").lower()
            if (
                (et and et != "general" and et in title)
                or any(t in title for t in tokens)
                or any(k in title for k in kw)
            ):
                mapping.setdefault(s["Submittal No"], []).append(p)
    return mapping


def params_for(document_id: str) -> list[dict]:
    return load_submittal_params().get(document_id, [])


def fixture(name: str) -> Optional[Any]:
    """Read a prose fixture from backend/data/fixtures/ if present, else None."""
    return _read_json(f"fixtures/{name}")
