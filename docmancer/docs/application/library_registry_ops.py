from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol
import shutil
import sqlite3

from docmancer.docs.models import (
    MANIFEST_INGESTION_POLICY_VERSION,
    DocsInspectResult,
    DocsPruneResult,
    DocsRemoveResult,
    LibraryInfo,
)
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
        if record.status == "partial" or str(record.last_error or "").startswith("partial ingestion:"):
            return "partial"
        pages, chunks = self.count_index_entries(record)
        if pages == 0 and chunks == 0 and Path(self.deps._index_config_for(record).index.db_path).exists():
            return "empty_index"
        size = self.index_size_for(record) if size_bytes is None else size_bytes
        if size == 0:
            return "empty_index"
        if self.deps._is_stale(record.last_refreshed_at):
            return "stale"
        manifest = (record.target_spec or {}).get("source_manifest") or {}
        policy_version = (record.target_spec or {}).get("ingestion_policy_version")
        if (
            manifest.get("schema_version") == 2
            and policy_version is not None
            and policy_version != MANIFEST_INGESTION_POLICY_VERSION
        ):
            return "needs_refresh"
        return "indexed"

    def reason_code_for(self, record: LibraryRecord, status: str) -> str:
        if status == "corpus_incomplete":
            return "corpus_incomplete"
        if status == "empty_index":
            return "empty_index"
        if status == "stale":
            return "stale"
        if status == "needs_refresh":
            return "needs_refresh"
        if status == "failed":
            return "failed"
        if status == "partial":
            return "partial_ingestion"
        if status == "indexed":
            return "healthy"
        return "not_indexed"

    def manifest_coverage(
        self,
        record: LibraryRecord,
        pages: int,
        *,
        config: Any | None = None,
    ) -> tuple[int, int, int, int, str | None]:
        target_spec = record.target_spec or {}
        manifest = target_spec.get("source_manifest") or {}
        if manifest.get("schema_version") != 2:
            return 0, 0, 0, 0, None
        documents = manifest.get("documents") or []
        expected_by_url = {
            str(document.get("blob_url") or ""): document
            for document in documents
            if isinstance(document, dict) and document.get("blob_url")
        }
        if len(expected_by_url) != len(documents):
            return len(documents), 0, len(documents), pages, target_spec.get("active_manifest_digest") or manifest.get("digest")
        config = config or self.deps._index_config_for(record)
        db_path = Path(config.index.db_path)
        if not db_path.exists():
            return len(documents), 0, len(documents), 0, target_spec.get("active_manifest_digest") or manifest.get("digest")
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT s.source, s.content, s.metadata_json, COUNT(sec.id) "
                    "FROM sources AS s LEFT JOIN sections AS sec ON sec.source_id = s.id "
                    "GROUP BY s.id"
                ).fetchall()
        except sqlite3.Error:
            return len(documents), 0, len(documents), 0, target_spec.get("active_manifest_digest") or manifest.get("digest")
        resolved_commit = str((manifest.get("discovery") or {}).get("resolved_commit_sha") or "")
        matched: set[str] = set()
        stale_orphans = 0
        for source, content, raw_metadata, chunk_count in rows:
            try:
                metadata = json.loads(raw_metadata or "{}")
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            canonical_url = str(metadata.get("canonical_url") or source or "")
            document = expected_by_url.get(canonical_url)
            if (
                document is None
                or canonical_url in matched
                or int(chunk_count) < 1
                or str(metadata.get("resolved_commit_sha") or "") != resolved_commit
                or str(metadata.get("git_blob_sha") or "") != str(document.get("git_blob_sha") or "")
                or str(metadata.get("content_sha256") or "") != hashlib.sha256(
                    str(content or "").encode("utf-8")
                ).hexdigest()
            ):
                stale_orphans += 1
                continue
            matched.add(canonical_url)
        expected = len(documents)
        indexed = len(matched)
        return expected, indexed, expected - indexed, stale_orphans, target_spec.get("active_manifest_digest") or manifest.get("digest")

    def manifest_fetched(self, record: LibraryRecord) -> int:
        """Count manifest identities whose fetched source provenance is present.

        Fetch success and extraction/index success are distinct inspection diagnostics,
        so this intentionally does not require any sections for a matching source.
        """
        target_spec = record.target_spec or {}
        manifest = target_spec.get("source_manifest") or {}
        if manifest.get("schema_version") != 2:
            return 0
        documents = manifest.get("documents") or []
        expected_by_url = {
            str(document.get("blob_url") or ""): document
            for document in documents
            if isinstance(document, dict) and document.get("blob_url")
        }
        if len(expected_by_url) != len(documents):
            return 0
        db_path = Path(self.deps._index_config_for(record).index.db_path)
        if not db_path.exists():
            return 0
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT source, content, metadata_json FROM sources").fetchall()
        except sqlite3.Error:
            return 0
        resolved_commit = str((manifest.get("discovery") or {}).get("resolved_commit_sha") or "")
        fetched: set[str] = set()
        for source, content, raw_metadata in rows:
            try:
                metadata = json.loads(raw_metadata or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            canonical_url = str(metadata.get("canonical_url") or source or "")
            document = expected_by_url.get(canonical_url)
            if (
                document is not None
                and canonical_url not in fetched
                and str(metadata.get("resolved_commit_sha") or "") == resolved_commit
                and str(metadata.get("git_blob_sha") or "") == str(document.get("git_blob_sha") or "")
                and str(metadata.get("content_sha256") or "") == hashlib.sha256(
                    str(content or "").encode("utf-8")
                ).hexdigest()
            ):
                fetched.add(canonical_url)
        return len(fetched)

    def active_generation_id(self, record: LibraryRecord) -> str | None:
        db_path = Path(self.deps._index_config_for(record).index.db_path)
        if not db_path.exists():
            return None
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT active_generation_id FROM index_state WHERE singleton = 1"
                ).fetchone()
        except sqlite3.Error:
            return None
        return str(row[0]) if row and row[0] else None

    def inspect_library_docs(self, canonical_id: str) -> DocsInspectResult:
        record = self.deps.registry.get(canonical_id)
        if record is None:
            return DocsInspectResult(canonical_id=canonical_id, status="missing", reason_code="missing", message="library docs target not found")
        size_bytes = self.index_size_for(record)
        pages, chunks = self.count_index_entries(record)
        manifest_expected, manifest_indexed, manifest_missing, manifest_stale_orphans, covered_manifest_digest = self.manifest_coverage(record, pages)
        active_manifest_digest = (record.target_spec or {}).get("active_manifest_digest") or covered_manifest_digest
        manifest_fetched = self.manifest_fetched(record)
        status = self.status_for(record, size_bytes)
        manifest = ((record.target_spec or {}).get("source_manifest") or {})
        discovery = manifest.get("discovery") or {}
        raw_attempt_diagnostics = (record.target_spec or {}).get("last_attempt_manifest_diagnostics")
        attempt_diagnostics = (
            {
                str(key): str(value)
                for key, value in raw_attempt_diagnostics.items()
                if key in {"attempted_manifest_digest", "reason_code"}
            }
            if isinstance(raw_attempt_diagnostics, dict)
            else None
        )
        manifest_incomplete = manifest.get("schema_version") == 2 and (
            not manifest.get("complete") or bool(manifest.get("truncated"))
        )
        if manifest_expected and (manifest_missing or manifest_stale_orphans or manifest_incomplete):
            status = "corpus_incomplete"
        return DocsInspectResult(
            canonical_id=record.library_id,
            source_id=record.source_id,
            status=status,
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            source_type=record.source_type,
            docs_url=record.docs_url,
            docs_url_template=record.docs_url_template,
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
            manifest_expected=manifest_expected,
            manifest_fetched=manifest_fetched,
            manifest_indexed=manifest_indexed,
            manifest_missing=manifest_missing,
            manifest_stale_orphans=manifest_stale_orphans,
            active_manifest_digest=active_manifest_digest,
            last_attempt_manifest_digest=(record.target_spec or {}).get("last_attempt_manifest_digest"),
            last_complete_manifest_digest=(record.target_spec or {}).get("last_complete_manifest_digest"),
            last_attempt_manifest_diagnostics=attempt_diagnostics,
            requested_ref=discovery.get("requested_ref"),
            resolved_commit_sha=discovery.get("resolved_commit_sha"),
            manifest_complete=manifest.get("complete") if manifest.get("schema_version") == 2 else None,
            manifest_truncated=manifest.get("truncated") if manifest.get("schema_version") == 2 else None,
            ingestion_policy_version=(record.target_spec or {}).get("ingestion_policy_version"),
            active_generation_id=self.active_generation_id(record),
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
            if record.status == "failed":
                candidates.append(record.library_id)
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
                    source_id=record.source_id,
                    canonical_id=record.canonical_id or record.library_id,
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
                    message=record.last_error or ("Index is present; run get_library_docs for topic-level health/relevance." if status == "indexed" else None),
                )
            )
        return items
