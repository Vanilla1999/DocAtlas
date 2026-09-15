"""Deterministic quality state for the final visible docs-context packet."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_ALLOWED_REASONS = {
    "coverage_unverified",
    "requested_part_missing",
    "budget_limited",
    "source_unavailable",
    "source_changed",
    "structure_unverified",
}


def context_quality(
    *,
    sources: Iterable[Mapping[str, Any]],
    component_coverage: Mapping[str, Any] | None = None,
    omissions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Classify only what the final packet can prove about its own coverage.

    Retrieval success is not completeness proof. ``checked`` therefore needs
    a non-empty recognized mandatory component contract whose witnesses all
    survived final projection, with no unresolved semantic residue.
    """
    sources = tuple(source for source in sources if isinstance(source, Mapping))
    if not sources:
        return {"status": "unavailable", "reasons": ["source_unavailable"]}

    coverage = component_coverage if isinstance(component_coverage, Mapping) else None
    if coverage is None:
        return {"status": "unverified", "reasons": ["coverage_unverified"]}

    mandatory = {
        str(value) for value in coverage.get("mandatory_component_ids") or () if value
    }
    covered = {
        str(value) for value in coverage.get("covered_component_ids") or () if value
    }
    missing = {
        str(value) for value in coverage.get("missing_component_ids") or () if value
    }
    unresolved = tuple(
        str(value) for value in coverage.get("unresolved_residue") or () if value
    )

    if missing:
        reasons = ["requested_part_missing"]
        if any(
            str(item.get("reason") or "") == "token_budget"
            and missing.intersection(str(value) for value in item.get("component_ids") or ())
            for item in omissions if isinstance(item, Mapping)
        ):
            reasons.append("budget_limited")
        return {"status": "partial", "reasons": reasons[:2]}

    if unresolved:
        return {"status": "unverified", "reasons": ["coverage_unverified"]}

    if mandatory and mandatory.issubset(covered) and str(coverage.get("status") or "") == "full":
        return {"status": "checked", "reasons": []}

    return {"status": "unverified", "reasons": ["coverage_unverified"]}


def normalize_context_quality(value: Any) -> dict[str, Any]:
    """Keep the public quality object small and deterministic during rewrites."""
    if not isinstance(value, Mapping):
        return {"status": "unverified", "reasons": ["coverage_unverified"]}
    status = str(value.get("status") or "unverified")
    if status not in {"checked", "partial", "unverified", "unavailable"}:
        status = "unverified"
    reasons: list[str] = []
    for reason in value.get("reasons") or ():
        reason = str(reason)
        if reason in _ALLOWED_REASONS and reason not in reasons:
            reasons.append(reason)
        if len(reasons) >= 2:
            break
    if status == "unverified" and not reasons:
        reasons.append("coverage_unverified")
    if status == "unavailable" and not reasons:
        reasons.append("source_unavailable")
    return {"status": status, "reasons": reasons}


__all__ = ["context_quality", "normalize_context_quality"]
