"""Compatibility adapters; prose supplies no typed QuestionPlan contract."""
from __future__ import annotations

from docmancer.docs.domain.question_plan_core import PlannedFacet, QuestionPlan


def _component_subject(value: str) -> str:
    return ""


def semantic_components(q: str) -> QuestionPlan | None:
    return None


def _governance_facet_plan(value: str, *, scope: str) -> PlannedFacet:
    # This legacy non-optional signature cannot represent unknown semantics.
    # Reject direct use rather than manufacturing a governance facet.
    raise ValueError("untyped governance facet is unresolved")


def governance_facets(q: str) -> QuestionPlan | None:
    return None


def public_tool_usage(q: str) -> QuestionPlan | None:
    return None


def public_tools_with_purposes(q: str) -> QuestionPlan | None:
    return None


def python_version_support(q: str) -> QuestionPlan | None:
    return None


def mcp_request_handling(q: str) -> QuestionPlan | None:
    return None


def provider_request_timeout(q: str) -> QuestionPlan | None:
    return None


__all__ = [
    "governance_facets", "mcp_request_handling", "provider_request_timeout",
    "public_tool_usage", "public_tools_with_purposes", "python_version_support",
    "semantic_components",
]
