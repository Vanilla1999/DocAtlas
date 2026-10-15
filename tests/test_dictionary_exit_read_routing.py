"""Read routing is literal/metadata-bound, never topical mutation authority."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from docmancer.docs.application.project_context_service import ProjectContextService, project_context_pack
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application._project_context_service_shared import _should_skip_low_trust_project_source
from docmancer.docs.application._unified_context_service_shared import _snippet_first_fallback_question
from docmancer.docs.domain.context_request_preferences import (
    direct_evidence_preference, recognized_request_parts, recognized_request_satisfied,
    visible_request_parts,
)
from docmancer.docs.domain.mutation_intent import MutationIntentContract
from docmancer.docs.models import (
    DependencyObservation, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata,
)


class ReadFacade:
    """Exercise assembled services without network or an embedding provider."""
    def __init__(self, root):
        self.calls = []
        self.metadata = ProjectMetadata(str(root), dependencies=[
            DependencyObservation(ecosystem="pub", package_name="flutter_riverpod"),
            DependencyObservation(ecosystem="pub", package_name="go_router"),
            DependencyObservation(ecosystem="python", package_name="mcp"),
        ])
        content = "MarbleValve retains the indexed project configuration. This repository-owned passage documents its literal setting and preserves a bounded local read context without granting permission to edit source files."
        (root / "README.md").write_text(content)
        self.docs = ProjectDocsResult(str(root), "MarbleValve", answer_available=False,
            results=[ProjectDocsChunk(title="MarbleValve", content=content,
                source=str(root / "README.md"), url=None, path="README.md",
                content_hash=sha256(content.encode()).hexdigest(), project_identity="repo",
                metadata={"token_estimate": 48})])

    def read_project_metadata(self, root):
        return self.metadata

    def get_project_docs(self, root, question, **kwargs):
        self.calls.append(("project_docs", question, kwargs))
        return self.docs

    def get_project_context(self, root, question, **kwargs):
        self.calls.append(("project_context", question, kwargs))
        return ProjectContextService(self).get_project_context(root, question, **kwargs)

    def get_docs(self, library, **kwargs):
        self.calls.append(("dependency", library, kwargs))
        return DocsResult(library_id="pub/go_router/2", library=library,
            version="2", topic=kwargs["topic"], refreshed=False,
            stale_before_refresh=False, warning=None, last_refreshed_at=None, results=[])

















