"""Bounded scheduling of explicit lookups and exact locators only."""
from __future__ import annotations

from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan


def scheduled_plan(plan: DocumentationQueryPlan, *, optional_limit: int = 12) -> tuple[DocumentationQueryPlan, tuple[DocumentationLookup, ...]]:
    """Root reads are separate; optional probes share the existing twelve slots.

    Public lookups keep their supplied text, including short Unicode queries.
    Scheduling neither interprets needs nor adds coverage/proof obligations.
    """
    if type(optional_limit) is not int or not 0 <= optional_limit <= 12:
        raise ValueError("optional_limit must be an integer between zero and twelve")
    selected = []
    seen = {plan.original_question.strip()}
    for row in plan.queries:
        if len(selected) >= optional_limit:
            break
        if row.origin not in {"host_lookup", "exact_path", "exact_anchor"} or row.text in seen:
            continue
        selected.append(row)
        seen.add(row.text)
    return plan, tuple(selected)
