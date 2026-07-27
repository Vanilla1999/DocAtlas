"""Staging, atomic publication, and rollback for library indexes."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable
import json
import os
import shutil
import sqlite3
import tempfile
import time

from docmancer.docs.models import RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.application.library_ingest_ports import LibraryPublicationPorts


class LibraryIndexPublication:
    """Own the only staging-to-production commit path for one library."""

    def __init__(self, ports: LibraryPublicationPorts) -> None:
        self.ports = ports

    def create_staging_index(
        self,
        record: LibraryRecord,
        *,
        staging_owner: dict[str, str] | None = None,
        empty: bool = False,
    ) -> tuple[Any, Path]:
        production = self.ports.index_config_for(record)
        db_path = Path(production.index.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=".docatlas-staging-", dir=db_path.parent))
        (root / ".docatlas-staging-owner.json").write_text(
            json.dumps({"created_at": time.time(), "pid": os.getpid(), **(staging_owner or {})}), encoding="utf-8"
        )
        staging = production.model_copy(deep=True)
        staging.index.db_path = str(root / "index.db")
        staging.index.extracted_dir = str(root / "extracted")
        try:
            if db_path.exists() and not empty:
                with sqlite3.connect(db_path) as source, sqlite3.connect(staging.index.db_path) as destination:
                    source.backup(destination)
            extracted = Path(production.index.extracted_dir)
            if extracted.exists() and not empty:
                shutil.copytree(extracted, staging.index.extracted_dir)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return staging, root

    @staticmethod
    def count_index_config(config: Any) -> tuple[int, int]:
        db_path = Path(config.index.db_path)
        if not db_path.exists():
            return 0, 0
        try:
            with sqlite3.connect(db_path) as conn:
                pages = int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
                chunks = int(conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0])
                return pages, chunks
        except sqlite3.Error:
            return 0, 0

    def publish_and_update(
        self,
        record: LibraryRecord,
        staging: tuple[Any, Path] | None,
        registry_update: Callable[[], Any],
        commit_guard: Callable[[], bool] | None = None,
        post_publish: Callable[[], None] | None = None,
        lock_held: bool = False,
    ) -> Any:
        if staging is None:
            return registry_update()
        staging_config, staging_root = staging
        production = self.ports.index_config_for(record)
        production_db = Path(production.index.db_path)
        production_extracted = Path(production.index.extracted_dir)
        staging_db = Path(staging_config.index.db_path)
        staging_extracted = Path(staging_config.index.extracted_dir)
        backup_root = Path(tempfile.mkdtemp(prefix=".docatlas-backup-", dir=production_db.parent))
        backup_db, backup_extracted, candidate_db = backup_root / production_db.name, backup_root / "extracted", backup_root / "candidate.db"
        committed = rolled_back = database_backed_up = database_published = extracted_backed_up = extracted_published = registry_changed = False
        result: Any = None
        with nullcontext() if lock_held else self.ports.lock_for(record.library_id):
            try:
                def require_active_generation() -> None:
                    if commit_guard is not None and not commit_guard():
                        raise RuntimeError("docs_job_generation_revoked")

                require_active_generation()
                if staging_db.exists():
                    with sqlite3.connect(staging_db) as source, sqlite3.connect(candidate_db) as destination:
                        source.backup(destination)
                require_active_generation()
                if production_db.exists():
                    production_db.replace(backup_db)
                    database_backed_up = True
                if production_extracted.exists():
                    production_extracted.replace(backup_extracted)
                    extracted_backed_up = True
                production_db.parent.mkdir(parents=True, exist_ok=True)
                require_active_generation()
                if candidate_db.exists():
                    candidate_db.replace(production_db)
                    database_published = True
                require_active_generation()
                if staging_extracted.exists():
                    production_extracted.parent.mkdir(parents=True, exist_ok=True)
                    staging_extracted.replace(production_extracted)
                    extracted_published = True
                require_active_generation()
                if post_publish is not None:
                    post_publish()
                require_active_generation()
                result = registry_update()
                registry_changed = True
                require_active_generation()
                committed = True
            except Exception as commit_error:
                try:
                    if database_published and production_db.exists():
                        production_db.unlink()
                    if database_backed_up and backup_db.exists():
                        backup_db.replace(production_db)
                    if extracted_published and production_extracted.exists():
                        shutil.rmtree(production_extracted)
                    if extracted_backed_up and backup_extracted.exists():
                        production_extracted.parent.mkdir(parents=True, exist_ok=True)
                        backup_extracted.replace(production_extracted)
                    if registry_changed:
                        self.ports.restore_record(record)
                    rolled_back = True
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"Library index commit failed and rollback backup was preserved at {backup_root}: {rollback_error}"
                    ) from commit_error
                raise
            finally:
                shutil.rmtree(staging_root, ignore_errors=True)
                if committed or rolled_back:
                    shutil.rmtree(backup_root, ignore_errors=True)
        self.ports.drop_library_agent(record)
        return result

    @staticmethod
    def discard_staging(staging: tuple[Any, Path] | None) -> None:
        if staging:
            shutil.rmtree(staging[1], ignore_errors=True)

    def cancelled_result(self, record: LibraryRecord, started: float) -> RefreshResult:
        return RefreshResult(
            library_id=record.library_id,
            status="cancelled",
            docs_url=record.docs_url,
            last_refreshed_at=record.last_refreshed_at,
            version=record.version,
            source_type=record.source_type,
            message="Library docs prefetch cancelled.",
            duration_ms=int((self.ports.monotonic() - started) * 1000),
        )
