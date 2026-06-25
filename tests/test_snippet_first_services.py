from __future__ import annotations

from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.models import DocsChunk, DocsResult, ProjectContextResult


def docs_result(content: str, *, metadata=None) -> DocsResult:
    return DocsResult(
        library_id="python:fastapi@latest:web",
        library="fastapi",
        version="latest",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning=None,
        last_refreshed_at="now",
        source_type="web",
        results=[DocsChunk(title="Depends", content=content, source="https://fastapi.tiangolo.com/tutorial/dependencies/", url="https://fastapi.tiangolo.com/tutorial/dependencies/", metadata=metadata or {})],
        resolved_version="latest",
    )


class FakeFacade:
    def __init__(self):
        self.calls = []
        self.library_result = docs_result("```python\nfrom fastapi import Depends\nDepends()\n```")
        self.project_context = ProjectContextResult(
            project_path="/repo",
            question="q",
            status="success",
            mode="auto",
            context_pack=[{"doc_scope": "project", "origin_lane": "project", "source_class": "project_doc", "path": "/repo/README.md", "title": "README", "content": "```bash\nuv run pytest\n```"}],
            trust_contract={"selected": [], "rejected": [], "risky": []},
        )

    def bootstrap_project_docs(self, *args, **kwargs):
        return type("Bootstrap", (), {"requires_confirmation": False, "warnings": [], "reason_code": "project_docs_ready"})()

    def get_project_context(self, project_path, question, **kwargs):
        self.calls.append(("get_project_context", kwargs))
        return self.project_context

    def resolve_library(self, library, ecosystem=None, version=None, docs_url=None, docs_url_template=None, source_type=None):
        self.calls.append(("resolve_library", {"library": library}))
        return type("Info", (), {"library_id": "python:fastapi@latest:web", "local": True, "stale": False, "status": "available"})()

    def get_docs(self, library, **kwargs):
        self.calls.append(("get_docs", kwargs))
        return self.library_result

    def read_project_metadata(self, project_path):
        return type("Meta", (), {"dependencies": []})()

    def _project_dependency_docs_state(self, metadata):
        return {"missing": [], "stale": []}


def test_unified_library_coding_query_returns_primary_snippet():
    facade = FakeFacade()
    result = UnifiedDocsContextService(facade).get_docs_context("How do I use FastAPI Depends?", library="fastapi", response_style="auto")
    assert result.response_style == "snippet-first"
    assert "Depends" in result.primary_snippet["code"]
    assert result.primary_snippet["doc_scope"] == "library"


def test_unified_conceptual_query_remains_evidence_first_in_auto():
    facade = FakeFacade()
    result = UnifiedDocsContextService(facade).get_docs_context("Why does the architecture isolate project docs?", project_path="/repo", prepare_project_docs=False)
    assert result.response_style == "evidence-first"
    assert result.primary_snippet is None


def test_unified_forced_snippet_first_project_command_query_can_return_project_snippet():
    facade = FakeFacade()
    result = UnifiedDocsContextService(facade).get_docs_context("Show the project test command", project_path="/repo", prepare_project_docs=False, response_style="snippet-first")
    assert result.primary_snippet["doc_scope"] == "project"
    assert "uv run pytest" in result.primary_snippet["code"]


def test_partial_success_does_not_invent_missing_library_snippet():
    facade = FakeFacade()
    facade.project_context = ProjectContextResult(project_path="/repo", question="q", status="success", context_pack=[{"doc_scope": "project", "origin_lane": "project", "source_class": "project_doc", "path": "/repo/README.md", "title": "README", "content": "project prose"}], trust_contract={"selected": [], "rejected": [], "risky": []})
    result = UnifiedDocsContextService(facade).get_docs_context("How do I use MissingLib?", project_path="/repo", library="missing", prepare_project_docs=False, response_style="snippet-first")
    assert result.primary_snippet is None or result.primary_snippet.get("origin_lane") != "library"


def test_latest_fallback_snippet_marked_not_exact():
    facade = FakeFacade()
    facade.library_result = docs_result("```python\nfrom fastapi import Depends\n```", metadata={"version": "latest", "requested_version": "0.1", "exact_version_match": False})
    result = UnifiedDocsContextService(facade).get_docs_context("FastAPI Depends example", library="fastapi", response_style="snippet-first")
    assert result.primary_snippet["exact_version_match"] is False
    assert "not_exact_version" in result.primary_snippet["risk_flags"]
