from __future__ import annotations

from docmancer.docs.application.project_context_service import ProjectContextService, context_pack_snippet, project_context_metrics, project_context_pack, project_why_selected
from docmancer.docs.interfaces.mcp.project_tools import _compact_project_context
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.models import DependencyObservation, DocsChunk, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata


class FakeProjectContextFacade:
    def __init__(self):
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
        return ProjectMetadata(project_path=project_path, dependencies=[DependencyObservation(ecosystem="pub", package_name="go_router")])

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
    result = ProjectContextService(facade).get_project_context("/repo", "use go_router", tokens=1200, limit=3)

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
    assert result.trust_contract["policy"]["direct_webfetch"] == "forbidden"
    assert ("docs", "go_router", {"topic": "use go_router", "tokens": 1200, "ecosystem": None, "version": None, "project_path": "/repo"}) in facade.calls
    assert ("project", "/repo", "use go_router", {"tokens": 1200, "limit": 3, "expand": None, "module": None, "module_path": None, "scope": None}) in facade.calls


def test_project_context_service_deps_only_skips_project_docs_and_marks_risk():
    facade = FakeProjectContextFacade()
    result = ProjectContextService(facade).get_project_context("/repo", "api", library="go_router", mode="deps-only")

    assert not any(call[0] == "project" for call in facade.calls)
    assert result.project_docs is None
    assert result.dependency_docs is facade.dependency_docs
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["risky_sources"])


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

    assert result.answer_available is True
    assert result.answer_type == "partial_navigational"
    assert result.answer_completeness["status"] == "partial"
    assert result.answer_completeness["source_search_required"] is True
    assert "Вернуть в работу" in result.answer_completeness["missing_terms"]
    assert "Активная" in result.answer_completeness["missing_terms"]
    source_action = result.recommended_next_actions[-1]
    assert source_action["action"] == "search_project_sources"
    assert source_action["tool"] == "code_search"
    assert "help_request_details_screen" in source_action["suggested_symbols"]


def test_story_specific_project_context_with_matched_terms_is_exact():
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

    assert result.answer_type == "exact"
    assert result.answer_completeness["status"] == "exact"
    assert result.answer_completeness["missing_terms"] == []
    assert not any(action.get("action") == "search_project_sources" for action in result.recommended_next_actions)


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
    assert pack[0]["source"] == {
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
