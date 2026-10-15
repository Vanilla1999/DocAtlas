"""Prepare authored test documents through the real confirmed member route.

The caller supplies finite fixture paths. Catalog discovery is not consent, and
the fixture never refreshes a generation precondition or retries a failed write.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.project_docs_member_transaction import (
    catalog_entry_hash,
    local_project_identity,
)
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import LocalMemberService


def cold_fixture_member_service(tmp_path, monkeypatch):
    """Select disposable host storage outside the separately created project."""
    home = tmp_path / "home"
    monkeypatch.setenv("DOCATLAS_HOME", str(home))
    config = DocmancerConfig()
    config.index.db_path = str(home / "mcp" / "members.db")
    config.index.extracted_dir = str(home / "mcp" / "extracted")
    cold = LocalMemberService(SimpleNamespace(config=config, source="explicit", path=None))
    assert cold._service is None
    assert not cold.member_storage_policy.app_home.exists()
    return cold


def fixture_member_mutation(service, project, paths, *, expected_generation_id):
    """Bind an explicit fixture selection to its current bytes and supplied CAS."""
    root = Path(project)
    entries = {entry.path: entry for entry in read_project_docs_catalog(root).entries}
    return {
        "operation": "sync_project_docs",
        "confirm": True,
        "storage_path": str(service.member_storage_policy.db_path),
        "catalog_sha256": hashlib.sha256((root / "docatlas.project-docs.yaml").read_bytes()).hexdigest(),
        "expected_generation_id": expected_generation_id,
        "documents": [
            {
                "path": path,
                "content_sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                "catalog_entry_hash": catalog_entry_hash(entries[path]),
            }
            for path in paths
        ],
    }


def indexed_fixture_member_service(tmp_path, monkeypatch, project, paths):
    """Confirm one cold lexical transaction, then expose the ordinary service."""
    root = Path(project)
    cold = cold_fixture_member_service(tmp_path, monkeypatch)
    mutation = fixture_member_mutation(cold, root, paths, expected_generation_id=None)
    original = {member["path"]: (root / member["path"]).read_bytes()
                for member in mutation["documents"]}
    result = cold.project_docs.sync_project_docs(str(root), mutation=mutation)
    policy = cold.member_storage_policy
    assert cold._service is None  # The write does not require an eager read service.
    assert result.status == "success"
    assert result.diagnostics["mode"] == "member_upsert"
    assert result.diagnostics["vector_sync"] == {"status": "not_requested"}
    metrics = result.diagnostics["metrics"]
    assert metrics["members"] == metrics["new_count"] == len(original)
    assert metrics["sources_deleted"] == metrics["changed_count"] == 0
    assert metrics["generation_id"] == policy.generation()
    assert policy.validate(root, mutation["storage_path"])
    with closing(policy.connect()) as conn:
        rows = conn.execute(
            "SELECT source, content, content_hash, metadata_json FROM generation_sources "
            "WHERE generation_id = ? ORDER BY source", (metrics["generation_id"],),
        ).fetchall()
    assert {row["source"] for row in rows} == {str(root / path) for path in original}
    requested = {member["path"]: member for member in mutation["documents"]}
    for row in rows:
        path = Path(row["source"]).relative_to(root).as_posix()
        metadata = json.loads(row["metadata_json"])
        assert row["content"].encode("utf-8") == original[path] == (root / path).read_bytes()
        assert row["content_hash"] == requested[path]["content_sha256"]
        assert metadata["project_doc_content_hash"] == "sha256:" + requested[path]["content_sha256"]
        assert metadata["project_doc_catalog_entry_hash"] == requested[path]["catalog_entry_hash"]
        assert metadata["project_identity"] == local_project_identity(root)
        assert metadata["source_class"] == "project_file"
    assert not (policy.db_path.parent / "extracted").exists()
    service = cold.materialize()
    assert service.config.index.db_path == str(policy.db_path)
    assert service.member_storage_policy is policy
    return service, result


def fixture_member_state(service):
    """Snapshot selected source and generation rows for rejection controls."""
    with closing(service.member_storage_policy.connect()) as conn:
        return {
            table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("sources", "sections", "index_state", "index_generations",
                          "generation_sources", "retrieval_children", "retrieval_children_fts")
        }
