"""Pluggable dense-embedding backend for the retrieval package (Phase 3).

Independent of `app/embeddings.py` by design — zero import coupling to the
existing pillars (IMPROVEMENTS.md Phase 3, finding 3). Mirrors that module's
model choice (`all-MiniLM-L6-v2` via `sentence-transformers`, already a
pinned dependency in requirements.txt) as the offline default, and adds a
pluggable external-API provider mirroring `app/config.py`'s `LLM_PROVIDER`
pattern: set `RETRIEVAL_EMBEDDINGS_PROVIDER=openai` + `OPENAI_API_KEY` to
embed via OpenAI's `text-embedding-3-small` instead. Any failure (network,
auth, timeout, malformed response) is caught and falls back to the local
model automatically — never raises, matching the project's "OFFLINE_MODE
must keep working end-to-end" rule.

Calls the OpenAI REST endpoint directly via `urllib` (stdlib) rather than
adding the `openai` pip package as a new dependency — this package's guiding
constraint is "no new heavy dependency without checking requirements.txt
first", and a bare HTTP POST is enough for one embeddings call.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# backend/app/retrieval/embeddings_provider.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_DIR / ".env")

MODEL_NAME = "all-MiniLM-L6-v2"
LOCAL_EMBEDDING_DIM = 384

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

RETRIEVAL_EMBEDDINGS_PROVIDER: str = os.environ.get("RETRIEVAL_EMBEDDINGS_PROVIDER", "local").strip().lower()
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()


@lru_cache(maxsize=1)
def _local_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _embed_local(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, LOCAL_EMBEDDING_DIM), dtype=np.float32)
    return _local_model().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)


def _embed_openai(texts: list[str]) -> np.ndarray:
    body = json.dumps({"model": OPENAI_EMBEDDING_MODEL, "input": list(texts)}).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_EMBEDDINGS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https host
        payload = json.loads(resp.read().decode("utf-8"))
    vecs = np.array([d["embedding"] for d in payload["data"]], dtype=np.float32)
    return _l2_normalize(vecs)


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized embeddings — dot product == cosine similarity, same
    contract as `app/embeddings.embed()`. Uses the external API only when
    `RETRIEVAL_EMBEDDINGS_PROVIDER=openai` AND `OPENAI_API_KEY` is set; any
    failure falls back to the local model rather than raising, so a flaky
    connection or missing key never breaks ingestion or query."""
    if not texts:
        return np.zeros((0, LOCAL_EMBEDDING_DIM), dtype=np.float32)
    if RETRIEVAL_EMBEDDINGS_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            return _embed_openai(texts)
        except Exception as exc:  # pragma: no cover - network/env dependent
            logger.warning(
                "retrieval.embeddings_provider: OpenAI embeddings call failed (%s); "
                "falling back to local sentence-transformers model.",
                exc,
            )
    return _embed_local(texts)
