"""Implementation shard 4 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part02 import _code_group_fragments

def requirement_probe_query(requirement: EvidenceRequirement) -> str | None:
    """Return a bounded lexical witness query for one canonical requirement."""

    obligation = requirement.as_proof_obligation()
    if obligation is not None:
        parts = (
            obligation.subject,
            *obligation.subject_aliases,
            obligation.attribute,
            obligation.relation,
            obligation.target,
            obligation.expected_value,
            obligation.item_kind,
            obligation.context,
        )
        value = " ".join(dict.fromkeys(
            str(part).strip() for part in parts if str(part or "").strip()
        ))
        return value[:320] or None
    if requirement.kind in {"exact_term", "entity"}:
        return requirement.value.strip() or None
    if requirement.kind == "facet":
        kind, _, detail = requirement.value.partition(":")
        if kind == "comparison":
            left, separator, right = detail.partition(":")
            return f"{left} {right}" if separator else None
        if kind == "result_access":
            entity, separator, _ = detail.partition(":")
            return f"{entity} result" if separator else None
    if requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        return " ".join(fragments) if fragments else None
    return None

__all__=['requirement_probe_query']
