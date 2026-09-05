from __future__ import annotations

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)


def _host_lookup_context_retrieval() -> dict:
    queries = [{
        "query_id": "query-original",
        "text": "Help me understand this project.",
        "origin": "original",
        "coverage_required": False,
    }]
    sources = []
    for index, topic in enumerate(
        ("purpose", "architecture", "data flow", "development", "testing"),
        start=1,
    ):
        query_id = f"query-lookup-{index}"
        query_text = f"project {topic} documentation"
        queries.append({
            "query_id": query_id,
            "text": query_text,
            "origin": "host_lookup",
            "coverage_required": False,
        })
        sources.append({
            "source_class": "project_doc",
            "path": f"docs/topic-{index}.md",
            "heading_path": topic.title(),
            "content": f"Project {topic} documentation gives a focused newcomer explanation.",
            "project_identity": "git:example/project",
            "authority": "source_of_truth",
            "doc_scope": "project",
            "lifecycle_status": "active",
            "freshness": "current",
            "index_freshness": "synchronized",
            "risk_flags": [],
            "retrieval_query_ids": [query_id],
            "retrieval_query_matches": {
                query_id: {
                    "qualified": True,
                    "mode": "and",
                    "query_text": query_text,
                },
            },
        })
    return {
        "context_pack": sources,
        "documentation_query_plan": {
            "query_ids": [item["query_id"] for item in queries],
            "required_query_ids": [],
            "queries": queries,
        },
    }


def test_docs_context_keeps_distinct_host_lookup_sources_until_source_limit():
    projection, snapshot = project_docs_context(
        retrieval=_host_lookup_context_retrieval(),
    )

    assert projection["kind"] == "docs_context"
    assert projection["answer_supported"] is False
    assert projection["edit_ready"] is False
    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert projection["missing_query_ids"] == [
        "query-original", "query-lookup-4", "query-lookup-5",
    ]
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_host_lookup_selection_is_not_a_global_latch():
    projection, _snapshot = project_docs_context(
        retrieval=_host_lookup_context_retrieval(), max_tokens=2_000,
    )

    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert projection["estimated_tokens"] <= 800


def test_docs_context_compacts_snippets_before_sacrificing_lookup_coverage():
    retrieval = _host_lookup_context_retrieval()
    for index, source in enumerate(retrieval["context_pack"], start=1):
        source["content"] = (
            "General background information for a new contributor. " * 20
            + source["content"]
            + " Additional implementation background for maintainers. " * 20
            + f" Stable topic marker {index}."
        )

    projection, snapshot = project_docs_context(retrieval=retrieval)

    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert all(len(source["snippet"]) >= 40 for source in projection["sources"])
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_compacts_long_sources_with_generated_facet_diagnostics():
    retrieval = _host_lookup_context_retrieval()
    for index, source in enumerate(retrieval["context_pack"], start=1):
        source["content"] = (
            f"Project topic {index} documentation " * 80
            + f"Stable newcomer conclusion for topic {index}."
        )
    retrieval["documentation_query_plan"]["public_query_ids"] = [
        "query-original", *(f"query-lookup-{index}" for index in range(1, 6)),
    ]
    for index in range(1, 5):
        retrieval["documentation_query_plan"]["queries"].append({
            "query_id": f"query-intent-{index}",
            "text": f"Generated diagnostic facet question {index}",
            "origin": "canonical_intent",
            "coverage_required": False,
            "facet_id": f"intent-context:facet-{index}",
        })

    projection, snapshot = project_docs_context(retrieval=retrieval)

    assert len(projection["sources"]) >= 2
    assert len(set(projection["covered_query_ids"])) >= 2
    assert not any(
        query_id.startswith("query-intent-")
        for query_id in projection["missing_query_ids"]
    )
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_rejects_match_found_only_in_hidden_retrieval_metadata():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source["content"] = "This visible paragraph discusses an unrelated release note."
    source["retrieval_query_matches"]["query-lookup-1"].update({
        "query_terms": ["project", "purpose", "documentation"],
        "field_matches": {
            "title": [],
            "body": [],
            "retrieval_text": ["project", "purpose", "documentation"],
        },
    })
    retrieval["context_pack"] = [source]

    projection, _snapshot = project_docs_context(retrieval=retrieval)

    assert projection["status"] == "insufficient_evidence"
    assert projection["context_available"] is False
