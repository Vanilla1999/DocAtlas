"""Retrieval-only query plan that never authorizes an answer or edit."""

from __future__ import annotations

from dataclasses import dataclass

from docmancer.docs.domain.question_frame_core import split_question_clauses


@dataclass(frozen=True, slots=True)
class DocumentationLookup:
    query_id: str
    text: str
    origin: str


@dataclass(frozen=True, slots=True)
class DocumentationQueryPlan:
    original_question: str
    queries: tuple[DocumentationLookup, ...]
    explicit_paths: tuple[str, ...] = ()
    schema_version: str = "documentation-query-plan-v1"

    def as_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query_ids": [query.query_id for query in self.queries],
            "queries": [
                {"query_id": query.query_id, "text": query.text, "origin": query.origin}
                for query in self.queries
            ],
            "explicit_paths": list(self.explicit_paths),
        }


def build_documentation_query_plan(
    question: str, *, lookup_queries: tuple[str, ...] = (), explicit_path: str | None = None,
) -> DocumentationQueryPlan:
    queries = [DocumentationLookup("query-original", question.strip(), "original")]
    queries.extend(
        DocumentationLookup(f"query-lookup-{index}", text.strip(), "host_lookup")
        for index, text in enumerate(lookup_queries, start=1)
        if text.strip()
    )
    seen = {query.text.casefold() for query in queries}
    clauses = split_question_clauses(question)
    if len(clauses) > 1:
        for clause in clauses:
            text = clause.strip()
            if not text or text.casefold() in seen or len(queries) >= 5:
                continue
            queries.append(DocumentationLookup(
                f"query-clause-{len(queries)}", text, "auto_clause",
            ))
            seen.add(text.casefold())
    if explicit_path:
        queries.append(DocumentationLookup("query-path-1", explicit_path, "exact_path"))
    return DocumentationQueryPlan(
        original_question=question,
        queries=tuple(queries),
        explicit_paths=(explicit_path,) if explicit_path else (),
    )


__all__ = [
    "DocumentationLookup",
    "DocumentationQueryPlan",
    "build_documentation_query_plan",
]
