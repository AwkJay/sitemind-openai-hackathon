"""On-disk persistence for company-uploaded corpora (Phase 3; relocated into
Codebook/standards-service, docs/BUILD_PLAN_CODEBOOK.md step 2).

Stores each named corpus under `standards-service/data/company_corpus/
<corpus_name>/` — this service's OWN data folder (relocation note: the
original `backend/app/retrieval/store.py` pointed at
`backend/data/company_corpus/`; this copy intentionally resolves to a fresh
directory under the new service instead of reaching back into `backend/`,
since Codebook owns its own persisted state and never writes into
`backend/data/`). Deliberately separate from `backend/data/standards/`
(which this package never touches, per the hard constraints in
docs/BUILD_PLAN_CODEBOOK.md). Chunks are saved as JSON (utf-8, per
CLAUDE.md's mojibake-bug discipline); the dense embedding matrix is saved as
a `.npy` — so a restart doesn't lose ingested corpora.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .index import Corpus, register_corpus

# standards-service/app/retrieval/store.py -> standards-service/data/company_corpus
COMPANY_CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "company_corpus"


def _corpus_dir(name: str) -> Path:
    d = COMPANY_CORPUS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_corpus(corpus: Corpus) -> None:
    d = _corpus_dir(corpus.name)
    (d / "chunks.json").write_text(
        json.dumps(corpus.chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if corpus._matrix is not None and corpus._matrix.size:
        np.save(d / "embeddings.npy", corpus._matrix)


def load_all_corpora() -> None:
    """Restore every corpus persisted under COMPANY_CORPUS_DIR into the
    in-memory registry. Called lazily (once) from router.py — only reached
    when config.RETRIEVAL_ENABLED is true, so this never runs, and this
    module's disk scan never happens, with the flag off."""
    if not COMPANY_CORPUS_DIR.exists():
        return
    for sub in sorted(COMPANY_CORPUS_DIR.iterdir()):
        if not sub.is_dir():
            continue
        chunks_path = sub / "chunks.json"
        if not chunks_path.exists():
            continue
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        corpus = Corpus(name=sub.name)
        corpus.chunks = chunks
        emb_path = sub / "embeddings.npy"
        if emb_path.exists() and chunks:
            corpus._matrix = np.load(emb_path)
            from rank_bm25 import BM25Okapi

            tokenized = [c["text"].lower().split() for c in chunks]
            corpus._bm25 = BM25Okapi(tokenized)
        register_corpus(corpus)
