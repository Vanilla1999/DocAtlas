from __future__ import annotations

import hashlib

from docmancer.docs.application.project_context_service import (
    ProjectContextService,
    _dependency_confirmation_blocks_local_answer,
    context_pack_snippet,
    project_context_metrics,
    project_context_pack,
    project_why_selected,
)
from docmancer.docs.domain.answer_completeness import (
    derive_project_answer_completeness,
    evaluate_project_answer_completeness,
)
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
            results=[DocsChunk(title="GoRouter", content="Use go_router for routing; this dependency documentation contains enough words for stable context selection and quality filters.", source="https://pub.dev", url="https://pub.dev")],
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
