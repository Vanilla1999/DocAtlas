"""Caller-owned read-output limits, independent of provenance and proof.

None is an actual absent limit, not a very large sentinel. The default context
has no override: existing production/legacy callers retain their old limits.
Only trusted application/research code can enter this context; source text and
public payload fields cannot select a policy. Resource/retrieval caps are separate.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True, slots=True)
class ReadDeliveryLimits:
    max_tokens: int | None = None
    max_sources: int | None = None
    max_snippet_chars: int | None = None
    # Kept finite for custom/legacy policies unless the trusted caller opts out.
    max_transport_bytes: int | None = 32_000

    def __post_init__(self) -> None:
        for name in ('max_tokens', 'max_sources', 'max_snippet_chars', 'max_transport_bytes'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f'{name} must be a positive integer or None')


COMPACT_READ_LIMITS = ReadDeliveryLimits(max_transport_bytes=None)
_ACTIVE: ContextVar[ReadDeliveryLimits | None] = ContextVar(
    'docatlas_read_delivery_limits', default=None,
)


def current_read_delivery_limits() -> ReadDeliveryLimits | None:
    return _ACTIVE.get()


@contextmanager
def use_read_delivery_limits(limits: ReadDeliveryLimits) -> Iterator[None]:
    if not isinstance(limits, ReadDeliveryLimits):
        raise TypeError('read limits must be a caller-owned ReadDeliveryLimits')
    token = _ACTIVE.set(limits)
    try:
        yield
    finally:
        _ACTIVE.reset(token)
