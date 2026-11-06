"""Explicit host-only activation for the complete-scope context candidate."""
from __future__ import annotations

import os
from pathlib import Path

EMERGENCY_TOKENS = 50000


def minimal_context_enabled() -> bool:
    """Validate candidate configuration without loading or downloading a model.

    Pinned asset hashes are verified by the scorer at execution. An absent policy
    is a supported diagnostic run (all sections retained), not a fallback filter.
    """
    value = os.environ.get("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", "0")
    if value not in {"0", "1"}:
        raise ValueError("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT must be 0 or 1")
    if value == "0":
        return False
    for name in ("DOCATLAS_EXPERIMENT_SELECTOR", "DOCATLAS_EXPERIMENT_SELECTOR_TOP_K"):
        if os.environ.get(name):
            raise ValueError(f"{name} conflicts with minimal context")
    compression = os.environ.get("DOCATLAS_CONTEXT_COMPRESSION")
    if compression not in (None, "off") or (
        compression is None and os.environ.get("DOCATLAS_MINILM_MODEL_DIR")
    ):
        raise ValueError("section compression conflicts with minimal context")
    for name in ("DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS", "DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS"):
        if name in os.environ and os.environ[name] != str(EMERGENCY_TOKENS):
            raise ValueError(f"{name} must be removed or set to {EMERGENCY_TOKENS} for minimal context")
    key = ("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH"
           if os.environ.get("DOCATLAS_MINIMAL_CONTEXT_RECIPE") == "qwen3-contextual-own-body-evidence-v1"
           else "DOCATLAS_EXPERIMENT_MINI_PATH")
    model = os.environ.get(key, "")
    if not model or not Path(model).is_absolute() or not Path(model).is_dir():
        raise ValueError(key + " must name an absolute prepared model directory")
    return True
