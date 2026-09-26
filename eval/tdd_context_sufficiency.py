"""TDD sidecar: assessed claims only; not a semantic judge or runtime policy."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any


def summarize_assessment(
    assessment: Mapping[str, Any],
    *,
    required_ids: Sequence[str],
    transport_ok: bool | None,
    citation_integrity: bool | None,
    budget_ok: bool | None,
) -> dict[str, Any]:
    """Acceptance summary for annotated answerable cases; implementation pending."""
    return {"verdict": "NOT_IMPLEMENTED"}
