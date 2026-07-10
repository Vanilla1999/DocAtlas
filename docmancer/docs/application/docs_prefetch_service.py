from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
import json
import shutil
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.curated_sources import canonical_source_identity
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


class DocsPrefetchDependencies(Protocol):
    jobs: Any
    registry: Any

    def _target_from_dict(self, value: dict[str, Any] | DocsTarget) -> DocsTarget: ...
    def _discover_pub_dartdoc_target(self, target: DocsTarget, warnings: list[str], job_id: str | None = None, canonical_id: str | None = None) -> DocsTarget: ...
    def _target_urls(self, target: DocsTarget) -> tuple[list[str], str | None]: ...
    def _target_to_spec(self, target: DocsTarget, urls: list[str] | None = None) -> dict[str, Any]: ...
    def _target_result_summary(self, result: DocsTargetResult) -> dict[str, Any]: ...
    def _now(self) -> str: ...
    def _is_stale(self, last_refreshed_at: str | None) -> bool: ...
    def _lock_for(self, library_id: str) -> Any: ...
    def _agent_instance(self, record: LibraryRecord | None = None) -> Any: ...


class DocsPrefetchService:
    def __init__(self, deps: DocsPrefetchDependencies):
        self.deps = deps
        self.jobs = deps.jobs
        self.registry = deps.registry

    def progress_callback_for(self, job_id: str | None, canonical_id: str):
        if not job_id:
            return None

        def _callback(event: dict[str, Any]) -> None:
            phase = event.get("phase") or "fetching"
            url = event.get("url") or event.get("current_url")
            changes: dict[str, Any] = {
                "phase": phase,
                "current_target": canonical_id,
                "message": event.get("message") or phase,
            }
            if url:
                changes["current_url"] = str(url)
            current = self.jobs.get(job_id)
            if event.get("total_pages") is not None:
                changes["total_pages"] = max(int(event["total_pages"]), current.total_pages if current else 0)
            if event.get("discovered_pages") is not None:
                changes["discovered_pages"] = int(event["discovered_pages"])
            if event.get("fetched_pages") is not None:
                changes["fetched_pages"] = int(event["fetched_pages"])
                changes["completed_pages"] = int(event["fetched_pages"])
            if event.get("indexed_pages") is not None:
                changes["indexed_pages"] = int(event["indexed_pages"])
            if event.get("failed_pages") is not None and current:
                changes["failed_pages"] = current.failed_pages + int(event["failed_pages"])
            self.jobs.update(job_id, **changes)
            self.jobs.append_event(job_id, event)

        return _callback

    def prefetch_docs_targets(
        self,
        targets: list[dict[str, Any] | DocsTarget],
        *,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> DocsTargetsPrefetchResult | DocsJobStartResult:
        if async_:
            job = self.jobs.create("prefetch_docs_targets")
            self.jobs.update(job.job_id, status="running", message="Started docs prefetch job.")
            threading.Thread(
                target=self._run_prefetch_docs_targets_job,
                args=(job.job_id, targets, force_refresh, continue_on_error),
                daemon=True,
            ).start()
            return DocsJobStartResult(job_id=job.job_id, status="running", message="Started docs prefetch job.")
        return self.prefetch_docs_targets_sync(
            targets,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
        )

    def _run_prefetch_docs_targets_job(
        self,
        job_id: str,
        targets: list[dict[str, Any] | DocsTarget],
        force_refresh: bool,
        continue_on_error: bool,
    ) -> None:
        try:
            self.prefetch_docs_targets_sync(
                targets,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                job_id=job_id,
            )
        except Exception as exc:
            self.jobs.append_error(job_id, str(exc))
            self.jobs.update(job_id, status="failed", phase="done", message=str(exc))

    def prefetch_docs_targets_sync(
        self,
        targets: list[dict[str, Any] | DocsTarget],
        *,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        job_id: str | None = None,
    ) -> DocsTargetsPrefetchResult:
        started = time.monotonic()
        results: list[DocsTargetResult] = []
        target_summaries: list[dict[str, Any]] = []
        seen: set[str] = set()
        warnings: list[str] = []
        aborted = False
        pages_indexed_total = 0
        pages_failed_total = 0
        targets_completed = 0
        targets_failed = 0
        raw_targets = list(targets)
        if job_id:
            self.jobs.update(
                job_id,
                status="running",
                phase="resolving",
                total_targets=len(raw_targets),
                message=f"Resolving {len(raw_targets)} docs targets.",
            )

        for index, raw_target in enumerate(raw_targets, start=1):
            if self.jobs.cancellation_requested(job_id):
                aborted = True
                if job_id:
                    self.jobs.append_warning(job_id, "Docs prefetch job cancelled before the next target started.")
                    self.jobs.update(job_id, status="cancelled", phase="done", message="Docs prefetch job cancelled.")
                break
            target = self.deps._target_from_dict(raw_target)
            version = normalize_version(target.version) or "latest"
            source_type = target.source_type or "api"
            canonical_id = canonical_library_id(target.library, target.ecosystem, version, source_type)
            if job_id:
                self.jobs.update(
                    job_id,
                    phase="resolving",
                    current_target=canonical_id,
                    message=f"Resolving target {index}/{len(raw_targets)}.",
                )
                self.jobs.append_event(job_id, {"phase": "resolving", "message": f"Target {index}/{len(raw_targets)} started", "target": canonical_id})

            if canonical_id in seen:
                targets_failed += 1
                result = DocsTargetResult(
                    canonical_id=canonical_id,
                    status="failed",
                    library=target.library,
                    ecosystem=target.ecosystem,
                    version=version,
                    source_type=source_type,
                    warnings=list(target.warnings),
                    message="duplicate canonical target id",
                )
                results.append(result)
                target_summaries.append(self.deps._target_result_summary(result))
                if job_id:
                    self.jobs.append_error(job_id, f"{canonical_id}: duplicate canonical target id")
                    self.jobs.update(job_id, failed_targets=targets_failed, message="duplicate canonical target id")
                if not continue_on_error:
                    aborted = True
                    break
                continue
            seen.add(canonical_id)

            target = self.deps._discover_pub_dartdoc_target(target, warnings, job_id=job_id, canonical_id=canonical_id)
            urls, error = self.deps._target_urls(target)
            if error:
                targets_failed += 1
                result = DocsTargetResult(
                    canonical_id=canonical_id,
                    status="failed",
                    library=target.library,
                    ecosystem=target.ecosystem,
                    version=version,
                    source_type=source_type,
                    warnings=list(target.warnings),
                    message=error,
                )
                results.append(result)
                target_summaries.append(self.deps._target_result_summary(result))
                if job_id:
                    self.jobs.append_error(job_id, f"{canonical_id}: {error}")
                    self.jobs.update(job_id, failed_targets=targets_failed, message=error)
                if not continue_on_error:
                    aborted = True
                    break
                continue

            target_spec = self.deps._target_to_spec(target, urls)
            record = self.registry.upsert(
                library=target.library,
                ecosystem=target.ecosystem,
                version=version,
                source_type=source_type,
                docs_url=urls[0],
                docs_url_template=target.docs_url_template,
                now=self.deps._now(),
                status="available",
                target_spec=target_spec,
            )

            with self.deps._lock_for(record.library_id):
                record = self.registry.get(record.library_id, source_type=record.source_type) or record
                if not force_refresh and not self.deps._is_stale(record.last_refreshed_at):
                    targets_completed += 1
                    results.append(
                        result := DocsTargetResult(
                            canonical_id=record.library_id,
                            status="skipped",
                            library=record.name,
                            ecosystem=record.ecosystem,
                            version=record.version,
                            source_type=record.source_type,
                            docs_url=record.docs_url,
                            warnings=list(target.warnings),
                        )
                    )
                    target_summaries.append(self.deps._target_result_summary(result))
                    if job_id:
                        self.jobs.update(
                            job_id,
                            completed_targets=targets_completed,
                            phase="indexing",
                            message=f"Skipped fresh target {index}/{len(raw_targets)}.",
                        )
                    continue
                try:
                    pages_indexed = 0
                    per_url_max_pages = target.max_pages if target.doc_format == "dartdoc" else (1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages)
                    if job_id:
                        self.jobs.update(
                            job_id,
                            phase="fetching",
                            total_pages=(self.jobs.get(job_id).total_pages if self.jobs.get(job_id) else 0) + len(urls),
                            message=f"Fetching target {index}/{len(raw_targets)}.",
                        )
                    progress_callback = self.progress_callback_for(job_id, record.library_id)
                    for url_index, url in enumerate(urls, start=1):
                        if self.jobs.cancellation_requested(job_id):
                            aborted = True
                            raise KeyboardInterrupt("Docs prefetch job cancelled.")
                        add_kwargs: dict[str, Any] = {
                            "max_pages": per_url_max_pages,
                            "browser": target.browser,
                            "metadata": {
                                "canonical_source_identity": canonical_source_identity(url),
                                "library_id": record.library_id,
                                "canonical_id": record.canonical_id or record.library_id,
                                "version": record.version,
                            },
                        }
                        if target.doc_format:
                            add_kwargs["doc_format"] = target.doc_format
                        if progress_callback:
                            add_kwargs["progress_callback"] = progress_callback
                            progress_callback({"phase": "fetching", "message": f"Fetching seed URL {url_index}/{len(urls)}", "url": url, "total_pages": len(urls)})
                        pages = self.deps._agent_instance(record).add(
                            url,
                            recreate=False,
                            **add_kwargs,
                        )
                        if isinstance(pages, int):
                            pages_indexed += pages
                            pages_indexed_total += pages
                        if job_id:
                            self.jobs.update(
                                job_id,
                                phase="indexing",
                                completed_pages=pages_indexed_total,
                                completed_chunks=pages_indexed_total,
                                total_chunks=max(self.jobs.get(job_id).total_chunks if self.jobs.get(job_id) else 0, pages_indexed_total),
                                message=f"Indexed {url_index}/{len(urls)} seed URLs.",
                            )
                            self.jobs.append_event(job_id, {"phase": "indexing", "message": f"Indexed seed URL {url_index}/{len(urls)}", "url": url})
                except KeyboardInterrupt:
                    if job_id:
                        self.jobs.append_warning(job_id, "Docs prefetch job cancelled before the current target was marked ready.")
                        self.jobs.update(job_id, status="cancelled", phase="done", message="Docs prefetch job cancelled.")
                    break
                except Exception as exc:
                    targets_failed += 1
                    pages_failed_total += 1
                    self.registry.upsert(
                        library=record.name,
                        ecosystem=record.ecosystem,
                        version=record.version,
                        source_type=record.source_type,
                        docs_url=record.docs_url,
                        docs_url_template=record.docs_url_template,
                        now=self.deps._now(),
                        status="failed",
                        last_error=str(exc),
                        target_spec=record.target_spec,
                    )
                    results.append(
                        result := DocsTargetResult(
                            canonical_id=record.library_id,
                            status="failed",
                            library=record.name,
                            ecosystem=record.ecosystem,
                            version=record.version,
                            source_type=record.source_type,
                            docs_url=record.docs_url,
                            warnings=list(target.warnings),
                            message=str(exc),
                        )
                    )
                    target_summaries.append(self.deps._target_result_summary(result))
                    if job_id:
                        self.jobs.append_error(job_id, f"{record.library_id}: {exc}")
                        self.jobs.update(
                            job_id,
                            failed_targets=targets_failed,
                            failed_pages=pages_failed_total,
                            message=str(exc),
                        )
                    if not continue_on_error:
                        aborted = True
                        break
                    continue

                targets_completed += 1
                refreshed_at = self.deps._now()
                record = self.registry.upsert(
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    source_type=record.source_type,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    now=refreshed_at,
                    status="available",
                    last_refreshed_at=refreshed_at,
                    last_error="",
                    target_spec=record.target_spec,
                )
                results.append(
                    result := DocsTargetResult(
                        canonical_id=record.library_id,
                        status="ready",
                        library=record.name,
                        ecosystem=record.ecosystem,
                        version=record.version,
                        source_type=record.source_type,
                        docs_url=record.docs_url,
                        pages_indexed=pages_indexed,
                        warnings=list(target.warnings),
                    )
                )
                target_summaries.append(self.deps._target_result_summary(result))
                if job_id:
                    self.jobs.update(
                        job_id,
                        completed_targets=targets_completed,
                        phase="indexing",
                        message=f"Indexed target {index}/{len(raw_targets)}.",
                    )
                    self.jobs.append_event(job_id, {"phase": "indexing", "message": f"Target {index}/{len(raw_targets)} finished", "target": record.library_id})

        failed = sum(1 for result in results if result.status == "failed")
        if aborted:
            status = "aborted"
        elif failed:
            status = "partial" if any(result.status in {"ready", "skipped"} for result in results) else "failed"
        else:
            status = "ok"
        duration_ms = int((time.monotonic() - started) * 1000)
        if job_id and not self.jobs.cancellation_requested(job_id):
            job_status = "succeeded" if status == "ok" else ("partial" if status in {"partial", "aborted"} else "failed")
            self.jobs.update(
                job_id,
                status=job_status,
                phase="done",
                completed_targets=targets_completed,
                failed_targets=targets_failed,
                completed_pages=pages_indexed_total,
                failed_pages=pages_failed_total,
                completed_chunks=pages_indexed_total,
                total_chunks=max(self.jobs.get(job_id).total_chunks if self.jobs.get(job_id) else 0, pages_indexed_total),
                target_results=target_summaries,
                message="Docs prefetch job finished.",
            )
        return DocsTargetsPrefetchResult(
            status=status,
            results=results,
            warnings=warnings,
            duration_ms=duration_ms,
            pages_indexed=pages_indexed_total,
            pages_failed=pages_failed_total,
            chunks_indexed=pages_indexed_total,
            targets_completed=targets_completed,
            targets_failed=targets_failed,
        )
