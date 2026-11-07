"""Explicit post-selection link expansion; never an alternate scorer."""
from __future__ import annotations

import os


ENVIRONMENT_KEY = "DOCATLAS_CONTEXT_LINKS"
OFF = "off"
ONE_HOP_V1 = "one-hop-v1"


def context_link_expansion() -> str:
    """Validate host configuration, including incompatible disabled paths.

    No assets are loaded here. The existing minimal-context/scorer checks still
    verify prepared model files and the pinned inference runtime at execution.
    """
    value = os.environ.get(ENVIRONMENT_KEY, OFF)
    if value not in {OFF, ONE_HOP_V1}:
        raise ValueError("invalid_DOCATLAS_CONTEXT_LINKS")
    if value == ONE_HOP_V1:
        if os.environ.get("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT") != "1":
            raise ValueError("one-hop-v1 requires DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1")
        if os.environ.get("DOCATLAS_MINIMAL_CONTEXT_RECIPE") != "qwen3-contextual-own-body-evidence-v1":
            raise ValueError("one-hop-v1 requires qwen3-contextual-own-body-evidence-v1")
    return value
