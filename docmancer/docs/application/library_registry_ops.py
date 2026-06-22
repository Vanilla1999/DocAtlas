from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
import shutil
import sqlite3

from docmancer.docs.models import DocsInspectResult, DocsPruneResult, DocsRemoveResult, LibraryInfo
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import normalize_library_name, normalize_version


class LibraryRegistryOpsDependencies(Protocol):
    registry: Any
    agent_gateway: Any

    def _index_config_for(self, record: LibraryRecord) -> Any: ...

    def _is_stale(self, last_refreshed_at: str | None) -> bool: ...


class LibraryRegistryOps:
    def __init__(self, deps: LibraryRegistryOpsDependencies):
        self.deps = deps

    def index_size_for(self, record: LibraryRecord) -> int:
        config = self.deps._index_config_for(record)
        total = 0
        db_path = Path(config.index.db_path)
        if db_path.exists():
            total += db_path.stat().st_size
        extracted = Path(config.index.extracted_dir)
        if extracted.exists():
            total += sum(path.stat().st_size for path in extracted.rglob("*") if path.is_file())
        return total

    def delete_index_for(self, record: LibraryRecord) -> int:
        config = self.deps._index_config_for(record)
        removed = 0
        db_path = Path(config.index.db_path)
        if db_path.exists():
            removed += db_path.stat().st_size
            db_path.unlink()
        extracted = Path(config.index.extracted_dir)
        if extracted.exists():
            removed += sum(path.stat().st_size for path in extracted.rglob("*") if path.is_file())
            shutil.rmtree(extracted)
        return removed

    def count_index_entries(self, record: LibraryRecord) -> tuple[int, int]:
        config = self.deps._index_config_for(record)
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

    def status_for(self, record: LibraryRecord, size_bytes: int | None = None) -> str:
        if record.status == "failed":
            return "failed"
        pages, chunks = self.count_index_entries(record)
        if pages == 0 and chunks == 0 and Path(self.deps._index_config_for(record).index.db_path).exists():
            return "empty_index"
        size = self.index_size_for(record) if size_bytes is None else size_bytes
        if size == 0:
            return "empty_index"
        if self.deps._is_stale(record.last_refreshed_at):
            return "stale"
        return "indexed"

    def reason_code_for(self, record: LibraryRecord, status: str) -> str:
        if status == "empty_index":
            return "empty_index"
        if status == "stale":
            return "stale"
        if status == "failed":
            return "failed"
        if status == "indexed":
            return "healthy"
        return "not_indexed"

    def inspect_library_docs(self, canonical_id: str) -> DocsInspectResult:
        record = self.deps.registry.get(canonical_id)
        if record is None:
            return DocsInspectResult(canonical_id=canonical_id, status="missing", reason_code="missing", message="library docs target not found")
        size_bytes = self.index_size_for(record)
        status = self.status_for(record, size_bytes)
        pages, chunks = self.count_index_entries(record)
        return DocsInspectResult(
            canonical_id=record.library_id,
            source_id=record.source_id,
            status=status,
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            source_type=record.source_type,
            docs_url=record.docs_url,
            docs_url_resolved=record.docs_url_resolved,
            docs_snapshot_exact=record.docs_snapshot_exact,
            requested_version=record.requested_version,
            resolved_version=record.resolved_version,
            version_source=record.version_source,
            version_confidence=record.version_confidence,
            version_inferred=record.version_inferred,
            last_refreshed_at=record.last_refreshed_at,
            stale=self.deps._is_stale(record.last_refreshed_at),
            pages=pages,
            chunks=chunks,
            reason_code=self.reason_code_for(record, status),
            size_bytes=size_bytes,
            warnings=[record.last_error] if record.last_error else [],
        )

    def remove_library_docs(self, canonical_id: str) -> DocsRemoveResult:
        record = self.deps.registry.get(canonical_id)
        if record is None:
            return DocsRemoveResult(canonical_id=canonical_id, removed=False, message="library docs target not found")
        removed_bytes = self.delete_index_for(record)
        removed = self.deps.registry.delete(record.library_id)
        self.deps.agent_gateway.drop_library_agent(record)
        return DocsRemoveResult(canonical_id=record.library_id, removed=removed, chunks_removed=removed_bytes)

    @staticmethod
    def record_age_cutoff_value(record: LibraryRecord) -> str | None:
        return record.last_refreshed_at or record.last_checked_at or record.added_at

    def prune_library_docs(
        self,
        *,
        library: str | None = None,
        keep_versions: list[str] | None = None,
        older_than_days: int = 90,
        dry_run: bool = True,
    ) -> DocsPruneResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        keep = {normalize_version(version) for version in (keep_versions or [])}
        candidates: list[str] = []
        normalized_library = normalize_library_name(library) if library else None
        for record in self.deps.registry.list():
            if normalized_library and record.normalized_name != normalized_library:
                continue
            if record.version in keep:
                continue
            value = self.record_age_cutoff_value(record)
            if not value:
                continue
            try:
                timestamp = datetime.fromisoformat(value)
            except ValueError:
                timestamp = datetime.min.replace(tzinfo=timezone.utc)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp <= cutoff:
                candidates.append(record.library_id)
        if dry_run:
            return DocsPruneResult(dry_run=True, would_remove=candidates)
        removed: list[str] = []
        for canonical_id in candidates:
            result = self.remove_library_docs(canonical_id)
            if result.removed:
                removed.append(result.canonical_id)
        return DocsPruneResult(dry_run=False, removed=removed)

    def list_libraries(self, stale_only: bool = False, limit: int | None = None) -> list[LibraryInfo]:
        items: list[LibraryInfo] = []
        for record in self.deps.registry.list(limit=limit):
            stale = self.deps._is_stale(record.last_refreshed_at)
            if stale_only and not stale:
                continue
            size_bytes = self.index_size_for(record)
            status = self.status_for(record, size_bytes)
            pages, chunks = self.count_index_entries(record)
            items.append(
                LibraryInfo(
                    library_id=record.library_id,
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    source_type=record.source_type,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    status=status,
                    local=record.last_refreshed_at is not None,
                    stale=stale,
                    last_refreshed_at=record.last_refreshed_at,
                    pages=pages,
                    chunks=chunks,
                    reason_code=self.reason_code_for(record, status),
                    message=record.last_error,
                )
            )
        return items
