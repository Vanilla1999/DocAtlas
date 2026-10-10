"""Negative compatibility for legacy coverage; prose completeness is unknown."""
from __future__ import annotations

from typing import Iterable, Protocol


class _ObligationLike(Protocol):
    kind: str
    subject: str
    attribute: str | None
    relation: str | None
    target: str | None
    item_kind: str | None
    expected_value: str | None
    context: str | None


def legacy_coverage_gaps(
    question: str,
    obligations: Iterable[_ObligationLike],
) -> tuple[str, ...]:
    """No known-question exception or vocabulary can certify legacy coverage."""
    if not any(True for _ in obligations):
        return ("unsupported_query:legacy_no_contract",)
    return ("legacy_unresolved:semantic_coverage_unknown",)


__all__ = ["legacy_coverage_gaps"]
