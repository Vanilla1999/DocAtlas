from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
import yaml

from docmancer.core.sqlite_store import SQLiteStore
from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.docs.application.project_docs_member_transaction import (
    MemberDocument, PinnedProject, UnsafeSQLitePathMutation, catalog_entry_hash,
    local_project_identity, member_document,
)
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, validate_prepare_docs_arguments
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import read_project_docs_catalog


@pytest.fixture
def local(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    for path, text in (("README.md", "# Overview\n\nOriginal lexical evidence.\n"),
                       ("other.md", "# Other\n\nUnrelated evidence.\n")):
        (root / path).write_text(text)
    home = tmp_path / "app-home"
    monkeypatch.setenv("DOCATLAS_HOME", str(home))
    policy = MemberStoragePolicy(home, home / "mcp" / "members.db")
    (root / "docatlas.yaml").write_text(f"index:\n  db_path: {policy.db_path}\n")
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "code_files": [], "documents": [
            {"path": path, "role": "overview", "scope": "project", "description": path}
            for path in ("README.md", "other.md")
        ],
    }))
    policy.initialize()
    store = SQLiteStore(policy.db_path)
    app = ProjectDocsService(SimpleNamespace(member_storage_policy=policy))
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


def memory_fixture(local):
    """Mechanics only: isolated memory, never a substitute persistence approval."""
    conn = sqlite3.connect(":memory:")
    with local[1]._connect() as source:
        conn.deserialize(source.serialize())
    conn.row_factory = sqlite3.Row
    return conn


def memory_documents(local, paths=("README.md",)):
    root, _store, _app = local
    members = request(local, paths=paths)["documents"]
    entries = {entry.path: entry for entry in read_project_docs_catalog(root).entries}
    return [member_document(root, MemberDocument(**member), entries[member["path"]],
                            (root / member["path"]).read_bytes()) for member in members]


def memory_upsert(local, conn, paths=("README.md",), generation=None):
    outcome, snapshot = local[1]._upsert_project_members_in_memory(
        conn.serialize(), memory_documents(local, paths), project_path=str(local[0]),
        expected_generation_id=generation,
    )
    conn.deserialize(snapshot)
    return outcome


def memory_state(conn):
    return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("sources", "sections", "index_generations", "generation_sources", "retrieval_children", "retrieval_children_fts")}


@pytest.mark.parametrize("confirm", [None, False, 1, "true"])
def test_confirmation_requires_literal_true_without_effects(local, confirm, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    mutation["confirm"] = confirm
    monkeypatch.setattr(module, "PinnedProject", lambda *_: pytest.fail("path effect"))
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
    monkeypatch.setattr(module, "PinnedProject", lambda *_: pytest.fail("path effect"))
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
    before = state(store)
    payload = handle_prefetch_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(root), "mutation": request(local),
    }, SimpleNamespace(project_docs=app))
    assert payload["status"] == "success"
    assert list(store.extracted_dir.iterdir()) == []
    assert len(state(store)["sources"]) == len(before["sources"]) + 1


def test_direct_ingest_operation(local):
    root, store, app = local
    before = state(store)
    result = app.ingest_project_docs(str(root), mutation=request(local, operation="ingest_project_docs"))
    assert result.status == "success"
    committed = state(store)
    with pytest.raises(PermissionError, match="matching operation"):
        app.ingest_project_docs(str(root), mutation=request(local))
    assert state(store) == committed and committed != before


def test_current_reader_hash_binding_and_crlf_bytes(local):
    root, store, _app = local
    (root / "README.md").write_bytes("# Ω\r\n\r\nExact original bytes.\r\n".encode())
    mutation = request(local)
    reader = ProjectMetadataReader().read(root)
    candidate = next(item for item in reader.docs_candidates if item.path == "README.md")
    assert candidate.catalog_entry_hash == mutation["documents"][0]["catalog_entry_hash"]
    assert candidate.content_hash == "sha256:" + mutation["documents"][0]["content_sha256"]
    with PinnedProject(root) as pinned:
        assert pinned.read("README.md", 256000) == (root / "README.md").read_bytes()


def test_unchanged_repeat_zero_writes(local):
    with memory_fixture(local) as conn:
        outcome = memory_upsert(local, conn)
        before = memory_state(conn)
        repeat = memory_upsert(local, conn, generation=outcome["generation_id"])
        assert repeat["derived_writes"] == 0
        assert repeat["unchanged_files"] == 1
        assert memory_state(conn) == before


def test_member_update_preserves_former_catalog_rows(local):
    root, store, _app = local
    conn = memory_fixture(local)
    first = memory_upsert(local, conn, paths=("README.md", "other.md"))
    other = tuple(conn.execute("SELECT * FROM sources WHERE source=?", (str(root / "other.md"),)).fetchone())
    catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    catalog["documents"] = catalog["documents"][:1]
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog))
    (root / "README.md").write_text("# Changed\n\nNew lexical evidence.\n")
    memory_upsert(local, conn, generation=first["generation_id"])
    assert tuple(conn.execute("SELECT * FROM sources WHERE source=?", (str(root / "other.md"),)).fetchone()) == other
    active = store._active_generation_id(conn)
    assert conn.execute("SELECT content FROM generation_sources WHERE generation_id=? AND source=?",
                        (active, str(root / "other.md"))).fetchone()[0].startswith("# Other")
    conn.close()


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
    with memory_fixture(local) as conn:
        memory_upsert(local, conn)
        before = memory_state(conn)
        with pytest.raises(ValueError, match="generation precondition"):
            memory_upsert(local, conn)
        assert memory_state(conn) == before


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
    conn = memory_fixture(local)
    before = memory_state(conn)
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
        memory_upsert(local, conn, paths=("README.md", "other.md"))
    assert memory_state(conn) == before
    conn.close()
    assert list(local[1].extracted_dir.iterdir()) == []


@pytest.mark.parametrize("lane", ["sources", "generation_sources"])
def test_conflicting_owner_denied_inside_transaction(local, lane):
    root, store, _app = local
    conn = memory_fixture(local)
    first = memory_upsert(local, conn)
    owner = json.loads(conn.execute(f"SELECT metadata_json FROM {lane}").fetchone()[0])
    owner["project_path"] = "/different/project"
    conn.execute(f"UPDATE {lane} SET metadata_json=?", (json.dumps(owner),))
    conn.commit()
    before = memory_state(conn)
    with pytest.raises(PermissionError, match="different owner"):
        memory_upsert(local, conn, generation=first["generation_id"])
    assert memory_state(conn) == before
    conn.close()


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
                                            f"index:\n  db_path: {store.db_path}\n" + configs[kind])
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


def test_d1_catalog_is_frozen_exact_reviewed_members():
    root = Path(__file__).resolve().parents[1]
    raw = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    assert raw["code_files"] == []
    assert len(raw["documents"]) == 14
    assert {item["path"] for item in raw["documents"]} == {
        "README.md", "CONTRIBUTING.md", "docs/INDEX.md", "docs/PROJECT_MAP.md",
        "wiki/Architecture.md", "docs/adr/0003-context-first-project-reads.md",
        "docs/mcp-docs-server.md", "docs/testing.md", "docs/project-docs-mcp-workflow.md",
        "wiki/Supported-Sources.md", "wiki/Commands.md", "docs/index-cleanup.md",
        "docs/modules/project-context-retrieval.md", "docs/modules/evidence-selection.md",
    }
    assert {item["path"]: item["module_path"] for item in raw["documents"]
            if item["scope"] == "module"} == {
        "docs/modules/project-context-retrieval.md": "docmancer/docs",
        "docs/modules/evidence-selection.md": "docmancer/docs",
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
    with pytest.raises((PermissionError, OSError)):
        sync(local, mutation)
    if kind == "journal_symlink":
        assert external.read_bytes() == b"untouched"
        Path(str(store.db_path) + "-journal").unlink()
    if kind == "database_symlink":
        store.db_path.unlink()
        external.rename(store.db_path)
    elif kind == "directory_symlink":
        store.db_path.parent.unlink()
        directory.rename(store.db_path.parent)
    assert state(store) == before


@pytest.mark.parametrize("kind", ["vector_backend", "chunk_config", "corrupt_snapshot"])
def test_active_generation_integrity_is_required(local, kind):
    root, store, _app = local
    conn = memory_fixture(local)
    generation = memory_upsert(local, conn)["generation_id"]
    if kind == "vector_backend":
        conn.execute("UPDATE index_generations SET vector_backend='qdrant'")
    elif kind == "chunk_config":
        conn.execute("UPDATE index_generations SET config_hash='incompatible'")
    else:
        conn.execute("UPDATE generation_sources SET content='corrupted'")
    conn.commit()
    before = memory_state(conn)
    with pytest.raises(ValueError):
        memory_upsert(local, conn, generation=generation)
    assert memory_state(conn) == before
    conn.close()


def test_same_generation_concurrent_writers_cannot_both_commit(local):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    mutation = request(local)
    barrier = Barrier(2)
    def writer():
        barrier.wait(timeout=5)
        try:
            return sync(local, mutation).status
        except (ValueError, sqlite3.OperationalError):
            return "denied"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: writer(), range(2)))
    assert sorted(results) == ["denied", "success"]
    with local[1]._connect() as conn:
        assert conn.execute("SELECT count(*) FROM sources").fetchone()[0] == 1


@pytest.mark.parametrize("input_path", ["docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore", "README.md"])
def test_all_inputs_reject_opened_fd_hardlinks(local, input_path, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root, store, _app = local
    if input_path == ".gitignore":
        (root / input_path).write_text("# fixture\n")
    mutation = request(local)
    os.link(root / input_path, root.parent / "foreign-input")
    forbidden_inode = (root / input_path).stat().st_ino
    original_read = os.read
    def read(fd, length):
        assert os.fstat(fd).st_ino != forbidden_inode, "hardlinked input bytes read"
        return original_read(fd, length)
    monkeypatch.setattr(module.os, "read", read)
    before = state(store)
    with pytest.raises(PermissionError, match="hardlink"):
        sync(local, mutation)
    assert state(store) == before


@pytest.mark.parametrize("kind", ["file_symlink", "file_regular", "parent_symlink", "parent_regular", "root_symlink", "hardlink"])
def test_replacement_between_validation_and_read_is_confined(local, kind, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root, store, _app = local
    directory = root / "docs"
    directory.mkdir()
    (directory / "member.md").write_text("Selected original bytes")
    raw = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    raw["documents"].append({"path": "docs/member.md", "role": "other", "scope": "project", "description": "Member"})
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(raw))
    mutation = request(local, paths=("docs/member.md",))
    foreign = root.parent / "foreign"
    foreign.mkdir()
    (foreign / "member.md").write_text("Forbidden foreign bytes")
    inode = (foreign / "member.md").stat().st_ino
    original_read = os.read
    def read(fd, count):
        assert os.fstat(fd).st_ino != inode, "foreign inode read"
        return original_read(fd, count)
    original_validate = module.finite_local_path
    def validate(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        if args[1] != "docs/member.md":
            return result
        if kind in {"file_symlink", "file_regular"}:
            (directory / "member.md").rename(directory / "original.md")
            if kind == "file_symlink":
                (directory / "member.md").symlink_to(foreign / "member.md")
            else:
                (directory / "member.md").write_text("Replacement bytes")
        elif kind in {"parent_symlink", "parent_regular"}:
            directory.rename(root / "original-docs")
            if kind == "parent_symlink":
                directory.symlink_to(foreign, target_is_directory=True)
            else:
                directory.mkdir()
                (directory / "member.md").write_text("Replacement bytes")
        elif kind == "root_symlink":
            root.rename(root.parent / "original-project")
            root.symlink_to(foreign, target_is_directory=True)
        else:
            os.link(directory / "member.md", foreign / "alias.md")
        return result
    monkeypatch.setattr(module, "finite_local_path", validate)
    monkeypatch.setattr(module.os, "read", read)
    with pytest.raises((PermissionError, OSError)) as error:
        sync(local, mutation)
    assert not isinstance(error.value, UnsafeSQLitePathMutation)
    assert (foreign / "member.md").read_text() == "Forbidden foreign bytes"


@pytest.mark.parametrize("kind", ["directory", "database", "journal", "wal", "shm", "hardlink"])
@pytest.mark.parametrize("phase", ["before_generation", "before_connect", "after_final_recheck"])
def test_storage_swap_cannot_connect_or_write_foreign_files(local, kind, phase, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root, store, _app = local
    mutation = request(local)
    outside = SQLiteStore(root.parent / "outside" / ".docatlas" / "docatlas.db")
    outside_before = outside.db_path.read_bytes()
    original_connect = MemberStoragePolicy.connect
    def checked_connect(self):
        if phase == "before_connect":
            replace()
        return original_connect(self)
    did_replace = []
    def replace():
        if did_replace:
            return
        did_replace.append(True)
        if kind == "directory":
            store.db_path.parent.rename(root / "original-storage")
            store.db_path.parent.symlink_to(outside.db_path.parent, target_is_directory=True)
        elif kind == "database":
            store.db_path.rename(store.db_path.with_name("original.db"))
            store.db_path.symlink_to(outside.db_path)
        elif kind == "hardlink":
            os.link(store.db_path, outside.db_path.parent / "alias.db")
        else:
            suffix = {"journal": "-journal", "wal": "-wal", "shm": "-shm"}[kind]
            Path(str(store.db_path) + suffix).symlink_to(outside.db_path)
    original_generation = MemberStoragePolicy.generation
    def generation(self):
        if phase == "before_generation":
            replace()
        return original_generation(self)
    original_upsert = SQLiteStore.upsert_project_members
    def upsert(self, *args, **kwargs):
        if phase == "after_final_recheck":
            replace()
        return original_upsert(self, *args, **kwargs)
    monkeypatch.setattr(MemberStoragePolicy, "generation", generation)
    monkeypatch.setattr(MemberStoragePolicy, "connect", checked_connect)
    monkeypatch.setattr(SQLiteStore, "upsert_project_members", upsert)
    with pytest.raises((PermissionError, OSError)):
        sync(local, mutation)
    assert did_replace
    assert outside.db_path.read_bytes() == outside_before
    assert sorted(path.name for path in outside.db_path.parent.iterdir()) == (
        ["alias.db", "docatlas.db", "extracted"] if kind == "hardlink" else ["docatlas.db", "extracted"]
    )


@pytest.mark.parametrize("field", ["catalog", "generation"])
def test_catalog_and_generation_preconditions_precede_document_reads(local, field, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    mutation["catalog_sha256" if field == "catalog" else "expected_generation_id"] = (
        "0" * 64 if field == "catalog" else "gen-" + "0" * 32
    )
    reads = []
    original = module._read_member
    def read(pinned, relative, limit, **kwargs):
        reads.append(relative)
        assert relative not in {"README.md", "other.md"}
        if field == "catalog":
            assert relative == "docatlas.project-docs.yaml"
        return original(pinned, relative, limit, **kwargs)
    monkeypatch.setattr(module, "_read_member", read)
    with pytest.raises(ValueError, match="precondition"):
        sync(local, mutation)
    assert reads


def test_remaining_aggregate_allowance_prevents_excess_member_read(local, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root, store, _app = local
    first = (root / "README.md").stat().st_size
    second = (root / "other.md").stat().st_size
    (root / "docatlas.yaml").write_text(
        f"index:\n  db_path: {store.db_path}\nproject:\n  max_scanned_bytes: " + str(first + second - 1) + "\n"
    )
    mutation = request(local, paths=("README.md", "other.md"))
    second_inode = (root / "other.md").stat().st_ino
    original = os.read
    def read(fd, length):
        assert os.fstat(fd).st_ino != second_inode, "excess aggregate bytes consumed"
        return original(fd, length)
    monkeypatch.setattr(module.os, "read", read)
    with pytest.raises(ValueError, match="bounded read limit"):
        sync(local, mutation)
    assert state(store)["sources"] == []


def test_deadline_expiry_after_validation_prevents_first_member_read(local, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    clock = SimpleNamespace(now=0.0, selected=False)
    original_validate = module.finite_local_path
    def validate(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        clock.selected = True
        return result
    original_recheck = PinnedProject.recheck
    def recheck(self):
        original_recheck(self)
        if clock.selected:
            clock.now = 10.0
    original_read = module._read_member
    def read(pinned, relative, limit, **kwargs):
        assert relative != "README.md", "expired member read started"
        return original_read(pinned, relative, limit, **kwargs)
    monkeypatch.setattr(module.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(module, "finite_local_path", validate)
    monkeypatch.setattr(PinnedProject, "recheck", recheck)
    monkeypatch.setattr(module, "_read_member", read)
    with pytest.raises(ValueError, match="deadline exhausted before member read"):
        sync(local, mutation)


@pytest.mark.parametrize("missing", ["O_DIRECTORY", "O_NOFOLLOW", "dir_fd", "platform"])
def test_unsupported_platform_denied_before_any_io(local, missing, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    mutation = request(local)
    if missing in {"O_DIRECTORY", "O_NOFOLLOW"}:
        monkeypatch.delattr(module.os, missing)
    elif missing == "dir_fd":
        monkeypatch.setattr(module.os, "supports_dir_fd", set())
    else:
        monkeypatch.setattr(module, "_DESCRIPTOR_READ_SUPPORTED", False)
    monkeypatch.setattr(module.os, "open", lambda *_args, **_kwargs: pytest.fail("filesystem IO"))
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: pytest.fail("SQLite IO"))
    with pytest.raises(PermissionError, match="unsupported_descriptor_read_platform"):
        sync(local, mutation)


def test_storage_entry_denies_before_consuming_documents_or_connecting(local, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    def documents():
        pytest.fail("documents consumed before unsafe route rejection")
        yield
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: pytest.fail("disk connect"))
    with pytest.raises(UnsafeSQLitePathMutation):
        local[1].upsert_project_members(documents(), project_path=str(local[0]), expected_generation_id=None)


def test_memory_mechanics_reject_disk_connections(local):
    before = state(local[1])
    with local[1]._connect() as conn:
        with pytest.raises(PermissionError, match="in-memory snapshot bytes"):
            local[1]._upsert_project_members_in_memory(
                conn, memory_documents(local), project_path=str(local[0]), expected_generation_id=None,
            )
    assert state(local[1]) == before


@pytest.mark.parametrize("input_path", ["docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore", "README.md"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_replacement_during_read_fails_at_recheck_without_foreign_read(local, input_path, kind, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root, store, _app = local
    if input_path == ".gitignore":
        (root / input_path).write_text("# fixture\n")
    mutation = request(local)
    selected_inode = (root / input_path).stat().st_ino
    outside = root.parent / "foreign-data"
    outside.write_text("Never read or write these bytes")
    foreign_inode = outside.stat().st_ino
    replaced = []
    original = os.read
    def read(fd, count):
        inode = os.fstat(fd).st_ino
        assert inode != foreign_inode, "foreign replacement inode read"
        data = original(fd, count)
        if inode == selected_inode and not replaced:
            replaced.append(True)
            if kind == "symlink":
                (root / input_path).rename(root / (input_path + ".original"))
                (root / input_path).symlink_to(outside)
            else:
                os.link(root / input_path, root.parent / "foreign-alias")
        return data
    monkeypatch.setattr(module.os, "read", read)
    with pytest.raises((PermissionError, OSError)) as error:
        sync(local, mutation)
    assert replaced
    assert not isinstance(error.value, UnsafeSQLitePathMutation)
    assert outside.read_text() == "Never read or write these bytes"
    assert state(store)["sources"] == []


def test_growing_file_never_consumes_more_than_remaining_allowance(local, monkeypatch):
    import docmancer.docs.application.project_docs_member_transaction as module
    root = local[0]
    limit = (root / "README.md").stat().st_size
    original = os.read
    consumed = []
    with PinnedProject(root) as pinned:
        target = pinned.bind("README.md")
        def read(fd, count):
            if fd == target and not consumed:
                with (root / "README.md").open("ab") as writer:
                    writer.write(b"x" * 1000)
            data = original(fd, count)
            if fd == target:
                consumed.append(len(data))
                assert sum(consumed) <= limit
            return data
        monkeypatch.setattr(module.os, "read", read)
        with pytest.raises(PermissionError, match="content"):
            pinned.read("README.md", limit)
    assert sum(consumed) == limit


@pytest.mark.parametrize("git_kind", ["none", "repository", "worktree_marker"])
def test_root_local_identity_never_reads_git_metadata(local, git_kind, monkeypatch):
    root = local[0]
    if git_kind == "repository":
        import subprocess
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "remote.origin.url", "https://invalid.example/fixture.git"], check=True)
    elif git_kind == "worktree_marker":
        (root / ".git").write_text("gitdir: /unselected/external/worktree\n")
    original_open = Path.open
    def open_path(path, *args, **kwargs):
        assert ".git" not in path.parts and "/unselected" not in str(path), "Git identity read"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", open_path)
    assert ProjectDocsService._repository_identity(root) == local_project_identity(root)
    assert local_project_identity(root) == "local:" + hashlib.sha256(str(root).encode()).hexdigest()


@pytest.mark.parametrize("git_kind", ["none", "repository", "worktree_marker"])
def test_real_service_retrieves_committed_fixture_member_bytes(local, git_kind, monkeypatch):
    """Actual member preparation feeds real lexical retrieval with bound bytes."""
    from docmancer.agent import DocmancerAgent
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.application.docs_job_service import DocsJobTracker
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import LibraryDocsService
    root, store, _app = local
    command = "doc-atlas mcp docs-serve"
    original = f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{command}`.\n".encode()
    (root / "README.md").write_bytes(original)
    programs = []
    for index in range(12):
        lines = [f"def validate_protocol_{index}(record):"]
        for field in range(36):
            lines += [f'    if record["binding_{index}_{field}"] != "protocol-{index}-value-{field}":',
                      f'        raise ValueError("invalid protocol {index} binding {field}")']
        lines.append(f'    return record["binding_{index}_35"]')
        programs.append("```python\n" + "\n".join(lines) + "\n```")
    large = ("# Protocol validation\n\n" + "\n\n".join(programs)).encode()
    assert len(large) == 50113
    (root / "protocols.md").write_bytes(large)
    catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    catalog["documents"] = [entry for entry in catalog["documents"] if entry["path"] == "README.md"]
    catalog["documents"].append({"path": "protocols.md", "role": "overview", "scope": "project", "description": "Protocols"})
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog))
    if git_kind == "repository":
        import subprocess
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "remote.origin.url", "https://invalid.example/fixture.git"], check=True)
    elif git_kind == "worktree_marker":
        (root / ".git").write_text("gitdir: /unselected/external/worktree\n")
    result = sync(local, request(local, paths=("README.md", "protocols.md")))
    outcome = result.diagnostics["metrics"]
    config = DocmancerConfig()
    config.index.db_path = str(store.db_path)
    config.index.extracted_dir = str(store.extracted_dir)
    config.retrieval.default_mode = "lexical"
    agent = DocmancerAgent(config=config)
    service = LibraryDocsService(config=config, config_source="explicit",
                                 registry=LibraryRegistry(config.index.db_path), agent=agent,
                                 job_tracker=DocsJobTracker(), library_index_root=root / "unused-library-indexes")
    original_open = Path.open
    def open_path(path, *args, **kwargs):
        assert ".git" not in path.parts and "/unselected" not in str(path), "Git identity read"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", open_path)
    identity = local_project_identity(root)
    chunks = service.project_docs.query_project_docs(str(root), command, tokens=8000, limit=20, scope="project")
    assert chunks
    assert any(command in chunk.text for chunk in chunks)
    originals = {"README.md": original, "protocols.md": large}
    for chunk in chunks:
        assert chunk.metadata["project_identity"] == identity
        assert chunk.metadata["repository_identity"] == identity
        assert chunk.metadata["project_path"] == str(root)
        assert chunk.metadata["source_class"] == "project_file"
        assert chunk.metadata["doc_scope"] == "project"
        assert chunk.text.encode() in originals[chunk.metadata["project_doc_path"]]
    large_chunks = service.project_docs.query_project_docs(
        str(root), " ".join(f"validate_protocol_{index}" for index in range(12)),
        tokens=20000, limit=20, scope="project",
    )
    assert large_chunks
    assert any("validate_protocol_" in chunk.text for chunk in large_chunks)
    assert all(chunk.text.encode() in originals[chunk.metadata["project_doc_path"]] for chunk in large_chunks)
    assert not service.project_docs.query_project_docs(str(root), command, scope="module")
    assert not agent.query(command, budget=8000, filters={
        "project_path": str(root), "project_identity": "git:invalid.example/fixture", "source_class": "project_file",
    })
    if git_kind == "none":
        from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
        payload = handle_context_tool("get_docs_context", {
            "question": "Which command starts the Docs MCP server?", "project_path": str(root),
        }, service)
        assert payload["sources"]
        assert any(command in row["snippet"] for row in payload["sources"])
        assert payload["status"] == "ok"
        public_bytes = sum(len(row["snippet"].encode()) for row in payload["sources"])
    else:
        public_bytes = None
    assert store.active_generation_id() == outcome["generation_id"]
    print(json.dumps({"identity_fixture": git_kind, "README_file_bytes": len(original),
                      "README_retrieved_bytes": sum(len(chunk.text.encode()) for chunk in chunks if chunk.metadata["project_doc_path"] == "README.md"),
                      "protocols_file_bytes": len(large),
                      "public_docs_source_bytes": public_bytes,
                      "protocols_retrieved_bytes": sum(len(chunk.text.encode()) for chunk in large_chunks if chunk.metadata["project_doc_path"] == "protocols.md")}, sort_keys=True))


@pytest.mark.parametrize("lane", ["sources", "generation_sources"])
@pytest.mark.parametrize("identity_field", ["project_identity", "repository_identity"])
def test_legacy_identity_is_not_silently_migrated(local, lane, identity_field):
    conn = memory_fixture(local)
    generation = memory_upsert(local, conn)["generation_id"]
    owner = json.loads(conn.execute(f"SELECT metadata_json FROM {lane}").fetchone()[0])
    owner[identity_field] = "git:unselected.example/legacy"
    conn.execute(f"UPDATE {lane} SET metadata_json=?", (json.dumps(owner),))
    conn.commit()
    before = memory_state(conn)
    with pytest.raises(PermissionError, match="different owner"):
        memory_upsert(local, conn, generation=generation)
    assert memory_state(conn) == before
    conn.close()
