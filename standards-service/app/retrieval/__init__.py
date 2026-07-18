"""Standalone standards/company-document retrieval package — Phase 3
(IMPROVEMENTS.md, "PHASE 3 — Standards retrieval layer + company-upload
ingestion pipeline", 2026-07-10).

Self-contained, sibling of `app/agents/`: zero import coupling to any
existing pillar (`agents/copilot.py`, `app/embeddings.py`, `app/ingest.py`,
`app/schemas.py`, `app/standards.py` are all read-only design references,
never imported from here). Generalizes the hybrid BM25 + dense-embedding,
RRF-fused retrieval pattern already proven in `agents/copilot.py` to (a) an
arbitrary company-uploaded document corpus and (b) a pluggable embeddings
backend (local sentence-transformers by default, optional external API).

Mounted behind the `config.RETRIEVAL_ENABLED` flag (default off) in
`app/main.py` — importing this package/subpackage only happens when that
flag is true, so nothing here executes at all in the default configuration.
"""
from __future__ import annotations
