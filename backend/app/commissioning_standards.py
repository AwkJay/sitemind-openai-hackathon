"""Loads the cooling/thermal envelope corpus for Commissioning QA (Pillar 5).

Mirrors app/standards.py's pattern (load once, hand out Citation objects) but
reads a SEPARATE file (commissioning_clauses.json) with source_type explicitly
marked "cross_source_unverified" on every row — see that file's _note for why.
Never merged into clauses.json / all_clauses(): mixing a Codebook-verified
corpus with a cross-source one in the same index would blur a distinction this
project depends on being visible everywhere it matters.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from .config import DATA_DIR
from .schemas import Citation

_PATH = DATA_DIR / "standards" / "commissioning_clauses.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    raw = json.loads(_PATH.read_text(encoding="utf-8"))
    return raw


def corpus_note() -> str:
    raw = _load()
    return raw.get("_note", "")


def simplification_note() -> str:
    raw = _load()
    return raw.get("known_simplification", "")


def _citation(row: dict) -> Citation:
    return Citation(
        standard=row["standard"],
        clause=row["clause"],
        text=row["text"],
        verify_url=row["verify_url"],
        source_type=row.get("source_type", "cross_source_unverified"),
    )


def envelope(parameter: str, equipment_class: str, kind: str) -> Optional[tuple[float, float, Citation]]:
    """Return (min_value, max_value, citation) for a (parameter, class, recommended|allowable)
    combination, or None if this corpus doesn't cover it (NOT_CHECKABLE — never guessed)."""
    rows = _load().get("clauses", [])
    for row in rows:
        if row["parameter"] != parameter or row["envelope"] != kind:
            continue
        cls = row["equipment_class"]
        if cls == "ALL" or cls == equipment_class or (cls == "A1_A2" and equipment_class in ("A1", "A2")):
            return row["min_value"], row["max_value"], _citation(row)
    return None


def all_rows() -> list[dict]:
    return list(_load().get("clauses", []))
