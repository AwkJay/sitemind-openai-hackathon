"""Local pydantic models for the standalone retrieval package (Phase 3).

Deliberately independent of `app/schemas.py` — this package must have zero
import coupling to the existing pillars (IMPROVEMENTS.md Phase 3, hard
constraint #3). It reuses the *concept* of `schemas.Citation.source_type` (a
reliability tag carried on every retrieved chunk) but defines its own type
here. `"company_uploaded"` is the tag for anything THIS pipeline ingests:
never manak-verified, never a known BIS/CEA primary source — trusted only to
the extent the uploading company vouches for it, and disclosed as such by
the frontend.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# "company_uploaded"          — ingested via POST /api/retrieval/upload; trusted
#                                only to the extent the uploading company vouches
#                                for it, never a known standard.
# "manak_indexed"  (Phase 3b)  — a locally-built read-only index OF manak-dev's
#                                public `.md` corpus text. NOT an authoritative
#                                manak API response and NOT equivalent to the
#                                live `manak_verified` citations the Compliance/
#                                Commissioning pillars already use — this is a
#                                parallel, independent read path for the new
#                                Knowledge Base unified search only.
# "sitemind_indexed" (Phase 3b) — a locally-built read-only index OF SiteMind's
#                                own `clauses.json`/`commissioning_clauses.json`.
#                                The existing pillars keep citing those files
#                                directly via `standards.py`, unaffected.
SourceType = Literal["company_uploaded", "manak_indexed", "sitemind_indexed"]


class RetrievalChunk(BaseModel):
    """Shape of one indexed chunk (see chunker.py for how these are produced).
    `text` is whitespace-normalized for scoring; `raw_text` is the exact,
    byte-for-byte original span — never paraphrased, never reworded."""

    chunk_id: str
    corpus_name: str
    document_id: str
    filename: str
    text: str
    raw_text: str
    heading: Optional[str] = None
    breadcrumb: Optional[str] = None
    start_char: int
    end_char: int
    structured: bool


class RetrievalCitation(BaseModel):
    """One retrieved-and-cited chunk returned from POST /api/retrieval/query."""

    chunk_id: str
    document_id: str
    filename: str
    heading: Optional[str] = None
    breadcrumb: Optional[str] = None
    text: str
    source_type: SourceType = "company_uploaded"
    score: float


class IngestManifest(BaseModel):
    document_id: str
    corpus_name: str
    filename: str
    chunk_count: int
    structured: bool
    provenance_tag: str


class CorpusSummary(BaseModel):
    corpus_name: str
    document_count: int
    chunk_count: int
    # Additive fields (Phase 3b) — default values keep this shape backward
    # compatible with any consumer built against Phase 3's plain 3-field
    # summary. `source` distinguishes a company-uploaded corpus from a
    # read-only filesystem-indexed one; `provenance_tag` surfaces the single
    # SourceType shared by every chunk in the corpus (or "mixed"/None).
    source: str = "company_upload"
    provenance_tag: Optional[str] = None


class QueryResult(BaseModel):
    question: str
    corpus_name: str
    abstained: bool
    floor: float
    citations: list[RetrievalCitation] = Field(default_factory=list)
