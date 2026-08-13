from __future__ import annotations

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.retrieval.query_planning import (
    MAX_EXACT_TERMS,
    build_query_plan,
    extract_document_locator,
    extract_exact_terms,
    compile_backend_filters,
    metadata_matches_filters,
)


def test_query_plan_is_deterministic_and_does_not_store_raw_query():
    query = "How do I use `Client.connect` with --dry-run and CONFIG_KEY?"
    first = build_query_plan(
        query,
        filters={"library_id": "sdk", "resolved_version": "2.4.1"},
        requested_lanes=("lexical", "dense"),
    )
    second = build_query_plan(
        query,
        filters={"resolved_version": "2.4.1", "library_id": "sdk"},
        requested_lanes=("lexical", "dense"),
    )

    assert first == second
    assert first.plan_hash
    assert first.original_query_hash
    assert query not in repr(first)
    assert {term.normalized_value for term in first.exact_terms} >= {
        "client.connect", "--dry-run", "config_key"
    }
    assert first.filters.library_id == "sdk"


def test_exact_term_extraction_is_bounded_and_classified():
    terms = extract_exact_terms(
        " ".join(f"--option-{index}" for index in range(40))
        + " ERR_42 docs/setup.md Namespace::Client"
    )

    assert len(terms) == MAX_EXACT_TERMS
    assert all(term.kind for term in terms)
    assert len({term.normalized_value for term in terms}) == len(terms)


def test_exact_term_extraction_does_not_treat_prose_as_config_or_path():
    terms = extract_exact_terms(
        "Keep the MCP fetch/index pipeline while updating CONFIG_KEY in docs/setup.md"
    )
    values = {term.value for term in terms}

    assert "MCP" not in values
    assert "fetch/index" not in values
    assert {"CONFIG_KEY", "docs/setup.md"} <= values


def test_path_term_suppresses_overlapping_symbol_and_config_terms():
    terms = extract_exact_terms("In docs/IOS_TRUSTED_TIME_PLAN.md, explain the policy")

    assert [(term.value, term.kind) for term in terms] == [
        ("docs/IOS_TRUSTED_TIME_PLAN.md", "path"),
    ]


def test_document_locator_requires_explicit_locative_language():
    assert extract_document_locator(
        "According to docs/IOS_TRUSTED_TIME_PLAN.md, what are the conventions?"
    ) == "docs/IOS_TRUSTED_TIME_PLAN.md"
    assert extract_document_locator(
        "Согласно docs/IOS_TRUSTED_TIME_PLAN.md, какой период политики?"
    ) == "docs/IOS_TRUSTED_TIME_PLAN.md"
    assert extract_document_locator(
        "Compare docs/old.md with docs/new.md before implementation"
    ) is None
    assert extract_document_locator("From `./docs/PLAN.md`, explain it.") == "docs/PLAN.md"
    assert extract_document_locator('In "ARCHITECTURE.md", explain it.') == "ARCHITECTURE.md"
    assert extract_document_locator("В ARCHITECTURE.md: что описано?") == "ARCHITECTURE.md"
    assert extract_document_locator("In docs/" + "x" * 241 + ".md, explain it") is None
    assert extract_document_locator("In docs/old.md and from docs/new.md, compare") is None


def test_query_plan_has_bounded_concept_query_and_typed_filters():
    plan = build_query_plan(
        "How can I configure the client retry behavior?",
        filters={
            "project_doc_path": "docs/PLAN.md",
            "source_classes": ["project_file", "official_doc"],
            "module_ids": ["runtime"],
            "exact_snapshot_required": True,
            "forbidden_sources": ["mirror.example"],
        },
        requested_lanes=("hybrid",),
    )

    assert len(plan.concept_queries) <= 3
    assert plan.concept_queries == ("configure client retry behavior",)
    assert plan.filters.source_classes == ("official_doc", "project_file")
    assert plan.filters.project_doc_path == "docs/PLAN.md"
    assert plan.filters.exact_snapshot_required is True
    assert plan.filters.forbidden_sources == ("mirror.example",)


def test_query_plan_preserves_the_canonical_requirement_set_and_uses_its_entities():
    requirements = build_requirements(
        "Compare create_task with gather and explain how the scheduled task result is obtained",
        profile="library_docs_answer",
        exact_snapshot_required=True,
        project_identity="project:example",
        module_id="runtime",
    )

    plan = build_query_plan(
        "Compare create_task with gather and explain how the scheduled task result is obtained",
        requirements=requirements,
    )

    assert plan.requirements is requirements
    assert plan.requirements_hash == requirements.requirements_hash
    assert requirements.query_requirement_spans
    assert {item.kind for item in requirements} >= {"exact_snapshot", "project_identity", "module_id"}
    assert {term.normalized_value for term in plan.exact_terms} >= {"create_task", "gather"}


def test_query_plan_binds_arbitrary_executed_filters_without_exposing_values():
    first = build_query_plan(
        "status query",
        filters={"status_code": "LIVE", "document_title_hash": {"in": {"b", "a"}}},
    )
    same = build_query_plan(
        "status query",
        filters={"document_title_hash": {"in": {"a", "b"}}, "status_code": "LIVE"},
    )
    changed = build_query_plan(
        "status query",
        filters={"status_code": "ARCHIVED", "document_title_hash": {"in": {"a", "b"}}},
    )

    assert first == same
    assert first.plan_hash != changed.plan_hash
    assert first.executed_filters_hash != changed.executed_filters_hash
    assert "LIVE" not in repr(first)


def test_verified_authority_does_not_admit_legal_and_forbidden_aliases_are_checked():
    compiled = compile_backend_filters({"minimum_authority": "verified"})
    assert "legal" not in compiled["authority"]["in"]
    assert "verified" in compiled["authority"]["in"]
    assert metadata_matches_filters(
        {"authority": "verified", "library_id": "sdk-v2"},
        {"minimum_authority": "verified", "forbidden_sources": ["other"]},
    )
    assert not metadata_matches_filters(
        {"authority": "verified", "library_id": "sdk-v2"},
        {"minimum_authority": "verified", "forbidden_sources": ["sdk-v2"]},
    )
