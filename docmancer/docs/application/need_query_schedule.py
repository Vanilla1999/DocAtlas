"""Bounded scheduling of explicit caller lookups only."""
from __future__ import annotations

from typing import Iterable

from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan
from docmancer.docs.domain.need_contracts import NeedContract

SEARCH_ORIGINS = frozenset({"host_lookup"})


def legacy_search_queries(plan: DocumentationQueryPlan, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationLookup, ...]:
    # Supplemental probes historically came from inferred requirements, not the
    # public lookup argument. They cannot become executable request queries.
    return tuple(row for row in plan.queries if row.origin == "host_lookup"
        and row.relation == "host_lookup" and row.public_parent_query_id is None)[:5]


def schedule_need_queries(plan: DocumentationQueryPlan, contracts: Iterable[NeedContract], *,
                         optional_limit: int = 12, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationLookup, ...]:
    if type(optional_limit) is not int or not 0 <= optional_limit <= 12:
        raise ValueError("optional_limit must be an integer between zero and twelve")
    return legacy_search_queries(plan)[:optional_limit]


def scheduled_plan(plan: DocumentationQueryPlan, *, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationQueryPlan, tuple[DocumentationLookup, ...]]:
    return plan, schedule_need_queries(plan, ())


def requirement_search_probes(requirements) -> tuple[str, ...]:
    return ()
