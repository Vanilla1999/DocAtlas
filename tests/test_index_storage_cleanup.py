from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def test_project_index_cleanup_is_preview_first_and_mcp_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "isolated-docmancer-home"))
    project = tmp_path / "project"
    storage = project / ".docmancer"
    extracted = storage / "extracted"
    extracted.mkdir(parents=True)
    database = storage / "project.db"
    database.write_text("index", encoding="utf-8")
    (extracted / "chunk.md").write_text("extract", encoding="utf-8")
    (project / "README.md").write_text("source document", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n",
        encoding="utf-8",
    )

    cli_result = CliRunner().invoke(
        cli,
        [
            "clear-index",
            "--scope",
            "project-local",
            "--project-path",
            str(project),
            "--format",
            "json",
        ],
    )

    assert cli_result.exit_code == 0, cli_result.output
    preview = json.loads(cli_result.output)
    assert preview["status"] == "preview"
    assert preview["config_source"] == "project_local"
    assert preview["db_path"] == str(database.resolve())
    assert preview["extracted_dir"] == str(extracted.resolve())
    assert preview["plan"] == [str(database.resolve()), str(extracted.resolve())]
    assert database.exists()
    assert extracted.exists()
    assert (project / "README.md").exists()
    assert (project / "docmancer.yaml").exists()

    mcp_result = call_docs_tool_payload(
        "prepare_docs",
        {"action": "clear_index", "scope": "project-local", "project_path": str(project)},
        LibraryDocsService(),
    )

    assert mcp_result["status"] == "confirmation_required"
    assert mcp_result["requires_confirmation"] is True
    assert mcp_result["arguments_patch"] == {
        "action": "clear_index",
        "scope": "project-local",
        "project_path": str(project.resolve()),
        "plan_digest": mcp_result["plan_digest"],
        "confirm": True,
    }
    assert database.exists()
    assert extracted.exists()

    applied = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "clear_index",
            "scope": "project-local",
            "project_path": str(project),
            "plan_digest": mcp_result["plan_digest"],
            "confirm": True,
        },
        LibraryDocsService(),
    )

    assert applied["status"] == "applied"
    assert applied["removed"] == [str(database.resolve()), str(extracted.resolve())]
    assert not database.exists()
    assert not extracted.exists()
    assert (project / "README.md").exists()
    assert (project / "docmancer.yaml").exists()


def _project_with_local_index(tmp_path: Path, name: str = "project"):
    project = tmp_path / name
    storage = project / ".docmancer"
    extracted = storage / "extracted"
    docs_indexes = storage / "docs-indexes"
    embeddings = storage / "embeddings-cache"
    qdrant = storage / "qdrant"
    for directory in (extracted, docs_indexes, embeddings, qdrant / "storage"):
        directory.mkdir(parents=True, exist_ok=True)
    database = storage / "project.db"
    sqlite_vec = storage / "sqlite-vec.db"
    for path in (
        database,
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
        Path(f"{database}-journal"),
        sqlite_vec,
        Path(f"{sqlite_vec}-wal"),
    ):
        path.write_text(path.name, encoding="utf-8")
    (extracted / "chunk.md").write_text("extract", encoding="utf-8")
    (docs_indexes / "library.db").write_text("docs", encoding="utf-8")
    (embeddings / "cache.bin").write_bytes(b"cache")
    (qdrant / "runtime.json").write_text(
        json.dumps({"ownership_token": "docmancer-managed-qdrant"}),
        encoding="utf-8",
    )
    (qdrant / "storage" / "collection").write_text("vectors", encoding="utf-8")
    (storage / "user-note.txt").write_text("preserve", encoding="utf-8")
    (project / "README.md").write_text("source", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n"
        "embeddings:\n"
        "  cache: .docmancer/embeddings-cache\n"
        "vector_store:\n"
        "  provider: sqlite-vec\n"
        "  options:\n"
        "    db_path: .docmancer/sqlite-vec.db\n",
        encoding="utf-8",
    )
    return project, storage, database, sqlite_vec


def test_project_cleanup_removes_sidecars_owned_vectors_and_caches_but_not_config(tmp_path):
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project, storage, database, sqlite_vec = _project_with_local_index(tmp_path)
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))

    kinds = {target.kind for target in plan.targets}
    assert {
        "sqlite_index", "sqlite_sidecar", "extracted_documents", "docs_indexes",
        "embeddings_cache", "managed_qdrant", "sqlite_vec", "sqlite_vec_sidecar",
    }.issubset(kinds)
    result = cleanup.apply(plan, expected_plan_digest=plan.plan_digest)

    assert result["status"] == "applied"
    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not sqlite_vec.exists()
    assert not (storage / "qdrant").exists()
    assert not (storage / "docs-indexes").exists()
    assert not (storage / "embeddings-cache").exists()
    assert (project / "docmancer.yaml").exists()
    assert (project / "README.md").exists()
    assert (storage / "user-note.txt").read_text(encoding="utf-8") == "preserve"


def test_cleanup_rejects_stale_preview(tmp_path):
    import pytest
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project, _storage, database, _sqlite_vec = _project_with_local_index(tmp_path)
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))
    database.write_text("changed after preview", encoding="utf-8")

    with pytest.raises(RuntimeError, match="stale cleanup plan"):
        cleanup.apply(plan, expected_plan_digest=plan.plan_digest)
    assert database.exists()


def test_cleanup_live_process_is_a_hard_blocker(tmp_path):
    import os
    import pytest
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project, storage, database, _sqlite_vec = _project_with_local_index(tmp_path)
    qdrant = storage / "qdrant"
    (qdrant / "qdrant.pid").write_text(str(os.getpid()), encoding="utf-8")
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))

    assert plan.blocking_reasons
    with pytest.raises(RuntimeError, match="live process"):
        cleanup.apply(plan, allow_incomplete=True)
    assert database.exists()


def test_unowned_qdrant_state_fails_closed_unless_explicitly_retained(tmp_path):
    import pytest
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project, storage, database, _sqlite_vec = _project_with_local_index(tmp_path)
    (storage / "qdrant" / "runtime.json").write_text("{}", encoding="utf-8")
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))

    assert "unowned_local_qdrant_state_not_deleted" in plan.incomplete_reasons
    with pytest.raises(RuntimeError, match="incomplete"):
        cleanup.apply(plan)
    result = cleanup.apply(plan, allow_incomplete=True)
    assert result["status"] == "applied"
    assert not database.exists()
    assert (storage / "qdrant").exists()


def test_global_index_cleanup_preserves_config_mcp_and_unrelated_files(tmp_path, monkeypatch):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    home = tmp_path / "docmancer-home"
    home.mkdir()
    database = home / "docmancer.db"
    extracted = home / "extracted"
    docs_indexes = home / "docs-indexes"
    embeddings = home / "embeddings-cache"
    for directory in (extracted, docs_indexes, embeddings, home / "mcp"):
        directory.mkdir(parents=True, exist_ok=True)
    database.write_text("db", encoding="utf-8")
    Path(f"{database}-wal").write_text("wal", encoding="utf-8")
    (extracted / "page").write_text("page", encoding="utf-8")
    (docs_indexes / "lib").write_text("lib", encoding="utf-8")
    (embeddings / "cache").write_text("cache", encoding="utf-8")
    (home / "docmancer.yaml").write_text("index: {}\n", encoding="utf-8")
    (home / "mcp" / "config.json").write_text("{}", encoding="utf-8")
    (home / "user-note.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setenv("DOCMANCER_HOME", str(home))
    config = DocmancerConfig.model_validate({
        "index": {"db_path": str(database), "extracted_dir": str(extracted)},
        "embeddings": {"cache": str(embeddings)},
        "vector_store": {"provider": "qdrant", "url": "https://qdrant.example"},
    })
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="global", global_config=config, global_config_source="test")
    assert plan.incomplete_reasons == ("remote_qdrant_state_not_deleted",)
    cleanup.apply(plan, allow_incomplete=True)

    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not extracted.exists()
    assert not docs_indexes.exists()
    assert not embeddings.exists()
    assert (home / "docmancer.yaml").exists()
    assert (home / "mcp" / "config.json").exists()
    assert (home / "user-note.txt").read_text(encoding="utf-8") == "keep"



def test_project_local_cleanup_does_not_touch_another_project_root(tmp_path):
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project_a, storage_a, database_a, _ = _project_with_local_index(tmp_path, "project-a")
    project_b, storage_b, database_b, sqlite_vec_b = _project_with_local_index(tmp_path, "project-b")

    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project_a))
    cleanup.apply(plan, expected_plan_digest=plan.plan_digest)

    assert not database_a.exists()
    assert (project_a / "docmancer.yaml").exists()
    assert database_b.exists()
    assert Path(f"{database_b}-wal").exists()
    assert sqlite_vec_b.exists()
    assert (storage_b / "qdrant" / "storage" / "collection").exists()
    assert (project_b / "docmancer.yaml").exists()
    assert (storage_a / "user-note.txt").exists()


def test_missing_global_home_preview_is_side_effect_free(tmp_path, monkeypatch):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    home = tmp_path / "missing-home"
    monkeypatch.setenv("DOCMANCER_HOME", str(home))
    config = DocmancerConfig.model_validate({
        "index": {
            "db_path": str(home / "docmancer.db"),
            "extracted_dir": str(home / "extracted"),
        },
        "embeddings": {"cache": str(home / "embeddings-cache")},
        "vector_store": {"provider": "sqlite-vec", "options": {"db_path": str(home / "sqlite-vec.db")}},
    })

    assert not home.exists()
    plan = IndexStorageCleanup().preview(
        scope="global", global_config=config, global_config_source="test",
    )
    assert not home.exists()
    assert all(not target.exists for target in plan.targets)


def test_cleanup_move_failure_restores_already_quarantined_targets(tmp_path, monkeypatch):
    import pytest
    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup

    project, storage, database, _ = _project_with_local_index(tmp_path)
    extracted = storage / "extracted"
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))
    original_rename = Path.rename

    def failing_rename(self: Path, target: Path):
        if self.resolve(strict=False) == extracted.resolve(strict=False):
            raise OSError("injected move failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)
    with pytest.raises(OSError, match="injected move failure"):
        cleanup.apply(plan, expected_plan_digest=plan.plan_digest)

    assert database.exists()
    assert extracted.exists()
    assert not list(tmp_path.glob(".*.cleanup-trash-*"))


def test_project_cleanup_then_sync_rebuilds_the_project_index(tmp_path, monkeypatch):
    from docmancer.core.config_resolution import resolve_config
    from docmancer.docs.service import LibraryDocsService

    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (docs / "guide.md").write_text(
        "# Rebuild guide\n\nRebuildMarker proves that the synchronized project index is available.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: docs/guide.md\n"
        "    role: other\n"
        "    scope: project\n"
        "    description: Cleanup resynchronization fixture.\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    impact: track\n",
        encoding="utf-8",
    )
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n"
        "embeddings:\n"
        "  cache: .docmancer/embeddings-cache\n"
        "vector_store:\n"
        "  provider: sqlite-vec\n"
        "  options:\n"
        "    db_path: .docmancer/sqlite-vec.db\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DOCMANCER_HOME", str(project / ".docmancer"))
    resolved = resolve_config(project_path=project)
    service = LibraryDocsService(
        config=resolved.config, config_source=resolved.source, config_path=resolved.path,
    )
    first = service.sync_project_docs(str(project), with_vectors=False)
    assert first.status == "success"
    assert Path(resolved.config.index.db_path).exists()

    from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))
    cleanup.apply(plan, expected_plan_digest=plan.plan_digest)
    assert not Path(resolved.config.index.db_path).exists()

    rebuilt = LibraryDocsService(
        config=resolved.config, config_source=resolved.source, config_path=resolved.path,
    )
    second = rebuilt.sync_project_docs(str(project), with_vectors=False)
    assert second.status == "success"
    hits = rebuilt.query_project_docs(str(project), "RebuildMarker", limit=5)
    assert hits
    assert any("RebuildMarker" in hit.text for hit in hits)
