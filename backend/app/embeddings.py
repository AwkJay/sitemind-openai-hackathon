"""Shared sentence-transformer embedder for semantic retrieval (Pillar 2 Copilot).

Replaces TF-IDF term-overlap retrieval with real semantic similarity — a
paraphrased question (different words, same meaning) can now match a chunk it
shares no vocabulary with. Runs a small local model (all-MiniLM-L6-v2, CPU,
~90 MB on first download) via sentence-transformers; this is inference with a
pretrained model, not training, so it doesn't touch the project's "no ML
training anywhere" rule — same category as calling an LLM API. Fully offline
after the model is cached locally: no network call at query time, independent
of LLM_PROVIDER/OFFLINE_MODE.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized embeddings, so a plain dot product equals cosine similarity."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    return _model().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
