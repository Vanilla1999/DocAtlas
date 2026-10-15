"""Literal source identities and explicit policy, without host/manager inference."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.docs import curated_sources as curated
from docmancer.docs.dart_official_docs import (
    DART_PACKAGE_OFFICIAL_DOCS,
    build_dart_diagnostics,
    get_seed_urls_for_package,
    has_official_docs,
    resolve_dart_official_docs,
)
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


def _service(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(config=config, registry=LibraryRegistry(config.index.db_path))


@pytest.mark.parametrize("library,ecosystem", [
    ("riverpod", "pub"), ("riverpod", "flutter"),
    ("react", "javascript"), ("react", "typescript"), ("react", "node"),
])
def test_framework_language_and_manager_do_not_select_other_ecosystem(library, ecosystem, tmp_path):
    assert curated.curated_source_for(library, ecosystem, None) is None
    info = _service(tmp_path).resolve_library(library, ecosystem=ecosystem)
    assert info.status == "needs_docs_url"
    assert info.library_id is None
    assert info.ecosystem == ecosystem




@pytest.mark.parametrize("ecosystem", ["pub", "flutter", "npm", "node", "typescript", "dart"])
def test_explicit_locator_keeps_protocol_identity_without_fetch(tmp_path, ecosystem):
    service = _service(tmp_path)
    info = service.resolve_library("literal_package", ecosystem=ecosystem, version="1.2.3",
                                   docs_url="https://docs.example/snapshot/1.2.3/", source_type="web")
    assert info.ecosystem == ecosystem
    assert info.requested_version == "1.2.3"
    assert info.local is False
    assert service.resolve_library(info.library_id, source_type="web").source_id == info.source_id




@pytest.mark.parametrize("source_type", [None, "api", "web"])
@pytest.mark.parametrize("version", [None, "1.2.3"])
def test_actual_crosspackage_caller_does_not_register_other_library(tmp_path, source_type, version):
    service = _service(tmp_path)
    info = service.resolve_library("firebase_firestore", ecosystem="dart", version=version, source_type=source_type)
    assert info.status == "needs_docs_url"
    assert info.library_id is None
    assert info.docs_url is None
    assert info.candidates == []
    assert service.registry.find_candidates("firebase_firestore", "dart", version, source_type) == []


def test_crosspackage_explicit_input_remains_caller_owned(tmp_path):
    service = _service(tmp_path)
    info = service.resolve_library("firebase_firestore", ecosystem="dart", version="1.2.3",
                                   docs_url="https://docs.example/explicit/", source_type="web")
    assert info.library_id is not None
    assert info.docs_url == "https://docs.example/explicit/"
    assert info.version_source == "explicit"
    assert not info.local


@pytest.mark.parametrize("package", ["cloud_firestore", "flutter_riverpod", "http", "unknown_package"])
def test_real_literal_package_api_snapshot_is_not_rewritten(tmp_path, package):
    expected = f"https://pub.dev/documentation/{package}/1.2.3/"
    assert resolve_dart_official_docs(package, "1.2.3").pubdev_docs_url == expected
    service = _service(tmp_path)
    info = service.resolve_library(package, ecosystem="dart", version="1.2.3", source_type="api")
    record = service.registry.get(info.library_id, source_type="api")
    assert info.docs_url == expected
    assert info.docs_snapshot_exact is True
    assert info.requested_version == info.resolved_version == "1.2.3"
    assert record.target_spec["seed_urls"] == []
    assert record.target_spec["allowed_domains"] == ["pub.dev"]
    assert record.target_spec["max_pages"] == 100




def test_automatic_root_uses_only_explicit_curated_policy(tmp_path):
    service = _service(tmp_path)
    info = service.resolve_library("riverpod", ecosystem="dart")
    source = curated.curated_source_for("riverpod", "dart", None)
    record = service.registry.get(info.library_id, source_type=info.source_type)
    assert record.target_spec == curated.curated_target_spec(source, version=None)
    assert record.target_spec["seed_urls"] == []
    assert record.target_spec["allowed_domains"] == ["riverpod.dev"]
    assert record.target_spec["max_pages"] == 24
    assert info.version_source == "curated_source_manifest"
    assert info.docs_snapshot_exact is False


def test_exact_request_never_auto_selects_unversioned_known_host(tmp_path):
    info = _service(tmp_path).resolve_library("riverpod", ecosystem="dart", version="2.4.0")
    assert info.library_id is None
    assert info.status == "needs_docs_url"
    assert info.version == "2.4.0"


def test_knowledge_host_does_not_override_explicit_source_policy(tmp_path, monkeypatch):
    original = curated.curated_source_for("riverpod", "dart", None)
    # Both locators already exist in the shipped identity map; no new corpus URL.
    source = replace(original, docs_url="https://pub.dev/documentation/riverpod/latest/",
                     allowed_domains=("pub.dev",), preferred_seeds=())
    monkeypatch.setattr(curated, "curated_sources", lambda: (source,))
    info = _service(tmp_path).resolve_library("riverpod", ecosystem="dart")
    assert info.docs_url == source.docs_url
    assert info.version_source == "curated_source_manifest"


@pytest.mark.parametrize("url,expected", [
    ("https://riverpod.dev/", True), ("https://riverpod.dev/unregistered", False),
    ("https://docs.example/", False), ("https://pub.dev.evil.example/", False),
    ("https://riverpod.dev/?pub.dev", False),
    ("https://pub.dev/documentation/riverpod/1.2.3/", False),
])
def test_diagnostics_require_registered_locator_not_host_substring(tmp_path, url, expected):
    service = _service(tmp_path)
    info = service.resolve_library("riverpod", ecosystem="dart", version="1.2.3", docs_url=url)
    result = service.library_docs._with_dart_diagnostics({}, info=info, chunks_created=0)
    assert result["dartdoc"]["used_official_docs"] is expected
    assert result["dartdoc"]["root_url"] == url
    assert result["dartdoc"]["reason_code"] == "dartdoc_ingest_produced_no_chunks"
    assert "mutation_authorized" not in result["dartdoc"]







