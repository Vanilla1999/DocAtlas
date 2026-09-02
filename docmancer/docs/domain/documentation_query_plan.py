"""Retrieval-only query plan that never authorizes an answer or edit."""

from __future__ import annotations

from dataclasses import dataclass
import re

from docmancer.docs.domain.question_frame_core import split_question_clauses
from docmancer.docs.domain.project_retrieval_intent import (
    build_project_retrieval_aliases,
    project_retrieval_disposition,
)
from docmancer.retrieval.query_planning import extract_exact_terms


@dataclass(frozen=True, slots=True)
class DocumentationLookup:
    query_id: str
    text: str
    origin: str
    coverage_required: bool = True
    facet_id: str | None = None
    requirement_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentationQueryPlan:
    original_question: str
    queries: tuple[DocumentationLookup, ...]
    explicit_paths: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    schema_version: str = "documentation-query-plan-v2"

    def as_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "original_question": self.original_question,
            "query_ids": [query.query_id for query in self.queries],
            "required_query_ids": [
                query.query_id for query in self.queries if query.coverage_required
            ],
            "queries": [
                {
                    "query_id": query.query_id,
                    "text": query.text,
                    "origin": query.origin,
                    "coverage_required": query.coverage_required,
                    "facet_id": query.facet_id,
                    "requirement_id": query.requirement_id,
                }
                for query in self.queries
            ],
            "explicit_paths": list(self.explicit_paths),
            "unresolved_parts": list(self.unresolved_parts),
        }


def build_documentation_query_plan(
    question: str, *, lookup_queries: tuple[str, ...] = (), explicit_path: str | None = None,
    requirements: object | None = None,
) -> DocumentationQueryPlan:
    retrieval_aliases = build_project_retrieval_aliases(question)
    force_context_only = (
        project_retrieval_disposition(question) == "broad_context"
        and any(alias.force_context_only for alias in retrieval_aliases)
    )
    queries = [DocumentationLookup(
        "query-original", question.strip(), "original",
        not force_context_only,
    )]
    seen = {query.text.casefold() for query in queries}
    if explicit_path and explicit_path.casefold() not in seen:
        queries.append(DocumentationLookup(
            "query-path-1", explicit_path, "exact_path", False,
        ))
        seen.add(explicit_path.casefold())
    for index, anchor in enumerate(technical_anchors(question), start=1):
        if anchor.casefold() in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-anchor-{index}", anchor, "exact_anchor", False,
        ))
        seen.add(anchor.casefold())
    for index, text in enumerate(lookup_queries[:5], start=1):
        cleaned = text.strip()
        if not cleaned or cleaned.casefold() in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-lookup-{index}", cleaned, "host_lookup", False,
        ))
        seen.add(cleaned.casefold())
    for index, alias in enumerate(retrieval_aliases, start=1):
        if alias.text.casefold() in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-intent-{index}", alias.text, "canonical_intent", False,
            (
                f"intent-context:{alias.intent_id}"
                if alias.force_context_only else f"intent:{alias.intent_id}"
            ),
        ))
        seen.add(alias.text.casefold())
    normalized = re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip()
    concept_queries = (
        (
            "project docs configuration" in normalized,
            "docatlas.project-docs.yaml project docs catalog configuration",
        ),
        (
            "project answer contract" in normalized and "document" in normalized,
            "project answer contract documentation docs/mcp-docs-server.md",
        ),
        (
            "refresh" in normalized and bool({"documentation", "docs"} & set(normalized.split())),
            "sync_project_docs project documentation after file changes",
        ),
        (
            "configure" in normalized and bool({"documentation", "docs"} & set(normalized.split())),
            "docatlas.yaml project docs configuration",
        ),
    )
    requirement_concepts = tuple(
        str(value).strip()
        for value in getattr(requirements, "concept_queries", ())
        if str(value).strip()
    )
    requirement_hints = tuple(
        str(value).strip()
        for value in getattr(requirements, "retrieval_hints", ())
        if str(value).strip()
    )
    optional_queries = [
        *((text, "concept_alias") for applies, text in concept_queries if applies),
        *((text, "concept_alias") for text in requirement_concepts),
        *((text, "retrieval_hint") for text in requirement_hints),
    ]
    optional_count = 0
    origin_counts = {"concept_alias": 0, "retrieval_hint": 0}
    for text, origin in optional_queries:
        if text.casefold() in seen or optional_count >= 4:
            continue
        origin_counts[origin] += 1
        queries.append(DocumentationLookup(
            f"query-{'concept' if origin == 'concept_alias' else 'hint'}-{origin_counts[origin]}",
            text,
            origin,
            False,
        ))
        optional_count += 1
        seen.add(text.casefold())
    return DocumentationQueryPlan(
        original_question=question,
        queries=tuple(queries),
        explicit_paths=(explicit_path,) if explicit_path else (),
        unresolved_parts=tuple(
            str(value) for value in getattr(requirements, "unresolved_parts", ()) if str(value)
        ),
    )


_SOURCE_RELATION_QUESTION_RE = re.compile(
    r"^\s*(?:does|do|is|are)\s+.+?\s+"
    r"(?:prove|proves|define|defines|document|documents|establish|establishes)\s+"
    r"(?P<claim>.+?)\s*[?.!]*$",
    re.I,
)

_STANDALONE_TECHNICAL_RE = re.compile(
    r"(?<![\w/])(?:~?/|\.{1,2}/)?(?:[A-Za-z0-9_.-]+/)*"
    r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![\w/])"
    r"|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"
)


def technical_anchors(question: str) -> tuple[str, ...]:
    values = [match.group(0) for match in _STANDALONE_TECHNICAL_RE.finditer(question)]
    values.extend(
        term.value for term in extract_exact_terms(question)
        if not any(term.value in value for value in values)
    )
    return tuple(dict.fromkeys(value for value in values if value))[:12]


def _relation_claim_query(question: str) -> str | None:
    match = _SOURCE_RELATION_QUESTION_RE.match(question)
    if match is None:
        return None
    claim = match.group("claim").strip()
    return claim[:500] if claim else None


__all__ = [
    "DocumentationLookup",
    "DocumentationQueryPlan",
    "build_documentation_query_plan",
    "technical_anchors",
]
