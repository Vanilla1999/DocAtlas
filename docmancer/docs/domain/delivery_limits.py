"""One host-only ceiling for selecting and rendering documentation context."""
from __future__ import annotations

import os


DEFAULT_DELIVERY_MAX_TOKENS = 12000


def delivery_token_ceiling() -> int:
    """Keep the normal limit; allow an explicit research-only host override.

    This is the offline codec/UTF-8 proxy budget for one tool response, not a
    model context-window or billing limit. It is never accepted from tool input.
    """
    name = "DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS"
    value = os.environ.get(name, str(DEFAULT_DELIVERY_MAX_TOKENS)).strip()
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)
