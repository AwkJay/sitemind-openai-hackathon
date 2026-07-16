"""Load the cached, REAL IS clauses and hand them out as Citation objects.

clauses.json is owned by the data agent. We only read it. If it is missing we
fall back to a tiny built-in copy so the server still boots and the demo works.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from .config import DATA_DIR
from .schemas import Citation

_CLAUSES_PATH = DATA_DIR / "standards" / "clauses.json"

# Minimal built-in fallback (subset of the real cache) so we never hard-crash.
_FALLBACK = {
    "clauses": [
        {
            "key": "IS456_26.4.2.2",
            "standard": "IS 456:2000",
            "clause": "26.4.2.2",
            "text": "For footings minimum cover shall be 50 mm.",
            "verify_url": "http://gaudi.local/manak/#is456_2000/clause:26.4.2",
        }
    ]
}


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    """Return {clause_key: clause_dict}. Cached for the process lifetime."""
    try:
        raw = json.loads(_CLAUSES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = _FALLBACK
    return {c["key"]: c for c in raw.get("clauses", [])}


def get_clause(key: str) -> Optional[Citation]:
    """Map a clause key (e.g. 'IS456_26.4.2.2') to a real Citation, or None."""
    c = _load().get(key)
    if c is None:
        return None
    return Citation(
        standard=c["standard"],
        clause=c["clause"],
        text=c["text"],
        verify_url=c["verify_url"],
        source_type=c.get("source_type", "manak_verified"),
    )


def all_clauses() -> list[dict]:
    """Raw clause dicts — used by the RAG index and the KG."""
    return list(_load().values())
