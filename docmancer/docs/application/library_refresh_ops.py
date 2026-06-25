from __future__ import annotations

from pathlib import Path
from typing import Any
import time

from docmancer.docs.models import RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.dart_official_docs import build_dart_diagnostics, canonical_dart_ecosystem


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

        sections_indexed = 0
        discovery_diagnostics: list[dict[str, Any]] = []
        try:
            target = self._target_from_record(record)
            urls = self._record_urls(record)
            seed_urls_for_discovery = list(target.seed_urls)
            if seed_urls_for_discovery and (target.docs_url or target.docs_url_template):
                urls = urls[:1]
            per_url_max_pages = target.max_pages if target.doc_format == "dartdoc" else (1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages)
            for url in urls:
                agent = self._agent_instance(record)
                indexed_sections = agent.add(
                    url,
                    recreate=False,
                    max_pages=per_url_max_pages,
                    browser=target.browser,
                    seed_urls=seed_urls_for_discovery if (target.docs_url or target.docs_url_template) else None,
                    metadata=_metadata_for_record(record),
                )
                if isinstance(indexed_sections, int):
                    sections_indexed += indexed_sections
                if getattr(agent, "last_discovery_diagnostics", None):
                    discovery_diagnostics.append(dict(agent.last_discovery_diagnostics))
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
                preindex={
                    "library": record.name,
                    "canonical_id": record.canonical_id,
                    "docs_url": record.docs_url,
                    "reason_code": "refresh_failed",
                    **_dart_refresh_diagnostics(
                        record,
                        pages_discovered=sections_indexed,
                        pages_extracted=0,
                        chunks_created=0,
                        reason_code="refresh_failed",
                    ),
                },
            )

        pages_after, chunks_after = self.registry_ops.count_index_entries(record)
        if sections_indexed == 0 or pages_after == 0 or chunks_after == 0:
            refreshed_at = self._now()
            reason = "ingest_produced_no_chunks" if sections_indexed > 0 else "no_extractable_content"
            self.registry.upsert(
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
                preindex=result.preindex,
            )
        return result
