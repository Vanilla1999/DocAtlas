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


def test_additive_hint_retry_preserves_primary_snippet_under_tight_budget():
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
        content=(
            "Maximum recall across repository breadth is an overview concern.\n\n"
            "The overview must not grant edit authority."
        ),
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
    base_retrieval = {
        "question": question,
        "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [primary],
        "documentation_query_plan": plan.as_payload(),
    }
    hinted_retrieval = {**base_retrieval, "context_pack": [primary, supporting]}

    before, _ = project_docs_context(retrieval=base_retrieval, max_tokens=410)
    after, _ = project_docs_context(retrieval=hinted_retrieval, max_tokens=410)

    assert before["sources"]
    previous = before["sources"][0]
    assert "The overview must not grant edit authority." in previous["snippet"]
    trial_by_id = {row["evidence_id"]: row for row in after["sources"]}
    assert previous["evidence_id"] in trial_by_id
    assert previous["snippet"] in trial_by_id[previous["evidence_id"]]["snippet"]
    assert after["estimated_tokens"] <= 410
    assert len(after["sources"]) <= 3
    assert after["answer_supported"] is False
    assert after["edit_ready"] is False


def test_visible_source_retention_requires_ids_and_existing_snippets():
    from docmancer.docs.application.docs_context_projection import _retains_visible_sources

    previous = {"sources": [{"evidence_id": "a", "snippet": "alpha beta"}]}
    assert _retains_visible_sources(
        previous, {"sources": [{"evidence_id": "a", "snippet": "alpha beta gamma"}]}
    ) is True
    assert _retains_visible_sources(
        previous, {"sources": [{"evidence_id": "a", "snippet": "alpha"}]}
    ) is False
    assert _retains_visible_sources(
        previous, {"sources": [{"evidence_id": "b", "snippet": "alpha beta"}]}
    ) is False


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


@pytest.mark.parametrize("subject", ["cache", "queue", "database"])
def test_comparison_relation_rejects_unrelated_same_sentence_clause(subject: str) -> None:
    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    for text in (
        (
            "Matching search result evidence describes sufficient answer condition terminology, "
            f"whereas this {subject} has new settings."
        ),
        (
            "Matching search result evidence describes sufficient answer condition terminology; "
            f"this {subject} is not enough to prove storage capacity."
        ),
        (
            "Matching search result evidence describes sufficient answer condition terminology; "
            f"this {subject} is different from last year."
        ),
    ):
        result = qualify_evidence(
            probe, query_id="query-relation-1", visible_text=text
        )
        assert result.qualified is False, text
        assert result.reason == "missing_visible_comparison_relation"


@pytest.mark.parametrize("text", [
    (
        "Matching search result evidence\n"
        "is not the same as\n"
        "sufficient answer condition."
    ),
    (
        "Matching search result evidence is not the\n"
        "same as sufficient answer condition."
    ),
    (
        "Matching search result evidence is different\n"
        "from sufficient answer condition."
    ),
])
def test_comparison_relation_preserves_soft_wrapped_prose(text: str) -> None:
    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    compact = " ".join(text.split())
    assert qualify_evidence(
        probe, query_id="query-relation-1", visible_text=compact
    ).qualified is True
    assert qualify_evidence(
        probe, query_id="query-relation-1", visible_text=text
    ).qualified is True


@pytest.mark.parametrize("text", [
    (
        "Matching search result evidence describes sufficient answer condition terminology.\n\n"
        "These cache settings are different."
    ),
    (
        "- Matching search result evidence describes sufficient answer condition terminology\n"
        "- These cache settings are different"
    ),
    (
        "| Matching search result evidence sufficient answer condition | "
        "These settings are different |"
    ),
    (
        "Matching search result evidence describes sufficient answer condition terminology.\n\n"
        "```text\nThese cache settings are different\n```"
    ),
    (
        "# Matching search result evidence sufficient answer condition\n\n"
        "These cache settings are different."
    ),
])
def test_comparison_relation_does_not_cross_structural_boundaries(text: str) -> None:
    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    result = qualify_evidence(
        probe, query_id="query-relation-1", visible_text=text
    )
    assert result.qualified is False
    assert result.reason == "missing_visible_comparison_relation"


def test_comparison_relation_keeps_valid_relation_with_unrelated_suffix() -> None:
    probe = {
        "query_text": (
            "matching search result evidence sufficient answer condition different separate"
        )
    }
    result = qualify_evidence(
        probe,
        query_id="query-relation-1",
        visible_text=(
            "Matching search result evidence is different from sufficient answer condition; "
            "this cache has new settings."
        ),
    )
    assert result.qualified is True


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


def test_comparison_relation_rejects_unrelated_proof_insufficiency_clause() -> None:
    probe = {"query_text": "matching search result evidence sufficient answer condition different separate"}
    distractor = qualify_evidence(
        probe, query_id="query-relation-1",
        visible_text=(
            "Matching search result evidence describes sufficient answer condition terminology. "
            "This cache is not enough to prove storage capacity."
        ),
    )
    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"


def test_comparison_relation_rejects_unrelated_different_from_clause() -> None:
    probe = {"query_text": "matching search result evidence sufficient answer condition different separate"}
    distractor = qualify_evidence(probe, query_id="query-relation-1", visible_text=(
        "Matching search result evidence describes sufficient answer condition terminology. "
        "These examples are different from last year."))
    assert distractor.qualified is False
    assert distractor.reason == "missing_visible_comparison_relation"



def test_multiple_host_lookups_do_not_let_baseline_only_candidate_preempt_lookup_diversity():
    from docmancer.docs.application.context_candidate_ranking import _prefer_missing_baseline_candidate

    def candidate(*query_ids: str) -> dict:
        return {
            "retrieval_query_matches": {
                query_id: {"qualified": True}
                for query_id in query_ids
            }
        }

    lookup_candidate = candidate("query-lookup-1", "query-lookup-2")
    anchor_only = candidate("query-anchor-1")
    canonical_only = candidate("query-intent-1")
    candidates = [lookup_candidate, anchor_only, canonical_only]

    _prefer_missing_baseline_candidate(
        candidates,
        [],
        {"query-original", "query-anchor-1", "query-lookup-1", "query-lookup-2"},
        {"query-lookup-1", "query-lookup-2"},
        {"query-intent-1"},
    )

    assert candidates[0] is lookup_candidate

def test_multiple_host_lookups_allow_baseline_protection_after_lookup_coverage_is_complete():
    from docmancer.docs.application.context_candidate_ranking import _prefer_missing_baseline_candidate

    def candidate(*query_ids: str) -> dict:
        return {
            "retrieval_query_matches": {
                query_id: {"qualified": True}
                for query_id in query_ids
            }
        }

    neutral = candidate("query-hint-1")
    anchor_only = candidate("query-anchor-1")
    candidates = [neutral, anchor_only]
    selected = [candidate("query-lookup-1", "query-lookup-2")]

    _prefer_missing_baseline_candidate(
        candidates,
        selected,
        {"query-original", "query-anchor-1", "query-lookup-1", "query-lookup-2"},
        {"query-lookup-1", "query-lookup-2"},
        {"query-intent-1"},
    )

    assert candidates[0] is anchor_only


def test_original_witness_is_protected_even_when_it_also_matches_host_lookup():
    question = "Does preparing dependency documentation also install the dependency into my application?"
    lookups = ("preparing documentation and installing project dependencies",)
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, lookup_queries=lookups, requirements=requirements)
    original = next(item for item in plan.queries if item.query_id == "query-original")
    host = next(item for item in plan.queries if item.query_id == "query-lookup-1")
    canonical = next(
        item for item in plan.queries
        if item.origin == "canonical_intent" and item.text == "install command line help"
    )
    boundary = _project_source(
        path="docs/boundary.md", query_id=original.query_id, query_text=original.text,
        content=(
            "Preparing dependency documentation reads manifests and lockfiles as version evidence; "
            "it does not install the dependency into your application or mutate project dependencies."
        ),
    )
    boundary["retrieval_query_ids"].append(host.query_id)
    boundary["retrieval_query_matches"][host.query_id] = {
        "qualified": True, "query_text": host.text, "query_origin": "host_lookup",
        "relation": "host_lookup",
    }
    weak_canonical = _project_source(
        path="docs/install.md", query_id=canonical.query_id, query_text=canonical.text,
        content="Install DocAtlas command line help with the one-line installer for the CLI.",
    )
    retrieval = {
        "question": question, "project_identity": PROJECT_ID,
        "requirements": requirements.hash_payload,
        "context_pack": [weak_canonical, boundary],
        "documentation_query_plan": plan.as_payload(),
    }
    payload, _snapshot = project_docs_context(retrieval=retrieval, max_tokens=340)
    assert [row["path_or_url"] for row in payload["sources"]] == ["docs/boundary.md"]


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


def test_additive_retry_restores_primary_bytes_before_accepting_new_evidence():
    from docmancer.docs.application import visible_evidence_retention as retention

    restore = getattr(retention, "restore_visible_sources", None)
    assert restore is not None, "additive retry restoration helper is missing"
    previous = {"sources": [{"evidence_id": "primary", "snippet": "alpha beta gamma"}]}
    previous_snapshot = {"primary": {"visible": "alpha beta gamma"}}
    trial = {"sources": [
        {"evidence_id": "primary", "snippet": "alpha beta"},
        {"evidence_id": "new", "snippet": "delta"},
    ]}
    trial_snapshot = {
        "primary": {"visible": "alpha beta"},
        "new": {"visible": "delta"},
    }
    payload, snapshot = restore(previous, previous_snapshot, trial, trial_snapshot)
    by_id = {row["evidence_id"]: row for row in payload["sources"]}
    assert by_id["primary"]["snippet"] == "alpha beta gamma"
    assert by_id["new"]["snippet"] == "delta"
    assert snapshot["primary"] == previous_snapshot["primary"]
