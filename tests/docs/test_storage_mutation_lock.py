from __future__ import annotations

from pathlib import Path

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.index_storage_cleanup import IndexStorageCleanup
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.infrastructure.storage_mutation_lock import (
    StorageMutationBusy,
    storage_mutation_lock,
    storage_mutation_lock_path,
)
from docmancer.agent import DocmancerAgent


def _service(tmp_path: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "state" / "index.sqlite")
    config.index.extracted_dir = str(tmp_path / "state" / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def test_project_sync_and_cleanup_share_the_same_database_mutation_lock(tmp_path):
    service = _service(tmp_path)
    db_path = Path(service.config.index.db_path)
    assert storage_mutation_lock_path(db_path).parent == db_path.parent

    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Project\n\nProject documentation.\n", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Project overview.\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    impact: track\n",
        encoding="utf-8",
    )

    with storage_mutation_lock(db_path, operation="test holder"):
        with pytest.raises(StorageMutationBusy, match="project docs sync blocked"):
            service.sync_project_docs(str(project), with_vectors=False)


def test_clear_index_refuses_while_the_same_database_is_being_mutated(tmp_path):
    project = tmp_path / "project"
    storage = project / ".docmancer"
    storage.mkdir(parents=True)
    db = storage / "project.db"
    db.write_text("index", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n",
        encoding="utf-8",
    )
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))

    with storage_mutation_lock(db, operation="test writer"):
        with pytest.raises(StorageMutationBusy, match="index cleanup blocked"):
            cleanup.apply(plan, expected_plan_digest=plan.plan_digest)
    assert db.exists()


def test_storage_mutation_lock_keeps_one_persistent_inode(tmp_path):
    db = tmp_path / "state" / "index.sqlite"
    with storage_mutation_lock(db, operation="first holder") as lock_path:
        first_inode = lock_path.stat().st_ino
    assert lock_path.exists()
    with storage_mutation_lock(db, operation="second holder") as second_path:
        assert second_path == lock_path
        assert second_path.stat().st_ino == first_inode
    assert lock_path.exists()


def test_missing_storage_cleanup_is_idempotent_without_creating_home(tmp_path, monkeypatch):
    home = tmp_path / "missing-home"
    monkeypatch.setenv("DOCMANCER_HOME", str(home))
    config = DocmancerConfig.model_validate({
        "index": {
            "db_path": str(home / "docmancer.db"),
            "extracted_dir": str(home / "extracted"),
        },
        "embeddings": {"cache": str(home / "embeddings-cache")},
        "vector_store": {
            "provider": "sqlite-vec",
            "options": {"db_path": str(home / "sqlite-vec.db")},
        },
    })
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(
        scope="global", global_config=config, global_config_source="test",
    )
    assert not home.exists()
    result = cleanup.apply(plan, expected_plan_digest=plan.plan_digest)
    assert result["status"] == "applied"
    assert result["removed"] == []
    assert not home.exists()


def test_writer_leases_are_visible_to_cleanup_without_serializing_each_other(tmp_path):
    from docmancer.docs.infrastructure.storage_mutation_lock import (
        active_storage_writer_leases,
        storage_writer_lease,
    )

    db = tmp_path / "state" / "index.sqlite"
    with storage_writer_lease(db, operation="writer one"):
        assert active_storage_writer_leases(db) == ("writer one (pid %d)" % __import__("os").getpid(),)
        with storage_writer_lease(db, operation="writer two"):
            active = active_storage_writer_leases(db)
            assert len(active) == 2
            assert any("writer one" in item for item in active)
            assert any("writer two" in item for item in active)
    assert active_storage_writer_leases(db) == ()


def test_cleanup_refuses_while_writer_lease_is_active(tmp_path):
    from docmancer.docs.infrastructure.storage_mutation_lock import storage_writer_lease

    project = tmp_path / "project-with-lease"
    storage = project / ".docmancer"
    storage.mkdir(parents=True)
    db = storage / "project.db"
    db.write_text("index", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n",
        encoding="utf-8",
    )
    cleanup = IndexStorageCleanup()
    plan = cleanup.preview(scope="project-local", project_path=str(project))

    with storage_writer_lease(db, operation="library docs refresh"):
        with pytest.raises(StorageMutationBusy, match="active index writer lease"):
            cleanup.apply(plan, expected_plan_digest=plan.plan_digest)
    assert db.exists()


def test_new_writer_cannot_register_while_cleanup_barrier_is_held(tmp_path):
    from docmancer.docs.infrastructure.storage_mutation_lock import (
        storage_cleanup_barrier,
        storage_writer_lease,
    )

    db = tmp_path / "state" / "index.sqlite"
    with storage_cleanup_barrier(db, operation="test cleanup"):
        with pytest.raises(StorageMutationBusy, match="registration blocked"):
            with storage_writer_lease(db, operation="new writer"):
                pass
