from __future__ import annotations

from contextlib import nullcontext

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable
import shutil
import sqlite3
import tempfile
import time

from docmancer.docs.models import RefreshResult
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.application.library_index_publication import LibraryIndexPublication
from docmancer.docs.application.library_ingest_ports import LibraryRefreshPorts
from docmancer.docs.application.library_refresh_policy import (
    dart_refresh_diagnostics as _dart_refresh_diagnostics,
    bounded_exception_diagnostics as _bounded_exception_diagnostics,
    manifest_attempt_spec as _manifest_attempt_spec,
    manifest_rollback_spec as _manifest_rollback_spec,
    merged_discovery_diagnostics as _merged_discovery_diagnostics,
    metadata_for_record as _metadata_for_record,
    published_manifest_spec as _published_manifest_spec,
    refresh_failure_code as _refresh_failure_code,
    retryable_failure as _retryable_failure,
    rollback_safe_manifest_spec as _rollback_safe_manifest_spec,
    safe_failure_message as _safe_failure_message,
)

logger = logging.getLogger(__name__)


class LibraryRefreshOps:
    """Refresh and prefetch operations for registered library docs."""

    def __init__(self, ports: LibraryRefreshPorts):
        self.ports = ports
        self.publication = LibraryIndexPublication(ports.publication)
        self._cleanup_orphaned_staging()

    def _cleanup_orphaned_staging(self, max_age_seconds: float = 24 * 60 * 60) -> None:
        parent = self.ports.staging_parent()
        cutoff = time.time() - max_age_seconds
        for root in parent.glob(".docatlas-staging-*"):
            marker = root / ".docatlas-staging-owner.json"
            try:
                if not marker.is_file() or marker.stat().st_mtime >= cutoff:
                    continue
                owner = json.loads(marker.read_text(encoding="utf-8"))
                job_id = str(owner["job_id"])
                generation_id = str(owner["generation_id"])
                jobs = self.ports.jobs
                if jobs is not None and jobs.generation_active(job_id, generation_id):
                    continue
                shutil.rmtree(root)
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Unable to clean orphaned staging directory: %s", root)

    def _persist_manifest_rollback_diagnostics(self, record: LibraryRecord, reason_code: str) -> None:
        if (record.target_spec or {}).get("last_attempt_manifest_digest") is None:
            return
        active = self.ports.registry.get(record.library_id, source_type=record.source_type)
        self.ports.registry.upsert(
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            docs_url=active.docs_url if active is not None else record.docs_url,
            docs_url_template=(
                active.docs_url_template if active is not None else record.docs_url_template
            ),
            source_type=record.source_type,
            now=self.ports.now(),
            target_spec=_manifest_rollback_spec(record.target_spec, reason_code),
        )

    def refresh_record(
        self,
        record: LibraryRecord,
        *,
        force: bool,
        should_cancel: Callable[[], bool] | None = None,
        deadline_at: float | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
        lock_held: bool = False,
    ) -> RefreshResult:
        started = self.ports.monotonic()
        if not record.docs_url:
            return RefreshResult(
                library_id=record.library_id,
                status="needs_docs_url",
                docs_url=None,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message="Pass docs_url to ingest this library.",
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                targets_failed=1,
            )
        pages, chunks = self.ports.registry_ops.count_index_entries(record)
        index_empty = pages == 0 and chunks == 0
        if not force and not self.ports.is_stale(record.last_refreshed_at) and not index_empty:
            return RefreshResult(
                library_id=record.library_id,
                status="skipped",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                targets_completed=1,
            )

        target = self.ports.target_from_record(record)
        source_manifest = target.source_manifest or {}
        discovery = source_manifest.get("discovery")
        unresolved_github_directory = (
            source_manifest.get("schema_version") == 2
            and "documents" not in source_manifest
            and not any(
                field in source_manifest
                for field in ("complete", "truncated", "digest", "reason_code")
            )
            and isinstance(discovery, dict)
            and discovery.get("kind") == "github_directory"
            and "resolved_commit_sha" not in discovery
        )
        if unresolved_github_directory:
            target = self.ports.resolve_github_directory_target(target)
            resolved_urls, target_error = self.ports.target_urls(target)
            if target_error:
                raise ValueError(target_error)
            resolved_spec = self.ports.target_to_spec(target, resolved_urls)
            record = LibraryRecord(
                **{
                    **record.__dict__,
                    "target_spec": {**(record.target_spec or {}), **resolved_spec},
                }
            )
        manifest = (
            normalize_resolved_github_manifest(target.source_manifest)
            if target.source_manifest.get("schema_version") == 2 else None
        )
        if manifest:
            active = self.ports.registry.get(record.library_id, source_type=record.source_type)
            attempted_target_spec = _manifest_attempt_spec(record.target_spec)
            persisted_attempt_spec = _rollback_safe_manifest_spec(attempted_target_spec)
            self.ports.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=active.docs_url if active is not None else record.docs_url,
                docs_url_template=(
                    active.docs_url_template if active is not None else record.docs_url_template
                ),
                source_type=record.source_type,
                now=self.ports.now(),
                target_spec=persisted_attempt_spec,
            )
            record = LibraryRecord(**{**record.__dict__, "target_spec": attempted_target_spec})
        staging = self.publication.create_staging_index(
            record,
            staging_owner=staging_owner,
            empty=bool(manifest),
        ) if should_cancel or manifest else None

        sections_indexed = 0
        discovery_diagnostics: list[dict[str, Any]] = []
        fetch_failure: Exception | None = None
        try:
            urls = self.ports.record_urls(record)
            direct_text_operations = target.doc_format == "direct-text"
            seed_urls_for_discovery = [] if direct_text_operations else list(target.seed_urls)
            if seed_urls_for_discovery and (target.docs_url or target.docs_url_template):
                urls = urls[:1]
            per_url_max_pages = target.max_pages if target.doc_format == "dartdoc" else (1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages)
            agent = self.ports.agent_gateway.agent_for_config(staging[0]) if staging else self.ports.agent_instance(record)

            operation_urls = urls[:1] if manifest else urls
            for url in operation_urls:
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
                    deadline_at=deadline_at,
                    source_manifest=manifest,
                    with_vectors=False if staging else True,
                )
                if isinstance(indexed_sections, int):
                    sections_indexed += indexed_sections
                if getattr(agent, "last_discovery_diagnostics", None):
                    discovery_diagnostics.append(dict(agent.last_discovery_diagnostics))
                fetch_failure = getattr(agent, "last_fetch_failure", None) or fetch_failure
        except Exception as exc:
            if should_cancel and should_cancel():
                self.publication.discard_staging(staging)
                return self.publication.cancelled_result(record, started)
            if begin_commit and not begin_commit():
                self.publication.discard_staging(staging)
                return self.publication.cancelled_result(record, started)
            self.publication.discard_staging(staging)
            reason_code = _refresh_failure_code(exc)
            retryable = _retryable_failure(exc, reason_code)
            message = _safe_failure_message(exc, reason_code)
            logger.warning("Refresh failed for record %s: %s", record.library_id, reason_code)
            if manifest:
                self._persist_manifest_rollback_diagnostics(record, reason_code)
            if not retryable and index_empty:
                self.ports.registry.upsert(
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    source_type=record.source_type,
                    now=self.ports.now(),
                    status="failed",
                    last_error=message,
                    target_spec=_manifest_rollback_spec(record.target_spec, reason_code),
                )
            return RefreshResult(
                library_id=record.library_id,
                status="failed",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=message,
                duration_ms=int((self.ports.monotonic() - started) * 1000),
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
            self.publication.discard_staging(staging)
            return self.publication.cancelled_result(record, started)

        pages_after, chunks_after = (
            self.publication.count_index_config(staging[0]) if staging else self.ports.registry_ops.count_index_entries(record)
        )
        crawl_diagnostics = _merged_discovery_diagnostics(discovery_diagnostics)
        page_failures = int(crawl_diagnostics.get("page_failure_count") or 0)
        page_reason_codes = list(dict.fromkeys(
            str(item.get("reason_code"))
            for item in crawl_diagnostics.get("page_failure_summary") or []
            if item.get("reason_code")
        ))
        if begin_commit and not begin_commit():
            self.publication.discard_staging(staging)
            return self.publication.cancelled_result(record, started)

        if manifest and staging is not None:
            _, _, manifest_missing, manifest_stale_orphans, _ = self.ports.registry_ops.manifest_coverage(
                record,
                pages_after,
                config=staging[0],
            )
            if manifest_missing or manifest_stale_orphans:
                self.publication.discard_staging(staging)
                self._persist_manifest_rollback_diagnostics(record, "manifest_source_set_mismatch")
                return RefreshResult(
                    library_id=record.library_id,
                    status="failed",
                    docs_url=record.docs_url,
                    last_refreshed_at=record.last_refreshed_at,
                    version=record.version,
                    source_type=record.source_type,
                    message="manifest_source_set_mismatch: retained the previous active corpus.",
                    duration_ms=int((self.ports.monotonic() - started) * 1000),
                    targets_failed=1,
                )

        vector_failure: Exception | None = None

        def _sync_vectors_before_commit() -> None:
            nonlocal vector_failure
            if staging is None:
                return
            try:
                staging_agent = self.ports.agent_gateway.agent_for_config(staging[0])
                sync_vectors = getattr(staging_agent, "sync_vectors", None)
                if callable(sync_vectors):
                    sync_vectors()
            except Exception as exc:
                vector_failure = exc

        def _commit_registry(**values: Any) -> Any:
            def update() -> Any:
                return self.ports.registry.upsert(**values)

            return self.publication.publish_and_update(
                record,
                staging,
                update,
                commit_guard=begin_commit,
                lock_held=lock_held,
            )

        if sections_indexed == 0 or pages_after == 0 or chunks_after == 0:
            refreshed_at = self.ports.now()
            reason = "ingest_produced_no_chunks" if sections_indexed > 0 else "no_extractable_content"
            if staging is not None and not index_empty:
                self.publication.discard_staging(staging)
                self._persist_manifest_rollback_diagnostics(record, reason)
                return RefreshResult(
                    library_id=record.library_id,
                    status="empty_index",
                    docs_url=record.docs_url,
                    last_refreshed_at=record.last_refreshed_at,
                    version=record.version,
                    source_type=record.source_type,
                    message=f"{reason}: retained the previous active corpus.",
                    duration_ms=int((self.ports.monotonic() - started) * 1000),
                    targets_failed=1,
                )
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
                target_spec=_rollback_safe_manifest_spec(record.target_spec),
            )
            index_config = self.ports.index_config_for(record)
            db_path = str(Path(index_config.index.db_path).resolve()) if index_config and index_config.index else None
            return RefreshResult(
                library_id=record.library_id,
                status="empty_index",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=f"{reason}: refresh indexed no usable chunks. Check docs_url, source_type, doc_format, browser, or Dartdoc seed discovery.",
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                chunks_indexed=chunks_after,
                targets_failed=1,
                preindex={
                    "library": record.name,
                    "canonical_id": record.canonical_id,
                    "docs_url": record.docs_url,
                    "docs_url_resolved": record.docs_url_resolved or record.docs_url,
                    "source_type": record.source_type or "api",
                    **crawl_diagnostics,
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
                    "elapsed_ms": int((self.ports.monotonic() - started) * 1000),
                },
            )

        if staging is not None and sections_indexed > 0:
            _sync_vectors_before_commit()
            if vector_failure is not None:
                self.publication.discard_staging(staging)
                self._persist_manifest_rollback_diagnostics(record, "vector_indexing_failed")
                failure_diagnostics = _bounded_exception_diagnostics(
                    vector_failure,
                    failure_phase="staging",
                    failure_operation="sync_vectors",
                )
                return RefreshResult(
                    library_id=record.library_id,
                    status="failed",
                    docs_url=record.docs_url,
                    last_refreshed_at=record.last_refreshed_at,
                    version=record.version,
                    source_type=record.source_type,
                    message=(
                        "vector_indexing_failed: retained the previous active corpus: "
                        f"{failure_diagnostics['exception_message']}"
                    ),
                    duration_ms=int((self.ports.monotonic() - started) * 1000),
                    targets_failed=1,
                    reason_codes=["vector_indexing_failed"],
                    preindex={
                        "reason_code": "vector_indexing_failed",
                        **failure_diagnostics,
                    },
                )

        refreshed_at = self.ports.now()
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
            target_spec=_published_manifest_spec(record.target_spec),
        )

        # Build preindex diagnostics
        index_config = self.ports.index_config_for(record)
        db_path = Path(index_config.index.db_path).resolve() if index_config and index_config.index else None
        reason_code = "healthy" if chunks_after > 0 else "empty_index"
        preindex = {
            "library": record.name,
            "canonical_id": record.canonical_id,
            "docs_url": record.docs_url,
            "docs_url_resolved": record.docs_url_resolved or record.docs_url,
            "docset_root": record.docs_url_resolved or record.docs_url,
            "source_type": record.source_type or "api",
            **crawl_diagnostics,
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
            "elapsed_ms": int((self.ports.monotonic() - started) * 1000),
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
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                pages_failed=max(page_failures, 1),
                chunks_indexed=chunks_after,
                targets_completed=1,
                reason_codes=[failure_code],
                preindex=preindex,
            )

        if page_failures:
            return RefreshResult(
                library_id=record.library_id,
                status="partial",
                docs_url=record.docs_url,
                last_refreshed_at=refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=f"partial_page_failures: {page_failures} page(s) failed or were skipped.",
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                pages_indexed=pages_after,
                pages_failed=page_failures,
                chunks_indexed=chunks_after,
                targets_completed=1,
                reason_codes=page_reason_codes or ["partial_page_failures"],
                preindex=preindex,
            )

        return RefreshResult(
            library_id=record.library_id,
            status="updated",
            docs_url=record.docs_url,
            last_refreshed_at=refreshed_at,
            version=record.version,
            source_type=record.source_type,
            duration_ms=int((self.ports.monotonic() - started) * 1000),
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
        deadline_at: float | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
    ) -> RefreshResult:
        started = self.ports.monotonic()
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
                        duration_ms=int((self.ports.monotonic() - started) * 1000),
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
                    deadline_at=deadline_at,
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
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                pages_indexed=pages_indexed,
                pages_failed=pages_failed,
                chunks_indexed=chunks_indexed,
                targets_completed=updated + skipped + partial,
                targets_failed=failed + needs_url,
                preindex=last.preindex if last else None,
                reason_codes=failure_codes,
            )

        info = self.ports.resolve_library(library, ecosystem, version, docs_url, docs_url_template, source_type)
        record = self.ports.record_from_info(info)
        if record is None:
            return RefreshResult(
                library_id=None,
                status="needs_docs_url",
                docs_url=docs_url,
                last_refreshed_at=None,
                version=version,
                source_type=source_type or "api",
                message="Pass docs_url to ingest this library.",
                duration_ms=int((self.ports.monotonic() - started) * 1000),
                targets_failed=1,
            )
        if should_cancel:
            record = self.ports.registry.get(record.library_id, None, source_type=record.source_type) or record
            return self.refresh_record(
                record,
                force=force,
                should_cancel=should_cancel,
                deadline_at=deadline_at,
                begin_commit=begin_commit,
                staging_owner=staging_owner,
            )
        with self.ports.lock_for(record.library_id):
            record = self.ports.registry.get(record.library_id, None, source_type=record.source_type) or record
            return self.refresh_record(record, force=force, lock_held=True)

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
        deadline_at: float | None = None,
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
            deadline_at=deadline_at,
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
