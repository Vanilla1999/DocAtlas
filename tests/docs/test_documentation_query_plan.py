from docmancer.docs.domain.documentation_query_plan import (
    DocumentationLookup,
    build_documentation_query_plan,
)
from docmancer.docs.domain.context_budget import ContextBudget
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    qualify_evidence,
)
import pytest


def test_documentation_query_plan_owns_public_retrieval_query_ids():
    plan = build_documentation_query_plan(
        "Please explain DocAtlas architecture and testing.",
        lookup_queries=(
            "project purpose",
            "project architecture",
            "project data flow",
            "local development",
            "test commands",
        ),
    ).as_payload()

    assert plan["public_query_ids"] == [
        "query-original",
        "query-lookup-1",
        "query-lookup-2",
        "query-lookup-3",
        "query-lookup-4",
        "query-lookup-5",
    ]
    assert plan["required_query_ids"] == []
    assert any(item["origin"] == "canonical_intent" for item in plan["queries"])
    assert not any(
        query_id.startswith("query-intent-") for query_id in plan["public_query_ids"]
    )


def test_documentation_query_plan_owns_audited_alias_lineage():
    plan = build_documentation_query_plan(
        "Как устроен полный процесс работы Docs MCP?",
        lookup_queries=("MCP public tools",),
    ).as_payload()
    by_origin = {
        origin: [item for item in plan["queries"] if item["origin"] == origin]
        for origin in {item["origin"] for item in plan["queries"]}
    }

    assert by_origin["original"][0]["relation"] == "direct"
    assert by_origin["original"][0]["public_parent_query_id"] is None
    assert by_origin["host_lookup"][0]["relation"] == "host_lookup"
    assert by_origin["host_lookup"][0]["public_parent_query_id"] is None
    assert all(
        item["relation"] == "audited_rewrite"
        and item["public_parent_query_id"] == "query-original"
        and item["preferred_catalog_roles"]
        for item in by_origin["canonical_intent"]
    )


def test_documentation_lookup_rejects_invalid_lineage():
    with pytest.raises(ValueError, match="unsupported"):
        DocumentationLookup("query-x", "x", "hint", relation="internal_hint")
    with pytest.raises(ValueError, match="public parent"):
        DocumentationLookup("query-x", "x", "canonical_intent", relation="audited_rewrite")


def test_context_budget_is_a_product_invariant():
    budget = ContextBudget()

    assert budget.max_sources == 3
    assert budget.max_tokens == 800
    assert budget.bounded_tokens(2_000) == 800


def test_evidence_qualification_fails_closed_and_owns_derived_lineage():
    rejected = qualify_evidence(
        {"qualified": True}, query_id="query-intent-1", visible_text="unrelated",
    )
    assert rejected.qualified is False
    assert rejected.reason == "missing_visible_query_terms"

    qualified = qualify_evidence(
        {
            "qualified": True,
            "query_text": "project architecture",
            "relation": "audited_rewrite",
        },
        query_id="query-intent-1",
        visible_text="Project architecture boundaries.",
    )
    parent = derived_parent_trace(
        qualified.trace,
        source_query_id="query-intent-1",
        parent_query_id="query-original",
    )
    assert qualified.qualified is True
    assert parent is not None
    assert parent["coverage_kind"] == "derived"
    assert parent["derived_from_query_ids"] == ["query-intent-1"]


def test_evidence_qualification_rejects_metadata_only_term_matches():
    qualification = qualify_evidence(
        {"qualified": True, "query_text": "project architecture"},
        query_id="query-original",
        visible_text="docs/project-architecture.md\nArchitecture\nunrelated body",
        evidence_text="unrelated body",
    )

    assert qualification.qualified is False
    assert qualification.reason == "insufficient_visible_match"
