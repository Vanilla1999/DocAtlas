from __future__ import annotations

from typing import Any
import time

from docmancer.docs.models import RefreshResult
from docmancer.docs.registry import LibraryRecord


class LibraryRefreshOps:
    """Refresh and prefetch operations for registered library docs."""

    def __init__(self, dependencies: Any):
        self.dependencies = dependencies

    def __getattr__(self, name: str) -> Any:
        return getattr(self.dependencies, name)

    def refresh_record(self, record: LibraryRecord, *, force: bool) -> RefreshResult:
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
        if not force and not self._is_stale(record.last_refreshed_at):
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

        pages_indexed = 0
        try:
            target = self._target_from_record(record)
            urls = self._record_urls(record)
            per_url_max_pages = target.max_pages if target.doc_format == "dartdoc" else (1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages)
            for url in urls:
                pages = self._agent_instance(record).add(
                    url,
                    recreate=False,
                    max_pages=per_url_max_pages,
                    browser=target.browser,
                    metadata={
                        "library_id": record.library_id,
                        "canonical_id": record.canonical_id,
                        "ecosystem": record.ecosystem,
                        "version": record.version,
                        "source_type": record.source_type,
                    },
                )
                if isinstance(pages, int):
                    pages_indexed += pages
        except Exception as exc:
            self.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=record.docs_url,
                docs_url_template=record.docs_url_template,
                source_type=record.source_type,
                now=self._now(),
                status="failed",
                last_error=str(exc),
                target_spec=record.target_spec,
            )
            return RefreshResult(
                library_id=record.library_id,
                status="failed",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                source_type=record.source_type,
                message=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_failed=1,
                targets_failed=1,
            )

        refreshed_at = self._now()
        self.registry.upsert(
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
        return RefreshResult(
            library_id=record.library_id,
            status="updated",
            docs_url=record.docs_url,
            last_refreshed_at=refreshed_at,
            version=record.version,
            source_type=record.source_type,
            duration_ms=int((time.monotonic() - started) * 1000),
            pages_indexed=pages_indexed,
            chunks_indexed=pages_indexed,
            targets_completed=1,
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
    ) -> RefreshResult:
        started = time.monotonic()
        if versions:
            updated = skipped = failed = needs_url = 0
            pages_indexed = pages_failed = chunks_indexed = 0
            last: RefreshResult | None = None
            for item_version in versions:
                last = self.refresh_docs(
                    library,
                    ecosystem=ecosystem,
                    version=item_version,
                    docs_url=docs_url if len(versions) == 1 else None,
                    docs_url_template=docs_url_template,
                    source_type=source_type,
                    force=force,
                    continue_on_error=continue_on_error,
                )
                if last.status == "updated":
                    updated += 1
                elif last.status == "skipped":
                    skipped += 1
                elif last.status == "needs_docs_url":
                    needs_url += 1
                else:
                    failed += 1
                pages_indexed += last.pages_indexed
                pages_failed += last.pages_failed
                chunks_indexed += last.chunks_indexed
                if not continue_on_error and last.status in {"failed", "needs_docs_url"}:
                    break
            aborted = not continue_on_error and last is not None and last.status in {"failed", "needs_docs_url"}
            status = "aborted" if aborted else ("failed" if failed else ("needs_docs_url" if needs_url else ("updated" if updated else "skipped")))
            return RefreshResult(
                library_id=None,
                status=status,
                docs_url=docs_url_template or docs_url,
                last_refreshed_at=last.last_refreshed_at if last else None,
                message=f"updated={updated} skipped={skipped} failed={failed} needs_docs_url={needs_url}",
                duration_ms=int((time.monotonic() - started) * 1000),
                pages_indexed=pages_indexed,
                pages_failed=pages_failed,
                chunks_indexed=chunks_indexed,
                targets_completed=updated + skipped,
                targets_failed=failed + needs_url,
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
            )
        return result
