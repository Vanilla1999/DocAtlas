from __future__ import annotations

from copy import deepcopy

import pytest

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


def _decode_support_envelope(value):
    import base64
    import json
    import zlib

    encoded = value["data"]
    encoded += "=" * (-len(encoded) % 4)
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(encoded)))


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


def test_docs_answer_projects_content_snippet_dicts():
    retrieval = {
        "status": "success",
        "answer_available": True,
        "context_pack": [{
            "path": "docs/PATROL_TESTING.md",
            "heading_path": "Long-Lived Patrol Session",
            "snippet": {
                "content": "start_patrol_develop is READY after PASS or FAIL."
            },
            "content": "start_patrol_develop is READY after PASS or FAIL.",
        }],
    }

    projection, snapshot = project_docs_answer(
        question="When is start_patrol_develop READY?", retrieval=retrieval,
    )

    assert projection["status"] == "ok"
    assert projection["sources"][0]["path_or_url"] == "docs/PATROL_TESTING.md"
    assert projection["sources"][0]["snippet"] == "start_patrol_develop is READY after PASS or FAIL."
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path_or_url", "docs/foreign.md"),
        ("section", "Foreign section"),
        ("snippet", "unbound text"),
        ("version_binding", "999"),
        ("content_sha256", "0" * 64),
    ],
)
def test_docs_projection_rejects_every_mutated_source_field(field, value):
    projection, snapshot = project_docs_answer(
        question="How do I set RETRY_LIMIT?",
        retrieval={
            "status": "success",
            "answer_available": True,
            "primary_snippet": {
                "source": "docs/retries.md",
                "title": "Retries",
                "content": "Set RETRY_LIMIT=3.",
                "version": "2.0",
            },
        },
    )
    tampered = deepcopy(projection)
    tampered["sources"][0][field] = value
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)

    errors = validate_model_visible_projection(
        tampered, snapshot=snapshot, max_tokens=800
    )

    assert errors
    assert any(field in error or "hash" in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "evidence_id",
        "path_or_url",
        "section",
        "snippet",
        "version_binding",
        "content_sha256",
    ],
)
def test_docs_projection_rejects_deleted_source_fields(field):
    projection, snapshot = project_docs_answer(
        question="How do I set RETRY_LIMIT?",
        retrieval={
            "status": "success",
            "answer_available": True,
            "primary_snippet": {
                "source": "docs/retries.md",
                "content": "Set RETRY_LIMIT=3.",
            },
        },
    )
    tampered = deepcopy(projection)
    tampered["sources"][0].pop(field)
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)

    errors = validate_model_visible_projection(
        tampered, snapshot=snapshot, max_tokens=800
    )

    assert errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "src/foreign.py"),
        ("symbol_or_section", "Foreign.run"),
        ("authority", "canonical"),
        ("instruction_trust", "scoped_agent_policy"),
        ("scope", "/foreign"),
        ("version_binding", "999"),
        ("content_sha256", "0" * 64),
    ],
)
def test_patch_projection_rejects_every_mutated_source_field(field, value):
    evidence = [{
        "path": "AGENTS.md",
        "heading_path": "Rules",
        "authority": "canonical",
        "repository_authority": "explicit_agent_policy",
        "instruction_trust": "scoped_agent_policy",
        "scope_verified": True,
        "policy_scope": "/project",
        "content": (
            "The patch must preserve source IDs.\n"
            "Run pytest tests/docs/test_mcp_boundary.py."
        ),
    }]
    packet = build_action_packet(
        question="Implement canonical projection",
        context_pack=evidence,
        project_path="/project",
    )
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=evidence
    )
    original = projection["sources"][0][field]
    tampered = deepcopy(projection)
    tampered["sources"][0][field] = (
        value if value != original else f"mutated-{value}"
    )
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)

    errors = validate_model_visible_projection(
        tampered, snapshot=snapshot, max_tokens=1_500
    )

    assert errors
    assert any(field in error or "hash" in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "evidence_id",
        "path",
        "symbol_or_section",
        "authority",
        "instruction_trust",
        "scope",
        "version_binding",
        "content_sha256",
    ],
)
def test_patch_projection_rejects_deleted_source_fields(field):
    evidence = [{
        "path": "AGENTS.md",
        "heading_path": "Rules",
        "authority": "canonical",
        "repository_authority": "explicit_agent_policy",
        "instruction_trust": "scoped_agent_policy",
        "scope_verified": True,
        "policy_scope": "/project",
        "content": "The patch must preserve source IDs.",
    }]
    packet = build_action_packet(
        question="Implement canonical projection",
        context_pack=evidence,
        project_path="/project",
    )
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=evidence
    )
    tampered = deepcopy(projection)
    tampered["sources"][0].pop(field)
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)

    errors = validate_model_visible_projection(
        tampered, snapshot=snapshot, max_tokens=1_500
    )

    assert errors


def test_projection_rejects_unknown_source_field_after_estimate_refresh():
    projection, snapshot = project_docs_answer(
        question="What is the retry policy?",
        retrieval={
            "status": "success",
            "answer_available": True,
            "primary_snippet": {
                "source": "docs/retries.md",
                "content": "Retries are bounded.",
            },
        },
    )
    tampered = deepcopy(projection)
    tampered["sources"][0]["authority"] = "canonical"
    tampered["estimated_tokens"] = estimate_projection_tokens(tampered)

    assert "projection source contains unknown fields: authority" in (
        validate_model_visible_projection(
            tampered, snapshot=snapshot, max_tokens=800
        )
    )


def test_actionable_question_discloses_when_safe_evidence_is_not_actionable():
    projection, snapshot = project_docs_answer(
        question="How do I configure retries?",
        retrieval={
            "status": "success",
            "answer_available": True,
            "primary_snippet": {
                "source": "docs/safe.md",
                "content": "Keep retries bounded.",
            },
        },
    )

    assert projection["status"] == "ok"
    assert projection["answer"] == "Keep retries bounded."
    assert "does not provide a concrete configuration" in projection[
        "limitations"
    ][0]
    assert projection["omitted_counts"]["answer_details"] == 1
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800
    ) == []


@pytest.mark.parametrize(
    ("question", "snippet"),
    [
        ("How do I configure retries?", "Set RETRY_LIMIT=3."),
        (
            "How do I call WidgetClient.fetch_record?",
            "WidgetClient.fetch_record(record_id, timeout=5)",
        ),
        ("What is the retry policy?", "Keep retries bounded."),
    ],
)
def test_actionable_or_conceptual_answers_do_not_get_false_limitations(
    question, snippet
):
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "answer_available": True,
            "primary_snippet": {"source": "docs/retries.md", "content": snippet},
        },
    )

    assert "limitations" not in projection
    assert "answer_details" not in projection["omitted_counts"]


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


def test_insufficient_projection_preserves_bounded_inspection_decision_context():
    payload = project_insufficient(
        kind="docs_answer",
        missing=["The registered documentation produced no usable evidence."],
        recommended_next_action={
            "tool": "prepare_docs",
            "type": "prepare_docs",
            "arguments_patch": {
                "action": "inspect_docs_target",
                "target": {"library": "sample", "docs_url": "https://docs.example/api/"},
                "max_pages": 3,
            },
            "observations": {"source_status": "partial", "indexed_chunks": 0},
            "security_scope": {"allowed_domains": ["docs.example"], "scope_expansion_allowed": False},
            "decision_options": [
                {"id": "inspect_registered_scope", "requires_confirmation": True},
                {"id": "stop_with_partial_results", "requires_confirmation": False},
            ],
            "agent_question": "Inspect the registered scope without indexing?",
            "requires_confirmation": True,
        },
    )

    action = payload["recommended_next_action"]
    assert action["arguments_patch"]["action"] == "inspect_docs_target"
    assert action["observations"]["indexed_chunks"] == 0
    assert action["security_scope"]["scope_expansion_allowed"] is False
    assert action["decision_options"][0]["id"] == "inspect_registered_scope"
    assert action["auto_execute"] is False
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=300) == []


def test_projection_intent_distinguishes_change_from_documentation_question():
    assert projection_kind("Implement the FooClient factory") == "patch_context"
    assert projection_kind("Create FooService") == "patch_context"
    assert projection_kind("Напиши новый обработчик") == "patch_context"
    assert projection_kind("Исправь обработку ошибок") == "patch_context"
    assert projection_kind("How do I use FooClient.create?") == "docs_answer"
    assert projection_kind("What is the retry policy?") == "docs_answer"


def test_library_public_call_without_canonical_decision_fails_closed():
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

    assert payload["status"] == "insufficient_evidence"
    assert payload["kind"] == "docs_answer"
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["reason_code"] == "canonical_support_decision_missing"
    assert payload["mandatory_coverage"] == 0.0
    assert payload["selected_evidence_ids"] == []
    assert "answer" not in payload
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


def test_docs_projection_uses_the_canonical_requirement_set_without_rebuilding_it():
    from docmancer.docs.application.evidence_selection import build_requirements

    requirements = build_requirements(
        "How are retries handled?", public_requirements=["bounded retry"],
    )
    diagnostics = {}
    payload, _ = project_docs_answer(
        question="How are retries handled?",
        retrieval={
            "status": "success", "answer_available": True, "requirements": requirements,
            "context_pack": [{"source": "docs/retry.md", "content": "Use bounded retry for failures."}],
        },
        selection_diagnostics=diagnostics,
    )

    assert payload["status"] == "ok"
    assert diagnostics["requirements_hash"] == requirements.requirements_hash


def test_docs_projection_preserves_underlying_support_decision_fields():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare async with launch and explain how to obtain the async result"
    candidate = {"source": "docs/launch.md", "content": "launch starts fire-and-forget work."}
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )
    full_support = selection.support_decision.as_payload()
    support = {
        key: full_support[key]
        for key in (
            "answer_supported", "answer_available", "support_status", "reason_code",
            "missing_requirement_ids", "satisfied_requirement_ids",
            "mandatory_requirement_ids", "mandatory_coverage", "evidence_coverage",
            "selected_evidence_ids", "decision_hash",
        )
    }
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "context_available": True,
            "answer_available": False, "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate], **support,
        },
    )

    assert {key: projection[key] for key in support} == support
    assert projection["status"] == "insufficient_evidence"


def test_supported_library_projection_shares_decision_and_visible_evidence_ids():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    candidate = {
        "stable_id": "runtime-witness",
        "source": "docs/runtime.md",
        "content": (
            "Compare create_task with gather; obtain the scheduled task result "
            "from create_task."
        ),
    }
    selection = select_evidence(
        [candidate],
        question=question,
        config=library_docs_selection_config(800),
    )

    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection,
            "context_pack": [candidate],
        },
    )

    selected_ids = list(selection.support_decision.selected_evidence_ids)
    assert projection["status"] == "ok"
    assert [source["evidence_id"] for source in projection["sources"]] == selected_ids
    assert projection["answer_evidence_ids"] == selected_ids
    assert projection["selected_evidence_ids"] == selected_ids


def test_tiny_budget_preserves_complete_canonical_support_envelope():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    candidate = {
        "stable_id": "runtime-witness",
        "source": "docs/runtime.md",
        "content": (
            "Compare create_task with gather; obtain the scheduled task result "
            "from create_task."
        ),
    }
    selection = select_evidence(
        [candidate],
        question=question,
        config=library_docs_selection_config(800),
    )
    retrieval = {
        "status": "success",
        "answer_available": True,
        "selection_profile": "library_docs_answer",
        "selection_decision": selection,
        "context_pack": [candidate],
    }

    normal, _ = project_docs_answer(
        question=question, retrieval=retrieval, max_tokens=800,
    )
    tiny, _ = project_docs_answer(
        question=question, retrieval=retrieval, max_tokens=100,
    )
    expected_support = selection.support_decision.as_payload()

    assert {key: normal[key] for key in expected_support} == expected_support
    assert tiny["status"] == "insufficient_evidence"
    assert estimate_projection_tokens(tiny) <= 300
    assert validate_model_visible_projection(tiny, snapshot={}, max_tokens=300) == []
    assert _decode_support_envelope(tiny["support_envelope"]) == expected_support


def test_library_projection_materializes_display_text_only_witness():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    text = "Compare create_task with gather; obtain the scheduled task result from create_task."
    candidate = {
        "stable_chunk_id": "display-only-witness",
        "parent_logical_id": "runtime",
        "source": "docs/runtime.md",
        "display_text": text,
        "display_content_hash": __import__("hashlib").sha256(text.encode()).hexdigest(),
        "authority": "official",
        "docs_exactness": "exact",
        "version": "3.12",
        "retrieval_rank": 1,
        "score": 1.0,
    }
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )

    projection, snapshot = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate],
        },
    )

    expected_ids = list(selection.support_decision.selected_evidence_ids)
    assert selection.support_decision.answer_supported is True
    assert [source["evidence_id"] for source in projection["sources"]] == expected_ids
    assert projection["answer_evidence_ids"] == expected_ids
    assert projection["selected_evidence_ids"] == expected_ids
    assert projection["sources"][0]["snippet"] == text
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_library_projection_does_not_add_language_specific_code_policy():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Show code comparing async with launch and explain how to obtain the async result"
    candidate = {
        "stable_id": "coroutine-witness", "source": "docs/coroutines.md",
        "content": "async differs from launch; obtain the async result with await().",
    }
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate],
        },
    )

    assert "required_code_groups" not in projection


def test_generic_projection_retains_compact_canonical_evidence_id():
    projection, _ = project_docs_answer(
        question="What is the retry policy?",
        retrieval={
            "status": "success", "answer_available": True,
            "primary_snippet": {
                "stable_id": "selector-owned-long-stable-chunk-identifier",
                "source": "docs/retries.md", "content": "Retries are bounded.",
            },
        },
    )

    assert projection["sources"][0]["evidence_id"].startswith("ev-")


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
