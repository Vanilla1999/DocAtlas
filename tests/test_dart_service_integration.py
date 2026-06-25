"""Test service integration for Dart/Flutter official docs auto-use."""

from __future__ import annotations

from types import MethodType
import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.agent import DocmancerAgent
from docmancer.docs.dart_official_docs import DartDocsResolution


class MultiRootFakeFetcher:
    last_discovery_diagnostics = {"discovery_strategy": "seed", "seed_pages": 2}

    def __init__(self, documents):
        self.documents = documents

    def fetch(self, url):
        return self.documents


def _service_with_fake_fetcher(tmp_path, monkeypatch, documents):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")

    def agent_factory(**kwargs):
        agent = DocmancerAgent(config=kwargs["config"])
        original_add = agent.add

        def add(url, recreate=False, **add_kwargs):
            add_kwargs["fetcher"] = MultiRootFakeFetcher(documents)
            return original_add(url, recreate=recreate, **add_kwargs)

        agent.add = add
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _dart_doc(source, content, *, docset_root, title="Guide", extra_metadata=None):
    metadata = {"docset_root": docset_root, "title": title}
    if extra_metadata:
        metadata.update(extra_metadata)
    return Document(source=source, content=content, metadata=metadata)


def test_riverpod_auto_uses_official_docs(tmp_path):
    """resolve_library for riverpod should auto-register with riverpod.dev."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="riverpod",
        ecosystem="flutter",
    )
    
    assert info.library_id is not None
    assert info.ecosystem == "dart"
    assert info.docs_url is not None
    assert "riverpod.dev" in info.docs_url
    record = service.registry.get(info.library_id, source_type=info.source_type)
    assert record is not None
    assert record.target_spec is not None
    assert record.target_spec["seed_urls"]
    assert any("concepts2/providers" in url for url in record.target_spec["seed_urls"])
    assert info.status in ("available", "needs_refresh")


def test_flutter_bloc_auto_uses_official_docs(tmp_path):
    """resolve_library for flutter_bloc should auto-register with bloclibrary.dev."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="flutter_bloc",
        ecosystem="flutter",
    )
    
    assert info.library_id is not None
    assert info.docs_url is not None
    assert "bloclibrary.dev" in info.docs_url
    assert info.status in ("available", "needs_refresh")


def test_unknown_dart_package_still_needs_docs_url(tmp_path):
    """Unknown Dart package without official docs should still return needs_docs_url."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="unknown_dart_package_xyz",
        ecosystem="flutter",
    )
    
    assert info.library_id is None
    assert info.status == "needs_docs_url"
    assert info.candidates is not None


def test_ecosystem_dart_also_works(tmp_path):
    """ecosystem='dart' should also trigger official docs lookup."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="riverpod",
        ecosystem="dart",
    )
    
    assert info.library_id is not None
    assert "riverpod.dev" in info.docs_url


def test_ecosystem_pub_also_works(tmp_path):
    """ecosystem='pub' should also trigger official docs lookup."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="flutter_bloc",
        ecosystem="pub",
    )
    
    assert info.library_id is not None
    assert "bloclibrary.dev" in info.docs_url


def test_python_package_not_affected(tmp_path):
    """Python packages should not be affected by Dart official docs logic."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="unknown_python_lib",
        ecosystem="python",
    )
    
    assert info.library_id is None
    assert info.status == "needs_docs_url"


def test_go_router_still_needs_docs_url(tmp_path):
    """go_router has no package-owned guide site, so auto-registration stays disabled."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    info = service.resolve_library(
        library="go_router",
        ecosystem="flutter",
    )
    
    assert info.library_id is None
    assert info.status == "needs_docs_url"


def test_riverpod_auto_registers_and_get_docs_returns_result(tmp_path):
    """get_docs for riverpod should register and return a result (may need refresh)."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    
    result = service.get_docs(
        library="riverpod",
        ecosystem="flutter",
        topic="Riverpod providers",
    )
    
    assert result is not None
    assert result.status != "needs_docs_url"


def test_dart_aliases_share_one_registry_identity(tmp_path):
    """flutter/pub/dart aliases should not create duplicate registry records."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    flutter = service.resolve_library("riverpod", ecosystem="flutter")
    pub = service.resolve_library("riverpod", ecosystem="pub")
    dart = service.resolve_library("riverpod", ecosystem="dart")

    assert flutter.library_id == pub.library_id == dart.library_id
    assert flutter.ecosystem == pub.ecosystem == dart.ecosystem == "dart"


def test_refresh_receives_auto_registered_seed_urls(tmp_path, monkeypatch):
    """Auto-registration target_spec must feed root + seed_urls into refresh."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)
    info = service.resolve_library("riverpod", ecosystem="flutter")
    record = service.registry.get(info.library_id, source_type=info.source_type)
    assert record is not None

    calls = []

    class FakeAgent:
        last_discovery_diagnostics = {"discovery_strategy": "seed", "seed_pages": 2}

        def add(self, url, **kwargs):
            calls.append((url, kwargs))
            return 0

    def fake_agent_instance(self, record=None):
        return FakeAgent()

    monkeypatch.setattr(service, "_agent_instance", MethodType(fake_agent_instance, service))

    result = service.refresh_docs(info.library_id, source_type=info.source_type, force=True)

    assert result.status == "empty_index"
    assert calls
    url, kwargs = calls[0]
    assert url == "https://riverpod.dev/"
    seed_urls = kwargs.get("seed_urls")
    assert seed_urls
    assert any("concepts2/providers" in seed for seed in seed_urls)
    assert result.preindex is not None
    assert result.preindex["dartdoc"]["package"] == "riverpod"


def test_refresh_metadata_overwrites_fetcher_identity_but_preserves_docset_root(tmp_path, monkeypatch):
    service = _service_with_fake_fetcher(
        tmp_path,
        monkeypatch,
        [
            _dart_doc(
                "https://pub.dev/documentation/riverpod/latest/riverpod/Provider-class.html",
                "# Provider API\nProvider API content for riverpod.",
                docset_root="https://pub.dev/documentation/riverpod/latest",
                title="Provider API",
                extra_metadata={
                    "library_id": "wrong-library",
                    "canonical_id": "wrong:canonical",
                    "ecosystem": "python",
                    "source_type": "guides",
                },
            )
        ],
    )

    info = service.resolve_library("riverpod", ecosystem="flutter")
    refreshed = service.refresh_docs(info.library_id, source_type=info.source_type, force=True)
    assert refreshed.status == "updated"

    result = service.get_docs("riverpod", ecosystem="flutter", topic="Provider API")
    assert result.status == "success"
    assert len(result.results) == 1
    metadata = result.results[0].metadata
    assert metadata["library_id"] == info.library_id
    assert metadata["canonical_id"] == info.canonical_id
    assert metadata["ecosystem"] == "dart"
    assert metadata["source_type"] == "web"
    assert "version" not in metadata
    assert metadata["docset_root"] == "https://pub.dev/documentation/riverpod/latest"


def test_dart_explicit_api_source_type_registers_pubdev_api_docset(tmp_path):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("flutter_bloc", ecosystem="flutter", source_type="api")

    assert info.library_id == "dart:flutter_bloc@latest:api"
    assert info.source_type == "api"
    assert info.docs_url == "https://pub.dev/documentation/flutter_bloc/latest/"
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    assert record.target_spec["doc_format"] == "dartdoc"


@pytest.mark.parametrize("version", [None, "", "latest", "stable", "main"])
def test_dart_api_latest_is_not_exact_snapshot(tmp_path, version):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("riverpod", ecosystem="dart", version=version, source_type="api")

    assert info.docs_snapshot_exact is False
    assert info.version_confidence is None
    assert info.version_inferred is True
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    assert record.target_spec["dart_docs"]["version_binding"] == "latest_pubdev_api"


def test_dart_api_stable_is_not_exact_snapshot(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("riverpod", ecosystem="dart", version="stable", source_type="api")

    assert info.docs_snapshot_exact is False
    assert info.docs_url == "https://pub.dev/documentation/riverpod/stable/"


def test_dart_api_main_is_not_exact_snapshot(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("riverpod", ecosystem="dart", version="main", source_type="api")

    assert info.docs_snapshot_exact is False
    assert info.docs_url == "https://pub.dev/documentation/riverpod/main/"


def test_dart_api_concrete_version_is_exact_snapshot(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("flutter_bloc", ecosystem="flutter", version="9.1.1", source_type="api")

    assert info.docs_url == "https://pub.dev/documentation/flutter_bloc/9.1.1/"
    assert info.docs_snapshot_exact is True
    assert info.version_confidence == "high"
    assert info.version_inferred is False
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    assert record.target_spec["dart_docs"]["version_binding"] == "pubdev_api_snapshot"


def test_dart_api_version_string_does_not_override_latest_url_semantics(tmp_path, monkeypatch):
    def fake_resolution(package, version=None, include_pubdev=True):
        return DartDocsResolution(
            package=package,
            official_docs_available=False,
            official_docs_urls=["https://pub.dev/documentation/flutter_bloc/latest/"],
            pubdev_docs_url="https://pub.dev/documentation/flutter_bloc/latest/",
            docs_strategy="pubdev_only",
            confidence="medium",
        )

    monkeypatch.setattr("docmancer.docs.application.library_docs_service.resolve_dart_official_docs", fake_resolution)
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "test.db")
    service = LibraryDocsService(config=config)

    info = service.resolve_library("flutter_bloc", ecosystem="flutter", version="9.1.1", source_type="api")

    assert info.docs_url == "https://pub.dev/documentation/flutter_bloc/latest/"
    assert info.docs_snapshot_exact is False
    assert info.version_confidence is None
    assert info.version_inferred is True
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    assert record.target_spec["dart_docs"]["version_binding"] == "latest_pubdev_api"


def test_riverpod_refresh_ingests_and_queries_official_and_pubdev_roots(tmp_path, monkeypatch):
    service = _service_with_fake_fetcher(
        tmp_path,
        monkeypatch,
        [
            _dart_doc(
                "https://riverpod.dev/docs/concepts2/refs",
                "# autoDispose ref.watch\nUse autoDispose providers with ref.watch for reactive dependencies.",
                docset_root="https://riverpod.dev",
                title="Refs",
            ),
            _dart_doc(
                "https://pub.dev/documentation/riverpod/latest/riverpod/AutoDisposeProvider-class.html",
                "# AutoDisposeProvider API\nThe AutoDisposeProvider API supports ref.watch and disposal behavior.",
                docset_root="https://pub.dev/documentation/riverpod/latest",
                title="AutoDisposeProvider",
            ),
            _dart_doc(
                "https://docs.python.org/3/library/asyncio.html",
                "# asyncio\nForeign Python project chunk mentioning riverpod autoDispose ref.watch must be rejected.",
                docset_root="https://docs.python.org/3",
                title="asyncio",
            ),
        ],
    )

    info = service.resolve_library("riverpod", ecosystem="flutter")
    refreshed = service.refresh_docs(info.library_id, source_type=info.source_type, force=True)
    assert refreshed.status == "updated"
    assert refreshed.pages_indexed > 0
    assert refreshed.chunks_indexed > 0

    official = service.get_docs("riverpod", ecosystem="flutter", topic="reactive dependencies")
    assert official.status == "success"
    official_sources = {chunk.source for chunk in official.results}
    assert any(source and source.startswith("https://riverpod.dev/") for source in official_sources)

    api = service.get_docs("riverpod", ecosystem="flutter", topic="AutoDisposeProvider API")
    assert api.status == "success"
    api_sources = {chunk.source for chunk in api.results}
    assert any(source and source.startswith("https://pub.dev/documentation/riverpod/latest/") for source in api_sources)

    foreign = service.get_docs("riverpod", ecosystem="flutter", topic="asyncio")
    assert not any(chunk.source and chunk.source.startswith("https://docs.python.org/") for chunk in foreign.results)
    assert any(warning["code"] == "wrong_docset_root" for warning in foreign.diagnostics["warnings"])


def test_flutter_bloc_refresh_ingests_and_queries_official_and_pubdev_roots(tmp_path, monkeypatch):
    service = _service_with_fake_fetcher(
        tmp_path,
        monkeypatch,
        [
            _dart_doc(
                "https://bloclibrary.dev/flutter-bloc-concepts/",
                "# BlocProvider\nBlocProvider creates and provides a Bloc instance to child widgets.",
                docset_root="https://bloclibrary.dev",
                title="Flutter Bloc Concepts",
            ),
            _dart_doc(
                "https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocProvider-class.html",
                "# BlocProvider API\nBlocProvider is a Flutter widget for dependency injection of blocs.",
                docset_root="https://pub.dev/documentation/flutter_bloc/latest",
                title="BlocProvider API",
            ),
            _dart_doc(
                "https://fastapi.tiangolo.com/tutorial/",
                "# FastAPI\nForeign project chunk mentioning flutter_bloc BlocProvider must be rejected.",
                docset_root="https://fastapi.tiangolo.com",
                title="FastAPI",
            ),
        ],
    )

    info = service.resolve_library("flutter_bloc", ecosystem="flutter")
    refreshed = service.refresh_docs(info.library_id, source_type=info.source_type, force=True)
    assert refreshed.status == "updated"
    assert refreshed.pages_indexed > 0
    assert refreshed.chunks_indexed > 0

    official = service.get_docs("flutter_bloc", ecosystem="flutter", topic="child widgets")
    assert official.status == "success"
    official_sources = {chunk.source for chunk in official.results}
    assert any(source and source.startswith("https://bloclibrary.dev/") for source in official_sources)

    api = service.get_docs("flutter_bloc", ecosystem="flutter", topic="dependency injection")
    assert api.status == "success"
    api_sources = {chunk.source for chunk in api.results}
    assert any(source and source.startswith("https://pub.dev/documentation/flutter_bloc/latest/") for source in api_sources)

    foreign = service.get_docs("flutter_bloc", ecosystem="flutter", topic="FastAPI")
    assert not any(chunk.source and chunk.source.startswith("https://fastapi.tiangolo.com/") for chunk in foreign.results)
    assert any(warning["code"] == "wrong_docset_root" for warning in foreign.diagnostics["warnings"])
