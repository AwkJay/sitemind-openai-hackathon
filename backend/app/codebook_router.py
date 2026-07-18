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
"""
from __future__ import annotations

from typing import Awaitable, Optional, TypeVar

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import codebook_client

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
