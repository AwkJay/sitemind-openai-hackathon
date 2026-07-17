"""SiteMind COPILOT RETRIEVAL evaluation — a FIFTH separate metric, never blended
with the other four (rule-decision, extraction, supply-chain logic, schedule logic).

What this measures and why it's scoped the way it is:
  * Pillar 2's retrieval moved from TF-IDF term-overlap to local sentence-transformer
    embeddings (all-MiniLM-L6-v2). Embedding cosine scores are NOT comparable to TF-IDF
    cosine scores (embeddings live in a denser space where even unrelated text scores
    higher), so the old 0.12 / 0.18 floors could not be reused blindly — they had to be
    re-tuned against a labeled set of on-topic vs off-topic queries, which is what this
    file does and reports.
  * Two things are checked:
    (1) RETRIEVAL FLOOR — a labeled set of on-topic (deliberately PARAPHRASED, not
        keyword-matching the corpus) vs off-topic/gibberish queries. A good floor lets
        every on-topic query retrieve something and every off-topic query abstain.
    (2) SEEN-BEFORE FLOOR — a labeled set of PARAPHRASED duplicates of real resolved
        RFIs (semantic match, not keyword overlap — the point of moving off TF-IDF) vs
        genuinely novel questions that should NOT match any resolved RFI.
  * For each, a small threshold sweep reports accuracy at each candidate value and the
    chosen floor with its accuracy — a real number from a real run, not asserted.
  * This is a correctness/calibration check on retrieval behaviour against a small
    hand-labeled set (n=12 retrieval cases, n=9 seen-before cases) — explicitly NOT a
    claim of broad retrieval quality across arbitrary project questions. State that
    caveat if this number is ever cited in a demo.

Run:  python -m eval.run_copilot_eval   (from backend/, venv active)
      -> writes eval/copilot_report.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from app.agents.copilot import _build_corpus  # noqa: E402
from app.data_loader import load_rfi_log  # noqa: E402
from app.embeddings import embed  # noqa: E402

# --------------------------------------------------------------------------- #
# (1) Retrieval floor — on-topic (paraphrased) vs off-topic/gibberish
# --------------------------------------------------------------------------- #
RETRIEVAL_CASES = [
    # on-topic: paraphrased, NOT keyword-matching the corpus text verbatim
    ("What grade of concrete should be used for reinforced sections built near the sea?", True),
    ("How much concrete cover do foundations need in a corrosive coastal environment?", True),
    ("Should the seismic importance factor be higher for a critical, always-on facility?", True),
    ("What's the maximum water-to-cement ratio allowed for concrete in harsh marine exposure?", True),
    ("Is the design wind speed tied to the local basic wind speed for the city?", True),
    ("What's the allowed steel percentage in a column's longitudinal reinforcement?", True),
    # off-topic / gibberish — must abstain
    ("What's the best pizza topping in Chennai?", False),
    ("asdkjaslkdj random gibberish gjkgh 12345", False),
    ("How do I reset my email password?", False),
    ("What's the weather like on Mars today?", False),
    ("Recommend a good movie to watch tonight.", False),
    ("Who won the last World Cup final?", False),
]

# --------------------------------------------------------------------------- #
# (2) Seen-before floor — paraphrased duplicates of resolved RFIs vs novel questions
# --------------------------------------------------------------------------- #
SEEN_BEFORE_CASES = [
    # (question, expected_matching_rfi_id_or_None)
    (
        "Has anyone already asked whether we should bump the raft concrete grade up "
        "for better resistance to chloride attack near the coast?",
        "RFI-CIV-061",
    ),
    (
        "Was a question already raised about verifying the allowable soil bearing "
        "pressure at foundation level against the geotech report?",
        "RFI-CIV-055",
    ),
    (
        "Did someone already ask about the height of the raised access floor in the "
        "white space?",
        "RFI-ARC-031",
    ),
    (
        "Has the chilled-water supply temperature for the cooling units already been "
        "confirmed somewhere in this project?",
        "RFI-MEP-090",
    ),
    (
        "Is there already an answer on whether the roof fasteners can handle "
        "cyclone-strength wind uplift?",
        "RFI-ARC-035",
    ),
    (
        "Was the pour sequencing / construction joint location for the big raft slab "
        "already resolved?",
        "RFI-CIV-066",
    ),
    # genuinely novel — must NOT confidently match any resolved RFI
    ("What's the procedure for commissioning the fire suppression system?", None),
    ("Has anyone asked about the elevator maintenance contract terms?", None),
    ("What's the warranty period on the roofing membrane?", None),
]


def _sweep(sims_labels: list[tuple[float, bool]], candidates: list[float]) -> tuple[float, float, list[dict]]:
    """Try each candidate threshold, return (best_threshold, best_accuracy, table)."""
    table = []
    best_t, best_acc = candidates[0], -1.0
    for t in candidates:
        correct = sum(1 for sim, expect in sims_labels if (sim >= t) == expect)
        acc = correct / len(sims_labels)
        table.append({"threshold": t, "accuracy": round(acc, 3)})
        if acc > best_acc:
            best_t, best_acc = t, acc
    return best_t, best_acc, table


def _eval_retrieval_floor() -> dict:
    corpus = _build_corpus()
    corpus_matrix = embed([c["text"] for c in corpus])
    queries = [q for q, _ in RETRIEVAL_CASES]
    q_matrix = embed(queries)
    sims_labels = []
    got = []
    for i, (q, expect_hit) in enumerate(RETRIEVAL_CASES):
        top_sim = float((corpus_matrix @ q_matrix[i]).max())
        sims_labels.append((top_sim, expect_hit))
        got.append({"question": q, "expect_hit": expect_hit, "top_similarity": round(top_sim, 4)})
    candidates = [round(0.05 * i, 2) for i in range(2, 16)]  # 0.10 .. 0.75
    best_t, best_acc, table = _sweep(sims_labels, candidates)
    return {
        "n": len(RETRIEVAL_CASES),
        "chosen_floor": best_t,
        "accuracy_at_chosen_floor": best_acc,
        "sweep": table,
        "cases": got,
    }


def _eval_seen_before_floor() -> dict:
    rfis = [r for r in load_rfi_log() if (r.get("Status") or "").strip().lower() in ("closed", "answered")]
    texts = [f"{r.get('Subject', '')} {r.get('Question', '')}" for r in rfis]
    rfi_matrix = embed(texts)
    ids = [r.get("RFI No") for r in rfis]

    queries = [q for q, _ in SEEN_BEFORE_CASES]
    q_matrix = embed(queries)

    sims_labels = []
    got = []
    for i, (q, expect_id) in enumerate(SEEN_BEFORE_CASES):
        sims = rfi_matrix @ q_matrix[i]
        best_i = int(sims.argmax())
        top_sim = float(sims[best_i])
        matched_id = ids[best_i]
        # "correct at threshold t" means: if expect_id is set, top match is that RFI
        # AND top_sim >= t; if expect_id is None, top_sim < t (correctly abstains).
        sims_labels.append((top_sim, expect_id is not None and matched_id == expect_id))
        got.append(
            {
                "question": q,
                "expect_id": expect_id,
                "top_match_id": matched_id,
                "top_match_is_expected": matched_id == expect_id if expect_id else None,
                "top_similarity": round(top_sim, 4),
            }
        )
    candidates = [round(0.05 * i, 2) for i in range(4, 18)]  # 0.20 .. 0.85
    best_t, best_acc, table = _sweep(sims_labels, candidates)
    return {
        "n": len(SEEN_BEFORE_CASES),
        "chosen_floor": best_t,
        "accuracy_at_chosen_floor": best_acc,
        "sweep": table,
        "cases": got,
    }


# The final values actually hardcoded in app/agents/copilot.py. The sweep above
# finds the widest accuracy-1.0 plateau; these are the midpoint of that plateau's
# underlying similarity gap (more margin than the sweep's first-passing edge) —
# see the comments beside _RETRIEVAL_FLOOR / _SEEN_BEFORE_FLOOR in copilot.py.
DEPLOYED_RETRIEVAL_FLOOR = 0.40
DEPLOYED_SEEN_BEFORE_FLOOR = 0.35


def main() -> None:
    t0 = time.time()
    retrieval = _eval_retrieval_floor()
    seen_before = _eval_seen_before_floor()

    # Benchmark embedding latency on the real corpus for the demo-readiness check.
    corpus = _build_corpus()
    bench_t0 = time.time()
    embed([c["text"] for c in corpus])
    corpus_embed_ms = round((time.time() - bench_t0) * 1000, 1)
    q_t0 = time.time()
    embed(["a single sample query for latency measurement"])
    single_query_ms = round((time.time() - q_t0) * 1000, 1)

    retrieval_deployed_acc = sum(
        1 for c in retrieval["cases"] if (c["top_similarity"] >= DEPLOYED_RETRIEVAL_FLOOR) == c["expect_hit"]
    ) / len(retrieval["cases"])
    seen_before_deployed_acc = sum(
        1
        for c in seen_before["cases"]
        if (c["top_similarity"] >= DEPLOYED_SEEN_BEFORE_FLOOR) == (c["expect_id"] is not None and c["top_match_is_expected"])
    ) / len(seen_before["cases"])

    report = {
        "retrieval_floor": retrieval,
        "seen_before_floor": seen_before,
        "deployed_floors": {
            "retrieval_floor": DEPLOYED_RETRIEVAL_FLOOR,
            "retrieval_floor_accuracy": round(retrieval_deployed_acc, 3),
            "seen_before_floor": DEPLOYED_SEEN_BEFORE_FLOOR,
            "seen_before_floor_accuracy": round(seen_before_deployed_acc, 3),
            "note": "The sweep's chosen_floor is the first threshold hitting max accuracy "
            "(narrowest margin). The deployed floors above are the midpoint of the full "
            "accuracy-1.0 plateau's underlying similarity gap — more robust to a slightly "
            "different question, same accuracy on this labeled set.",
        },
        "benchmark": {
            "corpus_size": len(corpus),
            "corpus_embed_ms": corpus_embed_ms,
            "single_query_embed_ms": single_query_ms,
            "note": "corpus_embed_ms is a one-time cost (cached via lru_cache in _index()); "
            "single_query_embed_ms is the per-question cost paid on every /copilot/ask call.",
        },
        "total_runtime_s": round(time.time() - t0, 2),
    }
    out = Path(__file__).parent / "copilot_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"Retrieval floor (sweep-optimal): {retrieval['chosen_floor']} | deployed: {DEPLOYED_RETRIEVAL_FLOOR} (accuracy {retrieval_deployed_acc} on n={retrieval['n']})")
    print(f"Seen-before floor (sweep-optimal): {seen_before['chosen_floor']} | deployed: {DEPLOYED_SEEN_BEFORE_FLOOR} (accuracy {seen_before_deployed_acc} on n={seen_before['n']})")
    print(f"Corpus embed (one-time, {len(corpus)} chunks): {corpus_embed_ms} ms")
    print(f"Single query embed: {single_query_ms} ms")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
