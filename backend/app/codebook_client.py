"""Codebook MCP client — this backend as an MCP *client* of Codebook (step 5,
docs/BUILD_PLAN_CODEBOOK.md).

Only ever imported when `config.CODEBOOK_ENABLED` is true (see the guarded
import in `app/main.py`) — with the flag off, this module and its only
non-stdlib import (the `mcp` client SDK) are never touched at all, same
import-gating discipline as `app/retrieval/router.py` + `RETRIEVAL_ENABLED`.

Connects to Codebook's own MCP server (`standards-service/app/mcp_server.py`,
mounted at `/mcp` on `config.CODEBOOK_MCP_URL`, default
`http://127.0.0.1:8010/mcp`) using the standard `mcp` Python SDK client
pattern: `mcp.client.streamable_http.streamablehttp_client` opens the
streamable-HTTP transport, `mcp.ClientSession` speaks the MCP protocol over
it. This is the same SDK (`mcp==1.9.4`, pinned identically to
`standards-service/requirements.txt` — see that file's own comment for why
this exact version, not latest) already proven live against Codebook's
server in the steps that built it.

Codebook's 4 tools (`list_corpora`, `search_standards`, `get_clause`,
`check_document_against_corpus`) each return ONE human-readable text block,
not a structured payload — see `mcp_server.py`'s module docstring for why
(mcp==1.9.4 has no `structured_output` passthrough, unlike the newer mcp
manak-dev itself resolves to). So every function below returns that text
block verbatim under a `"text"` key, plus whatever the caller already knows
about the call (query, corpus, ids) — never a best-effort reparse into
fields, which would risk silently drifting from what Codebook actually said.

A fresh session is opened per call rather than held open across requests:
this backend calls Codebook rarely (interactive REST requests proxied 1:1),
not in a tight loop, so the extra connect/initialize round-trip is a
non-issue and avoids any shared-session lifecycle/reconnect complexity.
"""
from __future__ import annotations

from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from . import config


class CodebookUnavailable(Exception):
    """Codebook's MCP server could not be reached, or a tool call returned a
    hard error. Raised instead of letting the underlying connection/transport
    exception propagate, so callers (codebook_router.py) have one exception
    type to translate into a clean HTTP response — Codebook being down must
    never crash this backend, same graceful-degradation contract as an
    unreachable Langfuse (see app/langfuse_sink.py)."""


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Open a fresh MCP session against Codebook, call one tool, return its
    single text block. Raises CodebookUnavailable on any connection failure
    (Codebook not running, wrong port, timeout, ...) or a tool-level hard
    error (e.g. unknown corpus_name/chunk_id — see mcp_server.py, those are
    raised ValueErrors the SDK surfaces as `isError=True`)."""
    try:
        # Explicit 100s timeout, not the SDK's 30s default: on Render's free
        # tier Codebook (standards-service) can take 60-90s to answer from a
        # cold start, and this backend only calls it on demand — the SDK
        # default gave up on Codebook well before it finished waking.
        async with streamablehttp_client(config.CODEBOOK_MCP_URL, timeout=100) as (
            read,
            write,
            _get_session_id,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    except CodebookUnavailable:
        raise
    except Exception as exc:
        raise CodebookUnavailable(
            f"Could not reach Codebook's MCP server at {config.CODEBOOK_MCP_URL} "
            f"(is standards-service/run.sh running?): {exc}"
        ) from exc

    text = "\n".join(
        block.text for block in result.content if getattr(block, "type", None) == "text"
    )
    if result.isError:
        raise CodebookUnavailable(f"Codebook tool {tool_name!r} returned an error: {text}")
    return text


async def list_corpora() -> dict:
    """Every corpus currently indexed by Codebook — real doc/chunk counts,
    source type, backing directory. Mirrors mcp_server.py's `list_corpora`."""
    text = await _call_tool("list_corpora", {})
    return {"text": text}


async def search_standards(query: str, corpus: Optional[str] = None, k: int = 5) -> dict:
    """Ranked chunks for `query`, optionally scoped to one `corpus` (a
    corpus_name from list_corpora). Mirrors mcp_server.py's `search_standards`."""
    args: dict[str, Any] = {"query": query, "k": k}
    if corpus:
        args["corpus_name"] = corpus
    text = await _call_tool("search_standards", args)
    return {"query": query, "corpus_name": corpus, "k": k, "text": text}


async def get_clause(doc_id: str, chunk_id: str) -> dict:
    """One chunk's exact verbatim text by document_id + chunk_id (both from a
    prior search_standards hit). Mirrors mcp_server.py's `get_clause`."""
    text = await _call_tool("get_clause", {"document_id": doc_id, "chunk_id": chunk_id})
    return {"document_id": doc_id, "chunk_id": chunk_id, "text": text}


async def check_document_against_corpus(document_path: str, corpus_name: str, k: int = 3) -> dict:
    """Check a document's requirement sentences against a real corpus with a
    deterministic CONFORMS/NON_CONFORM/NEEDS_REVIEW decision per sentence.
    `document_path` must be readable on Codebook's OWN host filesystem (see
    mcp_server.py's tool docstring for why this is a path, not an upload
    payload). Mirrors mcp_server.py's `check_document_against_corpus`."""
    text = await _call_tool(
        "check_document_against_corpus",
        {"document_path": document_path, "corpus_name": corpus_name, "k": k},
    )
    return {"document_path": document_path, "corpus_name": corpus_name, "k": k, "text": text}
