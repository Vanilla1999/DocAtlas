"""Real MPNet scorer for context rescue — uses frozen calibrated model.

Model: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
Threshold: 0.7453 (M2b frozen, zero FPR, recall=0.50 on calibration pool)
Scoring: cosine similarity between question and evidence text embeddings.

The scorer is stateless (no cache — BoundedScorer handles caching).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_CACHE_DIR = os.environ.get(
    "DOCATLAS_FASTEMBED_CACHE_DIR",
    "/tmp/fastembed_cache",
)

_model: "TextEmbedding | None" = None  # type: ignore[name-defined]


def _get_model():
    """Lazy-load the fastembed model (singleton)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=_MODEL_NAME, cache_dir=_CACHE_DIR)
    return _model


def _embed(text: str) -> np.ndarray:
    """Embed a single text, return normalised vector."""
    model = _get_model()
    vec = np.array(list(model.embed([text]))[0], dtype=np.float32)
    norm = np.linalg.norm(vec) + 1e-9
    return vec / norm


def mpnet_scorer(question: str, evidence_text: str) -> float:
    """Cosine similarity between question and evidence text.

    Returns float in [0, 1] (MPNet embeddings are non-negative cosine).
    """
    q_vec = _embed(question)
    e_vec = _embed(evidence_text)
    return float(np.dot(q_vec, e_vec))


def model_identity() -> dict[str, str]:
    """Return model identity for traceability."""
    return {
        "model_name": _MODEL_NAME,
        "model_revision": "Xenova/paraphrase-multilingual-mpnet-base-v2",
        "cache_dir": _CACHE_DIR,
        "calibration_digest": "m2b-calibration-v1",
    }
