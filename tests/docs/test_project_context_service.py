"""Split test module; helpers live in _shared_test_project_context_service.py."""
from tests.docs import _shared_test_project_context_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_project_context_service_returns_selected_project_and_dependency_sections():
    facade = FakeProjectContextFacade()
    result = ProjectContextService(facade).get_project_context("/repo", "use go_router", tokens=1200, limit=3, allow_network=True)

    assert result.status == "success"
    assert result.tool == "get_project_context"
    assert {item["source_class"] for item in result.context_pack} == {"project_doc", "dependency_doc"}
    dependency_item = next(item for item in result.context_pack if item["source_class"] == "dependency_doc")
    assert dependency_item["source"]["source_class"] == "dependency_doc"
    assert dependency_item["source"]["library"] == "go_router"
    assert dependency_item["source_url"] == "https://pub.dev"
    assert result.metrics["source_classes"] == ["dependency_doc", "project_doc"]
    assert result.metrics["quality"]["query_intent"] == "how_to"
    assert result.answer_outline["query_intent"] == "how_to"
    assert result.reason == "trusted_context_available"
    assert result.trust_contract["policy"]["direct_webfetch"] == "forbidden"
    assert ("docs", "go_router", {"topic": "use go_router", "tokens": 1200, "ecosystem": None, "version": None, "project_path": "/repo"}) in facade.calls
    project_call = next(call for call in facade.calls if call[0] == "project")
    assert project_call[:3] == ("project", "/repo", "use go_router")
    assert project_call[3]["requirements"] is result.requirements
    assert {key: value for key, value in project_call[3].items() if key != "requirements"} == {
        "tokens": 1200, "limit": 12, "expand": None, "module": None,
        "module_path": None, "scope": None,
    }


def test_project_context_service_deps_only_skips_project_docs_and_marks_risk():
    facade = FakeProjectContextFacade()
    result = ProjectContextService(facade).get_project_context("/repo", "api", library="go_router", mode="deps-only", allow_network=True)

    assert not any(call[0] == "project" for call in facade.calls)
    assert result.project_docs is None
    assert result.dependency_docs is facade.dependency_docs
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["sources"]["risky"])


def test_dependency_inference_does_not_confuse_docs_mcp_surface_with_mcp_package():
    metadata = ProjectMetadata(
        project_path="/repo",
        dependencies=[DependencyObservation(ecosystem="pypi", package_name="mcp")],
    )

    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "What are the three public Docs MCP tools?"
    ) is None
    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "Which command starts the Docs MCP server?"
    ) is None
    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "What version of the mcp dependency is installed?"
    ) == "mcp"
    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "How do I use `mcp`?"
    ) == "mcp"


def test_dependency_inference_uses_token_boundaries_not_substrings():
    metadata = ProjectMetadata(
        project_path="/repo",
        dependencies=[DependencyObservation(ecosystem="pub", package_name="flutter_bloc")],
    )

    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "How does blocking behavior work?"
    ) is None
    assert ProjectContextService.dependency_mentioned_in_question(
        metadata, "How does flutter_bloc integrate with this project?"
    ) == "flutter_bloc"


def test_inferred_dependency_confirmation_cannot_suppress_supported_project_answer():
    assert _dependency_confirmation_blocks_local_answer(
        has_confirmation=True,
        explicit_dependency_requested=False,
        local_answer_available=True,
    ) is False
    assert _dependency_confirmation_blocks_local_answer(
        has_confirmation=True,
        explicit_dependency_requested=False,
        local_answer_available=False,
    ) is True
    assert _dependency_confirmation_blocks_local_answer(
        has_confirmation=True,
        explicit_dependency_requested=True,
        local_answer_available=True,
    ) is True


def test_auto_mode_inferred_dependency_cannot_hide_supported_local_docs_answer(monkeypatch):
    facade = FakeProjectContextFacade()
    facade.metadata = ProjectMetadata(
        project_path="/repo",
        dependencies=[DependencyObservation(ecosystem="pypi", package_name="mcp")],
    )
    text = (
        "The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, "
        "and `docs_status`."
    )
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="What are the three public Docs MCP tools?",
        results=[
            ProjectDocsChunk(
                title="Docs MCP public tools",
                heading_path="Docs MCP public tools",
                content=text,
                stable_chunk_id="docs-mcp-tools",
                parent_logical_id="parent:docs-mcp-tools",
                char_start=0,
                char_end=len(text),
                line_start=1,
                line_end=1,
                display_content_hash=hashlib.sha256(text.encode()).hexdigest(),
                source="/repo/docs/mcp-docs-server.md",
                url=None,
                path="docs/mcp-docs-server.md",
                authority="source_of_truth",
                metadata={"score": 1.0},
            )
        ],
        indexed_sources=[
            {"path": "docs/mcp-docs-server.md", "source": "/repo/docs/mcp-docs-server.md"}
        ],
        answer_available=True,
    )
    monkeypatch.setattr(
        ProjectContextService,
        "dependency_mentioned_in_question",
        staticmethod(lambda _metadata, _question: "mcp"),
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo",
        "What are the three public Docs MCP tools?",
        mode="auto",
        limit=2,
    )

    assert result.status == "success"
    assert result.answer_available is True
    assert result.reason == "typed_evidence_contract_satisfied"
    assert result.requires_confirmation is False
    assert result.confirmation_reason is None
    assert result.next_action == {}
    assert not any(call[0] == "docs" for call in facade.calls)


def test_project_context_budget_overflow_keeps_answer_when_retained_trusted_evidence_is_complete(monkeypatch):
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="MCP boundary owns transport contracts",
        results=[
                ProjectDocsChunk(
                    title="MCP boundary owns transport contracts",
                    heading_path="MCP boundary owns transport contracts",
                    content="The MCP boundary owns transport contracts and validates every public request and response.",
                    stable_chunk_id="boundary",
                    parent_logical_id="parent:boundary",
                    char_start=0,
                    char_end=89,
                    line_start=1,
                    line_end=1,
                    display_content_hash=hashlib.sha256(
                        b"The MCP boundary owns transport contracts and validates every public request and response."
                    ).hexdigest(),
                source="/repo/docs/adr/0001-mcp-boundary-contracts.md", url=None,
                path="docs/adr/0001-mcp-boundary-contracts.md", authority="source_of_truth",
                metadata={"score": 1.0},
            ),
            ProjectDocsChunk(
                title="Oversized appendix", content="appendix " * 200,
                source="/repo/docs/appendix.md", url=None, path="docs/appendix.md",
                metadata={"score": 0.01},
            ),
        ],
    )
    monkeypatch.setitem(
        ProjectContextService.get_project_context.__globals__["fit_stage_items"].__globals__["STAGE_BYTE_LIMITS"],
        "project_docs", 1200,
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo", "MCP boundary owns transport contracts", mode="project-only", limit=2,
    )

    assert [item["path"] for item in result.context_pack if item["source_class"] == "project_doc"] == [
        "docs/adr/0001-mcp-boundary-contracts.md"
    ]
    assert "retrieval_stage_budget_exceeded" in result.warnings
    assert result.diagnostics["retrieval_routing"]["stages"]["project_docs"]["status"] == "insufficient"
    assert result.answer_completeness["missing_terms"] == []
    assert result.answer_available is True
    assert result.reason == "typed_evidence_contract_satisfied"


def test_project_context_budget_overflow_stays_fail_closed_when_required_evidence_is_dropped(monkeypatch):
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query='How does the MCP boundary enforce "mandatory handshake"?',
        results=[
            ProjectDocsChunk(
                title="MCP boundary",
                content="The MCP boundary owns transport contracts but this summary omits protocol details.",
                source="/repo/docs/adr/0001-mcp-boundary-contracts.md", url=None,
                path="docs/adr/0001-mcp-boundary-contracts.md", authority="source_of_truth",
                metadata={"score": 1.0},
            ),
            ProjectDocsChunk(
                title="Mandatory handshake", heading_path="Mandatory handshake",
                content=("padding " * 200) + "The mandatory handshake is enforced before dispatch.",
                source="/repo/docs/adr/0002-handshake.md", url=None,
                path="docs/adr/0002-handshake.md", authority="source_of_truth",
                metadata={"score": 0.01},
            ),
        ],
    )
    monkeypatch.setitem(
        ProjectContextService.get_project_context.__globals__["fit_stage_items"].__globals__["STAGE_BYTE_LIMITS"],
        "project_docs", 1200,
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo", 'How does the MCP boundary enforce "mandatory handshake"?', mode="project-only", limit=2,
    )

    assert "retrieval_stage_budget_exceeded" in result.warnings
    assert result.answer_available is False
    assert result.answer_completeness["status"] != "exact"
    assert "mandatory handshake" in result.answer_completeness["missing_terms"]


def test_story_specific_project_context_missing_terms_is_partial_navigational():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query='Как реализовать кнопку "Вернуть в работу" для закрытой заявки и перевести её в "Активная"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="""
Help requests follow UI -> Cubit -> Service -> Repository -> API.
Relevant places include help_requests_screen, help_request_details_screen,
new_help_request_screen, ToastUtils, and routes.
""".strip(),
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo",
        'Как реализовать кнопку "Вернуть в работу" для закрытой заявки и перевести её в "Активная"?',
        mode="project-only",
    )

    assert result.answer_available is False
    assert result.reason == "partial_navigational_context"
    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["status"] == "partial"
    assert result.answer_completeness["source_search_required"] is True
    assert result.answer_completeness["source_search_status"] == "required"
    assert result.answer_completeness["disposition"] == "search_local_source"
    assert result.answer_completeness["edit_ready"] is True
    assert "Вернуть в работу" in result.answer_completeness["missing_terms"]
    assert "Активная" in result.answer_completeness["missing_terms"]
    source_action = result.recommended_next_actions[-1]
    assert source_action["action"] == "search_project_sources"
    assert source_action["tool"] == "code_search"
    assert source_action["handled_by"] == "coding_agent"
    assert source_action["requires_confirmation"] is False
    assert source_action["repeat_docs_context"] is False
    assert "help_request_details_screen" in source_action["suggested_symbols"]


def test_canonical_support_overrides_conflicting_legacy_recovery_fields():
    from types import SimpleNamespace

    result = derive_project_answer_completeness(
        question='How do I implement "missing action"?',
        context_pack=[{"content": "Architecture overview."}],
        answer_available=True,
        intent=SimpleNamespace(wants_code_symbols=False, broad=False),
        support_decision=SimpleNamespace(
            answer_supported=True,
            mandatory_coverage=1.0,
            mandatory_requirement_ids=("required",),
        ),
        assigned_requirement_ids=["required"],
    )

    completeness = result["answer_completeness"]
    assert completeness["legacy_diagnostics"]["source_search_required"] is True
    assert completeness["source_search_required"] is False
    assert completeness["source_search_status"] == "not_required"
    assert completeness["disposition"] == "answer"
    assert completeness["edit_ready"] is True
    assert result["recommended_next_actions"] == []


def test_source_backed_completeness_marks_local_search_completed():
    question = 'Where is "SpeechSegmenter" implemented?'
    result = evaluate_project_answer_completeness(
        question=question,
        context_pack=[{
            "source_class": "source_evidence",
            "path": "lib/speech_segmenter.dart",
            "content": "lib/speech_segmenter.dart:10: class SpeechSegmenter",
        }],
        answer_available=True,
        intent=classify_project_query_intent(question),
    )

    completeness = result["answer_completeness"]
    assert completeness["status"] == "exact"
    assert completeness["source_search_required"] is False
    assert completeness["source_search_status"] == "completed"
    assert completeness["disposition"] == "use_context"
    assert completeness["edit_ready"] is True
    assert result["recommended_next_actions"] == []


def test_missing_exact_source_files_require_local_search_even_without_docs_answer():
    question = "Inspect speech_segmenter.dart and wear_voice_session.dart"
    result = evaluate_project_answer_completeness(
        question=question,
        context_pack=[{
            "source_class": "source_evidence",
            "path": "lib/wear_voice_session.dart",
            "content": "lib/wear_voice_session.dart:10: class WearVoiceSession",
        }],
        answer_available=False,
        intent=classify_project_query_intent(question),
    )

    completeness = result["answer_completeness"]
    assert completeness["source_search_required"] is True
    assert completeness["source_search_status"] == "required"
    assert completeness["disposition"] == "search_local_source"
    assert result["recommended_next_actions"][0]["tool"] == "code_search"
    assert result["recommended_next_actions"][0]["repeat_docs_context"] is False


def test_generic_test_query_is_not_trusted():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="test",
        results=[ProjectDocsChunk(title="README_TEST_TSD", content="test helper documentation", source="/repo/README_TEST_TSD.md", url=None, path="README_TEST_TSD.md")],
    )

    result = ProjectContextService(facade).get_project_context("/repo", "test", mode="project-only")

    assert result.answer_available is False
    assert result.reason != "trusted_context_available"
    assert result.diagnostics["trust_decision"]["confidence"] == "low"


def test_project_context_stops_on_project_docs_preflight_confirmation():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="unread badge архитектура help_chat",
        status="confirmation_required",
        reason_code="project_docs_preflight_confirmation_required",
        next_action={"type": "ask_user_to_update_or_confirm_project_docs"},
        requires_confirmation=True,
        confirmation_reason="project_docs_preflight",
        arguments_patch={"project_path": "/repo"},
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="unread badge architecture content that should not be trusted until preflight is resolved",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            )
        ],
        diagnostics={"preflight": {"requires_confirmation": True, "risks": [{"code": "placeholder_project_doc"}]}},
        next_actions=[{"tool": "sync_project_docs", "requires_confirmation": True}],
        message="Project docs preflight requires confirmation.",
    )

    result = ProjectContextService(facade).get_project_context("/repo", "unread badge архитектура help_chat", mode="project-only")

    assert result.status == "confirmation_required"
    assert result.answer_available is False
    assert result.answer_type == "unavailable"
    assert result.reason == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.context_pack == []
    assert result.trust_contract["policy"]["reason_code"] == "project_docs_preflight_confirmation_required"


def test_project_context_drops_placeholder_readme_from_context_pack():
    project_docs = ProjectDocsResult(
        project_path="/repo",
        query="overview",
        results=[
            ProjectDocsChunk(
                title="Readme",
                content="TODO: Put a short description of the package here.\n\n```dart\nconst like = 'sample';\n```",
                source="/repo/README.md",
                url=None,
                path="README.md",
            ),
            ProjectDocsChunk(
                title="Architecture",
                content="The real architecture document describes request, unread badge, and chat module responsibilities.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            ),
        ],
    )

    pack = project_context_pack(question="unread badge architecture", project_docs=project_docs, dependency_docs=None)

    assert [item["path"] for item in pack] == ["ARCHITECTURE.md"]
    assert "sample" not in pack[0]["content"]


def test_project_context_relevance_gate_accepts_structured_code_snippets():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="How does ScanDoc camera take photos?",
        results=[
            ProjectDocsChunk(
                title="ScanDoc camera",
                content="""
Use the ScanDoc camera service from the WebView camera flow.

```dart
final photo = await ScanDocCameraService.takePhoto();
```
""".strip(),
                source="/repo/docs/SCANDOC_WEB_CAMERA_API_PLAN.md",
                url=None,
                path="docs/SCANDOC_WEB_CAMERA_API_PLAN.md",
                heading_path="ScanDoc camera API",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo",
        "How does ScanDocCameraService.takePhoto work?",
        mode="project-only",
    )

    assert result.status == "success"
    assert isinstance(result.context_pack[0]["snippet"], dict)
    assert result.context_pack[0]["snippet"]["code"] == "final photo = await ScanDocCameraService.takePhoto();"


def test_russian_architecture_query_prefers_architecture_docs_over_feature_plans():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="архитектура",
        results=[
            ProjectDocsChunk(
                title="OIDC browser fix",
                content="OIDC browser selection plan mentions architecture once but is scoped to external auth.",
                source="/repo/docs/EXTERNAL_OIDC_BROWSER_SELECTION_FIX_PLAN.md",
                url=None,
                path="docs/EXTERNAL_OIDC_BROWSER_SELECTION_FIX_PLAN.md",
            ),
                ProjectDocsChunk(
                    title="Architecture",
                    content="Архитектура проекта: UI -> application -> domain -> infrastructure.",
                    stable_chunk_id="architecture",
                    parent_logical_id="parent:architecture",
                    char_start=0,
                    char_end=len("Архитектура проекта: UI -> application -> domain -> infrastructure."),
                    line_start=1,
                    line_end=1,
                    display_content_hash=hashlib.sha256(
                        "Архитектура проекта: UI -> application -> domain -> infrastructure.".encode()
                    ).hexdigest(),
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            ),
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", "архитектура", mode="project-only")

    assert result.diagnostics["query_intent"] == "architecture"
    assert result.context_pack[0]["path"] == "ARCHITECTURE.md"
    assert result.diagnostics["trust_decision"]["reason"] == "partial_navigational_context"
    assert result.diagnostics["trust_decision"]["query_terms_missing"] == []


def test_architecture_query_injects_root_architecture_when_retrieval_misses_it(tmp_path):
    (tmp_path / "ARCHITECTURE.md").write_text(
        "Project architecture overview: UI -> application -> domain -> infrastructure.\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="архитектура",
        results=[
            ProjectDocsChunk(
                title="OIDC browser fix",
                content="OIDC browser selection plan mentions architecture once but is scoped to external auth.",
                source=str(tmp_path / "docs/EXTERNAL_OIDC_BROWSER_SELECTION_FIX_PLAN.md"),
                url=None,
                path="docs/EXTERNAL_OIDC_BROWSER_SELECTION_FIX_PLAN.md",
            ),
        ],
    )

    result = ProjectContextService(facade).get_project_context(str(tmp_path), "архитектура", mode="project-only")

    assert result.context_pack[0]["path"] == "ARCHITECTURE.md"
    assert result.project_docs is not None
    injected = next(chunk for chunk in result.project_docs.results if chunk.path == "ARCHITECTURE.md")
    assert injected.source_class == "project_file"
    assert injected.metadata["injection_policy"] == "root_reviewable_project_doc_after_preflight"


def test_explicit_document_locator_prevents_broad_architecture_injection(tmp_path):
    plan_path = "docs/IOS_TRUSTED_TIME_PLAN.md"
    (tmp_path / "docs").mkdir()
    (tmp_path / plan_path).write_text("Trusted time conventions use a 72-hour period.\n", encoding="utf-8")
    (tmp_path / "ARCHITECTURE.md").write_text("Unrelated architecture conventions.\n", encoding="utf-8")
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="conventions",
        results=[
            ProjectDocsChunk(
                title="Trusted time plan", content="Trusted time conventions use a 72-hour period.",
                source=str(tmp_path / plan_path), url=None, path=plan_path,
            ),
            ProjectDocsChunk(
                title="Architecture", content="Unrelated architecture conventions.",
                source=str(tmp_path / "ARCHITECTURE.md"), url=None, path="ARCHITECTURE.md",
            ),
        ],
        indexed_sources=[
            {"path": plan_path, "source": str(tmp_path / plan_path)},
            {"path": "ARCHITECTURE.md", "source": str(tmp_path / "ARCHITECTURE.md")},
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), f"In {plan_path}, explain the conventions", mode="project-only"
    )

    assert result.project_docs is not None
    assert {chunk.path for chunk in result.project_docs.results} == {plan_path}
    project_call = next(call for call in facade.calls if call[0] == "project")
    assert project_call[3]["evidence_path"] == plan_path
    assert result.requirements is result.selection_decision.requirements
    assert result.support_decision is result.selection_decision.support_decision
    assert any(
        requirement.kind == "evidence_path" and requirement.value == plan_path
        for requirement in result.requirements
    )
    assert set(result.support_decision.selected_evidence_ids) == {
        candidate.stable_id for candidate in result.selection_decision.selected_candidates
    }


def test_project_shadow_selection_marks_navigation_context_as_non_factual():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(project_path="/repo", query="missing fact", results=[])

    result = ProjectContextService(facade).get_project_context(
        "/repo", "Where is MissingFact implemented?", mode="project-only"
    )

    assert result.selection_decision is not None
    assert result.support_decision is result.selection_decision.support_decision
    assert result.support_decision.answer_supported is False


def test_architecture_query_only_injects_authoritative_catalog_candidates(tmp_path):
    (tmp_path / "README.md").write_text("# Unlisted readme\n", encoding="utf-8")
    (tmp_path / "handbook").mkdir()
    system_doc = tmp_path / "handbook" / "system.md"
    system_doc.write_text(
        "Project architecture overview: UI -> application -> domain -> infrastructure.\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.metadata = ProjectMetadata(
        project_path=str(tmp_path),
        docs_catalog_present=True,
        docs_catalog_valid=True,
    )
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="архитектура",
        results=[
            ProjectDocsChunk(
                title="Feature plan",
                content="A narrow feature plan that mentions architecture.",
                source=str(tmp_path / "feature.md"),
                url=None,
                path="feature.md",
            ),
        ],
        candidate_sources=[
            {
                "path": "handbook/system.md",
                "reason": "project_architecture",
                "doc_scope": "project",
                "description": "Whole-project architecture.",
                "authority": "source_of_truth",
                "lifecycle_status": "active",
                "impact_policy": "track",
            },
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "архитектура", mode="project-only"
    )

    assert result.project_docs is not None
    assert {chunk.path for chunk in result.project_docs.results} == {
        "feature.md",
        "handbook/system.md",
    }
    assert all(chunk.path != "README.md" for chunk in result.project_docs.results)
    injected = next(
        chunk for chunk in result.project_docs.results if chunk.path == "handbook/system.md"
    )
    assert injected.description == "Whole-project architecture."
    assert injected.authority == "source_of_truth"


def test_architecture_query_does_not_fall_back_when_catalog_is_invalid(tmp_path):
    (tmp_path / "ARCHITECTURE.md").write_text(
        "This guessed source must not bypass an invalid explicit catalog.\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.metadata = ProjectMetadata(
        project_path=str(tmp_path),
        docs_catalog_present=True,
        docs_catalog_valid=False,
    )
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="архитектура",
        results=[
            ProjectDocsChunk(
                title="Existing safe result",
                content="Existing indexed result retained for this isolated boundary test.",
                source=str(tmp_path / "existing.md"),
                url=None,
                path="existing.md",
            ),
        ],
        candidate_sources=[],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "архитектура", mode="project-only"
    )

    assert result.project_docs is not None
    assert all(chunk.path != "ARCHITECTURE.md" for chunk in result.project_docs.results)


def test_architecture_injection_excludes_historical_and_module_catalog_docs(tmp_path):
    for rel in ("active.md", "completed.md", "module.md"):
        (tmp_path / rel).write_text(f"# {rel}\nArchitecture details.\n", encoding="utf-8")
    facade = FakeProjectContextFacade()
    facade.metadata = ProjectMetadata(
        project_path=str(tmp_path),
        docs_catalog_present=True,
        docs_catalog_valid=True,
    )
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="architecture",
        results=[
            ProjectDocsChunk(
                title="Existing",
                content="Existing architecture result.",
                source=str(tmp_path / "existing.md"),
                url=None,
                path="existing.md",
            ),
        ],
        candidate_sources=[
            {"path": "active.md", "reason": "project_architecture", "doc_scope": "project", "lifecycle_status": "active"},
            {"path": "completed.md", "reason": "project_architecture", "doc_scope": "project", "lifecycle_status": "completed", "authority": "source_of_truth"},
            {"path": "module.md", "reason": "module_architecture", "doc_scope": "module", "lifecycle_status": "active", "authority": "source_of_truth"},
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "architecture", mode="project-only"
    )

    assert result.project_docs is not None
    assert {chunk.path for chunk in result.project_docs.results} == {"existing.md", "active.md"}
