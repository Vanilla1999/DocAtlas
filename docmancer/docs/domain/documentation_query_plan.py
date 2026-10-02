"""Bounded explicit retrieval queries; never infer semantic equivalence."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from docmancer.docs.domain.query_terms import (
    documentation_exact_terms,
    documentation_technical_anchors,
    is_exact_technical_token,
)
from docmancer.docs.domain.technical_terms import extract_technical_terms

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
        # Existing downstream trace validators still consume these relations.
        # The planner below does not generate audited natural-language rewrites.
        if self.relation not in {"direct", "audited_rewrite", "host_lookup", "exact_anchor"}:
            raise ValueError(f"unsupported documentation query relation: {self.relation}")
        if self.relation == "audited_rewrite" and not self.public_parent_query_id:
            raise ValueError("audited rewrites require a public parent query")
        if self.relation in {"direct", "host_lookup"} and self.public_parent_query_id:
            raise ValueError(f"{self.relation} queries cannot derive parent coverage")
        for field in (
            "preferred_catalog_roles", "forbidden_catalog_roles", "forbidden_evidence_terms",
            "parent_exact_terms",
        ):
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
        public_origins = {"original", "host_lookup", "exact_anchor", "exact_path"}
        return {
            "schema_version": self.schema_version,
            "original_question": self.original_question,
            "query_ids": [query.query_id for query in self.queries],
            "required_query_ids": [query.query_id for query in self.queries if query.coverage_required],
            "public_query_ids": [query.query_id for query in self.queries if query.origin in public_origins],
            "queries": [
                {
                    "query_id": query.query_id,
                    "text": query.text,
                    "origin": query.origin,
                    "coverage_required": query.coverage_required,
                    "facet_id": query.facet_id,
                    "requirement_id": query.requirement_id,
                    "relation": query.relation,
                    "public_parent_query_id": query.public_parent_query_id,
                    "preferred_catalog_roles": list(query.preferred_catalog_roles),
                    "forbidden_catalog_roles": list(query.forbidden_catalog_roles),
                    "forbidden_evidence_terms": list(query.forbidden_evidence_terms),
                    "parent_exact_terms": list(query.parent_exact_terms),
                    "need_subject": query.need_subject,
                    "need_relation": query.need_relation,
                    "need_context": query.need_context,
                    **({"component_rewrite_audit": {
                        "rule": query.component_rewrite_audit[0],
                        "query_span_start": query.component_rewrite_audit[1],
                        "query_span_end": query.component_rewrite_audit[2],
                        "query_span_text": query.component_rewrite_audit[3],
                    }} if query.component_rewrite_audit else {}),
                }
                for query in self.queries
            ],
            "explicit_paths": list(self.explicit_paths),
            "unresolved_parts": list(self.unresolved_parts),
            "_component_contract": [dict(item) for item in self.component_contract],
            "component_scope_complete": self.component_scope_complete,
        }


def build_documentation_query_plan(
    question: str, *, lookup_queries: tuple[str, ...] = (), explicit_path: str | None = None,
    requirements: object | None = None,
) -> DocumentationQueryPlan:
    """Preserve raw question and exact locators; lookups cannot derive coverage.

    Requirements remain owned by eligibility/proof callers. They must not inject
    guessed natural-language needs, aliases or forbidden words into retrieval.
    """
    queries = [DocumentationLookup("query-original", question, "original")]
    seen = {question.strip()}
    if explicit_path:
        queries.append(DocumentationLookup(
            "query-path-1", explicit_path, "exact_path", False,
            relation="exact_anchor", public_parent_query_id="query-original",
        ))
        seen.add(explicit_path)
    for index, text in enumerate(lookup_queries[:5], 1):
        cleaned = text.strip()
        if not cleaned or cleaned in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-lookup-{index}", cleaned, "host_lookup", False, relation="host_lookup",
        ))
        seen.add(cleaned)
    quoted = [match.group(1) if match.group(1) is not None else match.group(2)
              for match in re.finditer(r'`([^`\n]+)`|"([^"\n]+)"', question)]
    exact = tuple(dict.fromkeys((
        *quoted, *(term.value for term in documentation_exact_terms(question) if term.kind != "quoted"),
        *technical_anchors(question),
        *(match.group(0) for match in re.finditer(r"(?<![\w.])\d+(?:\.\d+)+(?:[-+][\w.-]+)?(?![\w.])", question)),
    )))[:12]
    for index, text in enumerate(exact, 1):
        if text in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-anchor-{index}", text, "exact_anchor", False,
            relation="exact_anchor", public_parent_query_id="query-original",
        ))
        seen.add(text)
    return DocumentationQueryPlan(
        question, tuple(queries), explicit_paths=(explicit_path,) if explicit_path else (),
        unresolved_parts=("semantic_scope_unverified",), component_scope_complete=False,
    )


_STANDALONE_TECHNICAL_RE = re.compile(
    r"(?<![\w/])(?:~?/|\.{1,2}/)?(?:[A-Za-z0-9_.-]+/)*"
    r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![\w/])"
    r"|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"
)


def technical_anchors(question: str) -> tuple[str, ...]:
    values = [match.group(0) for match in _STANDALONE_TECHNICAL_RE.finditer(question)]
    values.extend(value for value in documentation_technical_anchors(question)
                  if not any(value in existing for existing in values))
    values.extend(
        term.raw for term in extract_technical_terms(question)
        if term.kind != "plain_term"
        and term.raw.casefold() not in {"docatlas", "docmancer"}
        and is_exact_technical_token(term.raw)
        and not any(term.raw in existing for existing in values)
    )
    return tuple(dict.fromkeys(value for value in values if value))[:12]


__all__ = ["DocumentationLookup", "DocumentationQueryPlan", "QueryRelation",
           "build_documentation_query_plan", "technical_anchors"]
