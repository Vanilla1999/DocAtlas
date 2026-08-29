from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from docmancer.docs.application.evidence_selection import AggregateMixedSelectionDecision, docs_selection_config, library_docs_selection_config, select_evidence
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.models import DocsChunk, DocsResult, LibraryInfo, ProjectContextResult, UnifiedDocsContextResult


@dataclass
class FakeMetadata:
    dependencies: list[Any] = field(default_factory=list)


class FakeFacade:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.library_local = True
        self.library_stale = False
        self.library_status = "available"
        self.library_message = None
        self.latest_library_local = True
        self.dependency_missing = False
        self.project_context = ProjectContextResult(
            project_path="/repo",
            question="q",
            status="success",
            mode="auto",
            context_pack=[{"doc_scope": "project", "source_class": "project_doc", "path": "README.md", "title": "README", "content": "project", "why_selected": "project docs"}],
            trust_contract={"selected": [], "rejected": [], "risky": []},
        )
        self.library_result = DocsResult(
            library_id="python:fastapi@latest:web",
            library="fastapi",
            version="latest",
            topic="Depends",
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at="now",
            source_type="web",
            results=[DocsChunk(title="Depends", content="FastAPI Depends", source="https://fastapi.tiangolo.com/tutorial/dependencies/", url="https://fastapi.tiangolo.com/tutorial/dependencies/", metadata={})],
            resolved_version="latest",
        )
        self.get_docs_results: list[DocsResult] = []
        self.wrote_repo_files = False
        self.prefetched_dependency_docs = False
        self.bootstrap_requires_confirmation = False
        self.bootstrap_reason_code = "project_docs_ready"

    def bootstrap_project_docs(self, project_path, question=None, *, allow_sync=True):
        self.calls.append(("bootstrap_project_docs", {"project_path": project_path, "question": question}))
        return type("Bootstrap", (), {
            "requires_confirmation": self.bootstrap_requires_confirmation,
            "warnings": [],
            "reason_code": self.bootstrap_reason_code,
            "confirmation_reason": "network_fetch" if self.bootstrap_requires_confirmation else None,
            "next_action": {"tool": "prefetch_project_dependency_docs"} if self.bootstrap_requires_confirmation else {},
            "arguments_patch": {"allow_network": True} if self.bootstrap_requires_confirmation else {},
        })()

    def get_project_context(self, project_path, question, **kwargs):
        self.calls.append(("get_project_context", {"project_path": project_path, "question": question, **kwargs}))
        return self.project_context

    def resolve_library(self, library, ecosystem=None, version=None, docs_url=None, docs_url_template=None, source_type=None):
        self.calls.append(("resolve_library", {"library": library, "ecosystem": ecosystem, "version": version, "source_type": source_type}))
        local = self.latest_library_local if version is None and docs_url else self.library_local
        return LibraryInfo(
            library_id=f"{ecosystem or 'python'}:{library}@{version or 'latest'}:{source_type or 'web'}",
            library=library,
            ecosystem=ecosystem,
            version=version or "latest",
            source_type=source_type or "web",
            status=self.library_status,
            local=local,
            stale=self.library_stale,
            last_refreshed_at="now" if local else None,
            message=self.library_message,
        )

    def get_docs(self, library, **kwargs):
        self.calls.append(("get_docs", {"library": library, **kwargs}))
        if self.get_docs_results:
            return self.get_docs_results.pop(0)
        return self.library_result

    def read_project_metadata(self, project_path):
        return FakeMetadata(dependencies=[type("Dep", (), {"package_name": "riverpod"})()])

    def _project_dependency_docs_state(self, metadata):
        return {"missing": ["riverpod"]} if self.dependency_missing else {"missing": [], "stale": []}

    def prefetch_project_dependency_docs(self, *args, **kwargs):
        self.prefetched_dependency_docs = True


def _service(facade: FakeFacade | None = None) -> UnifiedDocsContextService:
    return UnifiedDocsContextService(facade or FakeFacade())


def _call_names(facade: FakeFacade) -> list[str]:
    return [name for name, _ in facade.calls]
























































































def _exact_unsupported(version: str = "0.115.0") -> DocsResult:
    return DocsResult(
        library_id="",
        library="fastapi",
        version=version,
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning="unsupported",
        last_refreshed_at=None,
        status="exact_version_not_supported",
        requested_version=version,
        resolved_version=None,
        diagnostics={"exact_version": {"expected": version, "used": None, "match": None, "fallback": False, "reason_code": "versioned_docs_unavailable", "fallback_available": True, "fallback_docs_url": "https://fastapi.tiangolo.com/"}},
    )


def _latest_success() -> DocsResult:
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
        results=[DocsChunk(title="Depends", content="real latest chunk", source="https://fastapi.tiangolo.com/", url="https://fastapi.tiangolo.com/", metadata={})],
        resolved_version="latest",
    )
