"""Pillar 2 — Project & RFI Copilot (cited RAG).

Retrieval is local sentence-transformer embeddings (all-MiniLM-L6-v2, CPU, fully
offline — no external embedding service, no API key) over project docs +
standards clauses. When a key is present Claude composes a cited answer
strictly from the retrieved chunks; offline we serve the deterministic fixture
answer that best matches the question (each fixture row already carries real
sources), falling back to embedding retrieval. The 'seen-before' RFI lookup
matches the question against resolved RFIs (or the fixture's own seen_before)
using the same embeddings — semantic match, not keyword overlap, so a
paraphrased duplicate RFI is now detectable.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config, llm, trace
from ..data_loader import fixture, load_rfi_log, load_submittals
from ..embeddings import embed
from ..schemas import RFIAnswer
from ..standards import all_clauses

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class AskRequest(BaseModel):
    question: str


# --------------------------------------------------------------------------- #
# Offline fixture matching (slug -> trigger keywords)
# --------------------------------------------------------------------------- #
_SLUG_KEYWORDS: dict[str, list[str]] = {
    "transformer-yard-footing-grade-cover": ["transformer", "footing", "cover", "grade", "f-12", "f12"],
    "open-rfis-marine-cooling-rcc": ["open rfi", "open", "marine", "cooling", "rcc"],
    "design-wind-speed-chennai": ["wind", "chennai", "cladding", "cyclon"],
    "m30-vs-m35-severe-exposure-seen-before": ["m30", "m35", "seen before", "resolved", "before", "precedent"],
    "which-submittals-non-conforming": ["non-conform", "nonconform", "which submittal", "violat", "conform"],
    "importance-factor-data-centre": ["importance factor", "i=1.5", "i = 1.5", "seismic", "1893", "lifeline"],
}


@lru_cache(maxsize=1)
def _fixture_answer_embeddings():
    """Embed each fixture's own answer text once, cached — used to confirm a
    keyword hit is actually on-topic, not just a shared word."""
    answers = fixture("copilot_answers.json") or {}
    slugs = list(answers.keys())
    if not slugs:
        return {}
    vecs = embed([answers[s]["answer"] for s in slugs])
    return dict(zip(slugs, vecs))


# A single generic shared word (e.g. "chennai", a city name) can score exactly 1
# against a fixture's keyword list even when the rest of the question is unrelated
# (e.g. "best pizza topping in Chennai?" was matching the wind-speed fixture on
# "chennai" alone). Calibration against real fixture answers showed a flat
# embedding-similarity floor isn't safe on its own: a genuinely on-topic but short,
# differently-worded question ("Should the seismic importance factor be 1.5?", 2
# keyword hits) can score BELOW a single-keyword off-topic collision, because
# similarity-to-a-long-answer-paragraph varies a lot by fixture. So: >=2 independent
# keyword hits is treated as strong enough evidence on its own (two unrelated words
# both landing by coincidence is unlikely); exactly 1 hit is weak and must be
# confirmed against the fixture's own answer text before being trusted.
_FIXTURE_MATCH_FLOOR = 0.40
_FIXTURE_STRONG_SCORE = 2


def _match_fixture(question: str) -> Optional[dict]:
    answers = fixture("copilot_answers.json") or {}
    if not answers:
        return None
    ql = question.lower()
    candidates = [
        (slug, sum(1 for k in kws if k in ql))
        for slug, kws in _SLUG_KEYWORDS.items()
        if slug in answers
    ]
    candidates = [(s, sc) for s, sc in candidates if sc > 0]
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[1])
    top_slug, top_score = candidates[0]

    if top_score >= _FIXTURE_STRONG_SCORE:
        return answers[top_slug]

    fixture_vecs = _fixture_answer_embeddings()
    if top_slug in fixture_vecs:
        sim = float(embed([question])[0] @ fixture_vecs[top_slug])
        if sim < _FIXTURE_MATCH_FLOOR:
            return None
    return answers[top_slug]


# --------------------------------------------------------------------------- #
# Retrieval corpus (clauses + submittals + RFIs)
# --------------------------------------------------------------------------- #
def _build_corpus() -> list[dict]:
    chunks: list[dict] = []
    for c in all_clauses():
        chunks.append(
            {
                "text": f"{c['standard']} Cl. {c['clause']} {c.get('title', '')}: {c['text']}",
                "source": {"label": f"{c['standard']} Cl. {c['clause']}", "detail": c["text"], "verify_url": c["verify_url"]},
            }
        )
    for s in load_submittals():
        chunks.append(
            {
                "text": f"{s.get('Submittal No')} {s.get('Title', '')} {s.get('Discipline', '')} status {s.get('Status', '')}",
                "source": {"label": f"Submittal {s.get('Submittal No')}", "detail": f"{s.get('Title', '')} ({s.get('Discipline', '')})"},
            }
        )
    for r in load_rfi_log():
        chunks.append(
            {
                "text": f"{r.get('RFI No')} {r.get('Subject', '')} {r.get('Question', '')} status {r.get('Status', '')}",
                "source": {"label": f"RFI {r.get('RFI No')} ({r.get('Status', '')})", "detail": r.get("Subject", "")},
            }
        )
    return chunks


@lru_cache(maxsize=1)
def _index():
    corpus = _build_corpus()
    matrix = embed([c["text"] for c in corpus])
    return corpus, matrix


# Below this cosine-similarity floor, retrieval is too weak to ground an answer.
# Embedding cosine scores are NOT comparable to the old TF-IDF scores (embeddings
# sit in a denser, more "everything is somewhat similar" space) — this value was
# re-tuned empirically, not reused from the TF-IDF floor of 0.12. A labeled set of
# 12 paraphrased on-topic vs off-topic/gibberish queries (eval/run_copilot_eval.py)
# showed on-topic top-similarity in [0.566, 0.872] and off-topic in [0.060, 0.227] —
# 0.40 sits at the midpoint of that gap, not right at either edge. Accuracy 1.0 on
# that n=12 set; see eval/copilot_report.json for the real run.
_RETRIEVAL_FLOOR = 0.40


def _retrieve(question: str, k: int = 4) -> list[dict]:
    """Dense-only retrieval — this is the go/no-go ABSTENTION GATE, eval-calibrated
    at _RETRIEVAL_FLOOR (see eval/run_copilot_eval.py). Kept exactly as before;
    hybrid fusion (_hybrid_retrieve, below) never touches this decision, only
    which chunks are SELECTED once a query has already cleared it."""
    corpus, matrix = _index()
    q = embed([question])[0]
    sims = matrix @ q
    order = sims.argsort()[::-1][:k]
    return [corpus[i] for i in order if sims[i] >= _RETRIEVAL_FLOOR]


# --------------------------------------------------------------------------- #
# Hybrid retrieval (BM25 keyword + dense embeddings, fused) — added 2026-07-03.
# Improves recall on exact-match queries (an RFI number, a clause code, a
# document ID) that pure semantic search can miss. The abstention GATE above
# stays dense-only and untouched; hybrid fusion only changes which chunks are
# SELECTED once a query already cleared that gate.
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _bm25_index():
    from rank_bm25 import BM25Okapi

    corpus, _ = _index()
    tokenized = [c["text"].lower().split() for c in corpus]
    return BM25Okapi(tokenized)


def _rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    """Pure Reciprocal Rank Fusion: each rank_list is a sequence of corpus
    indices in descending relevance order (best first). Returns fused indices,
    best first. Standard formula: score(i) = sum(1 / (k + rank + 1)). Held-out
    tested in eval/run_hybrid_retrieval_eval.py against synthetic rank lists —
    a pure arithmetic check, separate from retrieval-quality evals."""
    scores: dict[int, float] = {}
    for rank_list in rank_lists:
        for rank, idx in enumerate(rank_list):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda i: scores[i], reverse=True)


def _hybrid_retrieve(question: str, k: int = 4) -> list[dict]:
    gate = _retrieve(question, k=1)  # unchanged dense-only abstention floor
    if not gate:
        return []

    corpus, matrix = _index()
    q = embed([question])[0]
    dense_order = list((matrix @ q).argsort()[::-1])

    bm25_scores = _bm25_index().get_scores(question.lower().split())
    bm25_order = list(bm25_scores.argsort()[::-1])

    fused = _rrf_fuse([dense_order, bm25_order])
    return [corpus[i] for i in fused[:k]]


# --------------------------------------------------------------------------- #
# "Seen-before" RFI lookup (resolved RFIs only)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _rfi_index():
    rfis = [r for r in load_rfi_log() if (r.get("Status") or "").strip().lower() in ("closed", "answered")]
    if not rfis:
        return [], None
    texts = [f"{r.get('Subject', '')} {r.get('Question', '')}" for r in rfis]
    return rfis, embed(texts)


# Re-tuned for embedding cosine scores, same method as _RETRIEVAL_FLOOR. A labeled
# set of 6 paraphrased duplicates of resolved RFIs vs 3 genuinely novel questions
# (eval/run_copilot_eval.py) showed duplicate top-similarity in [0.464, 0.782] and
# novel-question top-similarity in [0.183, 0.249] — 0.35 sits at the midpoint of
# that gap. Accuracy 1.0 on that n=9 set; see eval/copilot_report.json.
_SEEN_BEFORE_FLOOR = 0.35


def _seen_before(question: str, threshold: float = _SEEN_BEFORE_FLOOR) -> Optional[dict]:
    rfis, matrix = _rfi_index()
    if not rfis:
        return None
    q = embed([question])[0]
    sims = matrix @ q
    i = int(sims.argmax())
    if sims[i] < threshold:
        return None
    r = rfis[i]
    return {
        "rfi_id": r.get("RFI No"),
        "summary": r.get("Subject", ""),
        "resolution": f"Previously {r.get('Status', '').lower()} — see ref: {r.get('Ref', 'project records')}.",
    }


# --------------------------------------------------------------------------- #
# Answer composition
# --------------------------------------------------------------------------- #
_ANSWER_SYSTEM = (
    "You are SiteMind, a construction project copilot. Answer ONLY from the "
    "provided sources. If they don't contain the answer, say so. Cite every claim "
    "with [n] mapping to the source list. Never invent clause numbers or doc IDs. "
    "Keep the answer to 3-6 sentences."
)


def _online_answer(question: str, chunks: list[dict]) -> str:
    src_block = "\n".join(
        f"[{i + 1}] {c['source']['label']}: {c['source']['detail']}" for i, c in enumerate(chunks)
    )
    # complete_text returns "" on any provider failure — fall back to retrieved text.
    txt = llm.complete_text(_ANSWER_SYSTEM, f"Question: {question}\n\nSources:\n{src_block}")
    return txt or _fallback_answer(chunks)


def _fallback_answer(chunks: list[dict]) -> str:
    if not chunks:
        return "The project corpus does not contain enough information to answer this question."
    cites = " ".join(f"[{i + 1}]" for i in range(len(chunks)))
    return f"Based on the retrieved sources {cites}: " + chunks[0]["source"]["detail"]


def answer(question: str) -> RFIAnswer:
    run = trace.start(
        "copilot.ask",
        {"question": question, "llm_provider": config.LLM_PROVIDER, "offline_mode": config.OFFLINE_MODE},
    )
    with run.step("seen_before_lookup"):
        seen = _seen_before(question)

    # Prefer the curated fixture for KNOWN questions in any mode — it's accurate and
    # reliable on stage. Live LLM (when configured) handles UNSEEN questions.
    with run.step("match_fixture"):
        fx = _match_fixture(question)
    if fx is not None:
        run.finish({"source": "fixture", "seen_before": bool(fx.get("seen_before") or seen)})
        return RFIAnswer(
            answer=fx["answer"],
            sources=fx.get("sources", []),
            seen_before=fx.get("seen_before") or seen,
        )

    with run.step("retrieve", floor=_RETRIEVAL_FLOOR, method="hybrid_bm25_dense_rrf"):
        chunks = _hybrid_retrieve(question)
    with run.step("compose_answer", chunks=len(chunks)):
        txt = _online_answer(question, chunks) if not config.OFFLINE_MODE else _fallback_answer(chunks)
    run.finish({"source": "retrieval", "chunks_used": len(chunks), "abstained": len(chunks) == 0})
    return RFIAnswer(answer=txt, sources=[c["source"] for c in chunks], seen_before=seen)


@router.post("/ask", response_model=RFIAnswer)
def ask(req: AskRequest) -> RFIAnswer:
    return answer(req.question)
