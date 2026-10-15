"""Explicit retrieval requests; no generated queries or parent attribution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from docmancer.docs.domain.query_terms import documentation_technical_anchors

QueryRelation = Literal["direct", "audited_rewrite", "host_lookup", "exact_anchor"]


@dataclass(frozen=True, slots=True)
class DocumentationLookup:
    query_id: str
    text: str
    origin: str
    coverage_required: bool = True
    facet_id: str | None = None
    requirement_id: str | None = None
    relation: QueryRelation = "direct"
    public_parent_query_id: str | None = None
    preferred_catalog_roles: tuple[str, ...] = ()
    forbidden_catalog_roles: tuple[str, ...] = ()
    forbidden_evidence_terms: tuple[str, ...] = ()
    parent_exact_terms: tuple[str, ...] = ()
    component_rewrite_audit: tuple[str, int, int, str] | None = None
    need_subject: str | None = None
    need_relation: str | None = None
    need_context: str | None = None

    def __post_init__(self) -> None:
        if self.relation not in {"direct", "audited_rewrite", "host_lookup", "exact_anchor"}:
            raise ValueError(f"unsupported documentation query relation: {self.relation}")
        if self.relation == "audited_rewrite" and not self.public_parent_query_id:
            raise ValueError("audited rewrites require a public parent query")
        if self.relation in {"direct", "host_lookup"} and self.public_parent_query_id:
            raise ValueError(f"{self.relation} queries cannot derive parent coverage")
        for field in ("preferred_catalog_roles", "forbidden_catalog_roles",
                      "forbidden_evidence_terms", "parent_exact_terms"):
            object.__setattr__(self, field, tuple(getattr(self, field)))


@dataclass(frozen=True, slots=True)
class DocumentationQueryPlan:
    original_question: str
    queries: tuple[DocumentationLookup, ...]
    explicit_paths: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    component_contract: tuple[dict[str, object], ...] = ()
    component_scope_complete: bool = True
    schema_version: str = "documentation-query-plan-v2"

    def as_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "original_question": self.original_question,
            "query_ids": [q.query_id for q in self.queries],
            "required_query_ids": [q.query_id for q in self.queries if q.coverage_required],
            "public_query_ids": [q.query_id for q in self.queries if q.origin in {"original", "host_lookup"}],
            "queries": [{
                "query_id": q.query_id, "text": q.text, "origin": q.origin,
                "coverage_required": q.coverage_required, "facet_id": q.facet_id,
                "requirement_id": q.requirement_id, "relation": q.relation,
                "public_parent_query_id": q.public_parent_query_id,
                "preferred_catalog_roles": list(q.preferred_catalog_roles),
                "forbidden_catalog_roles": list(q.forbidden_catalog_roles),
                "forbidden_evidence_terms": list(q.forbidden_evidence_terms),
                "parent_exact_terms": list(q.parent_exact_terms),
                "need_subject": q.need_subject, "need_relation": q.need_relation,
                "need_context": q.need_context,
                **({"component_rewrite_audit": {
                    "rule": q.component_rewrite_audit[0],
                    "query_span_start": q.component_rewrite_audit[1],
                    "query_span_end": q.component_rewrite_audit[2],
                    "query_span_text": q.component_rewrite_audit[3],
                }} if q.component_rewrite_audit else {}),
            } for q in self.queries],
            "explicit_paths": list(self.explicit_paths),
            "unresolved_parts": list(self.unresolved_parts),
            "_component_contract": [dict(item) for item in self.component_contract],
            "component_scope_complete": self.component_scope_complete,
        }


def build_documentation_query_plan(
    question: str, *, lookup_queries: tuple[str, ...] = (), explicit_path: str | None = None,
    requirements: object | None = None,
) -> DocumentationQueryPlan:
    """Keep exact request bytes and the existing five-lookup resource ceiling.

    Requirements remain in their owning proof pipeline, not a source of search
    aliases, injected expectations, or inherited parent coverage. An explicit
    path remains scope metadata; it is not an additional executable query.
    """
    queries = [DocumentationLookup("query-original", question, "original")]
    for index, text in enumerate(lookup_queries[:5], 1):
        if not text.strip():
            continue
        queries.append(DocumentationLookup(
            f"query-lookup-{index}", text, "host_lookup", False, relation="host_lookup",
        ))
    return DocumentationQueryPlan(
        original_question=question, queries=tuple(queries),
        explicit_paths=(explicit_path,) if explicit_path else (),
        unresolved_parts=tuple(str(value) for value in
            getattr(requirements, "unresolved_parts", ()) if str(value)),
        # A retrieval-only plan cannot assert a proof/component interpretation.
        component_scope_complete=False,
    )


def technical_anchors(question: str) -> tuple[str, ...]:
    return documentation_technical_anchors(question)


__all__ = ["DocumentationLookup", "DocumentationQueryPlan", "QueryRelation",
           "build_documentation_query_plan", "technical_anchors"]
