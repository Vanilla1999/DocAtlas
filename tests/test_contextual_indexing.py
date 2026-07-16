from __future__ import annotations

import pytest

from docmancer.retrieval.contextual_indexing import (
    _canonical_url,
    build_context_prefix,
    embedding_input,
    extract_symbol_aliases,
    normalized_filter_metadata,
)
from docmancer.retrieval.contracts import CandidateHit, ContextConfig
from docmancer.retrieval.query_planning import build_query_plan, compile_backend_filters


def test_context_config_hash_is_canonical_and_limits_are_validated():
    first = ContextConfig(allowed_fields=("document_title", "heading_path"))
    second = ContextConfig(allowed_fields=("document_title", "heading_path"))

    assert first.config_hash == second.config_hash
    with pytest.raises(ValueError, match="cannot be negative"):
        ContextConfig(max_prefix_tokens=-1)
    with pytest.raises(ValueError, match="duplicates"):
        ContextConfig(allowed_fields=("heading_path", "heading_path"))


def test_filter_plan_parses_false_and_compiles_hard_constraints():
    plan = build_query_plan("query", filters={"exact_snapshot_required": "false"})
    assert plan.filters.exact_snapshot_required is False
    compiled = compile_backend_filters({
        "source_classes": ["project_doc"],
        "minimum_authority": "verified",
        "exact_snapshot_required": "true",
    })
    assert compiled["source_class"] == {"in": ["project_doc"]}
    assert compiled["docs_snapshot_exact"] is True
    assert "verified" in compiled["authority"]["in"]
    assert "community" not in compiled["authority"]["in"]


def test_malformed_url_port_is_rejected_without_raising():
    assert _canonical_url("https://example.com:not-a-port/docs") == ""


def test_context_prefix_is_deterministic_bounded_and_provenance_owned():
    metadata = {
        "title": "Client setup",
        "source_path": "docs/client.md",
        "library_name": "Example SDK",
        "resolved_version": "2.4.1",
        "authority": "official",
    }
    config = ContextConfig(max_prefix_bytes=220, max_prefix_tokens=55)
    first = build_context_prefix(
        metadata,
        heading_path=("Setup", "Client"),
        display_text="Call ExampleClient.connect() with CONFIG_KEY.",
        config=config,
    )
    second = build_context_prefix(
        dict(reversed(list(metadata.items()))),
        heading_path=("Setup", "Client"),
        display_text="Call ExampleClient.connect() with CONFIG_KEY.",
        config=config,
    )

    assert first == second
    assert len(first.text.encode("utf-8")) <= config.max_prefix_bytes
    assert first.token_estimate <= config.max_prefix_tokens
    assert all(field.provenance for field in first.fields)
    assert first.manifest()["content_hash"] == first.content_hash


def test_context_location_never_exposes_absolute_root_or_url_credentials():
    local = build_context_prefix(
        {"title": "Guide", "source_path": "/tmp/private/repo/docs/guide.md"},
        heading_path=(),
        display_text="body",
    )
    remote = build_context_prefix(
        {
            "title": "Guide",
            "canonical_url": "https://user:secret@example.com/docs/guide?q=token#part",
        },
        heading_path=(),
        display_text="body",
    )

    assert "/tmp/private" not in local.text
    assert "guide.md" in local.text
    assert "user" not in remote.text
    assert "secret" not in remote.text
    assert "q=token" not in remote.text
    assert "Location: https://example.com/docs/guide" in remote.text
    assert "Canonical Location:" not in remote.text


def test_catalog_description_requires_project_owned_source():
    external = build_context_prefix(
        {
            "title": "Guide",
            "source_class": "dependency_doc",
            "project_doc_description": "secret project routing hint",
        },
        heading_path=(),
        display_text="body",
    )
    string_false = build_context_prefix(
        {
            "title": "Guide",
            "project_docs": "false",
            "project_doc_description": "must stay hidden",
        },
        heading_path=(),
        display_text="body",
    )
    project = build_context_prefix(
        {
            "title": "Guide",
            "source_class": "project_file",
            "project_doc_description": "canonical migration runbook",
        },
        heading_path=(),
        display_text="body",
    )

    assert "secret project routing hint" not in external.text
    assert "must stay hidden" not in string_false.text
    assert "canonical migration runbook" in project.text


def test_alias_extraction_is_bounded_and_ignores_plain_words():
    aliases = extract_symbol_aliases(
        "Use FutureProvider.family with Namespace::Client, --dry-run, "
        "CONFIG_KEY, errors/ERR_42.md and ordinary words. " * 20
    )

    assert "FutureProvider.family" in aliases
    assert "Namespace::Client" in aliases
    assert "--dry-run" in aliases
    assert "ordinary" not in aliases
    assert len(aliases) <= 16
    assert sum(len(item.encode("utf-8")) for item in aliases) <= 512


def test_available_token_budget_drops_context_without_touching_body():
    prefix = build_context_prefix(
        {"title": "Very detailed document title", "source_path": "docs/guide.md"},
        heading_path=("Install",),
        display_text="verbatim body",
        available_tokens=0,
    )

    assert prefix.text == ""
    assert embedding_input(prefix, "verbatim body") == "verbatim body"
    assert prefix.truncated is True


def test_candidate_requires_stable_identity_and_positive_rank():
    with pytest.raises(ValueError, match="stable_child_id"):
        CandidateHit("", 1, None, "lexical", 1, None, "source")
    with pytest.raises(ValueError, match="component_rank"):
        CandidateHit("child-1", 1, None, "lexical", 0, None, "source")


def test_unknown_authority_is_not_embedding_noise_and_boolean_is_strict():
    prefix = build_context_prefix(
        {"title": "Guide", "authority": "unknown"},
        heading_path=(),
        display_text="body",
    )

    assert "Authority:" not in prefix.text
    assert normalized_filter_metadata({"docs_snapshot_exact": "false"})[
        "docs_snapshot_exact"
    ] == 0
    assert normalized_filter_metadata({"docs_snapshot_exact": "invalid"})[
        "docs_snapshot_exact"
    ] is None
