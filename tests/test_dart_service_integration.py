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
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
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


def test_riverpod_auto_registers_and_get_docs_returns_result(tmp_path, monkeypatch):
    """get_docs for riverpod should register and return a result (may need refresh)."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
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


