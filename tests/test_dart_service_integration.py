"""Test service integration for Dart/Flutter official docs auto-use."""

from __future__ import annotations

from types import MethodType

import pytest


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
    assert result.preindex["dartdoc"]["reason_code"] == "dartdoc_root_only"
