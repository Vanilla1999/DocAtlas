from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
import yaml

from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, validate_prepare_docs_arguments
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import read_project_docs_catalog


@pytest.fixture
def local(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for path, text in (("README.md", "# Overview\n\nOriginal lexical evidence.\n"),
                       ("other.md", "# Other\n\nUnrelated evidence.\n")):
        (root / path).write_text(text)
    (root / "docatlas.yaml").write_text("index:\n  db_path: .docatlas/docatlas.db\n")
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "code_files": [], "documents": [
            {"path": path, "role": "overview", "scope": "project", "description": path}
            for path in ("README.md", "other.md")
        ],
    }))
    store = SQLiteStore(root / ".docatlas" / "docatlas.db")
    app = ProjectDocsService(SimpleNamespace())
    return root, store, app


def request(local, paths=("README.md",), operation="sync_project_docs", generation=None):
    root, store, _app = local
    entries = {entry.path: entry for entry in read_project_docs_catalog(root).entries}
    return {"operation": operation, "confirm": True, "storage_path": str(store.db_path),
            "catalog_sha256": hashlib.sha256((root / "docatlas.project-docs.yaml").read_bytes()).hexdigest(),
            "expected_generation_id": generation, "documents": [
                {"path": path, "content_sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                 "catalog_entry_hash": catalog_entry_hash(entries[path])}
                for path in paths]}


def state(store):
    with store._connect() as conn:
        return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("sources", "sections", "index_generations", "generation_sources", "retrieval_children", "retrieval_children_fts")}


def sync(local, mutation):
    root, _store, app = local
    return app.sync_project_docs(str(root), mutation=mutation)


@pytest.mark.parametrize("confirm", [None, False, 1, "true"])
def test_confirmation_requires_literal_true_without_effects(local, confirm, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    mutation["confirm"] = confirm
    monkeypatch.setattr(module, "validate_project_path", lambda *_: pytest.fail("path effect"))
    with pytest.raises(PermissionError):
        sync(local, mutation)


@pytest.mark.parametrize("change", ["missing_generation", "unknown", "operation", "duplicate", "empty", "escape", "hash", "entry_hash"])
def test_invalid_contract_before_effects(local, change, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    if change == "missing_generation":
        del mutation["expected_generation_id"]
    elif change == "unknown":
        mutation["issuer"] = "host-policy://approved"
    elif change == "operation":
        mutation["operation"] = "ingest_project_docs"
    elif change == "duplicate":
        mutation["documents"] *= 2
    elif change == "empty":
        mutation["documents"] = []
    elif change == "escape":
        mutation["documents"][0]["path"] = "../outside.md"
    else:
        mutation["documents"][0]["content_sha256" if change == "hash" else "catalog_entry_hash"] = "BAD"
    monkeypatch.setattr(module, "validate_project_path", lambda *_: pytest.fail("path effect"))
    with pytest.raises((PermissionError, ValueError)):
        sync(local, mutation)


def test_legacy_entries_remain_effect_free(local, monkeypatch):
    import docmancer.docs.application._project_docs_service_part01 as part1
    import docmancer.docs.application._project_docs_service_part02 as part2
    monkeypatch.setattr(part1, "validate_project_path", lambda *_: pytest.fail("path effect"))
    monkeypatch.setattr(part2, "validate_project_path", lambda *_: pytest.fail("path effect"))
    root, _store, app = local
    with pytest.raises(PermissionError):
        app.ingest_project_docs(str(root), _coordination_held=True)
    with pytest.raises(PermissionError):
        app.sync_project_docs(str(root), changed_paths=["README.md"])
    with pytest.raises(PermissionError):
        app._sync_project_docs_incremental(root, None, with_vectors=False,
                                           changed_paths=None, deleted_paths=None, renamed_paths=None)


def test_public_dispatch_and_no_extraction(local, monkeypatch):
    root, store, app = local
    monkeypatch.setattr(SQLiteStore, "_stage_extraction", lambda *_: pytest.fail("extraction staging"))
    monkeypatch.setattr(SQLiteStore, "delete_source", lambda *_: pytest.fail("source deletion"))
    payload = handle_prefetch_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(root), "mutation": request(local),
    }, SimpleNamespace(project_docs=app))
    assert payload["status"] == "success"
    assert payload["metrics"]["transaction"] == "committed"
    assert payload["metrics"]["generation_id"].startswith("gen-")
    assert list(store.extracted_dir.iterdir()) == []
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM retrieval_children_fts WHERE retrieval_children_fts MATCH 'lexical'").fetchone()[0] > 0
        assert tuple(conn.execute("SELECT markdown_path, json_path FROM sources").fetchone()) == ("", "")


def test_direct_ingest_operation(local):
    root, store, app = local
    result = app.ingest_project_docs(str(root), mutation=request(local, operation="ingest_project_docs"))
    assert result.status == "success"
    assert result.vector_sync["transaction"] == "committed"
    assert store.get_document_content(str(root / "README.md")) == (root / "README.md").read_text()


def test_current_reader_hash_binding_and_crlf_bytes(local):
    root, store, _app = local
    (root / "README.md").write_bytes("# Ω\r\n\r\nExact original bytes.\r\n".encode())
    mutation = request(local)
    reader = ProjectMetadataReader().read(root)
    candidate = next(item for item in reader.docs_candidates if item.path == "README.md")
    assert candidate.catalog_entry_hash == mutation["documents"][0]["catalog_entry_hash"]
    assert candidate.content_hash == "sha256:" + mutation["documents"][0]["content_sha256"]
    sync(local, mutation)
    assert store.get_document_content(str(root / "README.md")).encode() == (root / "README.md").read_bytes()


def test_unchanged_repeat_zero_writes(local):
    outcome = sync(local, request(local)).diagnostics["metrics"]
    before = state(local[1])
    repeat = sync(local, request(local, generation=outcome["generation_id"]))
    assert repeat.diagnostics["metrics"]["derived_writes"] == 0
    assert repeat.diagnostics["metrics"]["unchanged_files"] == 1
    assert state(local[1]) == before


def test_member_update_preserves_former_catalog_rows(local):
    root, store, _app = local
    first = sync(local, request(local, paths=("README.md", "other.md"))).diagnostics["metrics"]
    other = store.source_metadata(str(root / "other.md"))
    catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    catalog["documents"] = catalog["documents"][:1]
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog))
    (root / "README.md").write_text("# Changed\n\nNew lexical evidence.\n")
    sync(local, request(local, generation=first["generation_id"]))
    assert store.source_metadata(str(root / "other.md")) == other
    assert "Unrelated" in store.get_document_content(str(root / "other.md"))
    with store._connect() as conn:
        active = store._active_generation_id(conn)
        assert conn.execute("SELECT content FROM generation_sources WHERE generation_id=? AND source=?",
                            (active, str(root / "other.md"))).fetchone()[0].startswith("# Other")


@pytest.mark.parametrize("field", ["catalog", "content", "generation", "storage"])
def test_precondition_failure_preserves_database(local, field):
    mutation = request(local)
    if field == "catalog":
        mutation["catalog_sha256"] = "0" * 64
    elif field == "content":
        mutation["documents"][0]["content_sha256"] = "0" * 64
    elif field == "generation":
        mutation["expected_generation_id"] = "gen-" + "0" * 32
    else:
        mutation["storage_path"] = str(local[0].parent / "user.db")
    before = state(local[1])
    with pytest.raises((PermissionError, ValueError)):
        sync(local, mutation)
    assert state(local[1]) == before


def test_stale_null_cannot_overwrite_concurrent_commit(local):
    stale = request(local)
    sync(local, request(local))
    before = state(local[1])
    with pytest.raises(ValueError, match="generation precondition"):
        sync(local, stale)
    assert state(local[1]) == before


def test_sqlite_writer_contention_is_fail_closed(local):
    mutation = request(local)
    before = state(local[1])
    with local[1]._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            sync(local, mutation)
        conn.rollback()
    assert state(local[1]) == before


@pytest.mark.parametrize("phase", ["second_document", "activation"])
def test_transaction_rolls_back_partial_work(local, phase, monkeypatch):
    mutation = request(local, paths=("README.md", "other.md"))
    before = state(local[1])
    if phase == "activation":
        monkeypatch.setattr(SQLiteStore, "_activate_generation", lambda *_: (_ for _ in ()).throw(RuntimeError("injected")))
    else:
        original = SQLiteStore._add_document
        calls = []
        def add(self, conn, doc):
            calls.append(doc.source)
            if len(calls) == 2:
                raise RuntimeError("injected")
            return original(self, conn, doc)
        monkeypatch.setattr(SQLiteStore, "_add_document", add)
    with pytest.raises(RuntimeError, match="injected"):
        sync(local, mutation)
    assert state(local[1]) == before
    assert list(local[1].extracted_dir.iterdir()) == []


@pytest.mark.parametrize("lane", ["sources", "generation_sources"])
def test_conflicting_owner_denied_inside_transaction(local, lane):
    root, store, _app = local
    first = sync(local, request(local)).diagnostics["metrics"]
    with store._connect() as conn:
        owner = json.loads(conn.execute(f"SELECT metadata_json FROM {lane}").fetchone()[0])
        owner["project_path"] = "/different/project"
        conn.execute(f"UPDATE {lane} SET metadata_json=?", (json.dumps(owner),))
    before = state(store)
    with pytest.raises(PermissionError, match="different owner"):
        sync(local, request(local, generation=first["generation_id"]))
    assert state(store) == before


@pytest.mark.parametrize("kind", ["symlink", "excluded", "generated", "budget", "utf8", "unselected", "code", "config_shadow", "vector"])
def test_source_and_storage_boundaries(local, kind):
    root, store, _app = local
    mutation = request(local)
    if kind == "symlink":
        target = root.parent / "outside.md"
        target.write_text("Outside")
        (root / "README.md").unlink()
        (root / "README.md").symlink_to(target)
    elif kind in {"excluded", "generated", "budget", "vector", "config_shadow"}:
        configs = {"excluded": "project:\n  exclude_paths: [README.md]\n",
                   "generated": "project:\n  generated_paths: [README.md]\n",
                   "budget": "project:\n  max_file_bytes: 1\n",
                   "vector": "retrieval:\n  default_mode: dense\n",
                   "config_shadow": "index:\n  db_path: /different/user.db\n"}
        (root / "docatlas.yaml").write_text(configs[kind] if kind == "config_shadow" else
                                            "index:\n  db_path: .docatlas/docatlas.db\n" + configs[kind])
    elif kind == "utf8":
        (root / "README.md").write_bytes(b"\xff")
        mutation["documents"][0]["content_sha256"] = hashlib.sha256(b"\xff").hexdigest()
    elif kind == "unselected":
        mutation["documents"][0]["path"] = "missing.md"
    elif kind == "code":
        catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
        catalog["code_files"] = ["secret.py"]
        (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog))
        mutation["catalog_sha256"] = hashlib.sha256((root / "docatlas.project-docs.yaml").read_bytes()).hexdigest()
    before = state(store)
    with pytest.raises((PermissionError, ValueError, OSError)):
        sync(local, mutation)
    assert state(store) == before


@pytest.mark.parametrize("field", ["with_vectors", "plan_digest", "deleted_paths", "changed_paths", "renamed_paths"])
def test_public_contract_rejects_legacy_fields(local, field):
    args = {"action": "sync_project_docs", "project_path": str(local[0]), "mutation": request(local), field: None}
    assert validate_prepare_docs_arguments(args)["status"] == "error"


def test_direct_contract_rejects_legacy_flags(local):
    root, _store, app = local
    with pytest.raises(PermissionError):
        app.sync_project_docs(str(root), mutation=request(local), with_vectors=True)
    with pytest.raises(PermissionError):
        app.ingest_project_docs(str(root), mutation=request(local, operation="ingest_project_docs"), skip_known=False)


def test_d1_catalog_is_frozen_exact_ten():
    root = Path(__file__).resolve().parents[1]
    raw = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    assert raw["code_files"] == []
    assert len(raw["documents"]) == 10
    assert {item["path"] for item in raw["documents"]} == {
        "README.md", "CONTRIBUTING.md", "docs/INDEX.md", "docs/PROJECT_MAP.md",
        "wiki/Architecture.md", "docs/adr/0003-context-first-project-reads.md",
        "docs/mcp-docs-server.md", "docs/testing.md", "docs/project-docs-mcp-workflow.md",
        "wiki/Supported-Sources.md",
    }


@pytest.mark.parametrize("kind", ["database_symlink", "journal_symlink", "hardlink", "directory_symlink"])
def test_storage_links_denied_without_mutation(local, kind):
    root, store, _app = local
    mutation = request(local)
    before = state(store)
    external = root.parent / "external.db"
    if kind == "database_symlink":
        store.db_path.rename(external)
        store.db_path.symlink_to(external)
    elif kind == "journal_symlink":
        external.write_bytes(b"untouched")
        Path(str(store.db_path) + "-journal").symlink_to(external)
    elif kind == "hardlink":
        import os
        os.link(store.db_path, external)
    else:
        directory = root.parent / "external-storage"
        store.db_path.parent.rename(directory)
        store.db_path.parent.symlink_to(directory, target_is_directory=True)
    with pytest.raises(PermissionError):
        sync(local, mutation)
    if kind == "journal_symlink":
        assert external.read_bytes() == b"untouched"
        Path(str(store.db_path) + "-journal").unlink()
    assert state(store) == before


@pytest.mark.parametrize("kind", ["vector_backend", "chunk_config", "corrupt_snapshot"])
def test_active_generation_integrity_is_required(local, kind):
    root, store, _app = local
    generation = sync(local, request(local)).diagnostics["metrics"]["generation_id"]
    with store._connect() as conn:
        if kind == "vector_backend":
            conn.execute("UPDATE index_generations SET vector_backend='qdrant'")
        elif kind == "chunk_config":
            conn.execute("UPDATE index_generations SET config_hash='incompatible'")
        else:
            conn.execute("UPDATE generation_sources SET content='corrupted'")
    before = state(store)
    with pytest.raises(ValueError):
        sync(local, request(local, generation=generation))
    assert state(store) == before


def test_same_generation_concurrent_writers_cannot_both_commit(local):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    mutation = request(local)
    barrier = Barrier(2)
    def writer():
        barrier.wait(timeout=5)
        try:
            return sync(local, mutation).status
        except (sqlite3.OperationalError, ValueError):
            return "denied"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: writer(), range(2)))
    assert sorted(results) == ["denied", "success"]
    with local[1]._connect() as conn:
        assert conn.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
