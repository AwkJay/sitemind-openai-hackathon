"""REST facade over Codebook's MCP server (step 5, docs/BUILD_PLAN_CODEBOOK.md).

Mounted in `app/main.py` ONLY when `config.CODEBOOK_ENABLED` is true — with
the flag off this module (and its only import, `codebook_client.py`) is
never imported, so the `mcp` client SDK dependency is never touched at all
(same import-gating discipline as `app/retrieval/router.py` +
`RETRIEVAL_ENABLED`).

This is the "SiteMind's backend becomes an MCP client, the browser UI talks
to SiteMind's backend, not Codebook directly" decision from the spec: every
endpoint here does exactly one MCP tool call via `codebook_client.py` and
returns its result as JSON. No retrieval/ranking/decision logic lives here —
that's all Codebook's, called over MCP, never reimplemented locally.

Codebook being unreachable (not started, wrong port, etc.) is a real,
expected operating state during local dev, not a bug — every endpoint
surfaces that as a clean 503 with a clear message (via
`codebook_client.CodebookUnavailable`) instead of a raw connection-refused
traceback, mirroring this codebase's existing graceful-degradation pattern
for other optional external dependencies (e.g. `/api/health`'s
`langfuse_enabled`, `app/langfuse_sink.py`).

**Codebook Console additions** (docs/codebook_console.md): the 3
`/console/...` routes below are a second kind of proxy in this same file —
they hit Codebook's plain REST retrieval API (`standards-service/app/
retrieval/router.py`) via `codebook_rest_client.py`'s `httpx` client, NOT the
MCP client above. Those 3 REST endpoints already return structured JSON
(corpora/documents/upload-manifest), so going through MCP would mean
re-parsing prose text back into fields — exactly what this file's own MCP
path avoids. Same `_call()` / `CodebookUnavailable` -> 503 translation
either way, so callers can't tell which transport served a given route.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Awaitable, Optional, TypeVar

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import codebook_client, codebook_rest_client

router = APIRouter(prefix="/api/codebook", tags=["codebook"])

T = TypeVar("T")


async def _call(awaitable: Awaitable[T]) -> T:
    """Run one codebook_client call, translating CodebookUnavailable into a
    clean HTTP 503 rather than letting the connection error surface raw."""
    try:
        return await awaitable
    except codebook_client.CodebookUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class CheckRequest(BaseModel):
    document_path: str
    corpus_name: str
    k: int = 3


@router.get("/corpora")
async def corpora() -> dict:
    """Every corpus Codebook has indexed — proxies mcp_server.py's `list_corpora`."""
    return await _call(codebook_client.list_corpora())


@router.get("/search")
async def search(q: str, corpus: Optional[str] = None, k: int = 5) -> dict:
    """Ranked chunks for query `q`, optionally scoped to `corpus` — proxies
    mcp_server.py's `search_standards`."""
    return await _call(codebook_client.search_standards(q, corpus=corpus, k=k))


@router.get("/clause/{doc_id}/{chunk_id}")
async def clause(doc_id: str, chunk_id: str) -> dict:
    """One chunk's exact verbatim text — proxies mcp_server.py's `get_clause`."""
    return await _call(codebook_client.get_clause(doc_id, chunk_id))


@router.post("/check")
async def check(req: CheckRequest) -> dict:
    """Check a document (already on Codebook's own host filesystem — see
    codebook_client.check_document_against_corpus's docstring) against a
    corpus — proxies mcp_server.py's `check_document_against_corpus`."""
    return await _call(
        codebook_client.check_document_against_corpus(req.document_path, req.corpus_name, k=req.k)
    )


@router.post("/check-upload")
async def check_upload(
    file: UploadFile = File(...),
    corpus_name: str = Form(...),
    k: int = Form(3),
) -> dict:
    """Same check as `/check`, but for a real browser file upload rather than
    a path already on Codebook's own host filesystem — `check_document_against_corpus`
    (Codebook's MCP tool) only ever reads a path, so the uploaded bytes are
    staged to a temp file (extension preserved, since `extract_text` dispatches
    on it) and cleaned up afterwards regardless of outcome."""
    suffix = Path(file.filename or "").suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()
        return await _call(
            codebook_client.check_document_against_corpus(tmp.name, corpus_name, k=k)
        )
    finally:
        os.unlink(tmp.name)


# ── Codebook Console (docs/codebook_console.md) ─────────────────────────────
# Plain-REST proxies over codebook_rest_client.py (httpx), not the MCP client
# above — see this module's docstring for why. Power the browsing/management
# UI at frontend/app/codebook/console/page.tsx.


@router.get("/console/corpora")
async def console_corpora() -> list[dict]:
    """Every corpus Codebook has indexed, as real structured JSON — proxies
    standards-service's own `GET /api/retrieval/corpora` directly over REST.
    Powers the Codebook Console's corpora list (name, document/chunk counts,
    provenance badge)."""
    return await _call(codebook_rest_client.list_corpora())


@router.get("/console/corpora/{name}/documents")
async def console_documents(name: str) -> list[dict]:
    """Every document in corpus `name`, each with its own provenance_tag —
    proxies standards-service's `GET /api/retrieval/corpora/{name}/documents`.
    A corpus can be "mixed" even when its own CorpusSummary.provenance_tag is
    a single value; the per-document tag returned here is authoritative."""
    return await _call(codebook_rest_client.list_documents(name))


@router.post("/console/upload")
async def console_upload(
    file: UploadFile = File(...),
    corpus_name: str = Form(...),
) -> dict:
    """Upload a document into `corpus_name` on Codebook's own retrieval
    index — proxies standards-service's `POST /api/retrieval/upload`
    (multipart passthrough). Always comes back tagged
    `provenance_tag="company_uploaded"` (Codebook's own convention for
    anything ingested via this path, as opposed to its internal
    filesystem-indexed verified-standards corpora)."""
    content = await file.read()
    return await _call(
        codebook_rest_client.upload_document(file.filename or "upload", content, corpus_name)
    )
