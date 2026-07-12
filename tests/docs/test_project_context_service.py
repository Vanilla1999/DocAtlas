from __future__ import annotations

from docmancer.docs.application.project_context_service import ProjectContextService, context_pack_snippet, project_context_metrics, project_context_pack, project_why_selected
from docmancer.docs.interfaces.mcp.project_tools import _compact_project_context
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.models import DependencyObservation, DocsChunk, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata


class FakeProjectContextFacade:
    def __init__(self):
        self.metadata = ProjectMetadata(
            project_path="/repo",
            dependencies=[DependencyObservation(ecosystem="pub", package_name="go_router")],
        )
        self.project_docs = ProjectDocsResult(
            project_path="/repo",
            query="needle",
        results=[ProjectDocsChunk(title="Readme", content="needle content with enough words to be useful for the project context pack selection and stable regression testing across quality filters", source="/repo/README.md", url=None, path="README.md")],
            indexed_sources=[{"path": "README.md", "source": "/repo/README.md"}],
        )
        self.dependency_docs = DocsResult(
            library_id="pub/go_router/14/api",
            library="go_router",
            version="14.8.1",
            topic="needle",
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            results=[DocsChunk(title="GoRouter", content="go_router content with enough words to be useful for dependency documentation context selection and stable regression testing across quality filters", source="https://pub.dev", url="https://pub.dev")],
            requested_version="14.8.1",
            resolved_version="14.8.1",
            version_source="lockfile_exact",
            docs_exactness="exact",
            docs_binding_source="pub_dartdoc",
            confidence="high",
        )
        self.calls = []

    def read_project_metadata(self, project_path):
        self.calls.append(("metadata", project_path))
        return self.metadata

    def get_project_docs(self, project_path, question, **kwargs):
        self.calls.append(("project", project_path, question, kwargs))
        return self.project_docs

    def get_docs(self, library, **kwargs):
        self.calls.append(("docs", library, kwargs))
        return self.dependency_docs

    def _dependency_mentioned_in_question(self, metadata, question):
        return "go_router" if "go_router" in question else None


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
    assert ("project", "/repo", "use go_router", {"tokens": 1200, "limit": 3, "expand": None, "module": None, "module_path": None, "scope": None}) in facade.calls


def test_project_context_service_deps_only_skips_project_docs_and_marks_risk():
    facade = FakeProjectContextFacade()
    result = ProjectContextService(facade).get_project_context("/repo", "api", library="go_router", mode="deps-only", allow_network=True)

    assert not any(call[0] == "project" for call in facade.calls)
    assert result.project_docs is None
    assert result.dependency_docs is facade.dependency_docs
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["sources"]["risky"])


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
    assert "Вернуть в работу" in result.answer_completeness["missing_terms"]
    assert "Активная" in result.answer_completeness["missing_terms"]
    source_action = result.recommended_next_actions[-1]
    assert source_action["action"] == "search_project_sources"
    assert source_action["tool"] == "code_search"
    assert "help_request_details_screen" in source_action["suggested_symbols"]


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
                content="Project architecture overview: UI -> application -> domain -> infrastructure.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            ),
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", "архитектура", mode="project-only")

    assert result.diagnostics["query_intent"] == "architecture"
    assert result.context_pack[0]["path"] == "ARCHITECTURE.md"
    assert result.diagnostics["trust_decision"]["reason"] == "trusted_context_available"
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


def test_story_specific_project_context_with_only_docs_matched_terms_requires_source_search():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query='Как реализовать кнопку "Вернуть в работу" для закрытой заявки и перевести её в "Активная"?',
        results=[
            ProjectDocsChunk(
                title="Help request reopen story",
                content='Кнопка "Вернуть в работу" переводит закрытую заявку в статус "Активная" and shows ToastUtils feedback.',
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests > Reopen",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo",
        'Как реализовать кнопку "Вернуть в работу" для закрытой заявки и перевести её в "Активная"?',
        mode="project-only",
    )

    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["status"] == "partial"
    assert result.answer_completeness["source_search_required"] is True
    assert result.answer_completeness["missing_terms"] == ["Вернуть в работу", "Активная"]
    assert result.recommended_next_actions[-1]["action"] == "search_project_sources"


def test_project_context_includes_repo_map_lane_for_matching_source_files(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
import 'package:flutter/material.dart';

class HelpRequestDetailsScreen extends StatelessWidget {
  void reopenRequest() {
    final label = 'Вернуть в работу';
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        'Как реализовать кнопку "Вернуть в работу"?',
        mode="project-only",
    )

    repo_map_items = [item for item in result.context_pack if item["source_class"] == "repo_map"]
    assert [item["path"] for item in repo_map_items] == ["lib/help_request_details_screen.dart"]
    assert repo_map_items[0]["language"] == "dart"
    assert repo_map_items[0]["string_literals"] == ["Вернуть в работу"]
    source_evidence_items = [item for item in result.context_pack if item["source_class"] == "source_evidence"]
    assert len(source_evidence_items) == 1
    assert source_evidence_items[0]["evidence_class"] == "source_snippet"
    assert source_evidence_items[0]["path"] == "lib/help_request_details_screen.dart"
    assert source_evidence_items[0]["line_start"] == 5
    assert source_evidence_items[0]["snippet"] == "final label = 'Вернуть в работу';"
    assert "repo_map" in result.metrics["source_classes"]
    assert "source_evidence" in result.metrics["source_classes"]
    assert result.diagnostics["repo_map"]["selected_files"] == 1
    assert result.diagnostics["source_evidence"]["matched_terms"] == ["Вернуть в работу"]
    assert result.answer_type == "exact"
    assert result.answer_completeness["missing_terms"] == []


def test_project_context_includes_code_graph_lane_for_project_source_queries(tmp_path):
    lib = tmp_path / "lib"
    screens = lib / "screens"
    cubit = lib / "cubit"
    screens.mkdir(parents=True)
    cubit.mkdir(parents=True)
    (screens / "help_request_screen.dart").write_text(
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  void build() {
    HelpRequestsCubit();
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (cubit / "help_requests_cubit.dart").write_text("class HelpRequestsCubit {}\n", encoding="utf-8")
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query="Где используется HelpRequestsCubit?",
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help request screen uses cubit classes in the UI flow.",
                source=str(tmp_path / "README.md"),
                url=None,
                path="README.md",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        "Где используется HelpRequestsCubit?",
        mode="project-only",
    )

    source_classes = {item["source_class"] for item in result.context_pack}
    assert result.status == "success"
    assert {"repo_map", "source_evidence", "code_graph"}.issubset(source_classes)
    graph_items = [item for item in result.context_pack if item["source_class"] == "code_graph"]
    assert graph_items[0]["path"] == "lib/screens/help_request_screen.dart"
    assert "HelpRequestsCubit" in graph_items[0]["content"]
    assert "repo_map" in result.diagnostics
    assert "source_evidence" in result.diagnostics
    assert result.diagnostics["code_graph"]["selected_items"] >= 1
    assert result.diagnostics["code_graph"]["graph"]["node_count"] >= 1
    assert "references" in result.diagnostics["code_graph"]["edge_kinds"] or "imports" in result.diagnostics["code_graph"]["edge_kinds"]


def test_project_context_deps_only_does_not_build_code_graph(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text("class HelpRequestScreen {}\n", encoding="utf-8")
    facade = FakeProjectContextFacade()

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        "HelpRequestScreen",
        library="go_router",
        mode="deps-only",
        allow_network=True,
    )

    assert not any(item["source_class"] == "code_graph" for item in result.context_pack)
    assert "code_graph" not in result.diagnostics


def test_project_context_code_graph_failure_is_non_fatal(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text("class HelpRequestScreen {}\n", encoding="utf-8")
    facade = FakeProjectContextFacade()

    def fail_build(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "docmancer.docs.application.project_context_service.build_project_code_graph",
        fail_build,
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        "HelpRequestScreen",
        mode="project-only",
    )

    assert result.status == "success"
    assert result.diagnostics["code_graph"] == {"error": "RuntimeError: boom", "selected_items": 0}


def test_trust_contract_uses_canonical_sources_and_exposes_source_evidence_context_sources(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
class HelpRequestDetailsScreen {
  final label = 'Вернуть в работу';
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API with enough context for stable project-doc selection.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
        indexed_sources=[{"path": "ARCHITECTURE.md", "source": str(tmp_path / "ARCHITECTURE.md")}],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        'Как реализовать кнопку "Вернуть в работу"?',
        mode="project-only",
    )

    contract = result.trust_contract
    assert "selected_sources" not in contract
    assert "selected" not in contract
    assert {item["source_class"] for item in contract["sources"]["selected"]} == {"project_file"}

    context_sources = contract["context_sources"]
    assert context_sources["schema_version"] == "context-sources-1.0"
    snippet = context_sources["source_evidence"][0]
    assert snippet["source_class"] == "source_evidence"
    assert snippet["evidence_class"] == "source_snippet"
    assert snippet["role"] == "source_backed_evidence"
    assert snippet["path"] == "lib/help_request_details_screen.dart"
    assert snippet["line_start"] == 2
    assert snippet["line_end"] == 2
    assert snippet["matched_terms"] == ["Вернуть в работу"]
    assert snippet["missing_terms"] == []
    assert snippet["reason"] == "requirement term matched a concrete project source line"

    repo_map = context_sources["repo_map"][0]
    assert repo_map["source_class"] == "repo_map"
    assert repo_map["role"] == "navigation_context"
    assert repo_map["proof_role"] == "navigation_only"
    assert repo_map["path"] == "lib/help_request_details_screen.dart"


def test_project_context_source_evidence_exposes_absent_terms_without_proof(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
class HelpRequestDetailsScreen {
  void reopenRequest() {
    final label = 'Вернуть в работу';
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query='Как реализовать кнопку "Вернуть в работу" и статус "Активная"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path),
        'Как реализовать кнопку "Вернуть в работу" и статус "Активная"?',
        mode="project-only",
    )

    source_evidence_items = [item for item in result.context_pack if item["source_class"] == "source_evidence"]
    assert [item["evidence_class"] for item in source_evidence_items] == ["source_snippet", "absent_in_source"]
    assert source_evidence_items[0]["matched_terms"] == ["Вернуть в работу"]
    assert source_evidence_items[1]["missing_terms"] == ["Активная"]
    assert source_evidence_items[1]["path"] is None
    assert "Активная" not in source_evidence_items[1]["content"]
    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["missing_terms"] == ["Активная"]
    assert result.recommended_next_actions[-1]["query_terms"] == ["Активная"]


def test_story_specific_unquoted_error_toast_phrases_are_missing_terms():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="Где добавить toast ошибки?",
        results=[
            ProjectDocsChunk(
                title="Core errors",
                content="Use ToastUtils with AppError and StateStatus in the UI -> Cubit -> Service flow.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Core error handling",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(
        "/repo",
        "Где и как добавить toast ошибки для Вернуть в работу: Сервис временно недоступен / Повторите попытку позднее и Нет соединения / Проверьте интернет и попробуйте снова?",
        mode="project-only",
    )

    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["missing_terms"] == [
        "Сервис временно недоступен",
        "Повторите попытку позднее",
        "Нет соединения",
        "Проверьте интернет и попробуйте снова",
    ]


def test_unquoted_russian_story_query_uses_requirement_chunks_not_weak_words():
    facade = FakeProjectContextFacade()
    question = (
        "Как реализовать Создать новый запрос на основании закрытой заявки, "
        "отправить название заявки в чат как первое обязательное поле и показать Вернуть в работу?"
    )
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query=question,
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="""
Help requests follow UI -> Cubit -> Service -> Repository -> API.
The UI layer has help_requests_screen for active/closed lists,
help_request_details_screen for comments and attachments, and
new_help_request_screen for creating requests through a chat-like form.
""".strip(),
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", question, mode="project-only")

    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["source_search_required"] is True
    missing_terms = result.answer_completeness["missing_terms"]
    assert "Создать новый запрос" in missing_terms
    assert "на основании закрытой заявки" in missing_terms
    assert "отправить название заявки в чат" in missing_terms
    assert "первое обязательное поле" in missing_terms
    assert "Вернуть в работу" in missing_terms
    assert "Создать" not in missing_terms
    assert "закрытой" not in missing_terms
    source_action = result.recommended_next_actions[-1]
    assert source_action["query_terms"] == missing_terms[:8]
    assert "Создать новый запрос" in source_action["query_terms"]
    assert "отправить название заявки в чат" in source_action["query_terms"]


def test_broad_story_query_with_code_identifier_still_requires_source_story_terms(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_chat.dart").write_text(
        """
library help_chat;

class HelpChatWidget {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    question = (
        "Для help_chat по бизнес-сценарию возврата/переоткрытия закрытой заявки в HELP какие файлы и слои нужно менять? "
        "Use Case: Возврат/переоткрытие запроса в HELP. Пользователь на вкладке Закрытые открывает закрытую заявку. "
        "Вернуть в работу отправляет статус Активная. При ошибках показывает toast: "
        "Сервис временно недоступен / Повторите попытку позднее; Нет соединения / Проверьте интернет и попробуйте снова. "
        "Создать новый запрос открывает экран создания новой заявки и показывает первое обязательное поле."
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query=question,
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="help_chat follows UI -> Cubit -> Service -> Repository -> API for HELP requests.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Help requests architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context(str(tmp_path), question, mode="project-only")

    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["source_search_required"] is True
    assert "help_chat" in result.answer_completeness["matched_terms"]
    missing_terms = result.answer_completeness["missing_terms"]
    assert "Создать новый запрос" in missing_terms
    assert "Сервис временно недоступен" in missing_terms
    assert "Нет соединения" in missing_terms
    context_sources = result.trust_contract["context_sources"]
    assert context_sources["repo_map"][0]["proof_role"] == "navigation_only"
    assert any(
        item["evidence_class"] == "source_snippet" and item["matched_terms"] == ["help_chat"]
        for item in context_sources["source_evidence"]
    )
    assert any(
        item["evidence_class"] == "absent_in_source" and "Сервис временно недоступен" in item["missing_terms"]
        for item in context_sources["source_evidence"]
    )
    assert result.recommended_next_actions[-1]["action"] == "search_project_sources"


def test_project_context_prefers_authoritative_workflow_docs_over_noisy_dogfood_artifacts():
    question = "How should agents use the Docmancer MCP workflow, project architecture, and conventions?"
    artifact_path = "docs/research/docatlas-dogfood-v4/nbo/patch-review/review_summary.md"
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query=question,
        results=[
            ProjectDocsChunk(
                title="Old dogfood patch-review output",
                content=(
                    "Docmancer MCP Workflow architecture conventions project context get_project_context. "
                    "This generated dogfood artifact repeats architecture workflow terms from an old review run."
                ),
                source=f"/repo/{artifact_path}",
                url=None,
                path=artifact_path,
                heading_path="Docmancer MCP Workflow",
                metadata={"score": 0.99},
            ),
            ProjectDocsChunk(
                title="Architecture",
                content=(
                    "Docmancer MCP Workflow is defined by authoritative architecture docs. "
                    "Agents inspect, sync, then call get_project_context for project workflow and conventions."
                ),
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Docmancer MCP Workflow",
                metadata={"score": 0.60},
            ),
            ProjectDocsChunk(
                title="Docs index",
                content=(
                    "The project docs index maps architecture, workflow, runbooks, and conventions for Docmancer MCP."
                ),
                source="/repo/docs/INDEX.md",
                url=None,
                path="docs/INDEX.md",
                heading_path="Docmancer MCP Workflow",
                metadata={"score": 0.55},
            ),
        ],
        indexed_sources=[
            {"path": artifact_path, "source": f"/repo/{artifact_path}"},
            {"path": "ARCHITECTURE.md", "source": "/repo/ARCHITECTURE.md"},
            {"path": "docs/INDEX.md", "source": "/repo/docs/INDEX.md"},
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", question, mode="project-only", limit=3)

    project_paths = [item["path"] for item in result.context_pack if item["source_class"] == "project_doc"]
    assert project_paths == ["ARCHITECTURE.md", "docs/INDEX.md"]
    assert artifact_path not in project_paths

    architecture_item = next(item for item in result.context_pack if item.get("path") == "ARCHITECTURE.md")
    assert architecture_item["source_type"] == "architecture"
    assert architecture_item["authority"] == "primary"
    assert architecture_item["risk_flags"] == []

    contract_sources = result.trust_contract["sources"]["selected"]
    contract_paths = [item["path"] for item in contract_sources]
    assert contract_paths == ["ARCHITECTURE.md", "docs/INDEX.md"]
    assert "selected" not in result.trust_contract
    assert "trusted_sources" not in result.trust_contract

    reading_paths = [item["path"] for item in result.answer_outline["recommended_reading_order"]]
    assert reading_paths[:2] == ["ARCHITECTURE.md", "docs/INDEX.md"]


def test_russian_story_requirement_chunks_drop_question_scaffolding_and_connectors():
    facade = FakeProjectContextFacade()
    question = (
        "Как реализовать кнопку подключения Bluetooth-устройств и проверить сценарий подключения внешнего сканера? "
        "Как изменить flow работы сервера, чтобы после запуска показать уведомление в верхней части экрана "
        "и проверить примеры запросов?"
    )
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query=question,
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Runtime flow follows UI -> Cubit -> Service -> Repository -> API for screens, scanner devices, and local server features.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
                heading_path="Runtime architecture",
            )
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", question, mode="project-only")

    assert result.answer_type == "partial_navigational"
    missing_terms = result.answer_completeness["missing_terms"]
    assert "Как реализовать кнопку" not in missing_terms
    assert "показать уведомление в верхней части экрана и" not in missing_terms
    assert "проверить сценарий подключения внешнего сканера" in missing_terms
    assert "показать уведомление в верхней части экрана" in missing_terms
    assert "проверить примеры запросов" in missing_terms


def test_context_pack_snippet_and_metrics_shape_are_stable():
    chunk = DocsChunk(
        title="Example",
        content="prose and code",
        source="source",
        url=None,
        metadata={"code_snippets": [{"language": "dart", "code": "GoRouter();"}]},
    )
    assert context_pack_snippet(chunk) == {
        "language": "dart",
        "code": "GoRouter();",
        "why_relevant": "code example extracted from matching Example section",
    }
    project_docs = ProjectDocsResult(
        project_path="/repo",
        query="needle",
        results=[ProjectDocsChunk(title="Readme", content="This README section has enough words to remain in a context pack after quality filtering.", source="/repo/README.md", url=None, path="README.md")],
    )
    pack = project_context_pack(project_docs=project_docs, dependency_docs=None)
    assert pack[0]["token_estimate"] > 2
    assert pack[0]["source_type"] == "readme"
    assert pack[0]["authority"] == "primary"
    assert pack[0]["risk_flags"] == []
    source = pack[0]["source"]
    assert source["source_type"] == "readme"
    assert source["authority"] == "primary"
    assert source["risk_flags"] == []
    assert {key: source[key] for key in (
        "source_class",
        "doc_scope",
        "module_id",
        "module_name",
        "module_path",
        "module_type",
        "path",
        "url",
        "title",
    )} == {
        "source_class": "project_doc",
        "doc_scope": "project",
        "module_id": None,
        "module_name": None,
        "module_path": None,
        "module_type": None,
        "path": "README.md",
        "url": None,
        "title": "Readme",
    }
    assert pack[0]["section"] == {
        "title": "Readme",
        "heading_path": None,
        "freshness": "current",
    }
    assert project_context_metrics(context_pack=pack, project_docs=project_docs, dependency_docs=None) == {
        "context_pack_items": 1,
        "selected_source_count": 1,
        "project_result_count": 1,
        "dependency_result_count": 0,
            "token_estimate": pack[0]["token_estimate"],
        "source_classes": ["project_doc"],
        "quality": {
            "query_intent": None,
            "changelog_items": 0,
            "changelog_ratio": 0.0,
            "unique_source_count": 1,
            "max_items_from_single_source": 1,
            "has_readme": True,
            "has_architecture": False,
            "has_contributing": False,
            "has_docs_mcp_source": False,
            "has_packs_mcp_source": False,
            "relevance_coverage": 1.0,
            "trivial_sections_filtered": 0,
            "noise_sections_demoted": 0,
            "warnings": [],
        },
        "token_savings": {
            "raw_docs_tokens": 0,
            "context_pack_tokens": pack[0]["token_estimate"],
            "savings_percent": None,
            "used_percent": None,
            "agentic_runway_multiplier": None,
            "meaning": "compression_vs_raw_docs_not_relevance_score",
        },
    }


def test_metrics_warn_when_changelog_present_for_non_release_query():
    intent = classify_project_query_intent("How does ingestion work?")
    metrics = project_context_metrics(
        context_pack=[{"path": "CHANGELOG.md"}, {"path": "README.md"}],
        project_docs=None,
        dependency_docs=None,
        intent=intent,
    )

    assert metrics["quality"]["changelog_items"] == 1
    assert any(warning["code"] == "changelog_in_non_release_context" for warning in metrics["quality"]["warnings"])


def test_why_selected_mentions_project_structure_for_contributing():
    item = ProjectDocsChunk(title="Contributing", content="content", source="/repo/CONTRIBUTING.md", url=None, path="CONTRIBUTING.md", heading_path="Project structure")
    assert "project structure" in project_why_selected(item).lower()


def test_why_selected_mentions_release_history_for_changelog():
    item = ProjectDocsChunk(title="Changelog", content="content", source="/repo/CHANGELOG.md", url=None, path="CHANGELOG.md", heading_path="Added")
    assert "release" in project_why_selected(item).lower()


def test_reranked_context_pack_why_selected_includes_intent_and_ranking_reason():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query="architecture",
        results=[
            ProjectDocsChunk(title="Changelog", content="changes", source="/repo/CHANGELOG.md", url=None, path="CHANGELOG.md", heading_path="Added", metadata={"score": 0.99}),
            ProjectDocsChunk(title="Architecture", content="pipeline", source="/repo/wiki/Architecture.md", url=None, path="wiki/Architecture.md", heading_path="Architecture > Pipeline", metadata={"score": 0.80}),
        ],
    )

    result = ProjectContextService(facade).get_project_context("/repo", "What is the architecture of docmancer?", mode="project-only", limit=2)
    architecture_item = next(item for item in result.context_pack if item["path"] == "wiki/Architecture.md")

    why = architecture_item["why_selected"].lower()
    assert "architecture" in why
    assert "boosted" in why
    assert "source diversity" in why


def test_compact_project_context_exposes_answer_outline_and_diagnostics():
    result = _compact_project_context({
        "project_path": "/repo",
        "question": "How does MCP work?",
        "status": "success",
        "tool": "get_project_context",
        "schema_version": "1.0-mvp",
        "answer_available": True,
        "mode": "auto",
        "answer_outline": {"query_intent": "mcp_disambiguation"},
        "diagnostics": {"query_intent": "mcp_disambiguation"},
    })

    assert result["answer_outline"] == {"query_intent": "mcp_disambiguation"}
    assert result["diagnostics"] == {"query_intent": "mcp_disambiguation"}
