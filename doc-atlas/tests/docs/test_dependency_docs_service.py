from __future__ import annotations

from docmancer.docs.application.dependency_docs_service import DependencyDocsService


class FakeDependencyFacade:
    def __init__(self):
        self.calls = []

    def _dependency_prefetch_project_docs_impl(self, project_path, **kwargs):
        self.calls.append((project_path, kwargs))
        return "prefetched"


def test_dependency_docs_service_delegates_prefetch_project_docs_options():
    facade = FakeDependencyFacade()
    service = DependencyDocsService(facade)

    result = service.prefetch_project_docs(
        "/repo",
        include_flutter=False,
        include_dart=True,
        include_rust=False,
        include_packages=["go_router"],
        force_refresh=True,
        continue_on_error=False,
        async_=True,
    )

    assert result == "prefetched"
    assert facade.calls == [("/repo", {
        "include_flutter": False,
        "include_dart": True,
        "include_rust": False,
        "include_packages": ["go_router"],
        "force_refresh": True,
        "continue_on_error": False,
        "async_": True,
    })]


def test_dependency_docs_service_alias_is_equivalent():
    facade = FakeDependencyFacade()
    service = DependencyDocsService(facade)

    assert service.prefetch_project_dependency_docs("/repo", include_packages=["serde"]) == "prefetched"
    assert facade.calls == [("/repo", {
        "include_flutter": True,
        "include_dart": False,
        "include_rust": True,
        "include_packages": ["serde"],
        "force_refresh": False,
        "continue_on_error": True,
        "async_": False,
    })]
