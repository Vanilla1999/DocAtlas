from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable
import shutil
import sqlite3
import tempfile
import time

import httpx

from docmancer.docs.models import RefreshResult
from docmancer.docs.fetch_policy import DocsFetchSecurityError
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.dart_official_docs import build_dart_diagnostics, canonical_dart_ecosystem

logger = logging.getLogger(__name__)


def _refresh_failure_code(exc: Exception) -> str:
    """Return a stable, safe failure category for a library ingestion attempt."""
    if isinstance(exc, DocsFetchSecurityError):
        return exc.category
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect_timeout"
    if isinstance(exc, httpx.ReadTimeout):
        return "read_timeout"
    if isinstance(exc, httpx.TimeoutException):
        return "network_timeout"
    if isinstance(exc, httpx.ConnectError):
        return "network_unreachable"
    if isinstance(exc, httpx.TransportError):
        return "network_transport_error"
    if isinstance(exc, httpx.HTTPStatusError):
        return "http_failure"
    message = str(exc).lower()
    if "extract" in message:
        return "extraction_failed"
    return "indexing_failed"


def _retryable_failure(exc: Exception, reason_code: str) -> bool:
    if isinstance(exc, DocsFetchSecurityError):
        return exc.retryable
    return reason_code in {
        "dns_failure",
        "network_unreachable",
        "connect_timeout",
        "read_timeout",
        "tls_failure",
        "network_timeout",
        "network_transport_error",
    }


def _safe_failure_message(exc: Exception, reason_code: str) -> str:
    if isinstance(exc, DocsFetchSecurityError):
        return f"{reason_code}: {exc.failed_url}"
    return reason_code


def _merged_discovery_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "discovery_strategy": "unknown",
            "sitemap_pages": 0,
            "seed_pages": 0,
            "fallback_pages": 0,
            "warnings": [],
        }
    strategies = []
    warnings: list[dict[str, Any]] = []
    sitemap_pages = seed_pages = fallback_pages = 0
    fallback_reasons = []
    for item in items:
        strategy = item.get("discovery_strategy")
        if strategy and strategy not in strategies:
            strategies.append(str(strategy))
        sitemap_pages += int(item.get("sitemap_pages") or 0)
        seed_pages += int(item.get("seed_pages") or 0)
        fallback_pages += int(item.get("fallback_pages") or 0)
        fallback_reason = item.get("fallback_reason")
        if fallback_reason and fallback_reason not in fallback_reasons:
            fallback_reasons.append(str(fallback_reason))
    for reason in fallback_reasons:
        warnings.append({"code": reason, "blocking": False})
    return {
        "discovery_strategy": "+".join(strategies) if strategies else "unknown",
        "sitemap_pages": sitemap_pages,
        "seed_pages": seed_pages,
        "fallback_pages": fallback_pages,
        "warnings": warnings,
    }


def _dart_refresh_diagnostics(
    record: LibraryRecord,
    *,
    pages_discovered: int | None,
    pages_extracted: int | None,
    chunks_created: int | None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    if canonical_dart_ecosystem(record.ecosystem) != "dart":
        return {}
    used_official_docs = bool(record.docs_url and "pub.dev" not in record.docs_url)
    return {
        "dartdoc": build_dart_diagnostics(
            package=record.name,
            version=record.version,
            root_url=record.docs_url,
            pages_discovered=pages_discovered,
            pages_extracted=pages_extracted,
            chunks_created=chunks_created,
            used_official_docs=used_official_docs,
            reason_code=reason_code,
        )
    }


def _metadata_for_record(record: LibraryRecord) -> dict[str, Any]:
    metadata = {
        "library_id": record.library_id,
        "canonical_id": record.canonical_id,
        "ecosystem": record.ecosystem,
        "source_type": record.source_type,
        "docs_url": record.docs_url,
        "docs_url_resolved": record.docs_url_resolved or record.docs_url,
        "registry_docset_root": record.docs_url_resolved or record.docs_url,
        "requested_version": record.requested_version,
        "resolved_version": record.resolved_version,
        "version_binding": (record.target_spec or {}).get("dart_docs", {}).get("version_binding"),
        "docs_snapshot_exact": record.docs_snapshot_exact,
    }
    if record.docs_snapshot_exact is not False and record.version:
        metadata["version"] = record.version
    return {key: value for key, value in metadata.items() if value is not None}


class LibraryRefreshOps:
    """Refresh and prefetch operations for registered library docs."""

    def __init__(self, dependencies: Any):
        self.dependencies = dependencies
        self._cleanup_orphaned_staging()

    def _cleanup_orphaned_staging(self, max_age_seconds: float = 24 * 60 * 60) -> None:
        config = getattr(self.dependencies, "config", None)
        if config is None:
            return
        parent = Path(config.index.db_path).expanduser().resolve().parent
        cutoff = time.time() - max_age_seconds
        for root in parent.glob(".docatlas-staging-*"):
            marker = root / ".docatlas-staging-owner.json"
            try:
                if not marker.is_file() or marker.stat().st_mtime >= cutoff:
                    continue
                owner = json.loads(marker.read_text(encoding="utf-8"))
                job_id = str(owner["job_id"])
                generation_id = str(owner["generation_id"])
                jobs = getattr(self.dependencies, "jobs", None)
                if jobs is not None and jobs.generation_active(job_id, generation_id):
                    continue
                shutil.rmtree(root)
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Unable to clean orphaned staging directory: %s", root)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.dependencies, name)

    def refresh_record(
        self,
        record: LibraryRecord,
        *,
        force: bool,
        should_cancel: Callable[[], bool] | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
    ) -> RefreshResult:
        started = time.monotonic()
        if not record.docs_url:
            return RefreshResult(
                library_id=record.library_id,
                status="needs_docs_url",
                docs_url=None,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message="Pass docs_url to ingest this library.",
                duration_ms=int((time.monotonic() - started) * 1000),
                targets_failed=1,
            )
        pages, chunks = self.registry_ops.count_index_entries(record)
        index_empty = pages == 0 and chunks == 0
        if not force and not self._is_stale(record.last_refreshed_at) and not index_empty:
            return RefreshResult(
                library_id=record.library_id,
                status="skipped",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                duration_ms=int((time.monotonic() - started) * 1000),
                targets_completed=1,
            )

        staging = self._create_staging_index(record, staging_owner=staging_owner) if should_cancel else None

        sections_indexed = 0
        discovery_diagnostics: list[dict[str, Any]] = []
        fetch_failure: Exception | None = None
        try:
            target = self._target_from_record(record)
            urls = self._record_urls(record)
            seed_urls_for_discovery = list(target.seed_urls)
            if seed_urls_for_discovery and (target.docs_url or target.docs_url_template):
                urls = urls[:1]
            per_url_max_pages = target.max_pages if target.doc_format == "dartdoc" else (1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages)
            agent = self.agent_gateway.agent_for_config(staging[0]) if staging else self._agent_instance(record)
            for url in urls:
                indexed_sections = agent.add(
                    url,
                    recreate=False,
                    max_pages=per_url_max_pages,
                    browser=target.browser,
                    seed_urls=seed_urls_for_discovery if (target.docs_url or target.docs_url_template) else None,
                    allowed_domains=target.allowed_domains,
                    path_prefixes=target.path_prefixes,
                    metadata=_metadata_for_record(record),
                    cancellation_callback=should_cancel,
                    with_vectors=False if staging else True,
                )
                if isinstance(indexed_sections, int):
                    sections_indexed += indexed_sections
                if getattr(agent, "last_discovery_diagnostics", None):
                    discovery_diagnostics.append(dict(agent.last_discovery_diagnostics))
                fetch_failure = getattr(agent, "last_fetch_failure", None) or fetch_failure
        except Exception as exc:
            if should_cancel and should_cancel():
                self._discard_staging(staging)
                return self._cancelled_result(record, started)
            if begin_commit and not begin_commit():
                self._discard_staging(staging)
                return self._cancelled_result(record, started)
            self._discard_staging(staging)
            reason_code = _refresh_failure_code(exc)
            retryable = _retryable_failure(exc, reason_code)
            message = _safe_failure_message(exc, reason_code)
            logger.warning("Refresh failed for record %s: %s", record.library_id, reason_code)
            if not retryable:
                self.registry.upsert(
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    source_type=record.source_type,
                    now=self._now(),
                    status="failed",
                    last_error=message,
                    target_spec=record.target_spec,
                )
            return RefreshResult(
                library_id=record.library_id,
                status="failed",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=message,
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_failed=1,
                targets_failed=1,
                preindex={
                    "library": record.name,
                    "canonical_id": record.canonical_id,
                    "docs_url": record.docs_url,
                    "reason_code": reason_code,
                    "failure_phase": getattr(exc, "phase", "indexing"),
                    "failed_url": getattr(exc, "failed_url", None),
                    "http_status": getattr(exc, "status_code", None),
                    "retryable": retryable,
                    **_dart_refresh_diagnostics(
                        record,
                        pages_discovered=sections_indexed,
                        pages_extracted=0,
                        chunks_created=0,
                        reason_code=reason_code,
                    ),
                },
            )

        if should_cancel and should_cancel():
            self._discard_staging(staging)
            return self._cancelled_result(record, started)

        pages_after, chunks_after = (
            self._count_index_config(staging[0]) if staging else self.registry_ops.count_index_entries(record)
        )
        if begin_commit and not begin_commit():
            self._discard_staging(staging)
            return self._cancelled_result(record, started)

        vector_failure: Exception | None = None

        def _sync_vectors_before_commit() -> None:
            nonlocal vector_failure
            try:
                production_agent = self._agent_instance(record)
                sync_vectors = getattr(production_agent, "sync_vectors", None)
                if callable(sync_vectors):
                    sync_vectors()
            except Exception as exc:
                vector_failure = exc

        def _commit_registry(**values: Any) -> Any:
            def update() -> Any:
                if vector_failure is not None:
                    values["last_error"] = f"vector_indexing_failed: {vector_failure}"
                return self.registry.upsert(**values)

            post_publish = _sync_vectors_before_commit if staging and sections_indexed > 0 else None
            return self._publish_staging_and_update(
                record,
                staging,
                update,
                commit_guard=begin_commit,
                post_publish=post_publish,
            )

        if sections_indexed == 0 or pages_after == 0 or chunks_after == 0:
            refreshed_at = self._now()
            reason = "ingest_produced_no_chunks" if sections_indexed > 0 else "no_extractable_content"
            _commit_registry(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=record.docs_url,
                docs_url_template=record.docs_url_template,
                source_type=record.source_type,
                now=refreshed_at,
                status="empty_index",
                last_refreshed_at=record.last_refreshed_at,
                last_error=reason,
                target_spec=record.target_spec,
            )
            index_config = self._index_config_for(record) if hasattr(self, "_index_config_for") else None
            db_path = str(Path(index_config.index.db_path).resolve()) if index_config and index_config.index else None
            return RefreshResult(
                library_id=record.library_id,
                status="empty_index",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=f"{reason}: refresh indexed no usable chunks. Check docs_url, source_type, doc_format, browser, or Dartdoc seed discovery.",
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                chunks_indexed=chunks_after,
                targets_failed=1,
                preindex={
                    "library": record.name,
                    "canonical_id": record.canonical_id,
                    "docs_url": record.docs_url,
                    "docs_url_resolved": record.docs_url_resolved or record.docs_url,
                    "source_type": record.source_type or "api",
                    **_merged_discovery_diagnostics(discovery_diagnostics),
                    "pages_indexed": pages_after,
                    "chunks_indexed": chunks_after,
                    "index_path": db_path,
                    "query_index_path": db_path,
                    "reason_code": reason,
                    **_dart_refresh_diagnostics(
                        record,
                        pages_discovered=pages_after,
                        pages_extracted=pages_after,
                        chunks_created=chunks_after,
                    ),
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                },
            )

        refreshed_at = self._now()
        _commit_registry(
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            docs_url=record.docs_url,
            docs_url_template=record.docs_url_template,
            source_type=record.source_type,
            now=refreshed_at,
            status="available",
            last_refreshed_at=refreshed_at,
            last_error="",
            target_spec=record.target_spec,
        )

        if vector_failure is not None:
            message = f"vector_indexing_failed: {vector_failure}"
            return RefreshResult(
                library_id=record.library_id,
                status="partial",
                docs_url=record.docs_url,
                last_refreshed_at=refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=message,
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                chunks_indexed=chunks_after,
                targets_completed=1,
                reason_codes=["vector_indexing_failed"],
            )

        # Build preindex diagnostics
        index_config = self._index_config_for(record)
        db_path = Path(index_config.index.db_path).resolve() if index_config and index_config.index else None
        reason_code = "healthy" if chunks_after > 0 else "empty_index"
        preindex = {
            "library": record.name,
            "canonical_id": record.canonical_id,
            "docs_url": record.docs_url,
            "docs_url_resolved": record.docs_url_resolved or record.docs_url,
            "docset_root": record.docs_url_resolved or record.docs_url,
            "source_type": record.source_type or "api",
            **_merged_discovery_diagnostics(discovery_diagnostics),
            "pages_indexed": pages_after,
            "chunks_indexed": chunks_after,
            "index_path": str(db_path) if db_path else None,
            "query_index_path": str(db_path) if db_path else None,
            "reason_code": reason_code,
            **_dart_refresh_diagnostics(
                record,
                pages_discovered=pages_after,
                pages_extracted=pages_after,
                chunks_created=chunks_after,
            ),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }

        if fetch_failure is not None:
            failure_code = _refresh_failure_code(fetch_failure)
            retryable = _retryable_failure(fetch_failure, failure_code)
            preindex.update(
                reason_code=failure_code,
                failure_phase=getattr(fetch_failure, "phase", "fetching"),
                failed_url=getattr(fetch_failure, "failed_url", None),
                http_status=getattr(fetch_failure, "status_code", None),
                retryable=retryable,
            )
            return RefreshResult(
                library_id=record.library_id,
                status="partial",
                docs_url=record.docs_url,
                last_refreshed_at=refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=_safe_failure_message(fetch_failure, failure_code),
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                chunks_indexed=chunks_after,
                targets_completed=1,
                reason_codes=[failure_code],
                preindex=preindex,
            )

        return RefreshResult(
            library_id=record.library_id,
            status="updated",
            docs_url=record.docs_url,
            last_refreshed_at=refreshed_at,
            version=record.version,
            source_type=record.source_type,
            duration_ms=int((time.monotonic() - started) * 1000),
            pages_indexed=pages_after,
            chunks_indexed=chunks_after,
            targets_completed=1,
            preindex=preindex,
        )

    def refresh_docs(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        versions: list[str] | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        force: bool = True,
        continue_on_error: bool = True,
        should_cancel: Callable[[], bool] | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
    ) -> RefreshResult:
        started = time.monotonic()
        if should_cancel and should_cancel():
            return RefreshResult(
                library_id=None,
                status="cancelled",
                docs_url=docs_url_template or docs_url,
                last_refreshed_at=None,
                version=version,
                source_type=source_type or "api",
                message="Library docs prefetch cancelled.",
            )
        if versions:
            updated = skipped = partial = failed = needs_url = 0
            pages_indexed = pages_failed = chunks_indexed = 0
            last: RefreshResult | None = None
            failure_codes: list[str] = []
            for item_version in versions:
                if should_cancel and should_cancel():
                    return RefreshResult(
                        library_id=None,
                        status="cancelled",
                        docs_url=docs_url_template or docs_url,
                        last_refreshed_at=last.last_refreshed_at if last else None,
                        message="Library docs prefetch cancelled.",
                        duration_ms=int((time.monotonic() - started) * 1000),
                        pages_indexed=pages_indexed,
                        pages_failed=pages_failed,
                        chunks_indexed=chunks_indexed,
                        targets_completed=updated + skipped,
                        targets_failed=failed + needs_url,
                    )
                last = self.refresh_docs(
                    library,
                    ecosystem=ecosystem,
                    version=item_version,
                    docs_url=docs_url if len(versions) == 1 else None,
                    docs_url_template=docs_url_template,
                    source_type=source_type,
                    force=force,
                    continue_on_error=continue_on_error,
                    should_cancel=should_cancel,
                    begin_commit=begin_commit,
                    staging_owner=staging_owner,
                )
                if last.status == "updated":
                    updated += 1
                elif last.status == "skipped":
                    skipped += 1
                elif last.status == "partial":
                    partial += 1
                    for reason_code in last.reason_codes:
                        if reason_code not in failure_codes:
                            failure_codes.append(reason_code)
                elif last.status == "needs_docs_url":
                    needs_url += 1
                else:
                    failed += 1
                    codes = list(last.reason_codes)
                    if not codes and last.preindex and last.preindex.get("reason_code"):
                        codes = [str(last.preindex["reason_code"])]
                    for reason_code in codes:
                        if reason_code not in failure_codes:
                            failure_codes.append(reason_code)
                pages_indexed += last.pages_indexed
                pages_failed += last.pages_failed
                chunks_indexed += last.chunks_indexed
                if not continue_on_error and last.status in {"failed", "needs_docs_url"}:
                    break
            aborted = not continue_on_error and last is not None and last.status in {"failed", "needs_docs_url"}
            status = "aborted" if aborted else ("failed" if failed else ("needs_docs_url" if needs_url else ("partial" if partial else ("updated" if updated else "skipped"))))
            message = f"updated={updated} skipped={skipped} partial={partial} failed={failed} needs_docs_url={needs_url}"
            if failure_codes:
                message = f"{message} reason_code={','.join(failure_codes)}"
            return RefreshResult(
                library_id=None,
                status=status,
                docs_url=docs_url_template or docs_url,
                last_refreshed_at=last.last_refreshed_at if last else None,
                message=message,
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_indexed=pages_indexed,
                pages_failed=pages_failed,
                chunks_indexed=chunks_indexed,
                targets_completed=updated + skipped + partial,
                targets_failed=failed + needs_url,
                preindex=last.preindex if last else None,
                reason_codes=failure_codes,
            )

        info = self.resolve_library(library, ecosystem, version, docs_url, docs_url_template, source_type)
        record = self._record_from_info(info)
        if record is None:
            return RefreshResult(
                library_id=None,
                status="needs_docs_url",
                docs_url=docs_url,
                last_refreshed_at=None,
                version=version,
                source_type=source_type or "api",
                message="Pass docs_url to ingest this library.",
                duration_ms=int((time.monotonic() - started) * 1000),
                targets_failed=1,
            )
        if should_cancel:
            record = self.registry.get(record.library_id, None, source_type=record.source_type) or record
            return self.refresh_record(
                record,
                force=force,
                should_cancel=should_cancel,
                begin_commit=begin_commit,
                staging_owner=staging_owner,
            )
        with self._lock_for(record.library_id):
            record = self.registry.get(record.library_id, None, source_type=record.source_type) or record
            return self.refresh_record(record, force=force)

    def prefetch_docs(
        self,
        library: str,
        ecosystem: str | None = None,
        versions: list[str] | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        should_cancel: Callable[[], bool] | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
    ) -> RefreshResult:
        selected_versions = versions or ["latest"]
        result = self.refresh_docs(
            library,
            ecosystem=ecosystem,
            versions=selected_versions,
            docs_url=docs_url,
            docs_url_template=docs_url_template,
            source_type=source_type,
            force=force_refresh,
            continue_on_error=continue_on_error,
            should_cancel=should_cancel,
            begin_commit=begin_commit,
            staging_owner=staging_owner,
        )
        messages = []
        if not versions:
            messages.append("No versions were provided; defaulted to latest.")
        if result.message:
            messages.append(result.message)
        if messages:
            return RefreshResult(
                library_id=result.library_id,
                status=result.status,
                docs_url=result.docs_url,
                last_refreshed_at=result.last_refreshed_at,
                version=result.version,
                source_type=result.source_type,
                message=" ".join(messages),
                duration_ms=result.duration_ms,
                pages_indexed=result.pages_indexed,
                pages_failed=result.pages_failed,
                chunks_indexed=result.chunks_indexed,
                targets_completed=result.targets_completed,
                targets_failed=result.targets_failed,
                preindex=result.preindex,
                reason_codes=result.reason_codes,
            )
        return result

    def _create_staging_index(
        self,
        record: LibraryRecord,
        *,
        staging_owner: dict[str, str] | None = None,
    ) -> tuple[Any, Path]:
        production = self._index_config_for(record)
        db_path = Path(production.index.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=".docatlas-staging-", dir=db_path.parent))
        (root / ".docatlas-staging-owner.json").write_text(
            json.dumps({"created_at": time.time(), "pid": os.getpid(), **(staging_owner or {})}),
            encoding="utf-8",
        )
        staging = production.model_copy(deep=True)
        staging.index.db_path = str(root / "index.db")
        staging.index.extracted_dir = str(root / "extracted")
        try:
            if db_path.exists():
                with sqlite3.connect(db_path) as source, sqlite3.connect(staging.index.db_path) as destination:
                    source.backup(destination)
            extracted = Path(production.index.extracted_dir)
            if extracted.exists():
                shutil.copytree(extracted, staging.index.extracted_dir)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return staging, root

    @staticmethod
    def _count_index_config(config: Any) -> tuple[int, int]:
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

    def _publish_staging_and_update(
        self,
        record: LibraryRecord,
        staging: tuple[Any, Path] | None,
        registry_update: Callable[[], Any],
        commit_guard: Callable[[], bool] | None = None,
        post_publish: Callable[[], None] | None = None,
    ) -> Any:
        if staging is None:
            return registry_update()
        staging_config, staging_root = staging
        production = self._index_config_for(record)
        production_db = Path(production.index.db_path)
        production_extracted = Path(production.index.extracted_dir)
        staging_db = Path(staging_config.index.db_path)
        staging_extracted = Path(staging_config.index.extracted_dir)
        backup_root = Path(tempfile.mkdtemp(prefix=".docatlas-backup-", dir=production_db.parent))
        backup_db = backup_root / production_db.name
        backup_extracted = backup_root / "extracted"
        candidate_db = backup_root / "candidate.db"

        committed = False
        rolled_back = False
        database_backed_up = False
        database_published = False
        extracted_backed_up = False
        extracted_published = False
        registry_changed = False
        result: Any = None
        with self._lock_for(record.library_id):
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
                        self.registry.restore(record)
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
        self.agent_gateway.drop_library_agent(record)
        return result

    @staticmethod
    def _discard_staging(staging: tuple[Any, Path] | None) -> None:
        if staging:
            shutil.rmtree(staging[1], ignore_errors=True)

    @staticmethod
    def _cancelled_result(record: LibraryRecord, started: float) -> RefreshResult:
        return RefreshResult(
            library_id=record.library_id,
            status="cancelled",
            docs_url=record.docs_url,
            last_refreshed_at=record.last_refreshed_at,
            version=record.version,
            source_type=record.source_type,
            message="Library docs prefetch cancelled.",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
