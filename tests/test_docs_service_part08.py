"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_inspect_library_docs_reports_complete_manifest_coverage(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-health", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "indexed"
    assert result.manifest_expected == 1
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 0
    assert result.manifest_stale_orphans == 0
    assert result.active_manifest_digest == manifest["digest"]


def test_inspect_library_docs_exposes_complete_manifest_and_generation_identity(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-inspection", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        docs_url_template="https://github.com/acme/sample/blob/{version}/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={
            "source_manifest": manifest,
            "active_manifest_digest": manifest["digest"],
            "last_attempt_manifest_digest": manifest["digest"],
            "last_complete_manifest_digest": manifest["digest"],
            "ingestion_policy_version": 1,
        },
    )
    _add_manifest_documents(service, record, manifest, generation=True)

    result = service.inspect_library_docs(record.library_id)

    assert result.docs_url_template == "https://github.com/acme/sample/blob/{version}/docs/guide.md"
    assert result.manifest_fetched == 1
    assert result.requested_ref == "v1"
    assert result.resolved_commit_sha == "1" * 40
    assert result.manifest_complete is True
    assert result.manifest_truncated is False
    assert result.ingestion_policy_version == 1
    assert result.active_generation_id is not None
    assert result.active_generation_id.startswith("gen-")


def test_inspect_library_docs_marks_old_manifest_policy_needs_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-old-policy", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest, "ingestion_policy_version": 0},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "needs_refresh"
    assert result.reason_code == "needs_refresh"


def test_inspect_library_docs_marks_incomplete_manifest_unhealthy(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [
            {"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12},
            {"path": "docs/extra.md", "git_blob_sha": "3" * 40, "size": 12},
        ],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-incomplete", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest, manifest["documents"][:1])
    store = SQLiteStore(
        service._index_config_for(record).index.db_path,
        service._index_config_for(record).index.extracted_dir,
    )
    store.add_documents([Document(
        source="https://github.com/acme/sample/blob/" + "1" * 40 + "/docs/stale.md",
        content="# stale\nWrong manifest source.",
        metadata={
            "canonical_url": "https://github.com/acme/sample/blob/" + "1" * 40 + "/docs/stale.md",
            "resolved_commit_sha": "1" * 40,
            "git_blob_sha": "4" * 40,
        },
    )])

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "corpus_incomplete"
    assert result.reason_code == "corpus_incomplete"
    assert result.manifest_expected == 2
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 1
    assert result.manifest_stale_orphans == 1


def test_inspect_library_docs_marks_truncated_manifest_unhealthy(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": False,
        "truncated": True,
    })
    record = service.registry.upsert(
        library="manifest-truncated", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "corpus_incomplete"
    assert result.reason_code == "corpus_incomplete"
    assert result.manifest_expected == 1
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 0










