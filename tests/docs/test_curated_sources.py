from __future__ import annotations

from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.docs.curated_sources import canonical_source_identity, curated_source_for, curated_sources, curated_target_spec
from docmancer.docs.service import LibraryDocsService


def _service(tmp_path: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(config=config)


def test_curated_manifest_covers_the_parity_libraries_with_bounded_official_sources() -> None:
    sources = curated_sources()

    assert len(sources) >= 30
    assert curated_source_for("fastapi", "python", None) is not None
    assert curated_source_for("react", "typescript", None) is not None
    assert curated_source_for("go_router", "flutter", "14.8.1") is not None
    assert all(source.allowed_domains and source.max_pages <= 24 for source in sources)


def test_curated_target_has_explicit_allowlist_and_never_invents_version_binding() -> None:
    source = curated_source_for("fastapi", "python", None)
    assert source is not None

    target = curated_target_spec(source, version=None)

    assert target["docs_url"] == "https://fastapi.tiangolo.com/"
    assert target["allowed_domains"] == ["fastapi.tiangolo.com"]
    assert target["source_manifest"]["official"] is True
    assert target["source_manifest"]["version_rule"] == "unversioned"
    assert canonical_source_identity("https://fastapi.tiangolo.com/") == canonical_source_identity("https://FASTAPI.tiangolo.com")


def test_exact_request_does_not_register_unversioned_curated_docs(tmp_path: Path) -> None:
    info = _service(tmp_path).resolve_library("fastapi", ecosystem="python", version="0.115.6", source_type="api")

    assert info.library_id is None
    assert info.status == "needs_docs_url"


def test_exact_curated_source_renders_the_requested_version() -> None:
    source = curated_source_for("go_router", "flutter", "16.2.0")
    assert source is not None
    assert source.exact_snapshot is True
    assert source.render("16.2.0") == "https://pub.dev/documentation/go_router/16.2.0/"
    assert curated_target_spec(source, version="16.2.0")["seed_urls"] == []
