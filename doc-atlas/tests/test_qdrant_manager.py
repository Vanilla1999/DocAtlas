from __future__ import annotations

import os
import sys

import pytest

from docmancer.runtime.qdrant_manager import (
    QdrantManager,
    detect_platform,
    ensure_running,
)


def test_detect_platform_returns_tuple_or_none():
    spec = detect_platform()
    # On any supported dev platform, this should resolve. On unsupported,
    # ensure_running's caller is expected to fall back to sqlite-vec.
    assert spec is None or (isinstance(spec, tuple) and len(spec) == 2)


def test_url_override_short_circuits(monkeypatch):
    monkeypatch.setenv("DOCMANCER_QDRANT_URL", "http://example.invalid:6333")
    res = ensure_running()
    assert res.url == "http://example.invalid:6333"
    assert res.managed is False
    assert res.reason == "env-override"


def test_status_for_unstarted_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "docmancer"))
    mgr = QdrantManager()
    st = mgr.status()
    assert st["alive"] is False
    assert st["owned"] is False
    assert st["pid"] is None


def test_stop_when_not_running_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "docmancer"))
    mgr = QdrantManager()
    assert mgr.stop() is False


def test_missing_binary_returns_fallback(tmp_path, monkeypatch):
    """Pointing at a nonexistent override binary triggers the fallback path."""
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "docmancer"))
    monkeypatch.setenv("DOCMANCER_QDRANT_BINARY", str(tmp_path / "does-not-exist"))
    mgr = QdrantManager()
    assert mgr.resolve_binary() is None
