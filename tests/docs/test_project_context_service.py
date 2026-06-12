from __future__ import annotations

from docmancer.docs.application.project_context_service import ProjectContextService, context_pack_snippet, project_context_metrics, project_context_pack
from docmancer.docs.models import DependencyObservation, DocsChunk, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata


class FakeProjectContextFacade:
    def __init__(self):
        self.project_docs = ProjectDocsResult(
            project_path="/repo",
            query="needle",
            results=[ProjectDocsChunk(title="Readme", content="needle content", source="/repo/README.md", url=None, path="README.md")],
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
            results=[DocsChunk(title="GoRouter", content="go_router content", source="https://pub.dev", url="https://pub.dev")],
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
    assert result.metrics["source_classes"] == ["dependency_doc", "project_doc"]
    assert result.trust_contract["policy"]["direct_webfetch"] == "forbidden"
    assert ("docs", "go_router", {"topic": "use go_router", "tokens": 1200, "ecosystem": None, "version": None, "project_path": "/repo"}) in facade.calls


def test_project_context_service_deps_only_skips_project_docs_and_marks_risk():
    facade = FakeProjectContextFacade()
    result = ProjectContextService(facade).get_project_context("/repo", "api", library="go_router", mode="deps-only")

    assert not any(call[0] == "project" for call in facade.calls)
    assert result.project_docs is None
    assert result.dependency_docs is facade.dependency_docs
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["risky_sources"])


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
        results=[ProjectDocsChunk(title="Readme", content="12345678", source="/repo/README.md", url=None, path="README.md")],
    )
    pack = project_context_pack(project_docs=project_docs, dependency_docs=None)
    assert pack[0]["token_estimate"] == 2
    assert project_context_metrics(context_pack=pack, project_docs=project_docs, dependency_docs=None) == {
        "context_pack_items": 1,
        "selected_source_count": 1,
        "project_result_count": 1,
        "dependency_result_count": 0,
        "token_estimate": 2,
        "source_classes": ["project_doc"],
    }
