"""In-memory hybrid (BM25 + dense) retrieval index for one named corpus —
the standalone retrieval package (Phase 3).

Independently re-implements the RRF-fusion pattern already proven in
`app/agents/copilot.py` (`_rrf_fuse`) — same standard formula, written fresh
here so this package has zero import coupling to the existing Copilot
pillar (IMPROVEMENTS.md Phase 3, finding 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi

from .embeddings_provider import embed

# Below this floor (the DENSE cosine similarity of the single best candidate),
# retrieval is judged too weak to ground an answer and the query abstains
# rather than returning the nearest-but-irrelevant chunk. This is a FRESH,
# independently-calibrated constant — NOT a reuse of copilot.py's
# _RETRIEVAL_FLOOR=0.40. It is applied to the raw dense cosine similarity of
# the top hit (the abstention GATE), the same two-stage pattern as
# copilot.py's `_retrieve` (dense-only gate) + `_hybrid_retrieve` (RRF-fused
# selection once the gate has cleared) — but tuned on THIS package's own tiny
# synthetic eval corpus rather than the project docs corpus, because the two
# corpora have very different size/vocabulary and a shared constant would be
# a coincidence, not a calibration. See eval/run_retrieval_eval.py's
# end-to-end cases: on-topic queries against the seeded 3-document eval
# corpus scored top-hit cosine similarity in roughly [0.45, 0.75]; a
# deliberately gibberish query scored well under 0.15. 0.30 sits
# comfortably inside that gap, closer to the off-topic side (conservative:
# prefer a false abstention over a hallucination-adjacent weak match).
RETRIEVAL_FLOOR = 0.30


def _rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    """Pure Reciprocal Rank Fusion, written independently of
    `app/agents/copilot.py`'s `_rrf_fuse` (same standard formula:
    score(i) = sum(1 / (k + rank + 1)), fused list returned best-first).
    Held-out tested in eval/run_retrieval_eval.py against an independent
    reference implementation — mirrors eval/run_hybrid_retrieval_eval.py's
    method exactly, applied to this package's own function."""
    scores: dict[int, float] = {}
    for rank_list in rank_lists:
        for rank, idx in enumerate(rank_list):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda i: scores[i], reverse=True)


@dataclass
class Corpus:
    """One named collection of ingested documents: chunk list + BM25 index +
    dense embedding matrix. `chunks` is the source of truth; the two indices
    are rebuilt from it on every `build`/`add` call (cheap at this corpus
    size — the same "brute-force over an in-memory matrix" choice made for
    `agents/copilot.py`, see IMPROVEMENTS.md Phase 3's architecture
    rationale against a hosted vector DB).

    `source` (Phase 3b): "company_upload" (default, Phase 3) — a corpus built
    from documents POSTed to /api/retrieval/upload, persisted to disk under
    `backend/data/company_corpus/` — or "filesystem_readonly" — a corpus
    built by reading real files already on disk (manak-dev's `.md` corpus,
    SiteMind's own `clauses.json`/`commissioning_clauses.json`) and NEVER
    written back to disk by this package. See `filesystem_corpora.py`."""

    name: str
    chunks: list[dict] = field(default_factory=list)
    source: str = "company_upload"
    _matrix: Optional[np.ndarray] = field(default=None, repr=False)
    _bm25: Optional[BM25Okapi] = field(default=None, repr=False)

    def build(self, chunks: list[dict]) -> None:
        """Replace the corpus's entire chunk set and rebuild both indices."""
        self.chunks = list(chunks)
        self._rebuild_indices()

    def add(self, chunks: list[dict]) -> None:
        """Append new chunks (e.g. from a newly-uploaded document) and
        rebuild both indices over the combined set."""
        self.chunks.extend(chunks)
        self._rebuild_indices()

    def _rebuild_indices(self) -> None:
        if not self.chunks:
            self._matrix = np.zeros((0, 384), dtype=np.float32)
            self._bm25 = None
            return
        self._matrix = embed([c["text"] for c in self.chunks])
        tokenized = [c["text"].lower().split() for c in self.chunks]
        self._bm25 = BM25Okapi(tokenized)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def document_ids(self) -> set[str]:
        return {c["document_id"] for c in self.chunks}

    @property
    def provenance_tag(self) -> Optional[str]:
        """The single SourceType shared by every chunk in this corpus, or
        "mixed" if more than one is present (not expected for the corpora
        this package currently builds, but guarded rather than assumed),
        or None if the corpus is empty."""
        tags = {c.get("provenance_tag", "company_uploaded") for c in self.chunks}
        if not tags:
            return None
        if len(tags) > 1:
            return "mixed"
        return next(iter(tags))

    def query(self, text: str, k: int = 4) -> list[dict]:
        """Hybrid RRF-fused top-k, gated by RETRIEVAL_FLOOR on the dense
        cosine similarity of the single best candidate (the abstention
        gate — mirrors copilot.py's dense-gate-then-hybrid-select shape).
        Returns [] when the corpus is empty or the query is judged too weak
        to ground an answer. Each returned dict carries a 'score' key (the
        chunk's own dense cosine similarity to the query, for display)."""
        if not self.chunks or self._bm25 is None:
            return []
        q = embed([text])[0]
        dense_sims = self._matrix @ q
        dense_order = list(dense_sims.argsort()[::-1])
        if dense_sims[dense_order[0]] < RETRIEVAL_FLOOR:
            return []  # abstain — even the single best dense match is too weak

        bm25_scores = self._bm25.get_scores(text.lower().split())
        bm25_order = list(np.argsort(bm25_scores)[::-1])

        fused = _rrf_fuse([dense_order, bm25_order])
        results = []
        for i in fused[:k]:
            chunk = dict(self.chunks[i])
            chunk["score"] = float(dense_sims[i])
            results.append(chunk)
        return results


_CORPORA: dict[str, Corpus] = {}


def get_or_create_corpus(name: str, source: str = "company_upload") -> Corpus:
    if name not in _CORPORA:
        _CORPORA[name] = Corpus(name=name, source=source)
    return _CORPORA[name]


def get_corpus(name: str) -> Optional[Corpus]:
    return _CORPORA.get(name)


def list_corpora() -> list[Corpus]:
    return list(_CORPORA.values())


def register_corpus(corpus: Corpus) -> None:
    """Used by store.py to restore a persisted corpus into the in-memory
    registry at startup (only reached when config.RETRIEVAL_ENABLED)."""
    _CORPORA[corpus.name] = corpus
