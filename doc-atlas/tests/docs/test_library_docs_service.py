from __future__ import annotations

from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService


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


def test_library_application_service_delegates_resolve_library():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.resolve_library("pytest", ecosystem="python", version="8") == "resolved"
    assert facade.calls == [("resolve", ("pytest", "python", "8", None, None, None))]


def test_library_application_service_delegates_get_docs_with_arguments():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.get_docs("pytest", topic="fixtures", tokens=100, force_refresh=True) == "docs"
    name, args, kwargs = facade.calls[0]
    assert name == "get"
    assert args == ("pytest",)
    assert kwargs["topic"] == "fixtures"
    assert kwargs["tokens"] == 100
    assert kwargs["force_refresh"] is True


def test_library_application_service_delegates_prune_options():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.prune_library_docs(library="go_router", keep_versions=["1"], older_than_days=30, dry_run=False) == "pruned"
    assert facade.calls == [("prune", {"library": "go_router", "keep_versions": ["1"], "older_than_days": 30, "dry_run": False})]
