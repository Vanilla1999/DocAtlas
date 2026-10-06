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


@pytest.mark.parametrize("library,ecosystem", [("react", "npm"), ("riverpod", "dart"), ("fastapi", "python")])
def test_literal_curated_spelling_retains_registered_policy(library, ecosystem):
    source = curated.curated_source_for(f" {library.upper()} ", f" {ecosystem.upper()} ", None)
    assert source is not None
    assert source.library == library
    assert source.ecosystem == ecosystem
    target = curated.curated_target_spec(source, version=None)
    assert target["allowed_domains"] == list(source.allowed_domains)
    assert target["path_prefixes"] == list(source.path_prefixes)
    assert target["max_pages"] == source.max_pages
    assert target["seed_urls"] == ([] if not source.verified_seeds else list(source.preferred_seeds))


@pytest.mark.parametrize("ecosystem", ["pub", "flutter", "npm", "node", "typescript", "dart"])
def test_explicit_locator_keeps_protocol_identity_without_fetch(tmp_path, ecosystem):
    service = _service(tmp_path)
    info = service.resolve_library("literal_package", ecosystem=ecosystem, version="1.2.3",
                                   docs_url="https://docs.example/snapshot/1.2.3/", source_type="web")
    assert info.ecosystem == ecosystem
    assert info.requested_version == "1.2.3"
    assert info.local is False
    assert service.resolve_library(info.library_id, source_type="web").source_id == info.source_id


@pytest.mark.parametrize("version", [None, "1.2.3"])
@pytest.mark.parametrize("include_pubdev", [False, True])
def test_crosspackage_identity_is_unresolved_without_guessed_replacement(version, include_pubdev):
    result = resolve_dart_official_docs(" Firebase_Firestore ", version, include_pubdev)
    assert result.package == "firebase_firestore"
    assert result.official_docs_urls == []
    assert result.pubdev_docs_url == ""
    assert result.docs_strategy == "unresolved"
    assert result.official_docs_available is False
    assert not has_official_docs("firebase_firestore")
    assert get_seed_urls_for_package("firebase_firestore", version) == []


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


def test_registered_url_order_and_caps_remain_literal():
    for package, sources in DART_PACKAGE_OFFICIAL_DOCS.items():
        resolution = resolve_dart_official_docs(package, "1.2.3")
        expected = list(sources.official_guides)
        if sources.pubdev_api:
            expected.append(sources.pubdev_api.format(version="1.2.3"))
        if sources.package_page:
            expected.append(sources.package_page)
        assert resolution.official_docs_urls == sorted(set(expected))
        assert get_seed_urls_for_package(package, "1.2.3", max_urls=1) == sorted(set(expected))[:1]


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


def test_unresolved_identity_diagnostics_do_not_reintroduce_locator():
    result = build_dart_diagnostics(package="firebase_firestore", version="1.2.3", root_url=None, chunks_created=0)
    assert result["docs_strategy"] == "unresolved"
    assert result["official_available"] is False
    assert result["root_url"] is None


def test_curated_source_manifest_copy_preserves_locked_path_budget():
    source = curated.curated_source_for("mcp", "python", "1.27.2")
    target = curated.curated_target_spec(source, version="1.27.2")
    assert target["path_prefixes"] == list(source.path_prefixes)
    assert target["max_pages"] == 24
    assert source.exact_snapshot
    target["source_manifest"]["discovery"]["directory"] = "other"
    assert source.source_manifest["discovery"]["directory"] == "docs"
    assert curated.curated_source_for("mcp", "python", "1.27.3") is None


@pytest.mark.parametrize("field,value,error", [
    ("ecosystem", "pub", "wrong_ecosystem"), ("version", "1.2.4", "wrong_version"),
    ("library_id", "dart:other@1.2.3:web", "wrong_library_id"),
    ("canonical_id", "other", "wrong_canonical_id"), ("source_type", "api", "wrong_source_type"),
    ("project_path", "/other", "project_doc_leak"), ("docset_root", "https://docs.example/other", "wrong_docset_root"),
    ("source_url", "https://evil.example/scope/page", "wrong_docset_root"),
])
def test_actual_chunk_identity_barriers_remain_fail_closed(tmp_path, field, value, error):
    service = _service(tmp_path)
    root = "https://docs.example/scope/1.2.3/"
    info = service.resolve_library("literal_package", ecosystem="dart", version="1.2.3", docs_url=root, source_type="web")
    metadata = dict(library_id=info.library_id, canonical_id=info.canonical_id, ecosystem=info.ecosystem,
                    version=info.version, source_type=info.source_type, docset_root=root)
    chunk = SimpleNamespace(source=root + "page", metadata=metadata)
    part = service.library_docs
    assert part._library_chunk_rejection_reason(chunk, info, {info.library_id}, {root}) is None
    metadata[field] = value
    assert part._library_chunk_rejection_reason(chunk, info, {info.library_id}, {root}) == error


def test_recovery_action_retains_confirmation_and_registered_scope(tmp_path):
    service = _service(tmp_path)
    info = service.resolve_library("literal_package", ecosystem="pub", docs_url="https://docs.example/scope/", source_type="web")
    action = service.library_docs._inspection_recovery_action(info)
    assert action["requires_confirmation"] is True
    assert action["security_scope"] == {"scope_expansion_allowed": False, "registered_source_only": True}
    assert action["arguments_patch"]["ecosystem"] == "pub"
