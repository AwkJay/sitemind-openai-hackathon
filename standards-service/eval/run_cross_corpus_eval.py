"""Held-out eval for Phase 3b's two read-only, filesystem-backed retrieval
corpora, relocated into Codebook/standards-service
(docs/BUILD_PLAN_CODEBOOK.md step 2):

  - `codebook_structural` (renamed from `manak_structural` — docs/codebook_changes.md
                            item 2, 2026-07-12) (17 real `.md` files under manak-dev/lib/)
  - `sitemind_existing_standards` (`clauses.json` + `commissioning_clauses.json`)

Byte-for-byte the same test logic as the original
`backend/eval/run_cross_corpus_eval.py` — only the sys.path bootstrap and
report path below changed to point at THIS service's own `app/retrieval/`
package, proving the relocated code reproduces the exact same real-corpus
ingestion counts and known-answer retrieval results. The original file is
untouched and still passes on its own (re-verified separately, see
docs/BUILD_PLAN_CODEBOOK.md's done-checks).

Independent of every other eval in this suite — never blended with the
existing 16, nor with Phase 3's own `run_retrieval_eval.py` (24 cases, tests
the generic chunker/RRF/company-upload path on inline synthetic fixtures).
This eval is the one that actually builds the two REAL corpora from disk and
proves retrieval quality against a handful of real, hand-verified
known-answer queries — each query's expected answer was located by directly
reading the real source file/JSON record BEFORE writing the assertion (see
comments at each case), never invented.

Five groups:
  (a) corpus_build_integrity  — both corpora build from real files with the
      expected document/chunk counts, correct `source`/`provenance_tag`.
  (b) known_answer_retrieval  — 2 queries per corpus, each with an expected
      document hit and an expected verbatim substring drawn from the real
      source file/record.
  (c) abstention              — a gibberish query against each corpus returns
      no results (the RETRIEVAL_FLOOR gate holds on real, much larger corpora
      too, not just the tiny synthetic ones in run_retrieval_eval.py).
  (d) verbatim_offset_integrity — for every chunk in both corpora,
      `raw_text == source_text[start_char:end_char]` where source_text is the
      REAL file content read directly from disk (manak's `.md` files,
      `clauses.json`/`commissioning_clauses.json`) — proves every citable
      chunk is a true byte-for-byte slice, never paraphrased.
  (e) manak_untouched          — building `codebook_structural` never wrote,
      moved, or deleted anything under manak-dev/ (mtimes of every file this
      eval reads are unchanged after the build).

NOTE: this eval genuinely builds `codebook_structural` from ~6,200 real chunks
using the local sentence-transformers model — on this machine that took
roughly 5 minutes end-to-end (CPU-only, no GPU). That cost is paid once per
eval run (and once per backend process, lazily, only when
RETRIEVAL_ENABLED=1) — it is not a per-query cost.

Run: `python -m eval.run_cross_corpus_eval` from `standards-service/` (venv
active). Writes `standards-service/eval/cross_corpus_report.json` in the
same `{n_cases, n_pass, accuracy, method, cases}` shape as the rest of the
suite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SERVICE_DIR = _THIS_DIR.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from app.retrieval.filesystem_corpora import (  # noqa: E402
    MANAK_CORPUS_NAME,
    MANAK_LIB_DIR,
    SITEMIND_CORPUS_NAME,
    SITEMIND_STANDARDS_DIR,
    SITEMIND_STANDARDS_FILES,
    _manak_md_files,
    build_manak_structural_corpus,
    build_sitemind_standards_corpus,
)

REPORT_PATH = _THIS_DIR / "cross_corpus_report.json"


def _file_stat_snapshot(paths: list[Path]) -> dict[str, tuple[float, int]]:
    """(mtime, size) per file — used to prove read-only access to manak-dev."""
    return {str(p): (p.stat().st_mtime, p.stat().st_size) for p in paths}


def main() -> None:
    # Snapshot manak-dev file stats BEFORE building the corpus, so group (e)
    # can prove the build touched nothing.
    manak_files = _manak_md_files()
    before = _file_stat_snapshot(manak_files)

    manak = build_manak_structural_corpus()
    sm = build_sitemind_standards_corpus()

    after = _file_stat_snapshot(_manak_md_files())

    all_cases: list[dict] = []

    # ------------------------------------------------------------------ #
    # (a) corpus_build_integrity
    # ------------------------------------------------------------------ #
    group_a = [
        {
            "name": "manak_document_count_matches_real_file_count",
            "expected": len(manak_files),
            "actual": len(manak.document_ids),
        },
        {
            "name": "manak_corpus_source_is_filesystem_readonly",
            "expected": "filesystem_readonly",
            "actual": manak.source,
        },
        {
            "name": "manak_corpus_provenance_tag",
            "expected": "codebook_verified",
            "actual": manak.provenance_tag,
        },
        {
            "name": "manak_corpus_nonempty",
            "expected": True,
            "actual": manak.chunk_count > 0,
        },
        {
            "name": "sitemind_document_count_matches_two_json_files",
            "expected": len(SITEMIND_STANDARDS_FILES),
            "actual": len(sm.document_ids),
        },
        {
            "name": "sitemind_corpus_source_is_filesystem_readonly",
            "expected": "filesystem_readonly",
            "actual": sm.source,
        },
        {
            "name": "sitemind_corpus_provenance_tag",
            "expected": "sitemind_indexed",
            "actual": sm.provenance_tag,
        },
    ]
    # clauses.json has 24 clause records, commissioning_clauses.json has 5 —
    # read directly from the real files, never hardcoded independent of them.
    clauses_path = SITEMIND_STANDARDS_DIR / "clauses.json"
    commissioning_path = SITEMIND_STANDARDS_DIR / "commissioning_clauses.json"
    expected_sm_chunk_count = len(
        json.loads(clauses_path.read_text(encoding="utf-8"))["clauses"]
    ) + len(json.loads(commissioning_path.read_text(encoding="utf-8"))["clauses"])
    group_a.append(
        {
            "name": "sitemind_chunk_count_equals_total_clause_records",
            "expected": expected_sm_chunk_count,
            "actual": sm.chunk_count,
        }
    )
    for c in group_a:
        c["group"] = "corpus_build_integrity"
        all_cases.append(c)

    # ------------------------------------------------------------------ #
    # (b) known_answer_retrieval — every expected answer below was found by
    # directly reading the real source file/JSON record first (see the grep/
    # read commands in the build session; not invented).
    # ------------------------------------------------------------------ #
    group_b: list[dict] = []

    # manak query 1: IS 456:2000, clause 26.4.2.2 — "26.4.2.2 For footings
    # minimum cover shall be 50 mm." (verified present verbatim at
    # manak-dev/lib/is456_2000/is.456.2000.md line 4099, inside the
    # "##### 26.4.2 Nominal Cover to Meet Durability Requirement" heading
    # span). This is the SAME real clause SiteMind's own clauses.json cites
    # as IS456_26.4.2.2 — an intentional cross-corpus consistency check.
    r1 = manak.query("What is the minimum nominal cover for footings under IS 456?", k=3)
    group_b.append(
        {
            "name": "manak_footing_cover_not_abstained",
            "expected": True,
            "actual": len(r1) > 0,
        }
    )
    group_b.append(
        {
            "name": "manak_footing_cover_hits_is456_document",
            "expected": True,
            "actual": any(r["document_id"] == "is456_2000" for r in r1),
        }
    )
    group_b.append(
        {
            "name": "manak_footing_cover_verbatim_text_present",
            "expected": True,
            "actual": any("For footings minimum cover shall be 50 mm" in r["raw_text"] for r in r1),
        }
    )

    # manak query 2: IS 1893 (Part 1):2016, clause 7.2.3 — Table 8 lists
    # "hospital buildings" at importance factor "1.5" (verified present
    # verbatim at manak-dev/lib/is1893_part1_2016/irc.gov.in.1893.2016.md,
    # inside the "#### 7.2.3 Importance Factor (I)" heading span).
    r2 = manak.query("What is the importance factor I for hospital buildings under IS 1893?", k=3)
    group_b.append(
        {
            "name": "manak_importance_factor_not_abstained",
            "expected": True,
            "actual": len(r2) > 0,
        }
    )
    group_b.append(
        {
            "name": "manak_importance_factor_hits_is1893_document",
            "expected": True,
            "actual": any(r["document_id"] == "is1893_part1_2016" for r in r2),
        }
    )
    group_b.append(
        {
            "name": "manak_importance_factor_verbatim_text_present",
            "expected": True,
            "actual": any(
                "hospital buildings" in r["raw_text"] and "1.5" in r["raw_text"] for r in r2
            ),
        }
    )

    # sitemind query 1: IS 3043:1987, clause 22.2.3 — "The continuity
    # resistance of the earth return path through the earth grid should be
    # maintained as low as possible and in no case greater than one ohm."
    # (verified present verbatim in clauses.json, key IS3043_1987_22.2.3).
    r3 = sm.query("What is the maximum earth grid continuity resistance under IS 3043?", k=3)
    group_b.append(
        {
            "name": "sitemind_earth_grid_resistance_not_abstained",
            "expected": True,
            "actual": len(r3) > 0,
        }
    )
    group_b.append(
        {
            "name": "sitemind_earth_grid_resistance_hits_clauses_document",
            "expected": True,
            "actual": any(r["document_id"] == "clauses" for r in r3),
        }
    )
    group_b.append(
        {
            "name": "sitemind_earth_grid_resistance_verbatim_text_present",
            "expected": True,
            "actual": any("greater than one ohm" in r["raw_text"] for r in r3),
        }
    )

    # sitemind query 2: ASHRAE TC9.9 (cross_source_unverified tier),
    # commissioning_clauses.json key ASHRAE_TC99_RECOMMENDED_TEMP — "Recommended
    # dry-bulb temperature range for IT equipment inlet air, all classes
    # A1-A4: 18.0-27.0 degC (64.4-80.6 degF)." (verified present verbatim).
    r4 = sm.query(
        "What is the ASHRAE recommended temperature range for data centre IT equipment inlet air?",
        k=3,
    )
    group_b.append(
        {
            "name": "sitemind_ashrae_temp_not_abstained",
            "expected": True,
            "actual": len(r4) > 0,
        }
    )
    group_b.append(
        {
            "name": "sitemind_ashrae_temp_hits_commissioning_document",
            "expected": True,
            "actual": any(r["document_id"] == "commissioning_clauses" for r in r4),
        }
    )
    group_b.append(
        {
            "name": "sitemind_ashrae_temp_verbatim_text_present",
            "expected": True,
            "actual": any("18.0-27.0 degC" in r["raw_text"] for r in r4),
        }
    )

    for c in group_b:
        c["group"] = "known_answer_retrieval"
        all_cases.append(c)

    # ------------------------------------------------------------------ #
    # (c) abstention
    # ------------------------------------------------------------------ #
    gibberish = "zzqx flibbertigibbet nonsense unrelated blorp banana spaceship"
    group_c = [
        {
            "name": "manak_gibberish_query_abstains",
            "expected": True,
            "actual": manak.query(gibberish, k=3) == [],
        },
        {
            "name": "sitemind_gibberish_query_abstains",
            "expected": True,
            "actual": sm.query(gibberish, k=3) == [],
        },
    ]
    for c in group_c:
        c["group"] = "abstention"
        all_cases.append(c)

    # ------------------------------------------------------------------ #
    # (d) verbatim_offset_integrity — every chunk in both real corpora
    # ------------------------------------------------------------------ #
    manak_texts: dict[str, str] = {}
    for p in manak_files:
        manak_texts[p.parent.name] = p.read_text(encoding="utf-8", errors="replace")

    manak_offsets_ok = True
    for c in manak.chunks:
        src = manak_texts.get(c["document_id"])
        if src is None or src[c["start_char"] : c["end_char"]] != c["raw_text"]:
            manak_offsets_ok = False
            break
    all_cases.append(
        {
            "name": "manak_all_chunks_verbatim_offset_integrity",
            "group": "verbatim_offset_integrity",
            "expected": True,
            "actual": manak_offsets_ok,
        }
    )

    sm_texts = {
        "clauses": clauses_path.read_text(encoding="utf-8"),
        "commissioning_clauses": commissioning_path.read_text(encoding="utf-8"),
    }
    sm_offsets_ok = True
    for c in sm.chunks:
        src = sm_texts.get(c["document_id"])
        if src is None or src[c["start_char"] : c["end_char"]] != c["raw_text"]:
            sm_offsets_ok = False
            break
    all_cases.append(
        {
            "name": "sitemind_all_chunks_verbatim_offset_integrity",
            "group": "verbatim_offset_integrity",
            "expected": True,
            "actual": sm_offsets_ok,
        }
    )

    # ------------------------------------------------------------------ #
    # (e) manak_untouched — building the corpus never wrote/moved/deleted
    # anything under manak-dev/.
    # ------------------------------------------------------------------ #
    all_cases.append(
        {
            "name": "manak_dev_files_unchanged_after_build",
            "group": "manak_untouched",
            "expected": before,
            "actual": after,
        }
    )
    all_cases.append(
        {
            "name": "manak_dev_file_count_unchanged_after_build",
            "group": "manak_untouched",
            "expected": len(before),
            "actual": len(after),
        }
    )

    for c in all_cases:
        c["pass"] = c["actual"] == c["expected"]

    n_cases = len(all_cases)
    n_pass = sum(1 for c in all_cases if c["pass"])
    report = {
        "n_cases": n_cases,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_cases, 4) if n_cases else 0.0,
        "method": (
            "Phase 3b — read-only cross-corpus search over manak-dev + "
            "existing SiteMind standards. Five independent groups: (a) both "
            "corpora build from the REAL files on disk with expected "
            "document/chunk counts and correct source/provenance tags, "
            "(b) 4 hand-verified known-answer queries (2 per corpus) hit the "
            "expected real document and cite verbatim text located by "
            "reading the source beforehand, (c) gibberish queries abstain "
            "against both real (not tiny synthetic) corpora, "
            "(d) EVERY chunk in both corpora satisfies "
            "raw_text == source_text[start_char:end_char] against the real "
            "file content read fresh from disk, (e) manak-dev/ file mtimes "
            "and file count are provably unchanged by building the corpus. "
            "Never blended with the existing 16 evals or with Phase 3's own "
            "run_retrieval_eval.py (24 cases, synthetic fixtures only)."
        ),
        "manak_chunk_count": manak.chunk_count,
        "manak_document_count": len(manak.document_ids),
        "sitemind_chunk_count": sm.chunk_count,
        "sitemind_document_count": len(sm.document_ids),
        "cases": [c for c in all_cases if c["name"] != "manak_dev_files_unchanged_after_build"]
        + [  # keep the raw per-file stat dict out of the printed per-case diff (too noisy) but keep pass/fail
            {
                **{k: v for k, v in c.items() if k not in ("expected", "actual")},
                "expected": "see manak_dev_file_count_unchanged_after_build for a compact check",
                "actual": "see manak_dev_file_count_unchanged_after_build for a compact check",
            }
            for c in all_cases
            if c["name"] == "manak_dev_files_unchanged_after_build"
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"cross-corpus eval: {n_pass}/{n_cases} passed (accuracy={report['accuracy']})")
    print(
        f"  codebook_structural: {manak.chunk_count} chunks / {len(manak.document_ids)} docs | "
        f"sitemind_existing_standards: {sm.chunk_count} chunks / {len(sm.document_ids)} docs"
    )
    for c in all_cases:
        status = "PASS" if c["pass"] else "FAIL"
        if c["name"] == "manak_dev_files_unchanged_after_build":
            print(f"  [{status}] ({c['group']}) {c['name']}: (per-file mtime/size dict, see report json)")
        else:
            print(f"  [{status}] ({c['group']}) {c['name']}: expected={c['expected']!r} actual={c['actual']!r}")

    if n_pass != n_cases:
        sys.exit(1)


if __name__ == "__main__":
    main()
