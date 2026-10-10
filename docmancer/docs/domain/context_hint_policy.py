"""Conservative compatibility hooks for removed generated retrieval hints."""
from __future__ import annotations

from typing import Any


def fallback_context_query_ids(plan: dict[str, Any], retrieval: dict[str, Any],
                               eligible_ids: set[str]) -> set[str]:
    # Generated hints cannot rescue failed public-question qualification.
    return set()


def has_context_hint_support(source: dict[str, Any], *, question: str = '') -> bool:
    return False


def preserves_unresolved_context_candidate(source: dict[str, Any], *,
        query_plan: dict[str, Any], expected_project_identity: str,
        lifecycle_intent: str = 'current') -> bool:
    return False
