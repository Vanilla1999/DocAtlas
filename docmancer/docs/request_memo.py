"""Request-local reuse of deterministic computations.

One MCP context request repeats the same pure work many times: every packet
trial requalifies the same visible sources, and every issued continuation
re-reads the same project catalog. Inside ``request_memo_scope`` such a
function may keep its result for identical inputs until the request ends.

Nothing is shared between requests and no size bound or tuning number is
involved. Outside a scope ``request_memo`` returns ``None`` and callers compute
exactly as before.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_MEMO: ContextVar[dict[str, dict[Any, Any]] | None] = ContextVar("docatlas_request_memo", default=None)


@contextmanager
def request_memo_scope() -> Iterator[None]:
    """Open one request's memo; a nested scope starts empty and is discarded."""
    token = _MEMO.set({})
    try:
        yield
    finally:
        _MEMO.reset(token)


def request_memo(namespace: str) -> dict[Any, Any] | None:
    """The current request's table for ``namespace``; ``None`` outside a scope."""
    memo = _MEMO.get()
    return None if memo is None else memo.setdefault(namespace, {})
