from __future__ import annotations

from copy import deepcopy

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import (
    FORBIDDEN_MODEL_KEYS,
    canonical_projection_bytes,
    estimate_projection_tokens,
    project_docs_answer,
    project_insufficient,
    project_patch_context,
    projection_kind,
    sanitized_projection_manifest,
    validate_model_visible_projection,
)
from docmancer.mcp.docs_server import call_docs_tool_payload


def _forbidden_occurrences(value):
    if isinstance(value, dict):
        return [key for key, child in value.items() if key in FORBIDDEN_MODEL_KEYS] + [
            found for child in value.values() for found in _forbidden_occurrences(child)
        ]
    if isinstance(value, list):
        return [found for child in value for found in _forbidden_occurrences(child)]
    return []


def test_docs_answer_is_deterministic_deduplicated_hashed_and_bounded():
    snippet = {
        "source": "https://example.test/api",
        "heading_path": "Create client",
        "code": "client = FooClient.create()",
        "version": "2.1.0",
        "surrounding_context": "raw text must remain internal",
    }
    retrieval = {
        "status": "success",
        "answer_available": True,
        "answer": "Create the client with the cited factory.",
        "primary_snippet": snippet,
        "primary_snippets": [deepcopy(snippet)],
        "supporting_snippets": [
            {"source": "https://example.test/config", "title": "Config", "content": "Set timeout=5.", "version": "2.1.0"},
            {"source": "https://example.test/retry", "title": "Retry", "content": "Retry once.", "version": "2.1.0"},
            {"source": "https://example.test/extra", "title": "Extra", "content": "Optional.", "version": "2.1.0"},
        ],
        "context_pack": [{"path": "raw.md", "content": "must not cross"}],
        "retrieval_diagnostics": {"query": "secret"},
    }

    first, snapshot = project_docs_answer(question="How do I create FooClient?", retrieval=retrieval)
    second, second_snapshot = project_docs_answer(question="How do I create FooClient?", retrieval=retrieval)

    assert canonical_projection_bytes(first) == canonical_projection_bytes(second)
    assert snapshot == second_snapshot
    assert first["kind"] == "docs_answer"
    assert first["status"] == "ok"
    # The exact FooClient identifier is fully supported by one span; Task 42
    # must not fill the remaining budget with unrelated optional sources.
    assert len(first["sources"]) == 1
    assert first["omitted_counts"]["sources"] >= 1
    assert estimate_projection_tokens(first) <= 800
    assert not _forbidden_occurrences(first)
    manifest = sanitized_projection_manifest(snapshot)
    assert len(manifest) == 1
    assert all("source" not in row and "snippet" not in row for row in manifest)
    assert validate_model_visible_projection(first, snapshot=snapshot, max_tokens=800) == []

    tampered = deepcopy(first)
    tampered["sources"][0]["content_sha256"] = "0" * 64
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)
    assert "projection source hash does not match" in " ".join(
        validate_model_visible_projection(tampered, snapshot=snapshot, max_tokens=800)
    )


def test_patch_projection_retains_validated_citations_without_raw_evidence():
    evidence = [{
        "path": "AGENTS.md",
        "heading_path": "Rules",
        "authority": "canonical",
        "repository_authority": "explicit_agent_policy",
        "instruction_trust": "scoped_agent_policy",
        "scope_verified": True,
        "policy_scope": "/project",
        "content": "The patch must preserve source IDs.\nRun pytest tests/docs/test_mcp_boundary.py.",
    }]
    packet = build_action_packet(
        question="Implement canonical projection", context_pack=evidence, project_path="/project",
    )
    assert validate_action_packet(packet, evidence_items=evidence, project_path="/project") == []

    projection, snapshot = project_patch_context(packet=packet, evidence_items=evidence)

    assert projection["kind"] == "patch_context"
    assert projection["status"] in {"ok", "truncated"}
    assert projection["invariants"][0]["evidence_ids"]
    assert not _forbidden_occurrences(projection)
    assert estimate_projection_tokens(projection) <= 1_500
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=1_500) == []

    for field in ("path", "symbol_or_section"):
        tampered = deepcopy(projection)
        tampered["sources"][0][field] = "tampered-value"
        tampered["estimated_tokens"] = estimate_projection_tokens(tampered)
        assert (
            f"projection source {field} does not match the internal snapshot"
            in validate_model_visible_projection(
                tampered, snapshot=snapshot, max_tokens=1_500
            )
        )


def test_insufficient_projection_is_fail_closed_and_at_most_300_tokens():
    payload = project_insufficient(
        kind="patch_context",
        missing=["Missing canonical evidence. " * 20, "Missing target evidence."],
        recommended_next_action={
            "tool": "prepare_docs",
            "arguments_patch": {"action": "sync_project_docs", "project_path": "/repo"},
            "requires_confirmation": True,
        },
    )

    assert payload["status"] == "insufficient_evidence"
    assert "implementation_guidance" not in payload
    assert "targets" not in payload
    assert payload["recommended_next_action"]["auto_execute"] is False
    assert estimate_projection_tokens(payload) <= 300
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=300) == []


def test_projection_intent_distinguishes_change_from_documentation_question():
    assert projection_kind("Implement the FooClient factory") == "patch_context"
    assert projection_kind("Create FooService") == "patch_context"
    assert projection_kind("Напиши новый обработчик") == "patch_context"
    assert projection_kind("Исправь обработку ошибок") == "patch_context"
    assert projection_kind("How do I use FooClient.create?") == "docs_answer"
    assert projection_kind("What is the retry policy?") == "docs_answer"


def test_normal_public_call_returns_only_one_canonical_projection():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "status": "success",
                "answer_available": True,
                "answer": "Use FooClient.create().",
                "primary_snippet": {
                    "source": "https://example.test/foo/2.1",
                    "title": "Create",
                    "code": "FooClient.create()",
                    "version": "2.1",
                },
                "context_pack": [{"source": "https://example.test/foo/2.1", "content": "raw full document"}],
                "retrieval_diagnostics": {"candidate_count": 20},
            }

    payload = call_docs_tool_payload(
        "get_docs_context",
        {"question": "How do I create FooClient?", "library": "foo", "version": "2.1"},
        Facade(),
    )

    assert payload["status"] == "ok"
    assert payload["kind"] == "docs_answer"
    assert set(payload) == {
        "status", "kind", "answer", "answer_evidence_ids", "sources", "omitted_counts", "estimated_tokens",
    }
    assert not _forbidden_occurrences(payload)


def test_partial_navigational_docs_result_fails_closed():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "status": "success",
                "answer_available": True,
                "answer": "You may safely change the API.",
                "answer_type": "partial_navigational",
                "answer_completeness": {"status": "partial", "source_search_required": True},
                "primary_snippet": {
                    "path": "docs/navigation.md",
                    "title": "Navigation",
                    "content": "This page only points to source.",
                },
                "lanes": {"project": {"status": "partial_success"}},
            }

    payload = call_docs_tool_payload(
        "get_docs_context",
        {"question": "How should I change the API?", "project_path": "/repo"},
        Facade(),
    )

    assert payload["status"] == "insufficient_evidence"
    assert "answer" not in payload


def test_docs_projection_forwards_host_requirements_and_scope_to_selector():
    retrieval = {
        "status": "success",
        "answer_available": True,
        "project_identity": "acme/project",
        "module_id": "runtime",
        "public_requirements": ["bounded retry"],
        "context_pack": [{
            "source": "docs/retry.md",
            "content": "Use bounded retry for failures.",
            "project_identity": "acme/project",
            "module_id": "runtime",
        }],
    }
    ok, _ = project_docs_answer(question="How are retries handled?", retrieval=retrieval)
    missing_scope = deepcopy(retrieval)
    missing_scope["context_pack"][0].pop("module_id")
    blocked, _ = project_docs_answer(
        question="How are retries handled?", retrieval=missing_scope
    )

    assert ok["status"] == "ok"
    assert blocked["status"] == "insufficient_evidence"


def test_patch_projection_binds_duplicate_path_sections_by_exact_evidence_id():
    evidence = [
        {
            "path": "src/a.py", "heading_path": "same", "source_class": "source_code",
            "authority": "canonical", "instruction_trust": "scoped_agent_policy",
            "content": "Must preserve FIRST behavior.", "snippet": "FIRST",
        },
        {
            "path": "src/a.py", "heading_path": "same", "source_class": "source_code",
            "authority": "canonical", "instruction_trust": "scoped_agent_policy",
            "content": "Must preserve SECOND behavior.", "snippet": "SECOND",
        },
    ]
    packet = build_action_packet(question="Fix a", context_pack=evidence, project_path="/repo")
    assert validate_action_packet(packet, evidence_items=evidence, project_path="/repo") == []

    projection, snapshot = project_patch_context(packet=packet, evidence_items=evidence)

    contents = [snapshot[row["evidence_id"]]["source"]["content"] for row in packet["source_of_truth"]]
    assert contents == ["Must preserve FIRST behavior.", "Must preserve SECOND behavior."]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=1_500) == []
