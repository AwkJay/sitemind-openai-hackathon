"""Shared embedder for semantic retrieval (Pillar 2 Copilot).

Replaces TF-IDF term-overlap retrieval with real semantic similarity — a
paraphrased question (different words, same meaning) can now match a chunk it
shares no vocabulary with. Calls the same model (all-MiniLM-L6-v2) hosted on
the Hugging Face Inference API rather than loading it in-process: this is
inference with a pretrained model, not training, so it doesn't touch the
project's "no ML training anywhere" rule — same category as calling an LLM
API. Previously ran the model locally via sentence-transformers/torch, but
that pulls ~181 MB (torch) into the process and pushes memory past the 512 MB
free-tier ceiling on every host we tested (Render, InsForge/Fly) the moment
Copilot's first query loads it — confirmed by watching both crash and
auto-restart on that exact code path. The API call is a few hundred ms over
the network instead, with no local model weights and no torch dependency.
Requires HF_TOKEN (a free Hugging Face access token); the same model, same
output contract (L2-normalized, 384-dim) either way.
"""
from __future__ import annotations

import httpx
import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_HF_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_NAME}/pipeline/feature-extraction"


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized embeddings, so a plain dot product equals cosine similarity."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)

    from . import config

    if not config.HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN is not set — Copilot's semantic retrieval needs a free "
            "Hugging Face access token (https://huggingface.co/settings/tokens) "
            "to call the Inference API. Set it in backend/.env."
        )

    resp = httpx.post(
        _HF_URL,
        headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
        json={"inputs": list(texts)},
        timeout=30.0,
    )
    resp.raise_for_status()
    return np.array(resp.json(), dtype=np.float32)
