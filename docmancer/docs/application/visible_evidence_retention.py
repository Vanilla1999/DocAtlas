"""Shared predicates for preserving already-visible evidence across bounded retries."""

from __future__ import annotations

from typing import Any


def retains_visible_sources(previous: dict[str, Any], trial: dict[str, Any]) -> bool:
    """Return whether every visible source and snippet survives in ``trial``."""
    trial_by_id = {
        str(row.get("evidence_id") or ""): row
        for row in trial.get("sources") or ()
        if isinstance(row, dict)
    }
    for row in previous.get("sources") or ():
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        replacement = trial_by_id.get(evidence_id)
        if replacement is None:
            return False
        old_snippet = str(row.get("snippet") or "")
        new_snippet = str(replacement.get("snippet") or "")
        if old_snippet and old_snippet not in new_snippet:
            return False
    return True
