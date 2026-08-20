"""Split test module; helpers live in _shared_test_model_visible_projection.py."""
from tests.docs import _shared_test_model_visible_projection as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
from docmancer.docs.interfaces.mcp.context_tools import _bound_module_recovery_projection

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
    packet, evidence = _ready_patch_fixture()
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
    packet, evidence = _ready_patch_fixture()
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
    packet, evidence = _ready_patch_fixture(
        policy_content="The patch must preserve source IDs.",
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


@pytest.mark.parametrize("budget", [256, 300, 1_500, 2_000])
def test_oversized_insufficient_projection_uses_a_valid_terminal_fallback(budget):
    payload = {
        "status": "insufficient_evidence",
        "kind": "docs_answer",
        "missing": ["missing " * 2_000],
        "recommended_next_action": {
            "tool": "prepare_docs",
            "observations": {"unbounded": "value " * 2_000},
        },
        "answer_supported": False,
        "answer_available": False,
        "support_status": "insufficient_evidence",
        "missing_requirement_ids": [f"requirement-{index}" for index in range(100)],
        "requirements_hash": "a" * 64,
        "selector_config_hash": "b" * 64,
        "eligibility_contract_hash": "c" * 64,
        "candidate_trace_hash": "d" * 64,
        "selection_hash": "e" * 64,
        "assignment_hash": "f" * 64,
        "decision_hash": "0" * 64,
    }

    bound_insufficient_projection(payload, max_tokens=budget)

    assert estimate_projection_tokens(payload) <= budget
    assert "support_envelope" not in payload
    assert "missing_requirement_ids" not in payload
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=budget) == []


def test_module_recovery_keeps_action_and_one_complete_exact_path_at_tiny_budget():
    paths = [
        "packages/" + (f"very-long-module-segment-{index}/" * 7) + "auth"
        for index in range(8)
    ]
    payload = {
        "status": "insufficient_evidence",
        "kind": "docs_answer",
        "missing": ["No complete source-backed documentation answer is available." * 8],
        "recommended_next_action": {
            "tool": "docs_status",
            "type": "docs_status",
            "arguments_patch": {
                "action": "project",
                "details": True,
                "project_path": "/repo/project",
            },
            "requires_confirmation": False,
            "reason": "Inspect modules and retry.",
            "auto_execute": False,
        },
        "operational_reason_code": "module_ambiguous",
        "module_candidates": [
            {"module_path": path, "module_name": "auth", "module_type": "package"}
            for path in paths
        ],
        "answer_supported": False,
        "answer_available": False,
        "support_status": "insufficient_evidence",
        "reason_code": "required_evidence_missing",
        "decision_hash": "0" * 64,
        "estimated_tokens": 0,
    }

    _bound_module_recovery_projection(payload, max_tokens=256)
    bound_insufficient_projection(payload, max_tokens=256)

    visible_paths = [row["module_path"] for row in payload["module_candidates"]]
    assert visible_paths
    assert set(visible_paths) <= set(paths)
    assert all(not path.endswith("…") for path in visible_paths)
    assert payload["operational_reason_code"] == "module_ambiguous"
    assert payload["recommended_next_action"]["tool"] == "docs_status"
    assert payload["recommended_next_action"]["arguments_patch"] == {
        "action": "project",
        "details": True,
        "project_path": "/repo/project",
    }
    assert estimate_projection_tokens(payload) <= 256
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=256) == []


def test_bounded_projection_keeps_audit_envelope_when_it_fits():
    payload = {
        "status": "insufficient_evidence",
        "kind": "docs_answer",
        "missing": ["No source is available."],
        "answer_supported": False,
        "answer_available": False,
        "support_status": "insufficient_evidence",
        "decision": "insufficient_evidence",
        "reason_code": "required_evidence_missing",
        "missing_requirement_ids": [],
        "satisfied_requirement_ids": [],
        "mandatory_requirement_ids": [],
        "mandatory_coverage": 0.0,
        "evidence_coverage": 0.0,
        "selected_evidence_ids": [],
        "requirements_hash": "1" * 64,
        "selector_config_hash": "2" * 64,
        "eligibility_contract_hash": "3" * 64,
        "candidate_trace_hash": "4" * 64,
        "selection_hash": "5" * 64,
        "assignment_hash": "6" * 64,
        "decision_hash": "0" * 64,
    }

    bound_insufficient_projection(payload, max_tokens=300)

    assert estimate_projection_tokens(payload) <= 300
    assert payload["support_envelope"]["encoding"] == "zlib+base64url"
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=300) == []


def test_validator_rejects_inconsistent_insufficient_support_summary():
    payload = project_insufficient(
        kind="docs_answer", missing=["No source is available."],
        recommended_next_action=None, max_tokens=300,
    )
    payload.update({
        "answer_supported": True,
        "answer_available": True,
        "support_status": "ok",
    })
    payload["estimated_tokens"] = estimate_projection_tokens(payload)

    errors = validate_model_visible_projection(payload, snapshot={}, max_tokens=300)

    assert "insufficient evidence has inconsistent answer_supported" in errors
    assert "insufficient evidence has inconsistent answer_available" in errors
    assert "insufficient evidence has inconsistent support_status" in errors


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
    assert "mandatory_coverage" not in payload
    assert "selected_evidence_ids" not in payload
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
                "next_actions": [
                    {
                        "action": "search_project_sources",
                        "type": "search_local_source",
                        "tool": "code_search",
                        "handled_by": "coding_agent",
                        "requires_confirmation": False,
                        "repeat_docs_context": False,
                        "query_terms": ["SpeechSegmenter"],
                        "suggested_doc_paths": ["lib/speech_segmenter.dart"],
                    },
                    {
                        "tool": "prepare_docs",
                        "arguments_patch": {"action": "sync_project_docs", "project_path": "/repo"},
                    },
                ],
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
    assert payload["disposition"] == "search_local_source"
    assert payload["edit_ready"] is False
    assert payload["source_search_status"] == "required"
    assert payload["requires_confirmation"] is False
    assert payload["recommended_next_action"]["tool"] == "code_search"
    assert payload["recommended_next_action"]["repeat_docs_context"] is False
    assert payload["recommended_next_action"]["query_terms"] == ["SpeechSegmenter"]
    assert "sync_project_docs" not in str(payload)


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


def test_project_projection_reuses_canonical_selection_and_evidence_ids():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    question = "Explain CONFIG_KEY"
    candidate = {
        "stable_id": "project-config-witness",
        "source": "docs/config.md",
        "content": "CONFIG_KEY enables the documented behavior.",
    }
    selection = select_evidence(
        [candidate], question=question, config=docs_selection_config(800)
    )

    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "context_pack": [candidate],
            "selection_decision": selection,
        },
        canonical_selection=selection,
    )

    assert projection["status"] == "ok"
    assert projection["decision_hash"] == selection.support_decision.decision_hash
    assert projection["answer_evidence_ids"] == list(
        selection.support_decision.selected_evidence_ids
    )
    assert [source["evidence_id"] for source in projection["sources"]] == projection["answer_evidence_ids"]


def test_assignment_backed_canonical_support_overrides_legacy_answer_availability_heuristic():
    from docmancer.docs.application.evidence_selection import build_requirements, project_docs_selection_config, select_evidence

    question = "What is the documented workflow?"
    candidate = {
        "stable_id": "workflow-witness",
        "source": "docs/workflow.md",
        "content": "The documented workflow is: run get_docs_context, follow prepare_docs, then retry the original question.",
    }
    requirements = build_requirements(
        question,
        public_requirements=["get_docs_context", "prepare_docs"],
        profile="project_docs_answer",
    )
    selection = select_evidence(
        [candidate], question=question, config=project_docs_selection_config(800),
        requirements=requirements,
    )

    projection, snapshot = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "answer_available": False,
            "answer_type": "partial_navigational",
            "selection_profile": "project_docs_answer",
            "context_pack": [candidate],
        },
        canonical_selection=selection,
    )

    assert selection.support_decision.answer_supported is True
    assert projection["status"] == "ok"
    assert projection["answer_evidence_ids"] == ["workflow-witness"]
    assert validate_model_visible_projection(
        projection,
        snapshot=snapshot,
        max_tokens=800,
        canonical_selection=selection,
    ) == []


def test_empty_assignment_canonical_selection_cannot_override_partial_retrieval():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    candidate = {
        "stable_id": "workflow-heading",
        "source": "docs/workflow.md",
        "content": "Workflow",
    }
    selection = select_evidence(
        [candidate], question="What is the documented workflow?", config=docs_selection_config(800),
    )

    projection, _ = project_docs_answer(
        question="What is the documented workflow?",
        retrieval={
            "status": "success",
            "answer_available": False,
            "answer_type": "partial_navigational",
            "context_pack": [candidate],
        },
        canonical_selection=selection,
    )

    assert selection.assignments == ()
    assert projection["status"] == "insufficient_evidence"


def test_docs_selector_accounts_for_serialized_projection_cost():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    candidates = [
        {
            "stable_id": f"source-{index}",
            "source": f"docs/source-{index}.md",
            "title": f"Source {index}",
            "relevance_score": 1.0 - index / 10,
            "content": " ".join(
                f"documented_{index}_{word}" for word in range(24)
            ),
        }
        for index in range(1, 4)
    ]
    selection = select_evidence(
        candidates,
        question="Summarize the documented facts",
        config=docs_selection_config(800),
    )

    projection, snapshot = project_docs_answer(
        question="Summarize the documented facts",
        retrieval={"status": "success", "context_pack": candidates},
        canonical_selection=selection,
    )

    assert selection.status == "ok"
    assert len(selection.selected_candidates) < len(candidates)
    # Generic selection has no claim assignments and cannot become a docs answer.
    assert projection["status"] == "insufficient_evidence"
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []
