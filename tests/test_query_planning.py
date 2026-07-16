from __future__ import annotations

from docmancer.retrieval.query_planning import (
    MAX_EXACT_TERMS,
    build_query_plan,
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


def test_query_plan_has_bounded_concept_query_and_typed_filters():
    plan = build_query_plan(
        "How can I configure the client retry behavior?",
        filters={
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
    assert plan.filters.exact_snapshot_required is True
    assert plan.filters.forbidden_sources == ("mirror.example",)


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
