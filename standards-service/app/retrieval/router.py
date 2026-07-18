"""FastAPI router for the standalone retrieval package (Phase 3).

Mounted in `app/main.py` ONLY when `config.RETRIEVAL_ENABLED` is true (see
IMPROVEMENTS.md Phase 3 + the hard constraints on that file) — with the flag
off, this module is never even imported, so none of these routes exist and
none of this package's dependencies (rank_bm25, sentence-transformers) are
touched at all.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .filesystem_corpora import ensure_filesystem_corpora
from .index import RETRIEVAL_FLOOR, get_corpus, list_corpora
from .ingest import UnsupportedFileType, ingest_document
from .models import CorpusSummary, IngestManifest, QueryResult, RetrievalCitation
from .store import COMPANY_CORPUS_DIR, load_all_corpora

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])

_loaded = False


def _ensure_loaded() -> None:
    """Restore any corpora persisted from a previous run, once per process,
    AND (Phase 3b) lazily build the two read-only filesystem corpora
    (manak's `.md` corpus + SiteMind's own standards JSON) the first time
    any retrieval endpoint is hit. Both steps are no-ops on every call after
    the first."""
    global _loaded
    if not _loaded:
        load_all_corpora()
        ensure_filesystem_corpora()
        _loaded = True


class QueryRequest(BaseModel):
    corpus_name: str
    question: str
    k: int = 4


@router.post("/upload", response_model=IngestManifest)
async def upload(corpus_name: str = Form(...), file: UploadFile = File(...)) -> IngestManifest:
    _ensure_loaded()
    content = await file.read()

    raw_dir = COMPANY_CORPUS_DIR / corpus_name / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'upload').name}"
    dest = raw_dir / safe_name
    dest.write_bytes(content)

    try:
        manifest = ingest_document(dest, corpus_name=corpus_name, provenance_tag="company_uploaded")
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IngestManifest(**manifest)


@router.get("/corpora", response_model=list[CorpusSummary])
def corpora() -> list[CorpusSummary]:
    _ensure_loaded()
    return [
        CorpusSummary(
            corpus_name=c.name,
            document_count=len(c.document_ids),
            chunk_count=c.chunk_count,
            source=c.source,
            provenance_tag=c.provenance_tag,
        )
        for c in list_corpora()
    ]


@router.get("/corpora/{name}/documents")
def corpus_documents(name: str) -> list[dict]:
    _ensure_loaded()
    corpus = get_corpus(name)
    if corpus is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{name}' not found.")
    docs: dict[str, dict] = {}
    for c in corpus.chunks:
        doc_id = c["document_id"]
        entry = docs.setdefault(
            doc_id,
            {
                "document_id": doc_id,
                "filename": c.get("filename"),
                "chunk_count": 0,
                "structured": c.get("structured", False),
                "provenance_tag": c.get("provenance_tag", "company_uploaded"),
            },
        )
        entry["chunk_count"] += 1
    return list(docs.values())


@router.post("/query", response_model=QueryResult)
def query(req: QueryRequest) -> QueryResult:
    _ensure_loaded()
    corpus = get_corpus(req.corpus_name)
    if corpus is None:
        return QueryResult(
            question=req.question,
            corpus_name=req.corpus_name,
            abstained=True,
            floor=RETRIEVAL_FLOOR,
            citations=[],
        )

    results = corpus.query(req.question, k=req.k)
    citations = [
        RetrievalCitation(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            filename=r.get("filename", ""),
            heading=r.get("heading"),
            breadcrumb=r.get("breadcrumb"),
            text=r["text"],
            # Phase 3b fix: reflect the chunk's OWN provenance tag rather than
            # hardcoding "company_uploaded" — that was correct for Phase 3
            # (only one corpus source existed) but would have mislabeled
            # manak_indexed/sitemind_indexed chunks as company uploads.
            source_type=r.get("provenance_tag", "company_uploaded"),
            score=r["score"],
        )
        for r in results
    ]
    return QueryResult(
        question=req.question,
        corpus_name=req.corpus_name,
        abstained=len(citations) == 0,
        floor=RETRIEVAL_FLOOR,
        citations=citations,
    )
