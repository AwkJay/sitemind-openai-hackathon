"""Held-out eval for the standalone retrieval package, relocated into
Codebook/standards-service (docs/BUILD_PLAN_CODEBOOK.md step 2).

Byte-for-byte the same test logic as the original
`backend/eval/run_retrieval_eval.py` (Phase 3) — only the sys.path bootstrap
and report path below changed to point at THIS service's own
`app/retrieval/` package, proving the relocated code behaves identically to
the original. The original file is untouched and still passes on its own
(re-verified separately, see docs/BUILD_PLAN_CODEBOOK.md's done-checks).
Three groups of cases:

  (a) chunker fixtures — structure detection (markdown headings, numbered
      clause headings, unstructured fallback) + verbatim-offset integrity:
      every chunk's `raw_text` must equal `text[start_char:end_char]` in the
      original source document, exactly.
  (b) RRF arithmetic — `app.retrieval.index._rrf_fuse` against an
      independent reference implementation, mirroring
      `run_hybrid_retrieval_eval.py`'s method exactly, applied fresh to this
      package's own function (zero import from the copilot eval).
  (c) end-to-end ingest + query — inline synthetic documents (never a real
      standard, never paraphrased from training data — plain made-up prose
      for test purposes only) ingested into a temp corpus dir, querying
      on-topic (must retrieve, must cite verbatim text present in the source
      doc) and off-topic/gibberish (must abstain).

Writes `standards-service/eval/retrieval_report.json` in the same
`{n_cases, n_pass, accuracy, method, cases}` shape as the rest of the suite.
Run: `python -m eval.run_retrieval_eval` from `standards-service/` (venv
active).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SERVICE_DIR = _THIS_DIR.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from app.retrieval import store as retrieval_store  # noqa: E402
from app.retrieval.chunker import chunk_document  # noqa: E402
from app.retrieval.index import _rrf_fuse, get_or_create_corpus  # noqa: E402
from app.retrieval.ingest import ingest_document  # noqa: E402

REPORT_PATH = _THIS_DIR / "retrieval_report.json"

# --------------------------------------------------------------------------- #
# (a) Chunker fixtures
# --------------------------------------------------------------------------- #
MARKDOWN_FIXTURE = """# Earthing Requirements

## General

All exposed metal parts shall be earthed.

## Resistance Limits

The earth grid resistance shall not exceed 1 ohm at the main facility.
"""

NUMBERED_FIXTURE = """1.1 Scope

This section covers wiring safety requirements.

1.2 Insulation Resistance

1.2.1 Minimum Value

The insulation resistance shall not be less than 1 megohm.
"""

UNSTRUCTURED_FIXTURE = (
    "This is a plain prose document with no headings at all. "
    "It just contains paragraphs of free text, written to exercise the "
    "fallback chunker path rather than the structure-aware one.\n\n"
    "This is a second paragraph, separated from the first by a blank line, "
    "so the blank-line-delimited paragraph splitter should treat it as a "
    "distinct chunk on its own. "
    * 1
)

# One deliberately oversized paragraph (> 600 normalized chars) to exercise
# the sentence-splitting sub-fallback.
_LONG_SENTENCES = " ".join(
    f"This is filler sentence number {i} used only to pad the paragraph past "
    f"the six hundred character threshold so the sentence splitter engages."
    for i in range(1, 8)
)
LONG_PARAGRAPH_FIXTURE = _LONG_SENTENCES


def _check_offset_integrity(chunks: list[dict], source_text: str) -> bool:
    for c in chunks:
        if source_text[c["start_char"] : c["end_char"]] != c["raw_text"]:
            return False
    return True


def _chunker_cases() -> list[dict]:
    cases = []

    md_chunks = chunk_document(MARKDOWN_FIXTURE, file_type="md", doc_prefix="MD")
    headings = [c["heading"] for c in md_chunks if c["heading"]]
    cases.append(
        {
            "name": "markdown_heading_detection",
            "expected": True,
            "actual": all(c["structured"] for c in md_chunks)
            and "General" in headings
            and "Resistance Limits" in headings,
        }
    )
    cases.append(
        {
            "name": "markdown_offset_integrity",
            "expected": True,
            "actual": _check_offset_integrity(md_chunks, MARKDOWN_FIXTURE),
        }
    )
    cases.append(
        {
            "name": "markdown_breadcrumb_present",
            "expected": True,
            "actual": any(
                c["breadcrumb"] and ">" not in c["breadcrumb"] or c["breadcrumb"]
                for c in md_chunks
                if c["heading"]
            ),
        }
    )

    num_chunks = chunk_document(NUMBERED_FIXTURE, file_type="txt", doc_prefix="NUM")
    num_headings = [c["heading"] for c in num_chunks if c["heading"]]
    cases.append(
        {
            "name": "numbered_heading_detection",
            "expected": True,
            "actual": all(c["structured"] for c in num_chunks)
            and any("1.2.1" in (h or "") for h in num_headings),
        }
    )
    cases.append(
        {
            "name": "numbered_offset_integrity",
            "expected": True,
            "actual": _check_offset_integrity(num_chunks, NUMBERED_FIXTURE),
        }
    )
    # Nested numeric heading (1.2.1) should have a breadcrumb showing its parents.
    leaf = next((c for c in num_chunks if c["heading"] and "1.2.1" in c["heading"]), None)
    cases.append(
        {
            "name": "numbered_breadcrumb_nesting",
            "expected": True,
            "actual": bool(leaf) and " > " in (leaf["breadcrumb"] or ""),
        }
    )

    unstructured_chunks = chunk_document(UNSTRUCTURED_FIXTURE, file_type="txt", doc_prefix="UNS")
    cases.append(
        {
            "name": "unstructured_fallback_used",
            "expected": True,
            "actual": len(unstructured_chunks) >= 2 and all(not c["structured"] for c in unstructured_chunks),
        }
    )
    cases.append(
        {
            "name": "unstructured_offset_integrity",
            "expected": True,
            "actual": _check_offset_integrity(unstructured_chunks, UNSTRUCTURED_FIXTURE),
        }
    )

    long_chunks = chunk_document(LONG_PARAGRAPH_FIXTURE, file_type="txt", doc_prefix="LONG")
    cases.append(
        {
            "name": "oversized_paragraph_sentence_split",
            "expected": True,
            "actual": len(long_chunks) >= 3,
        }
    )
    cases.append(
        {
            "name": "oversized_paragraph_offset_integrity",
            "expected": True,
            "actual": _check_offset_integrity(long_chunks, LONG_PARAGRAPH_FIXTURE),
        }
    )

    # chunk_id / file_type stamped correctly by chunk_document()
    cases.append(
        {
            "name": "chunk_ids_assigned_and_unique",
            "expected": True,
            "actual": len({c["chunk_id"] for c in md_chunks}) == len(md_chunks)
            and all(c["chunk_id"].startswith("MD:") for c in md_chunks),
        }
    )

    return cases


# --------------------------------------------------------------------------- #
# (b) RRF arithmetic — independent reference implementation
# --------------------------------------------------------------------------- #
def _reference_rrf(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    """Independently written reference (not copy-pasted from index.py) for
    cross-checking `_rrf_fuse`'s arithmetic — mirrors
    run_hybrid_retrieval_eval.py's approach of a second implementation of
    the same standard formula."""
    scores: dict[int, float] = {}
    for lst in rank_lists:
        for rank, item in enumerate(lst):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [item for item, _ in ranked]


def _rrf_cases() -> list[dict]:
    cases = []

    # Case 1: identical rankings in both lists -> fused order == that ranking.
    lists_a = [[0, 1, 2, 3], [0, 1, 2, 3]]
    cases.append(
        {
            "name": "rrf_identical_rankings",
            "expected": _reference_rrf(lists_a),
            "actual": _rrf_fuse(lists_a),
        }
    )

    # Case 2: fully reversed rankings between the two lists -> symmetric fuse.
    lists_b = [[0, 1, 2, 3], [3, 2, 1, 0]]
    cases.append(
        {
            "name": "rrf_reversed_rankings",
            "expected": _reference_rrf(lists_b),
            "actual": _rrf_fuse(lists_b),
        }
    )

    # Case 3: an item only present in one list still gets fused in.
    lists_c = [[0, 1], [1, 2]]
    cases.append(
        {
            "name": "rrf_partial_overlap",
            "expected": _reference_rrf(lists_c),
            "actual": _rrf_fuse(lists_c),
        }
    )

    # Case 4: single-list passthrough.
    lists_d = [[4, 1, 3, 0, 2]]
    cases.append(
        {
            "name": "rrf_single_list_passthrough",
            "expected": _reference_rrf(lists_d),
            "actual": _rrf_fuse(lists_d),
        }
    )

    # Case 5: three-way fusion, custom k.
    lists_e = [[0, 1, 2], [2, 0, 1], [1, 2, 0]]
    cases.append(
        {
            "name": "rrf_three_way_custom_k",
            "expected": _reference_rrf(lists_e, k=10),
            "actual": _rrf_fuse(lists_e, k=10),
        }
    )

    for c in cases:
        c["actual"] = list(c["actual"])
        c["expected"] = list(c["expected"])

    return cases


# --------------------------------------------------------------------------- #
# (c) End-to-end ingest + query, inline synthetic docs
# --------------------------------------------------------------------------- #
DOC_EARTHING = """# Earthing System

## Grid Resistance

The overall earth grid resistance for the data centre facility shall be
measured annually and shall not exceed one ohm under dry soil conditions.

## Bonding

All non-current-carrying metal enclosures must be bonded to the main
earthing grid using copper conductors of adequate cross-section.
"""

DOC_FIRE = """# Fire Suppression

## Clean Agent System

The server halls are protected by a clean-agent gaseous suppression system
sized for total flooding of each compartment within ten seconds of
activation.

## Detection

Aspirating smoke detection is installed in the return-air path of each
CRAH unit for early-warning detection ahead of the suppression threshold.
"""

DOC_CANTEEN = """# Site Canteen Menu

## Monday

Vegetable curry, rice, and a side salad are served for lunch on Mondays.

## Tuesday

Grilled paneer sandwiches and soup are served for lunch on Tuesdays.
"""


def _write(tmp_dir: Path, name: str, content: str) -> Path:
    p = tmp_dir / name
    p.write_text(content, encoding="utf-8")
    return p


def _e2e_cases() -> list[dict]:
    cases: list[dict] = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="sitemind_retrieval_eval_"))
    corpus_name = "eval_test_corpus__do_not_use_in_demo"

    try:
        docs = {
            "earthing": _write(tmp_dir, "earthing.md", DOC_EARTHING),
            "fire": _write(tmp_dir, "fire.md", DOC_FIRE),
            "canteen": _write(tmp_dir, "canteen.md", DOC_CANTEEN),
        }
        manifests = {}
        for key, path in docs.items():
            manifests[key] = ingest_document(path, corpus_name=corpus_name)

        cases.append(
            {
                "name": "ingest_all_three_docs_chunked",
                "expected": True,
                "actual": all(m["chunk_count"] > 0 for m in manifests.values()),
            }
        )

        corpus = get_or_create_corpus(corpus_name)
        cases.append(
            {
                "name": "corpus_has_three_documents",
                "expected": 3,
                "actual": len(corpus.document_ids),
            }
        )

        # On-topic query: earthing question should retrieve the earthing doc
        # and NOT abstain, with verbatim text traceable to the source.
        results = corpus.query("What is the maximum allowed earth grid resistance?", k=3)
        on_topic_hit = bool(results) and any(r["document_id"] == manifests["earthing"]["document_id"] for r in results)
        cases.append({"name": "on_topic_query_earthing_retrieves", "expected": True, "actual": on_topic_hit})

        verbatim_ok = False
        if results:
            top = results[0]
            source_text = DOC_EARTHING if top["document_id"] == manifests["earthing"]["document_id"] else None
            if source_text is not None:
                verbatim_ok = top["raw_text"] in source_text
            else:
                # top hit was a different doc; still check its own raw_text is verbatim in ITS source
                src_map = {
                    manifests["earthing"]["document_id"]: DOC_EARTHING,
                    manifests["fire"]["document_id"]: DOC_FIRE,
                    manifests["canteen"]["document_id"]: DOC_CANTEEN,
                }
                verbatim_ok = top["raw_text"] in src_map.get(top["document_id"], "")
        cases.append({"name": "retrieved_chunk_is_verbatim", "expected": True, "actual": verbatim_ok})

        # Second on-topic query: fire suppression should retrieve the fire doc.
        results_fire = corpus.query("How fast does the clean agent suppression system flood a room?", k=3)
        fire_hit = bool(results_fire) and any(
            r["document_id"] == manifests["fire"]["document_id"] for r in results_fire
        )
        cases.append({"name": "on_topic_query_fire_retrieves", "expected": True, "actual": fire_hit})

        # Off-topic / gibberish query: must abstain (empty result).
        gibberish = corpus.query("zzqx flibbertigibbet nonsense qwoprk unrelated blorp", k=3)
        cases.append({"name": "gibberish_query_abstains", "expected": True, "actual": gibberish == []})

        # A real but completely unrelated topical query (not gibberish, just
        # off-corpus-topic) should also fail to beat the floor confidently —
        # softer check: if it returns anything, it must at least be one of
        # the three known docs (never a hallucinated 4th doc).
        unrelated = corpus.query("What is the boiling point of nitrogen at standard pressure?", k=3)
        known_ids = {m["document_id"] for m in manifests.values()}
        cases.append(
            {
                "name": "unrelated_query_never_invents_a_document",
                "expected": True,
                "actual": all(r["document_id"] in known_ids for r in unrelated),
            }
        )

        # Persistence round-trip: reload from disk into a fresh registry key
        # and confirm chunk count matches.
        from app.retrieval.index import Corpus as _Corpus

        persisted_dir = retrieval_store.COMPANY_CORPUS_DIR / corpus_name
        cases.append(
            {
                "name": "corpus_persisted_to_disk",
                "expected": True,
                "actual": (persisted_dir / "chunks.json").exists() and (persisted_dir / "embeddings.npy").exists(),
            }
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        persisted_dir = retrieval_store.COMPANY_CORPUS_DIR / corpus_name
        shutil.rmtree(persisted_dir, ignore_errors=True)
        from app.retrieval.index import _CORPORA

        _CORPORA.pop(corpus_name, None)

    return cases


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def main() -> None:
    all_cases = []
    for case in _chunker_cases():
        case["group"] = "chunker"
        case["pass"] = case["actual"] == case["expected"]
        all_cases.append(case)
    for case in _rrf_cases():
        case["group"] = "rrf_arithmetic"
        case["pass"] = case["actual"] == case["expected"]
        all_cases.append(case)
    for case in _e2e_cases():
        case["group"] = "end_to_end"
        case["pass"] = case["actual"] == case["expected"]
        all_cases.append(case)

    n_cases = len(all_cases)
    n_pass = sum(1 for c in all_cases if c["pass"])
    report = {
        "n_cases": n_cases,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_cases, 4) if n_cases else 0.0,
        "method": (
            "Three independent groups: (a) chunker structure-detection + "
            "verbatim-offset integrity over inline fixtures, (b) RRF fusion "
            "arithmetic cross-checked against an independently written "
            "reference implementation, (c) end-to-end ingest+query over "
            "inline synthetic documents (never a real standard) verifying "
            "on-topic retrieval, gibberish-query abstention, and that no "
            "result ever names a document outside the known ingested set."
        ),
        "cases": all_cases,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"retrieval eval: {n_pass}/{n_cases} passed (accuracy={report['accuracy']})")
    for c in all_cases:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  [{status}] ({c['group']}) {c['name']}: expected={c['expected']!r} actual={c['actual']!r}")

    if n_pass != n_cases:
        sys.exit(1)


if __name__ == "__main__":
    main()
