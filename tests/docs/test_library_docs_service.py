from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from docmancer.docs.application.library_ingest_orchestrator import LibraryIngestOrchestrator
from docmancer.docs.application.library_ingest_ports import LibraryIngestPorts
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.models import RefreshResult


class FakeLibraryFacade:
    def __init__(self):
        self.calls = []

    def _library_resolve_library_impl(self, *args):
        self.calls.append(("resolve", args))
        return "resolved"

    def _library_get_docs_impl(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return "docs"

    def _library_prune_library_docs_impl(self, **kwargs):
        self.calls.append(("prune", kwargs))
        return "pruned"

