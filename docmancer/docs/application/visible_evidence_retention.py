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


def restore_visible_sources(
    previous: dict[str, Any], previous_snapshot: dict[str, Any],
    trial: dict[str, Any], trial_snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Overlay already-visible rows onto an additive retry with the same IDs.

    The retry may contribute new evidence IDs, but it cannot compact or rewrite
    evidence that was already model-visible in the primary packet.
    """
    from copy import deepcopy

    prior_rows = {
        str(row.get("evidence_id") or ""): row
        for row in previous.get("sources") or () if isinstance(row, dict)
    }
    restored = deepcopy(trial)
    restored_snapshot = deepcopy(trial_snapshot)
    restored["sources"] = [
        deepcopy(prior_rows.get(str(row.get("evidence_id") or ""), row))
        for row in trial.get("sources") or () if isinstance(row, dict)
    ]
    for evidence_id in prior_rows:
        if evidence_id in previous_snapshot and evidence_id in restored_snapshot:
            restored_snapshot[evidence_id] = deepcopy(previous_snapshot[evidence_id])
    return restored, restored_snapshot
