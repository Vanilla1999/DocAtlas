from __future__ import annotations

import pytest

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
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
    assert "source_of_truth" in compiled["authority"]["in"]
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


def test_generation_reserves_catalog_description_token_budget(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "index.db")
    agent = DocmancerAgent(config=config)
    description = "canonical migration runbook"
    content = "# Guide\n\n" + "bounded project documentation content " * 600

    sections = agent.ingest_documents([
        Document(
            source="guide.md",
            content=content,
            metadata={
                "format": "markdown",
                "source_class": "project_file",
                "project_docs": True,
                "project_doc_description": description,
            },
        ),
    ], with_vectors=False)

    assert sections > 0
    generation = agent.store.generation_info()
    assert generation is not None
    assert generation["status"] == "active"
    with agent.store._connect() as connection:
        rows = connection.execute(
            "SELECT retrieval_text, retrieval_token_estimate "
            "FROM retrieval_children WHERE generation_id = ?",
            (generation["generation_id"],),
        ).fetchall()
    assert rows
    assert all(row["retrieval_text"].count(description) == 2 for row in rows)
    assert all(row["retrieval_token_estimate"] <= 512 for row in rows)


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


@pytest.mark.parametrize("authority", ["source_of_truth", "supporting"])
def test_project_catalog_authority_survives_filter_normalization(authority):
    normalized = normalized_filter_metadata({"project_doc_authority": authority})

    assert normalized["authority"] == authority
