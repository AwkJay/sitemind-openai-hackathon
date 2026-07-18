"""Read-only, filesystem-backed corpora for the standalone retrieval package
(Phase 3b).

Extends Phase 3's company-upload retrieval package to ALSO cover two
existing, already-real text sources, purely as a parallel READ path:

  1. `manak_structural` — every `.md` file under manak-dev's own clause
     library (`MANAK_LIB_DIR` below), indexed with THIS package's own
     chunker (never manak's `chunker.py`/`indexer.py` — zero code coupling
     to that separate, independently-versioned service). Provenance tag
     `"manak_indexed"`.
  2. `sitemind_existing_standards` — every clause record in SiteMind's own
     `backend/data/standards/clauses.json` and `commissioning_clauses.json`,
     one chunk per clause (these files are already atomic clause records,
     not prose to re-chunk). Provenance tag `"sitemind_indexed"`.

Both corpora are READ-ONLY: this module never writes, moves, or modifies
any file under `manak-dev/` or `backend/data/standards/`, and — unlike
Phase 3's company-upload corpora — neither is persisted via `store.py`;
they are rebuilt in memory once per process, lazily, the first time
`ensure_filesystem_corpora()` is called (mirrors router.py's existing
`_ensure_loaded()` once-per-process pattern for restoring persisted
company corpora). This whole module is only ever imported from
`retrieval/router.py`, which is itself only imported by `main.py` when
`config.RETRIEVAL_ENABLED` is true — so with the flag off, none of this
file's code runs and none of these paths are ever read.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .chunker import _normalize, chunk_document
from .index import Corpus, get_corpus, register_corpus

logger = logging.getLogger(__name__)

MANAK_CORPUS_NAME = "manak_structural"
SITEMIND_CORPUS_NAME = "sitemind_existing_standards"

# manak-dev is a separate, sibling project directory — NOT inside this repo.
# This absolute path matches the one confirmed present via `find` before this
# module was written (17 real `.md` files under it, one per digitised
# standard). Read-only: this module only ever calls `Path.read_text()` on
# files under this directory, never a write/move/delete.
MANAK_LIB_DIR = Path("/home/awni/Documents/Project_hackathon/manak-dev/lib")

# backend/app/retrieval/filesystem_corpora.py -> backend/data/standards
# (the SAME files `app/standards.py` reads for the existing pillars — this
# module only ever reads them, via a completely independent code path; the
# existing pillars' own lookup in `standards.py` is untouched.)
SITEMIND_STANDARDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "standards"
SITEMIND_STANDARDS_FILES = ("clauses.json", "commissioning_clauses.json")


def _manak_md_files() -> list[Path]:
    """Glob (never a hardcoded list) every `.md` file under MANAK_LIB_DIR,
    recursively — manak nests each standard in its own subdirectory
    (`lib/<doc_id>/<file>.md`), so `rglob` is used rather than assuming a
    fixed nesting depth."""
    if not MANAK_LIB_DIR.exists():
        logger.warning(
            "filesystem_corpora: MANAK_LIB_DIR %s does not exist; "
            "manak_structural corpus will be built empty.",
            MANAK_LIB_DIR,
        )
        return []
    return sorted(MANAK_LIB_DIR.rglob("*.md"))


def build_manak_structural_corpus() -> Corpus:
    """Read every manak `.md` file (never write, never import manak's own
    indexer/chunker) and chunk it with THIS package's own structure-aware
    chunker. Each file's numbered-clause markdown headings (e.g.
    `##### 26.4.2 Nominal Cover to Meet Durability Requirement`) are picked
    up by the chunker's existing `_MD_HEADING_RE` path with no special-casing
    needed — verified directly against a real sample (IS 456's clause
    26.4.2.2) before writing this function."""
    corpus = Corpus(name=MANAK_CORPUS_NAME, source="filesystem_readonly")
    all_chunks: list[dict] = []
    for path in _manak_md_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        # Disambiguate potential filename collisions across manak's
        # per-standard subdirectories by prefixing with the parent dir name
        # (manak's own doc_id, e.g. "is456_2000").
        doc_id = f"{path.parent.name}"
        rel_name = str(path.relative_to(MANAK_LIB_DIR))
        chunks = chunk_document(text, file_type="md", doc_prefix=doc_id)
        for c in chunks:
            c["document_id"] = doc_id
            c["corpus_name"] = MANAK_CORPUS_NAME
            c["filename"] = rel_name
            c["provenance_tag"] = "manak_indexed"
        all_chunks.extend(chunks)
    corpus.build(all_chunks)
    return corpus


def _clause_chunks_from_file(path: Path, corpus_name: str) -> list[dict]:
    """One chunk per clause record in a SiteMind standards JSON file
    (`clauses.json` / `commissioning_clauses.json`). These files are
    already atomic clause records — re-running the prose chunker over a
    serialized JSON blob would be nonsensical — so each clause's `text`
    field becomes exactly one chunk. `raw_text` is located via a literal
    substring search of the clause's `text` value inside the file's real
    raw content (verified up front: all 29 clause `text` values across both
    files are found verbatim with zero misses), so `raw_text` is a true
    byte-for-byte slice of the actual file, never a re-serialization."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    doc_id = path.stem  # "clauses" / "commissioning_clauses"
    chunks: list[dict] = []
    for i, clause in enumerate(data.get("clauses", [])):
        text_val = clause.get("text", "")
        idx = raw.find(text_val)
        if idx >= 0:
            start_char, end_char = idx, idx + len(text_val)
            raw_text = raw[start_char:end_char]
        else:  # pragma: no cover - not observed against the real files today
            logger.warning(
                "filesystem_corpora: clause %s text not found verbatim in %s; "
                "using the JSON-decoded value with a zero offset.",
                clause.get("key"),
                path.name,
            )
            start_char, end_char = 0, 0
            raw_text = text_val

        key = clause.get("key") or f"{doc_id}-{i:04d}"
        breadcrumb = " > ".join(
            p for p in [clause.get("standard"), clause.get("title"), clause.get("clause")] if p
        ) or None

        chunks.append(
            {
                "chunk_id": f"{doc_id}:{key}",
                "text": _normalize(raw_text),
                "raw_text": raw_text,
                "heading": clause.get("title"),
                "breadcrumb": breadcrumb,
                "start_char": start_char,
                "end_char": end_char,
                "structured": True,
                "file_type": "json",
                "document_id": doc_id,
                "corpus_name": corpus_name,
                "filename": path.name,
                "provenance_tag": "sitemind_indexed",
            }
        )
    return chunks


def build_sitemind_standards_corpus() -> Corpus:
    """Read-only index over `clauses.json` + `commissioning_clauses.json`.
    Existing pillars keep reading these same files directly via
    `app/standards.py`, completely unaffected — this is a parallel index
    built by a separate module for the Knowledge Base UI's unified search
    box only."""
    corpus = Corpus(name=SITEMIND_CORPUS_NAME, source="filesystem_readonly")
    all_chunks: list[dict] = []
    for fname in SITEMIND_STANDARDS_FILES:
        path = SITEMIND_STANDARDS_DIR / fname
        if not path.exists():
            logger.warning("filesystem_corpora: %s not found; skipping.", path)
            continue
        all_chunks.extend(_clause_chunks_from_file(path, SITEMIND_CORPUS_NAME))
    corpus.build(all_chunks)
    return corpus


_FS_CORPORA_LOADED = False


def ensure_filesystem_corpora() -> None:
    """Build both read-only corpora into the in-memory registry, once per
    process. Called from router.py's `_ensure_loaded()` — reached only on
    the first request to any `/api/retrieval/*` endpoint, and only ever
    reachable at all when `config.RETRIEVAL_ENABLED` is true (see
    `router.py`'s module docstring)."""
    global _FS_CORPORA_LOADED
    if _FS_CORPORA_LOADED:
        return
    if get_corpus(MANAK_CORPUS_NAME) is None:
        register_corpus(build_manak_structural_corpus())
    if get_corpus(SITEMIND_CORPUS_NAME) is None:
        register_corpus(build_sitemind_standards_corpus())
    _FS_CORPORA_LOADED = True
