"""Fail-closed predicates for coding-agent recovery handoffs.

Documentation recovery may allow repository investigation without claiming that
DocAtlas proved the documentary contract.  Edit readiness is granted only for a
complete, non-automatic handoff to the host coding agent's local source search.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def is_safe_local_source_handoff(value: Any) -> bool:
    """Return whether ``value`` is the complete local-source recovery contract."""

    if not isinstance(value, Mapping):
        return False
    return bool(
        value.get("tool") == "code_search"
        and value.get("type") == "search_local_source"
        and value.get("handled_by") == "coding_agent"
        and value.get("requires_confirmation") is False
        and value.get("repeat_docs_context") is False
        and value.get("auto_execute") is False
    )


def has_safe_local_source_handoff(values: Iterable[Any] | None) -> bool:
    """Return whether a bounded action collection contains one safe handoff."""

    return any(is_safe_local_source_handoff(value) for value in values or ())


__all__ = ["has_safe_local_source_handoff", "is_safe_local_source_handoff"]
