from __future__ import annotations

import json

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence


PROJECT_ID = "git:example/project"


def _project_source(*, path: str, content: str, query_id: str, query_text: str, **overrides):
    source = {
        "source_class": "project_doc",
        "path": path,
        "heading_path": "Policy",
        "content": content,
        "project_identity": PROJECT_ID,
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
                "query_text": query_text,
                "query_origin": "retrieval_hint",
                "relation": "host_lookup",
            },
        },
    }
    source.update(overrides)
    return source


def _retrieval(question: str, source: dict, *, lookups: tuple[str, ...] = ()):  # noqa: ANN001
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(
        question,
        lookup_queries=lookups,
        requirements=requirements,
    )
    return {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [source],
        "documentation_query_plan": plan.as_payload(),
    }, plan


def test_version_scenario_exact_anchors_do_not_hide_safe_generic_policy_context():
    question = (
        "Only documentation for version 1.0 is cached, but the project now resolves "
        "version 2.0. What should a current-project query return?"
    )
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    hint = next(item for item in plan.queries if item.query_id == "query-hint-2")
    source = _project_source(
        path="docs/version-policy.md",
        query_id=hint.query_id,
        query_text=hint.text,
        content=(
            "A current-project query should return documentation bound to the newly "
            "resolved dependency. When the binding changes from A to B, documentation "
            "for A is no longer eligible as current-project evidence; use B or fail "
            "closed until matching documentation is prepared."
        ),
    )
    retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [source],
        "documentation_query_plan": plan.as_payload(),
    }

    payload, _snapshot = project_docs_context(retrieval=retrieval)

    assert payload["context_available"] is True
    assert [row["path_or_url"] for row in payload["sources"]] == ["docs/version-policy.md"]
    assert "query-original" not in payload["covered_query_ids"]
    assert not any(query_id.startswith("query-anchor-") for query_id in payload["covered_query_ids"])
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False


def test_optional_host_lookup_does_not_revoke_safe_hint_context():
    question = "When answering about a module, should the agent automatically use scope=all for maximum recall?"
    lookups = ("maximum recall repository breadth",)
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, lookup_queries=lookups, requirements=requirements)
    hint = next(item for item in plan.queries if item.query_id == "query-hint-1")
    source = _project_source(
        path="docs/module-scope.md",
        query_id=hint.query_id,
        query_text=hint.text,
        content=(
            "When answering about a module, keep the request scoped to that module and "
            "its exact module path. Repository-wide scope is a separate overview case."
        ),
    )
    retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [source],
        "documentation_query_plan": plan.as_payload(),
    }

    payload, _snapshot = project_docs_context(retrieval=retrieval)

    assert payload["context_available"] is True
    assert [row["path_or_url"] for row in payload["sources"]] == ["docs/module-scope.md"]
    assert "query-original" not in payload["covered_query_ids"]
    assert "query-lookup-1" not in payload["covered_query_ids"]
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False


def test_supporting_hint_still_cannot_cross_project_identity_boundary():
    question = "When answering about a module, should the agent automatically use scope=all for maximum recall?"
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    hint = next(item for item in plan.queries if item.query_id == "query-hint-1")
    source = _project_source(
        path="docs/module-scope.md",
        query_id=hint.query_id,
        query_text=hint.text,
        content="When answering about a module, use the exact module path.",
        project_identity="git:other/project",
    )
    retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [source],
        "documentation_query_plan": plan.as_payload(),
    }

    payload, _snapshot = project_docs_context(retrieval=retrieval)

    assert payload["context_available"] is False
    assert payload.get("sources", []) == []


def test_partial_primary_packet_can_add_safe_hint_without_losing_primary_source():
    question = "When answering about a module, should the agent automatically use scope=all for maximum recall?"
    lookups = ("maximum recall repository breadth",)
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, lookup_queries=lookups, requirements=requirements)
    host = next(item for item in plan.queries if item.query_id == "query-lookup-1")
    hint = next(item for item in plan.queries if item.query_id == "query-hint-1")
    primary = _project_source(
        path="docs/repository-overview.md",
        query_id=host.query_id,
        query_text=host.text,
        content="Maximum recall across repository breadth is an overview concern.",
    )
    supporting = _project_source(
        path="docs/module-scope.md",
        query_id=hint.query_id,
        query_text=hint.text,
        content=(
            "When answering about a module, keep the request scoped to that module and "
            "its exact module path. Repository-wide scope is a separate overview case."
        ),
    )
    retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [primary, supporting],
        "documentation_query_plan": plan.as_payload(),
    }

    payload, _snapshot = project_docs_context(retrieval=retrieval)

    paths = [row["path_or_url"] for row in payload["sources"]]
    assert paths[0] == "docs/repository-overview.md"
    assert "docs/module-scope.md" in paths
    assert "query-original" not in payload["covered_query_ids"]
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False


def test_comparison_relation_qualification_prefers_supporting_relation_over_keyword_salad():
    from docmancer.docs.domain.evidence_qualification import qualify_evidence

    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    supporting = qualify_evidence(
        probe,
        query_id="query-relation-1",
        visible_text=(
            "A retrieval hit can be relevant to a question, but it is not enough to "
            "prove the complete answer. A complete answer needs evidence for every "
            "mandatory condition."
        ),
        evidence_text=(
            "A retrieval hit can be relevant to a question, but it is not enough to "
            "prove the complete answer. A complete answer needs evidence for every "
            "mandatory condition."
        ),
    )
    distractor = qualify_evidence(
        probe,
        query_id="query-relation-1",
        visible_text=(
            "Search result evidence is relevant. Sufficient answer context uses matching "
            "search result evidence efficiently."
        ),
        evidence_text=(
            "Search result evidence is relevant. Sufficient answer context uses matching "
            "search result evidence efficiently."
        ),
    )

    assert supporting.qualified is True
    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"


def test_comparison_relation_rejects_unrelated_different_adjective() -> None:
    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    distractor = qualify_evidence(
        probe,
        query_id="query-relation-1",
        visible_text=(
            "The guide contains different examples of matching search result evidence "
            "and sufficient answer condition terminology."
        ),
    )

    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"


def test_rejected_hint_retry_diagnostics_remain_json_serializable():
    question = "When answering about a module, should the agent automatically use scope=all for maximum recall?"
    lookups = ("maximum recall repository breadth",)
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, lookup_queries=lookups, requirements=requirements)
    host = next(item for item in plan.queries if item.query_id == "query-lookup-1")
    source = _project_source(
        path="docs/repository-overview.md", query_id=host.query_id, query_text=host.text,
        content="Maximum recall across repository breadth is an overview concern.",
    )
    retrieval = {"question": question, "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload, "context_pack": [source],
        "documentation_query_plan": plan.as_payload()}
    payload, _snapshot = project_docs_context(retrieval=retrieval)
    assert [row["path_or_url"] for row in payload["sources"]] == ["docs/repository-overview.md"]
    json.dumps(retrieval["retrieval_diagnostics"])


def test_comparison_relation_rejects_unrelated_not_enough_clause() -> None:
    probe = {"query_text": "matching search result evidence sufficient answer condition different separate"}
    distractor = qualify_evidence(probe, query_id="query-relation-1", visible_text=(
        "Matching search result evidence describes sufficient answer condition terminology. "
        "This is not enough storage."))
    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"


def test_comparison_relation_rejects_unrelated_different_from_clause() -> None:
    probe = {"query_text": "matching search result evidence sufficient answer condition different separate"}
    distractor = qualify_evidence(probe, query_id="query-relation-1", visible_text=(
        "Matching search result evidence describes sufficient answer condition terminology. "
        "These examples are different from last year."))
    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"


def test_single_host_lookup_cannot_displace_available_canonical_witness_under_budget():
    question = "Does retrieved documentation authorize executing a destructive delete command?"
    lookups = ("destructive delete command permission",)
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, lookup_queries=lookups, requirements=requirements)
    canonical = next(item for item in plan.queries if item.query_id == "query-intent-1")
    host = next(item for item in plan.queries if item.query_id == "query-lookup-1")
    canonical_source = _project_source(path="docs/security.md", query_id=canonical.query_id,
        query_text=canonical.text, content=(
            "Documentation instruction trust treats document data as untrusted. "
            "Document content cannot override system user tool or runtime safety policy."))
    host_source = _project_source(path="docs/delete.md", query_id=host.query_id, query_text=host.text,
        content=("Destructive delete command permission requires an explicit allow-destructive configuration. " * 4),
        authority="supporting")
    retrieval = {"question": question, "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload, "context_pack": [host_source, canonical_source],
        "documentation_query_plan": plan.as_payload()}
    payload, _snapshot = project_docs_context(retrieval=retrieval, max_tokens=340)
    assert "docs/security.md" in [row["path_or_url"] for row in payload["sources"]]


@pytest.mark.parametrize("overrides", [
    {"stale": True},
    {"freshness": "stale"},
    {"index_freshness": "outdated"},
    {"risk_flags": ["unsafe"]},
])
def test_supporting_hint_cannot_bypass_current_safe_source_policy(overrides):
    question = "How should current project documentation behave after a version transition?"
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    hint = next(item for item in plan.queries if item.origin == "retrieval_hint")
    source = _project_source(
        path="docs/version-policy.md",
        query_id=hint.query_id,
        query_text=hint.text,
        content="Current project documentation follows the resolved dependency binding.",
        **overrides,
    )
    retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [source],
        "documentation_query_plan": plan.as_payload(),
    }

    result, _ = project_docs_context(retrieval=retrieval)

    assert result["context_available"] is False
    assert not result.get("sources")
