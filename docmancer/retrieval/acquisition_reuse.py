"""Request-scoped reuse of an identical candidate acquisition.

``get_docs_context`` reads the original question twice: in the requested scope
and again with ``authority=source_of_truth``. When the extra filter keeps every
window of that scope, both reads see the same rows, so the second search can
only repeat the first pool. Within one request the store then returns a copy of
the first pool instead of searching again.

Nothing is reused across requests. A pool is reused only for the same store,
active generation, query text and expansion, and only when the later filters
equal the earlier ones or extend them with keys that remove no window (equal
window counts under AND-only filters). No threshold or tuning is involved.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_ENTRIES: ContextVar[list[Any] | None] = ContextVar("docatlas_acquisition_reuse", default=None)


@contextmanager
def acquisition_reuse_scope(entries: list[Any]) -> Iterator[None]:
    """Let acquisitions inside this block share ``entries`` (one request)."""
    token = _ENTRIES.set(entries)
    try:
        yield
    finally:
        _ENTRIES.reset(token)


def active_acquisition_entries() -> list[Any] | None:
    return _ENTRIES.get()


def effective_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Filters as SQL applies them: ``None`` values impose no condition."""
    return {key: value for key, value in (filters or {}).items() if value is not None}


def extends_filters(base: dict[str, Any], extended: dict[str, Any]) -> bool:
    """Whether ``extended`` keeps every condition of ``base`` unchanged."""
    return all(key in extended and extended[key] == value for key, value in base.items())
