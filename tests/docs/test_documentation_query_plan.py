"""Explicit planning replaces NL aliases without weakening source controls."""
from types import SimpleNamespace

import pytest

from docmancer.docs.domain.context_budget import ContextBudget
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.application.need_query_schedule import scheduled_plan


@pytest.mark.parametrize("question", [
    "What happens if documentation is not indexed?",
    "Что происходит, если документация не проиндексирована?",
    "¿Qué sucede si no está indexada la documentación?",
    "文書が索引付けされていない場合はどうなりますか？",
    "ماذا يحدث إذا لم تتم فهرسة الوثائق؟",
    "  Mixed 文書 ميزانية además\n",
])
def test_raw_question_is_authoritative_and_unknown_grammar_still_searches(question):
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].text == question
    assert plan.queries[0].query_id == "query-original"
    assert plan.queries[0].relation == "direct"
    assert not any(q.origin in {"canonical_intent", "retrieval_need", "component_rewrite"} for q in plan.queries)
    assert not any(q.forbidden_evidence_terms or q.forbidden_catalog_roles for q in plan.queries)


@pytest.mark.parametrize("lookup", [
    "project architecture", "архитектура проекта", "引用", "ميزانية", "budget not metadata",
])
def test_host_lookup_never_derives_original_coverage(lookup):
    plan = build_documentation_query_plan("Explain architecture", lookup_queries=(lookup,))
    row = next(q for q in plan.queries if q.origin == "host_lookup")
    assert row.text == lookup
    assert row.relation == "host_lookup"
    assert row.public_parent_query_id is None
    assert row.parent_exact_terms == ()
    assert all(q.relation != "audited_rewrite" for q in plan.queries)


def test_exact_paths_identifiers_versions_and_case_are_preserved():
    question = 'Compare `ALPHA_KEY` and `alpha_key` in docs/settings.md with --no-cache version "2.0.1"'
    plan = build_documentation_query_plan(question, explicit_path="docs/settings.md")
    anchors = {q.text for q in plan.queries if q.origin == "exact_anchor"}
    assert {"ALPHA_KEY", "alpha_key", "--no-cache", "2.0.1"} <= anchors
    assert plan.explicit_paths == ("docs/settings.md",)
    assert next(q for q in plan.queries if q.origin == "exact_path").text == "docs/settings.md"
    assert plan.original_question == question


def test_requirements_cannot_inject_guessed_aliases_or_forbidden_words():
    requirements = SimpleNamespace(
        concept_queries=("guessed answer",), retrieval_hints=("guessed topic",),
        forbidden_evidence_terms=("metadata",),
    )
    plan = build_documentation_query_plan("budget includes metadata?", requirements=requirements)
    assert [q.text for q in plan.queries] == ["budget includes metadata?"]
    assert plan.queries[0].forbidden_evidence_terms == ()


def test_query_caps_duplicates_and_technical_case_identity():
    lookups = ("ALPHA_KEY", "alpha_key", "引用", "budget", "scope", "ignored")
    plan = build_documentation_query_plan("question", lookup_queries=lookups)
    assert [q.text for q in plan.queries if q.origin == "host_lookup"] == list(lookups[:5])
    _, probes = scheduled_plan(plan)
    assert len(probes) <= 12
    duplicate = build_documentation_query_plan("question", lookup_queries=("question", "budget", "budget"))
    assert [q.text for q in duplicate.queries] == ["question", "budget"]


def test_scheduler_does_not_generate_needs_or_rewrite_short_lookups():
    plan = build_documentation_query_plan("Compare if not enabled", lookup_queries=("引用", "not enabled"))
    result, probes = scheduled_plan(plan)
    assert result == plan
    assert [q.text for q in probes] == ["引用", "not enabled"]
    assert plan.as_payload()["required_query_ids"] == ["query-original"]


def test_documentation_lookup_rejects_invalid_lineage():
    with pytest.raises(ValueError, match="unsupported"):
        DocumentationLookup("query-x", "x", "hint", relation="internal_hint")
    with pytest.raises(ValueError, match="public parent"):
        DocumentationLookup("query-x", "x", "canonical_intent", relation="audited_rewrite")
    with pytest.raises(ValueError, match="cannot derive"):
        DocumentationLookup("query-x", "x", "host_lookup", relation="host_lookup", public_parent_query_id="query-original")


def test_context_budget_is_a_product_invariant():
    budget = ContextBudget()
    assert budget.max_sources == 3
    assert budget.max_tokens == 800
    assert budget.bounded_tokens(2_000) == 800


def test_evidence_qualification_fails_closed_and_rejects_metadata_only_matches():
    rejected = qualify_evidence({"qualified": True}, query_id="query-original", visible_text="unrelated")
    assert not rejected.qualified
    metadata = qualify_evidence(
        {"qualified": True, "query_text": "project architecture"}, query_id="query-original",
        visible_text="docs/project-architecture.md\nArchitecture\nunrelated body", evidence_text="unrelated body",
    )
    assert not metadata.qualified
    assert metadata.reason == "insufficient_visible_match"


@pytest.mark.parametrize("override,reason", [
    ({"project_identity": "other"}, "wrong_project_identity"),
    ({"stale": True}, "stale_evidence"),
    ({"risk_flags": ["unsafe"]}, "unsafe_evidence"),
    ({"lifecycle_status": "superseded"}, "lifecycle_not_allowed"),
])
def test_raw_query_does_not_override_source_guards(override, reason):
    result = qualify_evidence(
        {"query_text": "project architecture", "qualified": True}, query_id="query-original",
        visible_text="Project architecture boundaries.",
        candidate={"project_identity": "repo", **override}, expected_project_identity="repo",
    )
    assert not result.qualified
    assert result.reason == reason


@pytest.mark.parametrize("failed_direct", [False, True])
def test_derived_merge_never_invents_successful_direct_coverage(failed_direct):
    from docmancer.docs.application.context_selection import merge_query_matches
    derived = {"query-original": {"qualified": True, "coverage_kind": "derived", "derived_from_query_ids": ["query-intent-1"]}}
    failed = {"query-original": {"qualified": False, "coverage_kind": "direct"}}
    for inputs in ((derived, failed), (failed, derived)) if failed_direct else ((derived,),):
        trace = merge_query_matches(*inputs)["query-original"]
        assert trace["coverage_kinds"] == ["derived"]
        assert trace["derived_from_query_ids"] == ["query-intent-1"]
