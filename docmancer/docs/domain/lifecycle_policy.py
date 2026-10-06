"""One lifecycle policy for project-document retrieval and projection."""
from __future__ import annotations

from typing import Any, Mapping

from docmancer.docs.domain.project_answer_contract import LifecycleIntent


ACTIVE_LIFECYCLE = frozenset({"active", "current"})
HISTORICAL_LIFECYCLE = frozenset({"completed", "superseded", "historical"})


def lifecycle_filters_for_intent(intent: LifecycleIntent) -> dict[str, Any]:
    if intent == "current":
        return {"lifecycle_status": {"in": sorted(ACTIVE_LIFECYCLE)}}
    if intent == "historical":
        return {"lifecycle_status": {"in": sorted(HISTORICAL_LIFECYCLE)}}
    return {}


def temporal_relevance_for_status(status: str | None) -> str:
    return "current" if str(status or "active").casefold() in ACTIVE_LIFECYCLE else "historical"


def lifecycle_allows(metadata: Mapping[str, Any], intent: LifecycleIntent) -> bool:
    status = str(
        metadata.get("project_doc_lifecycle_status")
        or metadata.get("lifecycle_status")
        or "active"
    ).casefold()
    if intent == "either":
        return True
    if intent == "historical":
        return status in HISTORICAL_LIFECYCLE
    return status in ACTIVE_LIFECYCLE


def lifecycle_intent(question: str) -> LifecycleIntent:
    # Historical/either access must arrive as an explicit lifecycle value.
    return "current"


__all__ = [
    "ACTIVE_LIFECYCLE", "HISTORICAL_LIFECYCLE", "lifecycle_allows",
    "lifecycle_filters_for_intent", "lifecycle_intent", "temporal_relevance_for_status",
]
