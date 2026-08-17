"""Split tests from test_unified_docs_context.py; shared helpers remain in the façade module."""
from tests import _shared_test_unified_docs_context as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_project_docs_questions_with_patch_term_prefixes_do_not_recommend_patch_constraints():
    questions = [
        "How do pytest fixtures work?",
        "How is this different from Context7?",
        "How do dependency fixtures interact with project docs?",
        "How does update_or_create work?",
        "Explain the dependency upgrade guide",
        "Describe delete cascade documentation",
    ]

    for question in questions:
        result = _service(FakeFacade()).get_docs_context(question, project_path="/repo", prepare_project_docs=False)
        assert not any(action.get("tool") == "get_patch_constraints" for action in result.next_actions)


def test_library_question_does_not_recommend_patch_constraints():
    result = _service(FakeFacade()).get_docs_context("How do I patch a FastAPI dependency?", library="fastapi")
    assert result.mode_selected == "library"
    assert not any(isinstance(action, dict) and action.get("tool") == "get_patch_constraints" for action in result.next_actions)


def test_placeholder_preflight_returns_partial_project_context_without_blind_sync():
    class PlaceholderPreflightFacade(FakeFacade):
        def bootstrap_project_docs(self, project_path, question=None) -> Any:
            self.calls.append(("bootstrap_project_docs", {"project_path": project_path, "question": question}))
            return type("Bootstrap", (), {
                "requires_confirmation": True,
                "warnings": [],
                "reason_code": "project_docs_preflight_confirmation_required",
                "confirmation_reason": "project_docs_preflight",
                "next_action": {
                    "type": "ask_user_to_update_or_confirm_project_docs",
                    "risk_codes": ["placeholder_project_doc"],
                    "tool_after_confirmation": "sync_project_docs",
                },
                "arguments_patch": {"project_path": project_path, "with_vectors": True},
            })()

    facade = PlaceholderPreflightFacade()
    result = _service(facade).get_docs_context("architecture", project_path="/repo", mode="project")

    assert result.context_available is True
    assert result.answer_available is False
    assert result.status == "success"
    assert result.requires_confirmation is False
    assert result.confirmation_reason is None
    assert not any(
        action.get("type") == "ask_user_to_update_or_confirm_project_docs"
        for action in result.next_actions
        if isinstance(action, dict)
    )
    assert result.lanes["project"].get("requires_confirmation") is None
    assert result.context_pack
    assert ("bootstrap_project_docs", {"project_path": "/repo", "question": "architecture"}) in facade.calls
    assert any(call[0] == "get_project_context" for call in facade.calls)


def test_project_mode_prioritizes_confirmed_sync_for_discovered_unindexed_docs():
    class UnindexedPreflightFacade(FakeFacade):
        def bootstrap_project_docs(self, project_path, question=None) -> Any:
            self.calls.append(("bootstrap_project_docs", {"project_path": project_path, "question": question}))
            inspect_result = type("Inspect", (), {
                "project_docs": {"found": [{"path": "README.md"}], "indexed": []},
            })()
            return type("Bootstrap", (), {
                "requires_confirmation": True,
                "warnings": [],
                "reason_code": "project_docs_preflight_confirmation_required",
                "confirmation_reason": "project_docs_preflight",
                "next_action": {
                    "type": "ask_user_to_update_or_confirm_project_docs",
                    "tool_after_confirmation": "sync_project_docs",
                },
                "arguments_patch": {"project_path": project_path, "with_vectors": True},
                "inspect_result": inspect_result,
            })()

    facade = UnindexedPreflightFacade()
    result = _service(facade).get_docs_context("architecture", project_path="/repo", mode="project")

    assert result.status == "confirmation_required"
    assert result.answer_available is False
    assert result.next_action == {
        "type": "prepare_docs",
        "tool": "prepare_docs",
        "arguments_patch": {"action": "sync_project_docs", "project_path": "/repo"},
        "requires_confirmation": True,
        "confirmation_reason": "project_docs_preflight",
    }
    assert _call_names(facade) == ["bootstrap_project_docs"]


def test_auto_dependency_question_selects_dependency():
    facade = FakeFacade()
    facade.project_context = replace(facade.project_context, context_pack=[{"doc_scope": "dependency", "source_class": "dependency_doc", "dependency": "riverpod", "title": "autoDispose", "content": "dep"}])
    result = _service(facade).get_docs_context("Riverpod autoDispose?", project_path="/repo", prepare_project_docs=False, allow_network=True)
    assert result.mode_selected == "dependency"
    assert result.routing["dependency_detected"] is True


def test_auto_project_and_dependency_evidence_selects_mixed():
    facade = FakeFacade()
    facade.project_context = replace(facade.project_context, context_pack=[*facade.project_context.context_pack, {"doc_scope": "dependency", "source_class": "dependency_doc", "dependency": "riverpod", "title": "autoDispose", "content": "dep"}])
    result = _service(facade).get_docs_context("How project uses Riverpod?", project_path="/repo", prepare_project_docs=False, allow_network=True)
    assert result.mode_selected == "mixed"
    assert result.routing["evidence_scopes"] == ["dependency", "project"]


def test_auto_does_not_use_new_keyword_classifier():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("Riverpod autoDispose keyword should not force dependency", project_path="/repo", prepare_project_docs=False)
    assert result.mode_selected == "project"
    assert facade.calls[0][1]["mode"] == "auto"


def test_explicit_project_mode_stays_project_only():
    facade = FakeFacade()
    _service(facade).get_docs_context("Riverpod autoDispose?", project_path="/repo", mode="project", prepare_project_docs=False)
    assert facade.calls[0][1]["mode"] == "project-only"


def test_explicit_dependency_mode_stays_dependency():
    facade = FakeFacade()
    _service(facade).get_docs_context("Riverpod autoDispose?", project_path="/repo", mode="dependency", prepare_project_docs=False)
    assert facade.calls[0][1]["mode"] == "deps-only"


def test_duplicate_source_is_not_contamination():
    facade = FakeFacade()
    facade.project_context.context_pack.append({"doc_scope": "project", "source_class": "project_doc", "path": "README.md", "title": "README", "content": "dup"})
    result = _service(facade).get_docs_context("Project?", project_path="/repo", prepare_project_docs=False)
    assert result.contamination["detected"] is False
    assert result.deduplication["dropped_count"] == 1


def test_foreign_library_source_is_contamination():
    facade = FakeFacade()
    facade.library_result = replace(_latest_success(), library_id="python:click@latest:web", library="click")
    result = _service(facade).get_docs_context("Depends?", library="fastapi")
    assert result.contamination["detected"] is True
    assert "wrong_library_id" in result.contamination["reason_codes"]


def test_foreign_project_source_is_contamination():
    facade = FakeFacade()
    facade.project_context = replace(facade.project_context, context_pack=[{"doc_scope": "project", "path": "/other/README.md", "title": "Other", "content": "foreign"}])
    result = _service(facade).get_docs_context("Project?", project_path="/repo", prepare_project_docs=False)
    assert result.contamination["detected"] is True
    assert "foreign_project" in result.contamination["reason_codes"]


def test_deduplication_and_contamination_can_coexist():
    facade = FakeFacade()
    facade.project_context = replace(facade.project_context, context_pack=[
        {"doc_scope": "project", "path": "README.md", "title": "README", "content": "a"},
        {"doc_scope": "project", "path": "README.md", "title": "README", "content": "b"},
        {"doc_scope": "project", "path": "/other/README.md", "title": "Other", "content": "foreign"},
    ])
    result = _service(facade).get_docs_context("Project?", project_path="/repo", prepare_project_docs=False)
    assert result.deduplication["dropped_count"] == 1
    assert result.contamination["dropped_count"] == 1


def test_latest_fallback_cannot_return_foreign_library_or_project_docs():
    facade = FakeFacade()
    foreign_latest = DocsResult(
        library_id="python:click@latest:web",
        library="click",
        version="latest",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning=None,
        last_refreshed_at="now",
        results=[DocsChunk(title="Click", content="foreign", source="https://click.palletsprojects.com/", url="https://click.palletsprojects.com/", metadata={})],
        resolved_version="latest",
    )
    facade.get_docs_results = [_exact_unsupported(), foreign_latest]
    result = _service(facade).get_docs_context("Depends?", library="fastapi", ecosystem="python", version="0.115.0", allow_latest_fallback=True)
    assert result.context_pack == []
    assert result.contamination["detected"] is True
    assert "wrong_library_id" in result.contamination["reason_codes"]


def test_benchmark_contamination_ignores_duplicate_drops():
    from eval.live_mcp_context7_benchmark import NormalizedBenchmarkResult, compute_metrics

    result = NormalizedBenchmarkResult(
        provider="docatlas",
        provider_id="docatlas_preindexed",
        provider_mode="direct",
        mode="preindexed",
        case_id="unified_project_auto",
        query="q",
        suite="unified-context",
        status="success",
        latency_ms=1.0,
        setup_calls=1,
        sources=[],
        snippets=[],
        answer_text=None,
        warnings=[],
        reason_codes=["duplicate_source"],
        exact_version_used=None,
        contamination_hits=[],
        forbidden_source_hits=[],
        expected_source_hits=[],
        manual_review_required=False,
        deduplication_dropped_count=2,
    )
    metrics = compute_metrics([result])
    assert metrics["contamination_rate_all"] == 0.0
    assert metrics["deduplication_dropped_count"] == 2
