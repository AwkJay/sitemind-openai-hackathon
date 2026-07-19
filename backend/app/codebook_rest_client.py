"""Plain REST client for 3 of Codebook's own structured retrieval endpoints
(docs/codebook_console.md — the Codebook Console).

Sibling to `codebook_client.py`, but deliberately NOT the MCP client:
Codebook's retrieval router (`standards-service/app/retrieval/router.py`)
already returns structured JSON directly over plain REST for
`list_corpora` / `corpus_documents` / `upload` — going through MCP for these
would mean re-parsing a prose text block back into fields, exactly what
`codebook_client.py`'s own module docstring says never to do (mcp==1.9.4
tool calls return one human-readable text block, not a structured payload).
So this module talks straight `httpx` to Codebook's REST API instead.

Only ever imported when `config.CODEBOOK_ENABLED` is true (via
`codebook_router.py`, itself only imported under that same flag in
`app/main.py`) — same import-gating discipline as `codebook_client.py`.
`httpx` is already an installed transitive dependency (pulled in by `mcp`/
`anthropic`), so this adds no new package, just a new direct import path.

Reuses `codebook_client.CodebookUnavailable` as the one exception type for
"Codebook could not be reached" OR "Codebook's REST API returned a hard
error" (e.g. an unknown corpus name) — same fold-together-into-one-type
choice `codebook_client._call_tool` already makes for MCP tool calls, so
`codebook_router.py`'s existing `_call()` 503-translation helper works
unchanged for these endpoints too.
"""
from __future__ import annotations

import httpx

from .codebook_client import CodebookUnavailable
from . import config

# config.CODEBOOK_MCP_URL is "http://127.0.0.1:8010/mcp" — Codebook's plain
# REST routes live on that same host/port, just under "/api/retrieval/..."
# rather than "/mcp". Reuse the one configured host, don't add a second URL
# setting (per docs/codebook_console.md).
_BASE_URL = config.CODEBOOK_MCP_URL.rsplit("/mcp", 1)[0]

_TIMEOUT = httpx.Timeout(30.0)


async def _get(path: str) -> object:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE_URL}{path}")
    except httpx.HTTPError as exc:
        raise CodebookUnavailable(
            f"Could not reach Codebook's REST API at {_BASE_URL} "
            f"(is standards-service/run.sh running?): {exc}"
        ) from exc
    if resp.status_code >= 400:
        raise CodebookUnavailable(
            f"Codebook's REST API returned {resp.status_code} for {path}: {resp.text}"
        )
    return resp.json()


async def list_corpora() -> list[dict]:
    """Every corpus Codebook has indexed, as real structured JSON — proxies
    standards-service's `GET /api/retrieval/corpora` (a `CorpusSummary` list:
    corpus_name, document_count, chunk_count, source, provenance_tag).
    Powers the Codebook Console's corpora list."""
    return await _get("/api/retrieval/corpora")


async def list_documents(corpus_name: str) -> list[dict]:
    """Every document in one corpus, each with its OWN provenance_tag —
    proxies `GET /api/retrieval/corpora/{corpus_name}/documents`
    (document_id, filename, chunk_count, structured, provenance_tag per
    document). A corpus can be "mixed" even when its own CorpusSummary is a
    single provenance_tag; this per-document tag is the authoritative one."""
    return await _get(f"/api/retrieval/corpora/{corpus_name}/documents")


async def upload_document(filename: str, content: bytes, corpus_name: str) -> dict:
    """Upload one document into `corpus_name` on Codebook's own retrieval
    index — proxies `POST /api/retrieval/upload` (multipart `file` +
    `corpus_name` form field). Codebook always tags the result
    `provenance_tag="company_uploaded"` (its own convention for anything
    ingested this way, as opposed to its internal filesystem-indexed
    verified-standards corpora). Returns the real `IngestManifest` JSON
    (document_id, corpus_name, filename, chunk_count, structured,
    provenance_tag)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_BASE_URL}/api/retrieval/upload",
                data={"corpus_name": corpus_name},
                files={"file": (filename, content)},
            )
    except httpx.HTTPError as exc:
        raise CodebookUnavailable(
            f"Could not reach Codebook's REST API at {_BASE_URL} "
            f"(is standards-service/run.sh running?): {exc}"
        ) from exc
    if resp.status_code >= 400:
        raise CodebookUnavailable(
            f"Codebook's REST API returned {resp.status_code} for /api/retrieval/upload: {resp.text}"
        )
    return resp.json()
