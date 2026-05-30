from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from ipaddress import ip_address
from pathlib import Path
import shutil
import threading
import time
import uuid
from urllib.parse import urlparse

import yaml

from filelock import FileLock

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJob, DocsJobCancelResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRecord, LibraryRegistry
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.mcp import paths

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
MAX_DOCS_JOB_HISTORY = 100
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


class DocsJobTracker:
    def __init__(self, max_history: int = MAX_DOCS_JOB_HISTORY):
        self._jobs: dict[str, DocsJob] = {}
        self._cancel_requested: set[str] = set()
        self._job_order: dict[str, int] = {}
        self._next_order = 0
        self._lock = threading.Lock()
        self.max_history = max_history

    def _trim_locked(self) -> None:
        if len(self._jobs) <= self.max_history:
            return
        ordered = sorted(self._jobs.values(), key=lambda job: (job.updated_at or "", self._job_order.get(job.job_id, 0)), reverse=True)
        keep = {job.job_id for job in ordered[: self.max_history]}
        for job_id in list(self._jobs):
            if job_id not in keep:
                self._jobs.pop(job_id, None)
                self._cancel_requested.discard(job_id)
                self._job_order.pop(job_id, None)

    def create(self, kind: str) -> DocsJob:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        job = DocsJob(
            job_id=uuid.uuid4().hex,
            kind=kind,
            status="pending",
            phase="validating",
            message="Job created.",
            started_at=now,
            updated_at=now,
        )
        with self._lock:
            self._next_order += 1
            self._jobs[job.job_id] = job
            self._job_order[job.job_id] = self._next_order
            self._trim_locked()
        return job

    def update(self, job_id: str, **changes: Any) -> DocsJob | None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if changes.get("status") in {"succeeded", "partial", "failed", "cancelled"} and "finished_at" not in changes:
                changes["finished_at"] = now
            changes["updated_at"] = now
            job = replace(job, **changes)
            self._jobs[job_id] = job
            return job

    def append_warning(self, job_id: str, warning: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            warnings = list(job.warnings)
            warnings.append(warning)
        self.update(job_id, warnings=warnings)

    def append_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            errors = list(job.errors)
            errors.append(error)
        self.update(job_id, errors=errors)

    def get(self, job_id: str) -> DocsJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: (job.updated_at or "", self._job_order.get(job.job_id, 0)), reverse=True)
        return jobs[:limit] if limit else jobs

    def cancel(self, job_id: str) -> DocsJobCancelResult:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return DocsJobCancelResult(job_id=job_id, status="not_found", message="Job not found.")
            self._cancel_requested.add(job_id)
            if job.status in {"succeeded", "partial", "failed", "cancelled"}:
                status = "cancelled" if job.status == "cancelled" else "cancelling"
                return DocsJobCancelResult(job_id=job_id, status=status, message="Job already finished.")
        self.update(job_id, status="cancelling", message="Cancellation requested.")
        self.append_warning(job_id, "Cancellation requested; job will stop between targets/pages.")
        return DocsJobCancelResult(job_id=job_id, status="cancelling", message="Cancellation requested.")

    def cancellation_requested(self, job_id: str | None) -> bool:
        if job_id is None:
            return False
        with self._lock:
            return job_id in self._cancel_requested


DOCS_JOB_TRACKER = DocsJobTracker()


class LibraryDocsService:
    def __init__(
        self,
        *,
        config: DocmancerConfig | None = None,
        registry: LibraryRegistry | None = None,
        agent: Any | None = None,
        project_reader: ProjectMetadataReader | None = None,
        job_tracker: DocsJobTracker | None = None,
        stale_after_days: int = STALE_AFTER_DAYS,
    ):
        self.config = config or DocmancerConfig()
        self.registry = registry or LibraryRegistry(self.config.index.db_path)
        self._agent = agent
        self._agents: dict[str, Any] = {}
        self.project_reader = project_reader or ProjectMetadataReader()
        self.stale_after_days = stale_after_days
        self.jobs = job_tracker or DOCS_JOB_TRACKER

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def get_docs_job_status(self, job_id: str) -> DocsJob | None:
        return self.jobs.get(job_id)

    def list_docs_jobs(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        return self.jobs.list(status=status, limit=limit)

    def cancel_docs_job(self, job_id: str) -> DocsJobCancelResult:
        return self.jobs.cancel(job_id)

    def _is_stale(self, last_refreshed_at: str | None) -> bool:
        if not last_refreshed_at:
            return True
        try:
            refreshed = datetime.fromisoformat(last_refreshed_at)
        except ValueError:
            return True
        if refreshed.tzinfo is None:
            refreshed = refreshed.replace(tzinfo=timezone.utc)
        return refreshed <= datetime.now(timezone.utc) - timedelta(days=self.stale_after_days)

    def _index_config_for(self, record: LibraryRecord) -> DocmancerConfig:
        config = self.config.model_copy(deep=True)
        root = paths.docmancer_home() / "docs-indexes"
        root.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(record.library_id) or "library"
        config.index.db_path = str(root / f"{safe}.db")
        config.index.extracted_dir = str(root / safe / "extracted")
        return config

    def _agent_instance(self, record: LibraryRecord | None = None) -> Any:
        if self._agent is None:
            if record is None:
                self._agent = DocmancerAgent(config=self.config)
            else:
                if record.library_id not in self._agents:
                    self._agents[record.library_id] = DocmancerAgent(config=self._index_config_for(record))
                return self._agents[record.library_id]
        return self._agent

    def _lock_for(self, library_id: str) -> FileLock:
        lock_dir = paths.docmancer_home() / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(library_id) or "library"
        return FileLock(str(lock_dir / f"docs-{safe}.lock"))

    def resolve_library(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
    ) -> LibraryInfo:
        normalized_version = normalize_version(version)
        if docs_url is None and docs_url_template and normalized_version:
            docs_url = self._render_docs_url(docs_url_template, library, normalized_version)

        record = self.registry.get(library, ecosystem, normalized_version, source_type)
        if record is not None and ecosystem:
            canonical_id = canonical_library_id(record.name, ecosystem, record.version, source_type or record.source_type)
            if record.library_id != canonical_id and record.ecosystem in {None, ecosystem}:
                migrated = self.registry.migrate_library_id(record.library_id, canonical_id)
                record = migrated or record
        if record is None and docs_url:
            record = self.registry.upsert(
                library=library,
                ecosystem=ecosystem,
                version=normalized_version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                source_type=source_type,
                now=self._now(),
                status="available",
            )
        if record is None:
            return LibraryInfo(
                library_id=None,
                library=library,
                ecosystem=ecosystem,
                version=normalized_version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                status="needs_docs_url",
                local=False,
                stale=True,
                message="Pass docs_url or docs_url_template with version to register and ingest this library.",
            )
        if docs_url and docs_url != record.docs_url:
            record = self.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                source_type=source_type,
                now=self._now(),
                status="available",
            )
        stale = self._is_stale(record.last_refreshed_at)
        return LibraryInfo(
            library_id=record.library_id,
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            source_type=record.source_type,
            docs_url=record.docs_url,
            docs_url_template=record.docs_url_template,
            status=record.status or "available",
            local=record.last_refreshed_at is not None,
            stale=stale,
            last_refreshed_at=record.last_refreshed_at,
            message=record.last_error,
        )

    def _record_from_info(self, info: LibraryInfo) -> LibraryRecord | None:
        if info.library_id is None:
            return None
        return self.registry.get(info.library_id, None, source_type=info.source_type)

    @staticmethod
    def _render_docs_url(template: str, library: str, version: str) -> str:
        return template.format(library=library, version=version)

    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return self.project_reader.read(project_path)

    @staticmethod
    def _is_flutter_library(library: str) -> bool:
        return normalize_library_name(library) in {"flutter", "flutter-api"}

    @staticmethod
    def _flutter_docs_url_for(version: str | None, channel: str | None) -> str:
        selected = (channel or version or "").lower()
        if selected in {"main", "master"}:
            return "https://main-api.flutter.dev/"
        return "https://api.flutter.dev/"

    @staticmethod
    def _flutter_docs_version_for(version: str | None, channel: str | None) -> str | None:
        selected = (channel or version or "").lower()
        if selected in {"main", "master"}:
            return "main"
        if channel:
            return channel
        if version:
            return "stable"
        return None

    def _project_version_for(
        self,
        *,
        library: str,
        ecosystem: str | None,
        project_path: str | None,
    ) -> tuple[str | None, str | None, str | None, list[str], str | None, bool | None]:
        if not project_path:
            return None, None, None, [], None, None
        metadata = self.read_project_metadata(project_path)
        warnings = list(metadata.warnings)
        if self._is_flutter_library(library):
            selected = self._flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if selected:
                if metadata.flutter_version and selected == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                return (
                    selected,
                    self._flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                    None,
                    warnings,
                    metadata.flutter_version or metadata.flutter_channel,
                    False,
                )
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None

        if ecosystem == "pub" or library in metadata.packages:
            version = metadata.packages.get(library)
            if version:
                return version, None, PUB_DOCS_URL_TEMPLATE, warnings, version, True
            warnings.append(PACKAGE_NOT_FOUND_WARNING)
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None

        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, None, None

    @staticmethod
    def _join_warnings(*items: str | None, extra: list[str] | None = None) -> str | None:
        values = [item for item in items if item]
        if extra:
            values.extend(extra)
        return " ".join(values) if values else None

    def _refresh_record(self, record: LibraryRecord, *, force: bool) -> RefreshResult:
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
            per_url_max_pages = 1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages
            for url in urls:
                pages = self._agent_instance(record).add(
                    url,
                    recreate=False,
                    max_pages=per_url_max_pages,
                    browser=target.browser,
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
            return self._refresh_record(record, force=force)

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


    @staticmethod
    def _target_from_dict(value: dict[str, Any] | DocsTarget) -> DocsTarget:
        if isinstance(value, DocsTarget):
            return value
        return DocsTarget(
            library=value["library"],
            ecosystem=value.get("ecosystem"),
            version=value.get("version") or "latest",
            source_type=value.get("source_type") or "api",
            docs_url=value.get("docs_url"),
            docs_url_template=value.get("docs_url_template"),
            seed_urls=list(value.get("seed_urls") or []),
            allowed_domains=list(value.get("allowed_domains") or []),
            path_prefixes=list(value.get("path_prefixes") or []),
            max_pages=int(value.get("max_pages") or 200),
            browser=bool(value.get("browser") or False),
            warnings=list(value.get("warnings") or []),
        )


    @staticmethod
    def _target_to_spec(target: DocsTarget, urls: list[str] | None = None) -> dict[str, Any]:
        return {
            "library": target.library,
            "ecosystem": target.ecosystem,
            "version": normalize_version(target.version) or "latest",
            "source_type": target.source_type or "api",
            "docs_url": target.docs_url,
            "docs_url_template": target.docs_url_template,
            "seed_urls": list(target.seed_urls),
            "resolved_urls": list(urls or []),
            "allowed_domains": list(target.allowed_domains),
            "path_prefixes": list(target.path_prefixes),
            "max_pages": target.max_pages,
            "browser": target.browser,
            "warnings": list(target.warnings),
        }

    def _target_from_record(self, record: LibraryRecord) -> DocsTarget:
        spec = record.target_spec or {}
        return DocsTarget(
            library=spec.get("library") or record.name,
            ecosystem=spec.get("ecosystem") or record.ecosystem,
            version=spec.get("version") or record.version,
            source_type=spec.get("source_type") or record.source_type or "api",
            docs_url=spec.get("docs_url") if "docs_url" in spec else record.docs_url,
            docs_url_template=spec.get("docs_url_template") if "docs_url_template" in spec else record.docs_url_template,
            seed_urls=list(spec.get("seed_urls") or []),
            allowed_domains=list(spec.get("allowed_domains") or []),
            path_prefixes=list(spec.get("path_prefixes") or []),
            max_pages=int(spec.get("max_pages") or 200),
            browser=bool(spec.get("browser") or False),
            warnings=list(spec.get("warnings") or []),
        )

    def _record_urls(self, record: LibraryRecord) -> list[str]:
        spec = record.target_spec or {}
        resolved = spec.get("resolved_urls")
        if isinstance(resolved, list) and resolved:
            return [str(url) for url in resolved]
        target = self._target_from_record(record)
        urls, _ = self._target_urls(target)
        return urls or ([record.docs_url] if record.docs_url else [])

    @staticmethod
    def _is_remote_url(url: str) -> bool:
        return urlparse(url).scheme in {"http", "https"}


    @staticmethod
    def _url_security_error(url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return f"unsupported URL scheme: {parsed.scheme}"
        host = parsed.hostname or ""
        if host in {"localhost", "localhost.localdomain"}:
            return "localhost URLs are not allowed"
        try:
            address = ip_address(host)
        except ValueError:
            return None
        if address.is_loopback or address.is_private or address.is_link_local or address.is_multicast:
            return "private network URLs are not allowed"
        return None

    @staticmethod
    def _host_allowed(url: str, allowed_domains: list[str]) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)

    @staticmethod
    def _path_allowed(url: str, path_prefixes: list[str]) -> bool:
        if not path_prefixes:
            return True
        path = urlparse(url).path or "/"
        return any(path.startswith(prefix) for prefix in path_prefixes)

    def _target_urls(self, target: DocsTarget) -> tuple[list[str], str | None]:
        version = normalize_version(target.version) or "latest"
        urls = list(target.seed_urls)
        if target.docs_url:
            urls.insert(0, target.docs_url)
        elif target.docs_url_template:
            urls.insert(0, self._render_docs_url(target.docs_url_template, target.library, version))
        if not urls:
            return [], "target must provide docs_url, docs_url_template, or seed_urls"
        for url in urls:
            security_error = self._url_security_error(url)
            if security_error:
                return [], security_error
            if self._is_remote_url(url):
                if not target.allowed_domains:
                    return [], "allowed_domains is required for remote docs targets"
                if not self._host_allowed(url, target.allowed_domains):
                    return [], f"URL host is not in allowed_domains: {url}"
                if not self._path_allowed(url, target.path_prefixes):
                    return [], f"URL path is outside path_prefixes: {url}"
        return urls, None


    @staticmethod
    def _merge_manifest_defaults(defaults: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        merged = dict(defaults)
        merged.update(target)
        return merged

    def _resolve_manifest_project_version(
        self,
        target: dict[str, Any],
        project_path: str | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        if target.get("version") != "project-version":
            return target
        spec = target.get("project_version") or {}
        package = spec.get("package") or target.get("library")
        fallback = spec.get("fallback") or "latest"
        resolved = fallback
        if project_path:
            metadata = self.read_project_metadata(project_path)
            warnings.extend(metadata.warnings)
            resolved = metadata.packages.get(package) or fallback
            if resolved == fallback and package not in metadata.packages:
                warnings.append(f"{package}: Package was not found in pubspec.lock; using {fallback}.")
        else:
            warnings.append(f"{target.get('id') or target.get('library')}: project_path is required for project-version; using {fallback}.")
        updated = dict(target)
        updated["version"] = resolved
        return updated

    def validate_docs_manifest(
        self,
        manifest_path: str,
        *,
        project_path: str | None = None,
        targets: list[str] | None = None,
    ) -> DocsManifestValidationResult:
        path = Path(manifest_path).expanduser()
        errors: list[str] = []
        warnings: list[str] = []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return DocsManifestValidationResult(False, str(path), errors=[f"invalid YAML: {exc}"])
        except OSError as exc:
            return DocsManifestValidationResult(False, str(path), errors=[str(exc)])
        if not isinstance(data, dict):
            return DocsManifestValidationResult(False, str(path), errors=["manifest must be a mapping"])
        if data.get("version") != 1:
            errors.append("manifest version must be 1")
        defaults = data.get("defaults") or {}
        raw_targets = data.get("targets") or []
        if not isinstance(raw_targets, list):
            errors.append("targets must be a list")
            raw_targets = []

        selected = set(targets or [])
        seen_ids: set[str] = set()
        seen_canonical: set[str] = set()
        docs_targets: list[DocsTarget] = []
        valid_source_types = {"api", "guides", "tutorials", "migration", "reference"}

        for index, raw in enumerate(raw_targets):
            if not isinstance(raw, dict):
                errors.append(f"targets[{index}] must be a mapping")
                continue
            target_id = raw.get("id")
            if selected and target_id not in selected:
                continue
            if target_id:
                if target_id in seen_ids:
                    errors.append(f"duplicate target id: {target_id}")
                seen_ids.add(target_id)
            merged = self._merge_manifest_defaults(defaults, raw)
            merged = self._resolve_manifest_project_version(merged, project_path, warnings)
            source_type = merged.get("source_type") or "api"
            if source_type not in valid_source_types:
                errors.append(f"invalid source_type for {target_id or merged.get('library')}: {source_type}")
                continue
            try:
                target = self._target_from_dict(merged)
            except KeyError as exc:
                errors.append(f"target {target_id or index} missing required field: {exc.args[0]}")
                continue
            canonical_id = canonical_library_id(target.library, target.ecosystem, target.version, target.source_type)
            if canonical_id in seen_canonical:
                errors.append(f"duplicate canonical target id: {canonical_id}")
            seen_canonical.add(canonical_id)
            _, error = self._target_urls(target)
            if error:
                errors.append(f"{target_id or canonical_id}: {error}")
                continue
            docs_targets.append(target)

        if selected:
            found = {raw.get("id") for raw in raw_targets if isinstance(raw, dict)}
            for target_id in selected - found:
                errors.append(f"unknown target id: {target_id}")
        return DocsManifestValidationResult(not errors, str(path), targets=docs_targets, errors=errors, warnings=warnings)

    def prefetch_docs_manifest(
        self,
        manifest_path: str,
        *,
        project_path: str | None = None,
        targets: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> DocsTargetsPrefetchResult | DocsJobStartResult:
        if async_:
            job = self.jobs.create("prefetch_docs_manifest")
            self.jobs.update(job.job_id, status="running", message="Started docs prefetch job.")
            threading.Thread(
                target=self._run_prefetch_docs_manifest_job,
                args=(job.job_id, manifest_path, project_path, targets, force_refresh, continue_on_error),
                daemon=True,
            ).start()
            return DocsJobStartResult(job_id=job.job_id, status="running", message="Started docs prefetch job.")

        validation = self.validate_docs_manifest(manifest_path, project_path=project_path, targets=targets)
        if not validation.valid:
            return DocsTargetsPrefetchResult(
                status="failed",
                warnings=validation.warnings + validation.errors,
                message="manifest validation failed",
            )
        result = self.prefetch_docs_targets(
            validation.targets,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
        )
        if validation.warnings:
            return DocsTargetsPrefetchResult(
                status=result.status,
                results=result.results,
                warnings=validation.warnings + result.warnings,
                message=result.message,
            )
        return result

    def _run_prefetch_docs_manifest_job(
        self,
        job_id: str,
        manifest_path: str,
        project_path: str | None,
        targets: list[str] | None,
        force_refresh: bool,
        continue_on_error: bool,
    ) -> None:
        try:
            self.jobs.update(job_id, status="running", phase="validating", message="Validating docs manifest.")
            validation = self.validate_docs_manifest(manifest_path, project_path=project_path, targets=targets)
            if validation.warnings:
                for warning in validation.warnings:
                    self.jobs.append_warning(job_id, warning)
            if not validation.valid:
                for error in validation.errors:
                    self.jobs.append_error(job_id, error)
                self.jobs.update(job_id, status="failed", phase="done", message="manifest validation failed")
                return
            self._prefetch_docs_targets_sync(
                validation.targets,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                job_id=job_id,
            )
        except Exception as exc:
            self.jobs.append_error(job_id, str(exc))
            self.jobs.update(job_id, status="failed", phase="done", message=str(exc))

    @staticmethod
    def _target_result_summary(result: DocsTargetResult) -> dict[str, Any]:
        return {
            "canonical_id": result.canonical_id,
            "status": result.status,
            "pages_indexed": result.pages_indexed,
            "message": result.message,
        }

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
        return self._prefetch_docs_targets_sync(
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
            self._prefetch_docs_targets_sync(
                targets,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                job_id=job_id,
            )
        except Exception as exc:
            self.jobs.append_error(job_id, str(exc))
            self.jobs.update(job_id, status="failed", phase="done", message=str(exc))

    def _prefetch_docs_targets_sync(
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
            target = self._target_from_dict(raw_target)
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
                target_summaries.append(self._target_result_summary(result))
                if job_id:
                    self.jobs.append_error(job_id, f"{canonical_id}: duplicate canonical target id")
                    self.jobs.update(job_id, failed_targets=targets_failed, message="duplicate canonical target id")
                if not continue_on_error:
                    aborted = True
                    break
                continue
            seen.add(canonical_id)

            urls, error = self._target_urls(target)
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
                target_summaries.append(self._target_result_summary(result))
                if job_id:
                    self.jobs.append_error(job_id, f"{canonical_id}: {error}")
                    self.jobs.update(job_id, failed_targets=targets_failed, message=error)
                if not continue_on_error:
                    aborted = True
                    break
                continue

            target_spec = self._target_to_spec(target, urls)
            record = self.registry.upsert(
                library=target.library,
                ecosystem=target.ecosystem,
                version=version,
                source_type=source_type,
                docs_url=urls[0],
                docs_url_template=target.docs_url_template,
                now=self._now(),
                status="available",
                target_spec=target_spec,
            )

            with self._lock_for(record.library_id):
                record = self.registry.get(record.library_id, source_type=record.source_type) or record
                if not force_refresh and not self._is_stale(record.last_refreshed_at):
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
                    target_summaries.append(self._target_result_summary(result))
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
                    per_url_max_pages = 1 if target.seed_urls and not target.docs_url and not target.docs_url_template else target.max_pages
                    if job_id:
                        self.jobs.update(
                            job_id,
                            phase="fetching",
                            total_pages=(self.jobs.get(job_id).total_pages if self.jobs.get(job_id) else 0) + len(urls),
                            message=f"Fetching target {index}/{len(raw_targets)}.",
                        )
                    for url_index, url in enumerate(urls, start=1):
                        if self.jobs.cancellation_requested(job_id):
                            aborted = True
                            raise KeyboardInterrupt("Docs prefetch job cancelled.")
                        pages = self._agent_instance(record).add(
                            url,
                            recreate=False,
                            max_pages=per_url_max_pages,
                            browser=target.browser,
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
                        now=self._now(),
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
                    target_summaries.append(self._target_result_summary(result))
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
                refreshed_at = self._now()
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
                target_summaries.append(self._target_result_summary(result))
                if job_id:
                    self.jobs.update(
                        job_id,
                        completed_targets=targets_completed,
                        phase="indexing",
                        message=f"Indexed target {index}/{len(raw_targets)}.",
                    )

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

    def get_docs(
        self,
        library: str,
        topic: str | None = None,
        tokens: int | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        force_refresh: bool = False,
        project_path: str | None = None,
    ) -> DocsResult:
        project_warnings: list[str] = []
        requested_version = version
        version_source = "explicit" if version is not None else None
        docs_snapshot_exact: bool | None = None
        if version is None and project_path:
            project_version, project_docs_url, project_template, project_warnings, requested_version, docs_snapshot_exact = self._project_version_for(
                library=library,
                ecosystem=ecosystem,
                project_path=project_path,
            )
            if project_version:
                version = project_version
                version_source = "project"
                docs_url = docs_url or project_docs_url
                docs_url_template = docs_url_template or project_template
        elif version is not None and ecosystem == "pub":
            docs_snapshot_exact = True
        if ecosystem is None and self._is_flutter_library(library):
            ecosystem = "flutter"

        info = self.resolve_library(library, ecosystem, version, docs_url, docs_url_template, source_type)
        if info.library_id is None:
            warning = self._join_warnings("needs_docs_url", extra=project_warnings)
            warnings = [warning] if warning else []
            return DocsResult(
                library_id="",
                library=library,
                version=version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=True,
                warning=warning,
                last_refreshed_at=None,
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
            )

        stale_before = info.stale
        refreshed = False
        warning = None
        if version is None and info.version == "latest":
            warning = "No version was provided; using latest/default docs."
        if project_warnings:
            warning = self._join_warnings(warning, extra=project_warnings)
        warnings = [warning] if warning else []
        if force_refresh or stale_before:
            result = self.refresh_docs(info.library_id, ecosystem=None, docs_url=docs_url, source_type=info.source_type, force=force_refresh)
            refreshed = result.status == "updated"
            if result.status in {"failed", "needs_docs_url"}:
                warning = result.status if not result.message else f"{result.status}: {result.message}"
                warnings = [warning]
                if not info.local:
                    return DocsResult(
                        info.library_id,
                        info.library,
                        info.version,
                        topic,
                        False,
                        stale_before,
                        warning,
                        None,
                        source_type=info.source_type,
                        results=[],
                        warnings=warnings,
                        requested_version=requested_version,
                        resolved_version=info.version,
                        version_source=version_source,
                        docs_snapshot_exact=docs_snapshot_exact,
                    )

        latest = self.resolve_library(info.library_id, source_type=info.source_type)
        record = self.registry.get(info.library_id, source_type=info.source_type)
        if record is None:
            return DocsResult(
                info.library_id,
                info.library,
                info.version,
                topic,
                refreshed,
                stale_before,
                warning,
                latest.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=info.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
            )
        query = f"{info.library} {topic}".strip() if topic else info.library
        chunks = self._agent_instance(record).query(query, budget=tokens or DEFAULT_DOC_TOKENS)
        if any((chunk.metadata or {}).get("library_id") for chunk in chunks):
            allowed_ids = {info.library_id}
            if info.version:
                from docmancer.docs.resolver import legacy_library_id

                allowed_ids.add(legacy_library_id(info.library, info.version))
            chunks = [chunk for chunk in chunks if (chunk.metadata or {}).get("library_id") in allowed_ids]
        return DocsResult(
            library_id=info.library_id,
            library=latest.library,
            version=latest.version,
            topic=topic,
            refreshed=refreshed,
            stale_before_refresh=stale_before,
            warning=warning,
            last_refreshed_at=latest.last_refreshed_at,
            source_type=info.source_type,
            results=[
                DocsChunk(
                    title=(chunk.metadata or {}).get("title"),
                    content=chunk.text,
                    source=chunk.source,
                    url=chunk.source if chunk.source.startswith(("http://", "https://")) else None,
                )
                for chunk in chunks
            ],
            warnings=warnings,
            requested_version=requested_version,
            resolved_version=latest.version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
        )

    def prefetch_project_docs(
        self,
        project_path: str,
        include_flutter: bool = True,
        include_dart: bool = False,
        include_packages: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
    ) -> ProjectPrefetchResult:
        metadata = self.read_project_metadata(project_path)
        results: list[RefreshResult] = []
        warnings = list(metadata.warnings)

        if include_flutter:
            flutter_version = self._flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if flutter_version:
                if metadata.flutter_version and flutter_version == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                result = self.refresh_docs(
                    "flutter-api",
                    ecosystem="flutter",
                    version=flutter_version,
                    source_type="api",
                    docs_url=self._flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                    force=force_refresh,
                )
                results.append(result)
                if not continue_on_error and result.status in {"failed", "needs_docs_url"}:
                    return ProjectPrefetchResult(project=metadata, results=results, warnings=warnings)
            else:
                warnings.append(NO_PROJECT_VERSION_WARNING)
                result = RefreshResult(
                    library_id="flutter-api",
                    status="needs_docs_url",
                    docs_url=None,
                    last_refreshed_at=None,
                    message=NO_PROJECT_VERSION_WARNING,
                )
                results.append(result)
                if not continue_on_error:
                    return ProjectPrefetchResult(project=metadata, results=results, warnings=warnings)

        if include_dart:
            warnings.append("Dart SDK documentation version detection is not implemented.")

        for package in include_packages or []:
            version = metadata.packages.get(package)
            if not version:
                warnings.append(f"{package}: {PACKAGE_NOT_FOUND_WARNING}")
                result = RefreshResult(
                    library_id=package,
                    status="needs_docs_url",
                    docs_url=None,
                    last_refreshed_at=None,
                    message=PACKAGE_NOT_FOUND_WARNING,
                )
                results.append(result)
                if not continue_on_error:
                    break
                continue
            result = self.refresh_docs(
                package,
                ecosystem="pub",
                version=version,
                docs_url_template=PUB_DOCS_URL_TEMPLATE,
                source_type="api",
                force=force_refresh,
            )
            results.append(result)
            if not continue_on_error and result.status in {"failed", "needs_docs_url"}:
                break

        return ProjectPrefetchResult(project=metadata, results=results, warnings=warnings)


    def _index_size_for(self, record: LibraryRecord) -> int:
        config = self._index_config_for(record)
        total = 0
        db_path = Path(config.index.db_path)
        if db_path.exists():
            total += db_path.stat().st_size
        extracted = Path(config.index.extracted_dir)
        if extracted.exists():
            total += sum(path.stat().st_size for path in extracted.rglob("*") if path.is_file())
        return total


    def _delete_index_for(self, record: LibraryRecord) -> int:
        config = self._index_config_for(record)
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

    def inspect_library_docs(self, canonical_id: str) -> DocsInspectResult:
        record = self.registry.get(canonical_id)
        if record is None:
            return DocsInspectResult(canonical_id=canonical_id, status="missing", message="library docs target not found")
        return DocsInspectResult(
            canonical_id=record.library_id,
            status=record.status or "available",
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            source_type=record.source_type,
            docs_url=record.docs_url,
            last_refreshed_at=record.last_refreshed_at,
            stale=self._is_stale(record.last_refreshed_at),
            size_bytes=self._index_size_for(record),
            warnings=[record.last_error] if record.last_error else [],
        )

    def remove_library_docs(self, canonical_id: str) -> DocsRemoveResult:
        record = self.registry.get(canonical_id)
        if record is None:
            return DocsRemoveResult(canonical_id=canonical_id, removed=False, message="library docs target not found")
        removed_bytes = self._delete_index_for(record)
        removed = self.registry.delete(record.library_id)
        self._agents.pop(record.library_id, None)
        return DocsRemoveResult(canonical_id=record.library_id, removed=removed, chunks_removed=removed_bytes)

    def _record_age_cutoff_value(self, record: LibraryRecord) -> str | None:
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
        for record in self.registry.list():
            if normalized_library and record.normalized_name != normalized_library:
                continue
            if record.version in keep:
                continue
            value = self._record_age_cutoff_value(record)
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
        for record in self.registry.list(limit=limit):
            stale = self._is_stale(record.last_refreshed_at)
            if stale_only and not stale:
                continue
            items.append(
                LibraryInfo(
                    library_id=record.library_id,
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    source_type=record.source_type,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    status=record.status,
                    local=record.last_refreshed_at is not None,
                    stale=stale,
                    last_refreshed_at=record.last_refreshed_at,
                    message=record.last_error,
                )
            )
        return items


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
