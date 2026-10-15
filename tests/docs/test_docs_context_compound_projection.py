from __future__ import annotations

from copy import deepcopy
import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.recovery import build_recovery_diagnosis
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


def _alias_fragment_retrieval():
    retrieval = _host_lookup_context_retrieval()
    queries = [
        ("query-lookup-1", "amber bronze cobalt denim", "host_lookup"),
        ("query-lookup-2", "ember frost glacier hazel", "host_lookup"),
        ("query-intent-1", "alpha beta", "canonical_intent"),
        ("query-intent-2", "alpha", "canonical_intent"),
    ]
    retrieval["documentation_query_plan"] = {
        "required_query_ids": [], "public_query_ids": ["query-lookup-1", "query-lookup-2"],
        "queries": [{"query_id": key, "text": text, "origin": origin, "facet_id": key}
                    for key, text, origin in queries],
    }
    source = retrieval["context_pack"][0]
    source["content"] = (
        "alpha beta amber bronze.\n\n" + "Unrelated prose for background. " * 20
        + "\n\nThe amber bronze cobalt denim procedure combines ember frost glacier hazel for the complete operation."
    )
    source["retrieval_query_matches"] = {
        key: {"qualified": True, "query_text": text} for key, text, _ in queries
    }
    source["line_start"] = 1
    retrieval["context_pack"] = [source]
    return retrieval
