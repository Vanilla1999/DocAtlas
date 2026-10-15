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




