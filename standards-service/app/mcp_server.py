"""Codebook's MCP server (step 3, docs/BUILD_PLAN_CODEBOOK.md).

Exposes the retrieval package already relocated into `app/retrieval/`
(step 2) as three MCP tools any agent can call: `list_corpora`,
`search_standards`, `get_clause`. Built the same way manak-dev's own MCP
server is built — see
`/home/awni/Documents/Project_hackathon/manak-dev/app/backend/mcp_server.py`
(read-only reference, never imported, never modified) — same SDK
(`mcp.server.fastmcp.FastMCP`), same streamable-HTTP transport mounted at
`/mcp` with the session manager run for the lifetime of the app (see
`app/main.py`).

**One deliberate deviation from manak-dev's exact response shape**, forced by
a real dependency conflict (see `requirements.txt`'s comment): manak-dev
pins `mcp>=1.2` and resolves to 1.28.1, whose `FastMCP.tool()` accepts a
`structured_output=False` escape hatch that lets a tool return a pre-built
`types.CallToolResult` (content block + `structuredContent` + explicit
`isError`) verbatim. Codebook is pinned to `mcp==1.9.4` instead — the newest
release that resolves cleanly against `fastapi==0.115.0`'s own
`starlette<0.39` pin (kept byte-identical to `backend/requirements.txt` on
purpose, since the relocated retrieval package must behave identically to
the original). 1.9.4 has neither `structured_output` nor that passthrough:
returning a `CallToolResult` from a tool function gets double-wrapped (JSON-
dumped into a single new text block) by `_convert_to_content`, and
`isError` is only ever set `True` by the SDK when the tool function raises.
Confirmed both failure modes locally before adapting. So here: every tool
returns a **plain human-readable string** (still "one consolidated prose
block the model reads," just without a separate `structuredContent` mirror),
and a genuine hard failure (unknown corpus, unknown chunk) is a raised
`ValueError` — the SDK's own `call_tool` handler catches it and sets
`isError=True` with the message as the content, which is the same
information manak-dev's own `_unresolved_code`/`_not_found` hard-error path
conveys, just via the SDK's built-in exception path instead of a
hand-built `CallToolResult`.

This module does NOT reimplement ranking, chunking, or corpus loading — it
calls straight into `app/retrieval/index.py` (`list_corpora`/`get_corpus`,
the `Corpus.query` hybrid BM25+dense+RRF search already proven in
`run_retrieval_eval.py`/`run_cross_corpus_eval.py`) and
`app/retrieval/router.py`'s `_ensure_loaded()` lazy-load pattern (restore any
persisted company corpora, then build the two read-only filesystem corpora
on first use). Every chunk returned is the real, already-indexed
`raw_text` — never generated, never paraphrased by an LLM; this module
contains no LLM call at all.

Tool scope — 4 tools total (step 4 adds `check_document_against_corpus`, the
new reasoning primitive; see `document_check.py` for its full pipeline and
stated limitations, not reimplemented here):
  - `list_corpora`     — live corpus metadata (name, source type, doc/chunk
                          counts, backing directory for filesystem corpora).
  - `search_standards` — ranked chunks for a query, optionally scoped to one
                          corpus; calls `Corpus.query` (hybrid RRF, gated by
                          `RETRIEVAL_FLOOR`) — never a fresh ranking impl.
  - `get_clause`       — exact verbatim `raw_text` for one previously-seen
                          `chunk_id` (+ its `document_id`, for disambiguation
                          and a defensive mismatch check), read directly off
                          the already-loaded in-memory chunk record. Never
                          synthesizes text: an unmatched id is a hard error.
  - `check_document_against_corpus` — given a document already readable on
                          this service's own filesystem (a path, not an
                          upload payload — see this tool's own docstring
                          below for why) and a target corpus name, extracts
                          candidate requirement sentences, searches this
                          same index per sentence, and deterministically
                          decides CONFORMS/NON_CONFORM/NEEDS_REVIEW against
                          the real matched clause's own extractable
                          threshold — never an LLM decision, never a
                          fabricated clause.

Deliberately NO `from __future__ import annotations` here (unlike the rest
of this codebase's usual house style) — mcp==1.9.4's `Tool.from_function`
inspects `inspect.signature(fn).parameters[...].annotation` directly (see
`mcp/server/fastmcp/tools/base.py`) expecting real runtime type objects, not
PEP 563 stringified annotations; with the future import present,
`Optional[str]` arrives as the *string* `"Optional[str]"` and its internal
`issubclass(annotation, Context)` check crashes on a non-class. Confirmed by
reproducing the exact `TypeError: issubclass() arg 1 must be a class`
locally before removing this import.
"""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import document_check
from .retrieval import router as retrieval_router
from .retrieval.filesystem_corpora import (
    MANAK_CORPUS_NAME,
    MANAK_LIB_DIR,
    SITEMIND_CORPUS_NAME,
    SITEMIND_STANDARDS_DIR,
)
from .retrieval.index import RETRIEVAL_FLOOR, Corpus, get_corpus
from .retrieval.index import list_corpora as _list_corpora

INSTRUCTIONS = (
    "Search and fetch real, verbatim text from Codebook's indexed standards "
    "corpora — manak-sourced structural codes, SiteMind's own verified "
    "standards, and any company-uploaded documents.\n"
    "\n"
    "- Call `list_corpora` first to see what's indexed and its real doc/chunk "
    "counts.\n"
    "- Call `search_standards` with a keyword query (optionally scoped to one "
    "corpus_name from list_corpora) to find ranked, relevant chunks. Each hit "
    "already carries its full verbatim chunk text — this is not a stub "
    "search, the text returned IS the citable text.\n"
    "- Call `get_clause` with a hit's exact `document_id` + `chunk_id` (both "
    "shown in every search_standards result) to re-fetch that exact chunk's "
    "verbatim text directly from the index, e.g. to re-verify a citation "
    "later in a conversation without re-running the search.\n"
    "- Every returned chunk is real text already present in the corpus on "
    "disk — never generated or paraphrased. A query too weak to confidently "
    "match anything abstains (empty results) rather than returning the "
    "nearest irrelevant chunk."
)


def _backing_dir(corpus: Corpus) -> Optional[str]:
    """The real directory a filesystem-readonly corpus is built from, for
    `list_corpora`'s disclosure — None for a company_upload corpus (no single
    backing directory; it's whatever was individually uploaded)."""
    if corpus.source != "filesystem_readonly":
        return None
    if corpus.name == MANAK_CORPUS_NAME:
        return str(MANAK_LIB_DIR)
    if corpus.name == SITEMIND_CORPUS_NAME:
        return str(SITEMIND_STANDARDS_DIR)
    return None


def _corpus_row(corpus: Corpus) -> dict:
    return {
        "corpus_name": corpus.name,
        "source_type": corpus.source,  # "filesystem_readonly" | "company_upload"
        "document_count": len(corpus.document_ids),
        "chunk_count": corpus.chunk_count,
        "provenance_tag": corpus.provenance_tag,
        "backing_directory": _backing_dir(corpus),
    }


def _render_corpora(rows: list[dict]) -> str:
    if not rows:
        return "No corpora are currently loaded."
    lines = [f"{len(rows)} corpora loaded:", ""]
    for r in rows:
        lines.append(f"- {r['corpus_name']}  ({r['source_type']})")
        lines.append(f"    documents: {r['document_count']}, chunks: {r['chunk_count']}")
        if r["backing_directory"]:
            lines.append(f"    backed by: {r['backing_directory']}")
        lines.append("")
    lines.append(
        "Use the exact corpus_name in search_standards to scope a query to one "
        "corpus, or omit it to search all loaded corpora."
    )
    return "\n".join(lines)


def _chunk_row(c: dict) -> dict:
    return {
        "corpus_name": c.get("corpus_name"),
        "document_id": c.get("document_id"),
        "chunk_id": c.get("chunk_id"),
        "filename": c.get("filename"),
        "heading": c.get("heading"),
        "breadcrumb": c.get("breadcrumb"),
        "text": c.get("raw_text", c.get("text", "")),
        "provenance_tag": c.get("provenance_tag", "company_uploaded"),
        "score": c.get("score"),
    }


def _render_search(query: str, corpus_name: Optional[str], rows: list[dict]) -> str:
    n = len(rows)
    head = f"{n} match{'es' if n != 1 else ''} for {query!r}"
    if corpus_name:
        head += f" in {corpus_name}"
    else:
        head += " across all loaded corpora"
    lines = [head + ":", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. [{r['corpus_name']}] {r['document_id']} :: {r['chunk_id']}   (score {r['score']:.3f})")
        if r.get("breadcrumb"):
            lines.append(f"   {r['breadcrumb']}")
        lines.append(f"   {r['text'][:300]}{'…' if len(r['text']) > 300 else ''}")
        lines.append(
            f"   → get_clause(document_id={r['document_id']!r}, chunk_id={r['chunk_id']!r})"
        )
        lines.append("")
    if not rows:
        lines.append(
            "No matches cleared the retrieval floor for this query — try different "
            "keywords/synonyms, or call list_corpora to confirm what's indexed."
        )
    return "\n".join(lines)


def _render_check(document_path: str, corpus_name: str, findings: list[dict]) -> str:
    n = len(findings)
    if n == 0:
        return (
            f"No candidate requirement sentences (number+unit, or a modal word co-occurring "
            f"with a number) were detected in {document_path!r}."
        )
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["decision"]] = counts.get(f["decision"], 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    lines = [
        f"{n} candidate requirement sentence(s) checked against corpus {corpus_name!r} "
        f"in {document_path!r} ({summary}):",
        "",
    ]
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. [{f['decision']}] \"{f['source_sentence']}\"")
        mc = f.get("matched_clause")
        if mc:
            score = mc.get("score")
            score_str = f"  (score {score:.3f})" if score is not None else ""
            lines.append(f"   matched: [{mc['corpus_name']}] {mc['document_id']} :: {mc['chunk_id']}{score_str}")
            text = mc["text"]
            lines.append(f"   clause text: {text[:300]}{'…' if len(text) > 300 else ''}")
        else:
            lines.append("   no clause in this corpus cleared the retrieval floor for this sentence.")
        if f.get("abstain_reason"):
            lines.append(f"   reason: {f['abstain_reason']}")
        prose = f["prose"]
        lines.append(f"   {prose['finding']}")
        lines.append(f"   {prose['detail']}")
        lines.append(f"   action: {prose['action']}")
        lines.append("")
    return "\n".join(lines)


def build_mcp() -> FastMCP:
    # Mirrors manak-dev's own build_mcp(): stateless_http + json_response are
    # this project's convention for the friendliest mode behind local dev
    # (no SSE session affinity — this codebase's own CLAUDE.md notes SSE has
    # failed to connect before, for manak specifically; HTTP transport is the
    # one already proven to work).
    mcp = FastMCP(
        "codebook",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )

    @mcp.tool()
    def list_corpora() -> str:
        """List every corpus currently indexed by Codebook — the same live
        in-memory registry `search_standards`/`get_clause` read from, never a
        hardcoded/cached list. Takes no arguments.

        Returns each corpus's name, source type (`filesystem_readonly` for a
        real directory on disk indexed read-only — manak's structural codes,
        SiteMind's own verified standards — vs `company_upload` for a
        document POSTed through the ingest pipeline), its real document and
        chunk counts, and, for filesystem corpora, the exact directory backing
        it.
        """
        retrieval_router._ensure_loaded()
        rows = [_corpus_row(c) for c in _list_corpora()]
        return _render_corpora(rows)

    # Description built explicitly (not left to the decorator to read
    # `func.__doc__`) so RETRIEVAL_FLOOR's real, current value is interpolated
    # in — never a stale hardcoded number if that constant is retuned later.
    _search_standards_doc = f"""Search Codebook's indexed corpora for chunks relevant to `query`.
Ranking is the existing hybrid BM25 + dense-embedding index (fused via
Reciprocal Rank Fusion, already held-out tested in
run_retrieval_eval.py / run_cross_corpus_eval.py) — this tool never
re-ranks or re-scores, it calls straight into that index.

Args:
    query: Keywords or a natural-language question.
    corpus_name: Optionally scope to one corpus (see list_corpora for
        the exact names, e.g. "manak_structural",
        "sitemind_existing_standards"). Omit to search every loaded
        corpus and merge results by score.
    k: Max hits to return (default 5, capped at 50). When
        corpus_name is omitted this is the total across all corpora,
        not per corpus.

Returns each hit's corpus, document_id, chunk_id, heading/breadcrumb, and a
300-char text excerpt of its verbatim chunk text inline (the excerpt is a
plain slice of the real text, never truncated mid-fabrication) plus the
exact get_clause(...) call to re-fetch that chunk's FULL verbatim text, and
its retrieval score. A query too weak to confidently match anything in a
given corpus abstains for that corpus (this index's own RETRIEVAL_FLOOR
gate, currently {RETRIEVAL_FLOOR}) rather than returning its nearest
irrelevant chunk — a total-zero result is a soft miss (empty list), not an
error. An unknown corpus_name IS a hard error (raised, not silently
ignored)."""

    @mcp.tool(description=_search_standards_doc)
    def search_standards(query: str, corpus_name: Optional[str] = None, k: int = 5) -> str:
        retrieval_router._ensure_loaded()
        k = max(1, min(k, 50))

        if corpus_name:
            corpus = get_corpus(corpus_name)
            if corpus is None:
                known = ", ".join(sorted(c.name for c in _list_corpora())) or "(none loaded)"
                raise ValueError(f"No corpus named {corpus_name!r}. Known corpora: {known}.")
            hits = [_chunk_row(c) for c in corpus.query(query, k=k)]
        else:
            hits = []
            for corpus in _list_corpora():
                hits.extend(_chunk_row(c) for c in corpus.query(query, k=k))
            hits.sort(key=lambda r: r["score"], reverse=True)
            hits = hits[:k]

        return _render_search(query, corpus_name, hits)

    @mcp.tool()
    def get_clause(document_id: str, chunk_id: str) -> str:
        """Fetch ONE chunk's exact, verbatim text by its `document_id` +
        `chunk_id` (both shown on every search_standards hit). This never
        regenerates or paraphrases text — it reads the chunk record directly
        out of the already-built in-memory index, the same record
        search_standards scored, so the text returned is byte-identical to
        what's on disk.

        Args:
            document_id: The chunk's document_id, e.g. "is456_2000" or
                "clauses" (from a prior search_standards hit).
            chunk_id: The exact chunk_id from a prior search_standards hit,
                e.g. "is456_2000:0042".

        Returns the chunk's corpus, document, heading/breadcrumb, its full
        verbatim text, and provenance tag (e.g. "manak_indexed",
        "sitemind_indexed", "company_uploaded"). Raises (hard error, not a
        best-guess substitute) if no chunk with that exact document_id +
        chunk_id is currently indexed.
        """
        retrieval_router._ensure_loaded()
        for corpus in _list_corpora():
            for c in corpus.chunks:
                if c.get("document_id") == document_id and c.get("chunk_id") == chunk_id:
                    row = _chunk_row(c)
                    lines = [f"[{row['corpus_name']}] {row['document_id']} :: {row['chunk_id']}"]
                    if row.get("breadcrumb"):
                        lines.append(row["breadcrumb"])
                    lines.append("")
                    lines.append(row["text"])
                    lines.append("")
                    lines.append(f"provenance: {row['provenance_tag']}")
                    return "\n".join(lines)

        raise ValueError(
            f"No chunk found for document_id={document_id!r}, chunk_id={chunk_id!r}. "
            "Call search_standards to find a valid chunk_id, or list_corpora to "
            "confirm the document is indexed."
        )

    @mcp.tool()
    def check_document_against_corpus(document_path: str, corpus_name: str, k: int = 3) -> str:
        """Check a document's requirement sentences against a real standards
        corpus, with a deterministic CONFORMS/NON_CONFORM/NEEDS_REVIEW
        decision per sentence — Codebook's own reasoning primitive, not just
        a retrieval call. See `document_check.py` for the full pipeline.

        Args:
            document_path: Absolute (or Codebook-process-relative) path to a
                .pdf/.docx/.txt/.md file already readable on this service's
                own filesystem. (Deliberately a path, not an inline content
                payload: the spec's alternative — POST-upload then
                reference by id via the existing company_upload pipeline —
                would persist the document into a searchable corpus, which
                is the wrong semantics for a one-off "check this doc"
                request; a path keeps this call self-contained and avoids
                binary-content-over-MCP-arguments transport concerns
                entirely, at the cost of requiring the caller to have
                filesystem access to Codebook's host — acceptable for this
                same-host, MCP-client-is-SiteMind's-own-backend design.)
            corpus_name: The corpus to check against (see list_corpora for
                valid names, e.g. "sitemind_existing_standards",
                "manak_structural").
            k: How many candidate clauses to retrieve per sentence before
                taking the top one as "the" matched clause (default 3,
                capped at 20).

        Returns, per candidate requirement sentence found in the document:
        the exact source sentence, the best-matched clause's corpus/
        document/chunk id + its FULL verbatim text (never paraphrased), and
        the decision. A sentence is CONFORMS/NON_CONFORM only when BOTH the
        document sentence AND the matched clause yield a comparable
        number+unit with a determinable min/max direction and matching
        units — anything else (no clause found, clause has no extractable
        threshold, unit mismatch, no direction marker) is NEEDS_REVIEW,
        citing the real clause rather than guessing. The pass/fail decision
        is ALWAYS deterministic Python; prose is LLM-composed only when a
        provider is configured (see config.OFFLINE_MODE), otherwise a
        Python string template — this tool works with zero API keys.

        Raises (hard error) if `document_path` doesn't exist, its extension
        is unsupported, or `corpus_name` isn't currently loaded.
        """
        retrieval_router._ensure_loaded()
        k = max(1, min(k, 20))
        findings = document_check.check_document_against_corpus(document_path, corpus_name, k=k)
        return _render_check(document_path, corpus_name, findings)

    return mcp
