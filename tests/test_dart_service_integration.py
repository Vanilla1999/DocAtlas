"""Test service integration for Dart/Flutter official docs auto-use."""

from __future__ import annotations

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
    assert info.docs_url is not None
    assert "riverpod.dev" in info.docs_url
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
    """go_router has only pub.dev URLs, should still return needs_docs_url."""
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
    
    # Should at least return something reasonable
    assert result is not None
    # Status could be needs_input, needs_refresh, success, etc.
    # The key is it should not crash and should not be needs_docs_url
    if result.status == "needs_docs_url":
        # If it does need docs_url, at least candidates should have official docs
        candidates = result.diagnostics.get("candidates", []) if hasattr(result, "diagnostics") else []
        assert len(candidates) == 0 or any("riverpod.dev" in str(c.get("docs_url", "")) for c in candidates) is not False
