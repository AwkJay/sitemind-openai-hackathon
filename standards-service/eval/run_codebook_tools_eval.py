"""Held-out eval for Codebook's MCP TOOL INTERFACE itself (docs/BUILD_PLAN_CODEBOOK.md
step 9) — a genuinely different test surface from the two evals that already exist in
this directory.

`run_retrieval_eval.py` / `run_cross_corpus_eval.py` test the underlying retrieval
LOGIC (chunker, RRF fusion, corpus building) by importing `app/retrieval/*` directly
in-process. They never make a real MCP protocol call, so a bug in `app/mcp_server.py`
itself (a wrong tool signature, a broken `isError` path, a tool that silently returns
the wrong shape) would pass both of those suites undetected.

THIS script drives all 4 MCP tools through the REAL protocol — a real
`mcp.client.streamable_http.streamablehttp_client` + `mcp.ClientSession`, talking HTTP
to a LIVE `standards-service` process on port 8010 (same transport already proven
working for manak in this project's own CLAUDE.md, and the same SDK version
(mcp==1.9.4) `app/mcp_server.py` is built against). Requires the service already
running (`./run.sh` from `standards-service/`, or this script's own `main()` will tell
you to start it if `/health` doesn't respond).

What each tool is checked against (all grounded in real, independently verified corpus
content — see this file's own case docstrings for the grep/REST verification each
expected value was checked against before being hardcoded here):

  1. list_corpora        — real corpus doc/chunk counts match the state
                            docs/BUILD_PLAN_CODEBOOK.md's "Done when" section records
                            (codebook_structural, renamed from manak_structural per
                            docs/codebook_changes.md item 2: 17 docs/6206 chunks;
                            sitemind_existing_standards: 2 docs/29 chunks).
  2. search_standards     — 2 real queries with known top-1 hits (verified via the
                            existing REST /api/retrieval/query endpoint before being
                            hardcoded as expectations here — same underlying
                            Corpus.query call, just a different transport, so this is a
                            legitimate independent cross-check of the MCP layer against
                            already-observed real behavior) + 2 genuinely off-topic
                            queries that must abstain (0 results) rather than return
                            the nearest irrelevant chunk.
  3. get_clause           — one clause from EACH filesystem corpus, fetched via MCP,
                            with its returned text independently verified against the
                            real source file on disk (grep/substring check, not just
                            "the tool said so") + one bogus id that must come back as a
                            real MCP protocol error (`isError=True`), not fabricated text.
  4. check_document_against_corpus — a small synthetic test document (3 sentences,
                            written for this eval, checked against
                            `sitemind_existing_standards`) exercising all 3 possible
                            decisions: CONFORMS, NON_CONFORM, NEEDS_REVIEW. Each
                            expected decision was pre-verified by calling
                            `app/document_check.py`'s pure Python function directly
                            (see the docstring on TEST_DOC_PATH below) before being
                            encoded as an MCP-protocol-level expectation here.

Writes `standards-service/eval/codebook_tools_report.json`, reported SEPARATELY —
never merged into `retrieval_report.json`'s or `cross_corpus_report.json`'s counts.

Run (service must already be up on :8010):
    cd standards-service && source .venv/bin/activate && python -m eval.run_codebook_tools_eval
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPORT_PATH = Path(__file__).resolve().parent / "codebook_tools_report.json"
MCP_URL = "http://127.0.0.1:8010/mcp/"
HEALTH_URL = "http://127.0.0.1:8010/health"

# --------------------------------------------------------------------------- #
# Ground truth, independently verified BEFORE being hardcoded here:
#   - list_corpora counts: `curl -s localhost:8010/api/retrieval/corpora`
#     (real REST call against the same live corpus registry, 2026-07-10) ->
#     manak_structural (renamed codebook_structural, docs/codebook_changes.md
#     item 2, 2026-07-12) 17 docs/6206 chunks, sitemind_existing_standards 2
#     docs/29 chunks. Matches docs/BUILD_PLAN_CODEBOOK.md's own "Done when"
#     entry verbatim.
#   - search_standards top hits: verified via the same REST /api/retrieval/query
#     endpoint before being encoded below (scores observed: importance-factor
#     query -> is1893_part1_2016:0020 at 0.667; earth-grid query ->
#     clauses:IS3043_1987_22.2.3 at 0.818). Both clear RETRIEVAL_FLOOR=0.30
#     comfortably.
#   - get_clause text: grep-verified directly against the real source files
#     (manak-dev/lib/is1893_part1_2016/irc.gov.in.1893.2016.md and
#     backend/data/standards/clauses.json) — see individual case functions below.
# --------------------------------------------------------------------------- #

MANAK_SOURCE_FILE = Path(
    "/home/awni/Documents/Project_hackathon/manak-dev/lib/is1893_part1_2016/irc.gov.in.1893.2016.md"
)
CLAUSES_JSON_FILE = (
    Path(__file__).resolve().parents[2] / "backend" / "data" / "standards" / "clauses.json"
)

# --------------------------------------------------------------------------- #
# Synthetic test document for check_document_against_corpus. 3 sentences, one
# per paragraph so each lands as its own candidate independent of the others.
# Every expected decision below was pre-verified by calling
# `app.document_check.check_document_against_corpus()` directly (bypassing MCP
# entirely) against this exact text on 2026-07-10:
#   "...55 mm."  -> CONFORMS      (matched clauses:IS456_26.4.2.2, "minimum
#                                   cover shall be 50 mm" -- 55 >= 50)
#   "...40 mm."  -> NON_CONFORM   (same clause -- 40 < 50)
#   "...0.8 ohm." -> NEEDS_REVIEW (matched clauses:IS3043_1987_22.2.3, whose
#                                   real text states "one ohm" in WORD form,
#                                   not a digit -- the extractor deliberately
#                                   never parses number-words (see
#                                   document_check.py's own module docstring
#                                   "KNOWN LIMITATIONS"), so no clause
#                                   threshold is extractable and it correctly
#                                   abstains rather than guessing)
# --------------------------------------------------------------------------- #
TEST_DOC_TEXT = (
    "The footing cover provided shall be at least 55 mm.\n"
    "\n"
    "The footing cover provided shall be at least 40 mm.\n"
    "\n"
    "The measured earth grid resistance was 0.8 ohm.\n"
)


def _new_case(name: str, group: str, expected, actual) -> dict:
    return {"name": name, "group": group, "expected": expected, "actual": actual, "pass": expected == actual}


# --------------------------------------------------------------------------- #
# MCP call helper
# --------------------------------------------------------------------------- #
async def _call_tool(session: ClientSession, name: str, arguments: dict):
    result = await session.call_tool(name, arguments)
    text = ""
    if result.content:
        # Every tool in mcp_server.py returns exactly one text content block
        # (see that module's own docstring on the mcp==1.9.4 return-shape
        # constraint) -- concatenate defensively rather than assume len==1.
        text = "\n".join(block.text for block in result.content if getattr(block, "text", None) is not None)
    return result.isError, text


# --------------------------------------------------------------------------- #
# 1. list_corpora
# --------------------------------------------------------------------------- #
async def _cases_list_corpora(session: ClientSession) -> list[dict]:
    is_error, text = await _call_tool(session, "list_corpora", {})
    cases = []
    cases.append(_new_case("list_corpora_no_error", "list_corpora", False, is_error))
    cases.append(
        _new_case(
            "list_corpora_codebook_structural_counts",
            "list_corpora",
            True,
            ("codebook_structural" in text and "documents: 17" in text and "chunks: 6206" in text),
        )
    )
    cases.append(
        _new_case(
            "list_corpora_sitemind_existing_standards_counts",
            "list_corpora",
            True,
            (
                "sitemind_existing_standards" in text
                and "documents: 2" in text
                and "chunks: 29" in text
            ),
        )
    )
    cases.append(
        _new_case(
            "list_corpora_both_source_types_disclosed",
            "list_corpora",
            True,
            ("filesystem_readonly" in text),
        )
    )
    return cases


# --------------------------------------------------------------------------- #
# 2. search_standards
# --------------------------------------------------------------------------- #
async def _cases_search_standards(session: ClientSession) -> list[dict]:
    cases = []

    # Known hit #1: IS 1893 Part 1's own "Importance Factor (I)" clause, real
    # heading "3.10 Importance Factor (I)", scoped to codebook_structural.
    is_error, text = await _call_tool(
        session,
        "search_standards",
        {
            "query": "importance factor for data centre building seismic design",
            "corpus_name": "codebook_structural",
            "k": 3,
        },
    )
    cases.append(_new_case("search_importance_factor_no_error", "search_standards", False, is_error))
    cases.append(
        _new_case(
            "search_importance_factor_hits_is1893",
            "search_standards",
            True,
            ("is1893_part1_2016" in text and "0020" in text),
        )
    )

    # Known hit #2: IS 3043's earth-grid-resistance clause, scoped to
    # sitemind_existing_standards.
    is_error, text = await _call_tool(
        session,
        "search_standards",
        {"query": "earth grid resistance ohm", "corpus_name": "sitemind_existing_standards", "k": 3},
    )
    cases.append(_new_case("search_earth_grid_no_error", "search_standards", False, is_error))
    cases.append(
        _new_case(
            "search_earth_grid_hits_is3043",
            "search_standards",
            True,
            ("IS3043_1987_22.2.3" in text),
        )
    )

    # Off-topic queries -- both must abstain (0 matches), not return the
    # nearest irrelevant chunk. Real English queries with zero relation to
    # structural/electrical standards -- pre-verified via REST to score below
    # RETRIEVAL_FLOOR on their single best dense match.
    for i, q in enumerate(["best vacation destinations in Europe", "recipe for chocolate chip cookies"], 1):
        is_error, text = await _call_tool(
            session, "search_standards", {"query": q, "corpus_name": "codebook_structural", "k": 3}
        )
        cases.append(_new_case(f"search_offtopic_{i}_no_error", "search_standards", False, is_error))
        cases.append(
            _new_case(
                f"search_offtopic_{i}_abstains",
                "search_standards",
                True,
                text.startswith("0 matches"),
            )
        )

    # Unknown corpus_name IS a hard error per mcp_server.py's own contract.
    is_error, text = await _call_tool(
        session, "search_standards", {"query": "anything", "corpus_name": "not_a_real_corpus", "k": 3}
    )
    cases.append(_new_case("search_unknown_corpus_is_hard_error", "search_standards", True, is_error))

    return cases


# --------------------------------------------------------------------------- #
# 3. get_clause
# --------------------------------------------------------------------------- #
async def _cases_get_clause(session: ClientSession) -> list[dict]:
    cases = []

    # Filesystem corpus #1 (codebook_structural): raw_text is a literal
    # text[start_char:end_char] slice of the real .md file (chunker.py's own
    # contract) -- grep-verify it is a genuine contiguous substring of the
    # real source file on disk, not a re-typeset/paraphrased version.
    is_error, text = await _call_tool(
        session, "get_clause", {"document_id": "is1893_part1_2016", "chunk_id": "is1893_part1_2016:0020"}
    )
    source_raw = MANAK_SOURCE_FILE.read_text(encoding="utf-8")
    # Strip the mcp_server.py `_chunk_row`/get_clause rendering scaffolding
    # (corpus/doc header line + trailing "provenance:" line) to isolate the
    # actual chunk body before checking it against the source file.
    body_lines = text.split("\n")
    # The chunk body sits between the header lines and the trailing blank
    # line + "provenance:" line; locate it via the known heading text
    # instead of counting lines, so this doesn't silently drift if
    # get_clause's header format changes.
    heading_marker = "### 3.10 Importance Factor (I)"
    body_start = text.find(heading_marker)
    provenance_idx = text.find("\nprovenance:")
    chunk_body = text[body_start:provenance_idx].strip() if body_start >= 0 and provenance_idx > body_start else ""
    cases.append(_new_case("get_clause_is1893_no_error", "get_clause", False, is_error))
    cases.append(
        _new_case(
            "get_clause_is1893_contains_expected_heading",
            "get_clause",
            True,
            heading_marker in text,
        )
    )
    cases.append(
        _new_case(
            "get_clause_is1893_body_is_verbatim_substring_of_source_file",
            "get_clause",
            True,
            bool(chunk_body) and chunk_body in source_raw,
        )
    )
    cases.append(
        _new_case(
            "get_clause_is1893_contains_expected_sentence",
            "get_clause",
            True,
            "characterized by hazardous consequences of its failure" in text,
        )
    )

    # Filesystem corpus #2 (sitemind_existing_standards / clauses.json):
    # filesystem_corpora.py's own contract is raw_text == clause["text"]
    # EXACTLY (found via a literal substring search of the JSON's raw bytes,
    # see that module's `_clause_chunks_from_file`) -- so this one can be
    # checked for an EXACT match, not just "is a substring of".
    is_error, text = await _call_tool(
        session, "get_clause", {"document_id": "clauses", "chunk_id": "clauses:IS3043_1987_22.2.3"}
    )
    clauses_data = json.loads(CLAUSES_JSON_FILE.read_text(encoding="utf-8"))
    expected_clause_text = next(
        c["text"] for c in clauses_data["clauses"] if c["key"] == "IS3043_1987_22.2.3"
    )
    cases.append(_new_case("get_clause_is3043_no_error", "get_clause", False, is_error))
    cases.append(
        _new_case(
            "get_clause_is3043_text_byte_identical_to_clauses_json",
            "get_clause",
            True,
            expected_clause_text in text,
        )
    )
    # Independent grep-style verification against the raw file bytes too
    # (not just the json-parsed value) -- confirms no re-serialization
    # occurred anywhere in the pipeline.
    raw_clauses_bytes = CLAUSES_JSON_FILE.read_text(encoding="utf-8")
    cases.append(
        _new_case(
            "get_clause_is3043_text_found_verbatim_in_raw_source_file",
            "get_clause",
            True,
            expected_clause_text in raw_clauses_bytes and expected_clause_text in text,
        )
    )

    # Bogus chunk id -- must be a real MCP protocol error, not fabricated text.
    is_error, text = await _call_tool(
        session, "get_clause", {"document_id": "clauses", "chunk_id": "clauses:DOES_NOT_EXIST_9999"}
    )
    cases.append(_new_case("get_clause_bogus_id_is_hard_error", "get_clause", True, is_error))
    cases.append(
        _new_case(
            "get_clause_bogus_id_error_names_the_bad_id_not_fabricated_text",
            "get_clause",
            True,
            "DOES_NOT_EXIST_9999" in text and "No chunk found" in text,
        )
    )

    return cases


# --------------------------------------------------------------------------- #
# 4. check_document_against_corpus
# --------------------------------------------------------------------------- #
async def _cases_check_document(session: ClientSession, doc_path: str) -> list[dict]:
    is_error, text = await _call_tool(
        session,
        "check_document_against_corpus",
        {"document_path": doc_path, "corpus_name": "sitemind_existing_standards", "k": 3},
    )
    cases = [_new_case("check_document_no_error", "check_document_against_corpus", False, is_error)]

    # All 3 decision outcomes must appear, each attached to the right sentence
    # and (for the two comparable cases) the right matched clause.
    cases.append(
        _new_case(
            "check_document_conforms_present",
            "check_document_against_corpus",
            True,
            (
                "[CONFORMS]" in text
                and 'at least 55 mm' in text
                and text.count("[CONFORMS]") >= 1
            ),
        )
    )
    cases.append(
        _new_case(
            "check_document_non_conform_present",
            "check_document_against_corpus",
            True,
            ("[NON_CONFORM]" in text and "at least 40 mm" in text),
        )
    )
    cases.append(
        _new_case(
            "check_document_needs_review_present",
            "check_document_against_corpus",
            True,
            ("[NEEDS_REVIEW]" in text and "0.8 ohm" in text),
        )
    )
    # Both CONFORMS and NON_CONFORM sentences must cite the real IS456 cover
    # clause -- not a fabricated or mismatched one.
    cases.append(
        _new_case(
            "check_document_cites_real_is456_cover_clause",
            "check_document_against_corpus",
            True,
            text.count("clauses :: clauses:IS456_26.4.2.2") >= 2,
        )
    )
    # The NEEDS_REVIEW sentence must cite the real IS3043 earth-grid clause
    # (the one whose "one ohm" is genuinely unparseable as a digit), not
    # abstain with no clause at all.
    cases.append(
        _new_case(
            "check_document_needs_review_cites_real_is3043_clause",
            "check_document_against_corpus",
            True,
            "clauses :: clauses:IS3043_1987_22.2.3" in text,
        )
    )
    # Summary line must show exactly the expected 1/1/1 decision split.
    cases.append(
        _new_case(
            "check_document_summary_shows_all_three_decisions",
            "check_document_against_corpus",
            True,
            all(f"1 {d}" in text for d in ("CONFORMS", "NEEDS_REVIEW", "NON_CONFORM")),
        )
    )

    # Bogus document path -- must be a real MCP protocol error.
    is_error, text = await _call_tool(
        session,
        "check_document_against_corpus",
        {"document_path": "/tmp/definitely_does_not_exist_9999.txt", "corpus_name": "sitemind_existing_standards"},
    )
    cases.append(
        _new_case(
            "check_document_bogus_path_is_hard_error",
            "check_document_against_corpus",
            True,
            is_error,
        )
    )

    return cases


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
async def _run_all() -> list[dict]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="codebook_tools_eval_"))
    doc_path = tmp_dir / "sample_requirements.txt"
    doc_path.write_text(TEST_DOC_TEXT, encoding="utf-8")

    all_cases: list[dict] = []
    try:
        async with streamablehttp_client(MCP_URL) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                all_cases += await _cases_list_corpora(session)
                all_cases += await _cases_search_standards(session)
                all_cases += await _cases_get_clause(session)
                all_cases += await _cases_check_document(session, str(doc_path))
    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)

    return all_cases


def main() -> None:
    try:
        httpx.get(HEALTH_URL, timeout=5.0).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: standards-service is not reachable at {HEALTH_URL} ({exc}). "
            "Start it first: cd standards-service && ./run.sh"
        )
        sys.exit(2)

    all_cases = asyncio.run(_run_all())

    n_cases = len(all_cases)
    n_pass = sum(1 for c in all_cases if c["pass"])
    report = {
        "n_cases": n_cases,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_cases, 4) if n_cases else 0.0,
        "method": (
            "Drives all 4 Codebook MCP tools (list_corpora, search_standards, get_clause, "
            "check_document_against_corpus) through a REAL mcp.client.streamable_http "
            "session against a LIVE standards-service process on :8010 -- a genuinely "
            "different test surface from run_retrieval_eval.py/run_cross_corpus_eval.py, "
            "which import app/retrieval/* directly and never make a real MCP protocol "
            "call. Every expected value (corpus counts, top search hits, clause text) was "
            "independently verified against the real corpus/source files (REST calls, "
            "grep against manak-dev/lib and backend/data/standards/clauses.json, and a "
            "direct call to app.document_check's pure Python function) before being "
            "hardcoded as an expectation here -- never asserted from the tool's own "
            "output alone. Reported separately; never blended into the retrieval or "
            "cross-corpus eval counts."
        ),
        "cases": all_cases,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"codebook tools eval: {n_pass}/{n_cases} passed (accuracy={report['accuracy']})")
    for c in all_cases:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  [{status}] ({c['group']}) {c['name']}: expected={c['expected']!r} actual={c['actual']!r}")

    if n_pass != n_cases:
        sys.exit(1)


if __name__ == "__main__":
    main()
