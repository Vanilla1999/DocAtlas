from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from ipaddress import ip_address
from pathlib import Path
import json
import shutil
import threading
import time
import uuid
from urllib.parse import urlparse

import yaml
import httpx

from filelock import FileLock

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJob, DocsJobCancelResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectContextResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRecord, LibraryRegistry
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
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

    def append_event(self, job_id: str, event: dict[str, Any], max_events: int = 50) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        event = dict(event)
        event.setdefault("at", now)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            events = [*job.events, event][-max_events:]
        self.update(job_id, events=events, last_event_at=now)

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
                requested_version=normalized_version,
                resolved_version=normalized_version,
                version_source="explicit" if normalized_version else None,
                version_confidence="high" if normalized_version else None,
                version_inferred=normalized_version is None,
            )
        if record is None:
            candidates = self.registry.find_candidates(library, ecosystem, normalized_version, source_type)
            if len(candidates) == 1:
                record = candidates[0]
            elif len(candidates) > 1:
                return LibraryInfo(
                    library_id=None,
                    library=library,
                    ecosystem=ecosystem,
                    version=normalized_version,
                    docs_url=docs_url,
                    docs_url_template=docs_url_template,
                    source_type=source_type,
                    status="ambiguous",
                    local=False,
                    stale=True,
                    message="Multiple registered documentation sources match this library. Choose one candidate and retry.",
                    candidates=[self._candidate_payload(candidate) for candidate in candidates],
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
        if docs_url is None and docs_url_template and normalized_version:
            docs_url = self._render_docs_url(docs_url_template, library, normalized_version)
        input_resolved_url = docs_url or (
            self._render_docs_url(docs_url_template, library, normalized_version)
            if docs_url_template and normalized_version
            else None
        )
        if input_resolved_url and record.docs_url_resolved and input_resolved_url != record.docs_url_resolved:
            return LibraryInfo(
                library_id=record.library_id,
                source_id=record.source_id,
                canonical_id=record.canonical_id,
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
                status="docs_url_conflict",
                local=record.last_refreshed_at is not None,
                stale=self._is_stale(record.last_refreshed_at),
                last_refreshed_at=record.last_refreshed_at,
                message="Input docs_url conflicts with the registered docs locator. Use the registered source or explicitly refresh/re-register it.",
            )
        if input_resolved_url and not record.docs_url_resolved:
            record = self.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                source_type=record.source_type,
                now=self._now(),
                status="available",
                requested_version=record.requested_version,
                resolved_version=record.resolved_version,
                version_source=record.version_source,
                version_confidence=record.version_confidence,
                version_inferred=record.version_inferred,
                docs_snapshot_exact=record.docs_snapshot_exact,
            )
        stale = self._is_stale(record.last_refreshed_at)
        return LibraryInfo(
            library_id=record.library_id,
            source_id=record.source_id,
            canonical_id=record.canonical_id,
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
            status=record.status or "available",
            local=record.last_refreshed_at is not None,
            stale=stale,
            last_refreshed_at=record.last_refreshed_at,
            message=record.last_error,
        )

    @staticmethod
    def _candidate_payload(record: LibraryRecord) -> dict[str, Any]:
        return {
            "source_id": record.source_id,
            "canonical_id": record.canonical_id,
            "library_id": record.library_id,
            "library": record.name,
            "ecosystem": record.ecosystem,
            "version": record.version,
            "source_type": record.source_type,
            "docs_url": record.docs_url,
            "arguments_patch": {
                "library": record.library_id,
                "source_type": record.source_type,
            },
        }

    @staticmethod
    def _docs_policy(status: str, *, has_registered_source: bool) -> dict[str, Any]:
        if status == "ambiguous":
            return {"direct_webfetch": "forbidden", "reason_code": "registry_candidates_exist"}
        if has_registered_source:
            return {"direct_webfetch": "forbidden", "reason_code": "registered_source_exists"}
        return {"direct_webfetch": "discovery_only", "reason_code": "no_registered_source"}

    def _docs_identity(self, info: LibraryInfo | None, *, docs_url_source: str | None = None) -> dict[str, Any]:
        return {
            "source_id": info.source_id if info else None,
            "canonical_id": info.canonical_id if info else None,
            "library": info.library if info else None,
            "ecosystem": info.ecosystem if info else None,
            "version": info.version if info else None,
            "docs_url": info.docs_url if info else None,
            "docs_url_source": docs_url_source,
            "selected_by": "registry" if docs_url_source == "registry" else None,
            "docs_snapshot_exact": info.docs_snapshot_exact if info else None,
        }

    @staticmethod
    def _docs_request(input_args: dict[str, Any], info: LibraryInfo | None = None) -> dict[str, Any]:
        effective = dict(input_args)
        if info:
            effective.update(
                {
                    "library": info.library,
                    "ecosystem": info.ecosystem,
                    "version": info.version,
                    "source_type": info.source_type,
                    "docs_url": info.docs_url,
                    "docs_url_template": info.docs_url_template,
                }
            )
        return {"input": input_args, "effective": effective}

    def _record_from_info(self, info: LibraryInfo) -> LibraryRecord | None:
        if info.library_id is None:
            return None
        return self.registry.get(info.library_id, None, source_type=info.source_type)

    def _resolve_docs_source(
        self,
        library: str,
        ecosystem: str | None,
        version: str | None,
        docs_url: str | None,
        docs_url_template: str | None,
        source_type: str | None,
        *,
        input_docs_url: str | None = None,
        input_docs_url_template: str | None = None,
    ) -> DocsSourceResolution:
        """Resolve the effective source before asking the caller for docs_url.

        Registered sources own their stored locator. That lets
        get_library_docs(library, topic) use a unique existing docs_url without
        forcing the caller to remember it, while unknown sources still produce a
        genuine needs_docs_url response.
        """
        info = self.resolve_library(library, ecosystem, version, docs_url, docs_url_template, source_type)
        docs_url_source = (
            "input"
            if input_docs_url or input_docs_url_template
            else ("registry" if info.library_id and (info.docs_url or info.docs_url_template) else None)
        )
        diagnostics: dict[str, Any] = {
            "resolver": {
                "status": info.status,
                "selected_by": "registry" if docs_url_source == "registry" else docs_url_source,
                "stored_locator": info.docs_url or info.docs_url_template,
                "candidate_count": len(info.candidates),
            }
        }
        return DocsSourceResolution(
            info=info,
            docs_url_source=docs_url_source,
            has_registered_source=info.library_id is not None or info.status == "ambiguous",
            diagnostics=diagnostics,
        )

    @staticmethod
    def _render_docs_url(template: str, library: str, version: str) -> str:
        return template.format(library=library, version=version)

    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return self.project_reader.read(project_path)

    def _indexed_project_doc_sources(self, project_path: str) -> list[dict[str, Any]]:
        root = Path(project_path).expanduser().resolve()
        agent = self._agent_instance()
        rows: list[dict[str, Any]] = []
        with agent.store._connect() as conn:
            for row in conn.execute(
                """
                SELECT source, metadata_json, ingested_at
                FROM sources
                WHERE json_extract(metadata_json, '$.project_path') = ?
                  AND json_extract(metadata_json, '$.source_class') = 'project_file'
                  AND json_extract(metadata_json, '$.project_docs') = 1
                ORDER BY source
                """,
                (str(root),),
            ):
                metadata = json.loads(row["metadata_json"] or "{}")
                rows.append({
                    "source": row["source"],
                    "path": metadata.get("project_doc_path") or metadata.get("source_path"),
                    "source_class": metadata.get("source_class"),
                    "content_hash": metadata.get("project_doc_content_hash"),
                    "mtime_ns": metadata.get("project_doc_mtime_ns"),
                    "reason": metadata.get("project_doc_reason"),
                    "ingested_at": row["ingested_at"],
                })
        return rows

    @staticmethod
    def _partition_project_doc_state(
        candidates: list[dict[str, Any]],
        indexed_sources: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        candidate_by_path = {item.get("path"): item for item in candidates if item.get("path")}
        indexed_by_path = {item.get("path"): item for item in indexed_sources if item.get("path")}
        current: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        for path, indexed in indexed_by_path.items():
            candidate = candidate_by_path.get(path)
            if not candidate:
                ignored.append({**indexed, "stale": True, "reason": "indexed_source_not_discovered"})
                continue
            stale_reasons: list[str] = []
            if candidate.get("content_hash") != indexed.get("content_hash"):
                stale_reasons.append("content_hash_changed")
            if candidate.get("mtime_ns") != indexed.get("mtime_ns"):
                stale_reasons.append("mtime_changed")
            merged = {**indexed, "candidate": candidate, "stale": bool(stale_reasons)}
            if stale_reasons:
                merged["stale_reasons"] = stale_reasons
                merged["current_content_hash"] = candidate.get("content_hash")
                merged["current_mtime_ns"] = candidate.get("mtime_ns")
                stale.append(merged)
            else:
                current.append(merged)
        return current, stale, ignored

    @staticmethod
    def _create_project_docs_next_action(root: Path, query: str | None = None) -> dict[str, Any]:
        get_project_docs_args = {"project_path": str(root)}
        if query:
            get_project_docs_args["query"] = query
        return {
            "action": "create_reviewable_project_doc",
            "requires_confirmation": True,
            "preferred_path": "ARCHITECTURE.md",
            "suggested_paths": ["ARCHITECTURE.md", "README.md", "docs/architecture.md"],
            "reason": "No official project docs files were discovered. Ask the user before creating a reviewable architecture doc in the repository.",
            "agent_guidance": "If the user approves, inspect the codebase, create ARCHITECTURE.md as a normal reviewable file, then call inspect_project_docs and ingest_project_docs before answering repo-specific architecture questions.",
            "after": [
                {
                    "tool": "inspect_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root)},
                },
                {
                    "tool": "ingest_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root)},
                },
                {
                    "tool": "get_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": get_project_docs_args,
                },
            ],
        }

    def inspect_project_docs(self, project_path: str) -> ProjectDocsInspectResult:
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
        manifests_found = [name for name in ("pubspec.yaml", "Cargo.toml") if (root / name).exists()]
        lockfiles_found = [name for name in ("pubspec.lock", "Cargo.lock") if (root / name).exists()]
        exact_versions_available = any(item.resolved_version for item in metadata.dependencies)
        recommended_next_actions: list[dict[str, Any]] = []
        if stale_sources:
            recommended_next_actions.append({
                "tool": "ingest_project_docs",
                "requires_confirmation": False,
                "reason": "Some indexed project docs are stale; re-index reviewable docs files.",
            })
        elif candidate_sources and len(indexed_sources) < len(candidate_sources):
            recommended_next_actions.append({
                "tool": "ingest_project_docs",
                "requires_confirmation": False,
                "reason": "Project docs found but not indexed.",
            })
        if exact_versions_available:
            recommended_next_actions.append({
                "tool": "prefetch_project_docs",
                "requires_confirmation": True,
                "reason": "Exact dependency versions found in project lockfiles; fetching docs may use network.",
            })
        if not candidate_sources:
            recommended_next_actions.append(self._create_project_docs_next_action(root))
        project_docs = {
            "found": candidate_sources,
            "indexed": indexed_sources,
            "stale": stale_sources,
            "ignored": ignored_sources,
        }
        dependency_sources = {
            "manifests_found": manifests_found,
            "lockfiles_found": lockfiles_found,
            "exact_versions_available": exact_versions_available,
            "network_fetch_required": exact_versions_available,
        }
        return ProjectDocsInspectResult(
            project_detected=root.exists() and root.is_dir(),
            project_path=str(root),
            project_type=metadata.detected_ecosystems,
            project_docs=project_docs,
            dependency_sources=dependency_sources,
            candidate_sources=candidate_sources,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            ignored_sources=ignored_sources,
            recommended_next_actions=recommended_next_actions,
            agent_guidance="Call get_project_docs for repo-specific questions after project docs are indexed. If docs are missing, ask before creating a reviewable ARCHITECTURE.md, then inspect and ingest it. If docs are stale, call ingest_project_docs first. Ask before network dependency docs fetches.",
            warnings=metadata.warnings,
        )

    def ingest_project_docs(
        self,
        project_path: str,
        *,
        skip_known: bool = True,
        with_vectors: bool = True,
    ) -> ProjectDocsIngestResult:
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        warnings = list(metadata.warnings)
        candidates = list(metadata.docs_candidates)
        if not candidates:
            return ProjectDocsIngestResult(
                status="no_project_docs",
                project=metadata,
                candidate_count=0,
                warnings=warnings,
                message="No project-owned docs candidates were discovered.",
            )

        candidate_by_abs = {(root / item.path).resolve(): item for item in candidates}
        include = tuple(item.path for item in candidates)

        def _metadata_for_file(path: Path) -> dict[str, Any]:
            candidate = candidate_by_abs.get(path.resolve())
            result: dict[str, Any] = {
                "project_path": str(root),
                "source_class": "project_file",
                "project_docs": True,
            }
            if candidate:
                result.update({
                    "project_doc_path": candidate.path,
                    "project_doc_reason": candidate.reason,
                    "project_doc_content_hash": candidate.content_hash,
                    "project_doc_mtime_ns": candidate.mtime_ns,
                })
            return result

        agent = self._agent_instance()
        try:
            sections_indexed = agent.ingest(
                root,
                include=include,
                recursive=True,
                skip_known=skip_known,
                with_vectors=with_vectors,
                metadata={"project_path": str(root), "source_class": "project_file", "project_docs": True},
                metadata_for_file=_metadata_for_file,
            )
        except ValueError as exc:
            return ProjectDocsIngestResult(
                status="failed",
                project=metadata,
                candidate_count=len(candidates),
                indexed_sources=[],
                skipped_sources=getattr(agent, "last_ingest_skips", []),
                sections_indexed=0,
                warnings=[*warnings, str(exc)],
                message=str(exc),
            )

        return ProjectDocsIngestResult(
            status="success",
            project=metadata,
            candidate_count=len(candidates),
            indexed_sources=[asdict(item) for item in candidates],
            skipped_sources=getattr(agent, "last_ingest_skips", []),
            sections_indexed=sections_indexed,
            warnings=warnings,
            message=f"Indexed {len(candidates)} project docs candidate(s).",
        )

    def query_project_docs(
        self,
        project_path: str,
        query: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        source_class: str = "project_file",
    ):
        root = Path(project_path).expanduser().resolve()
        return self._agent_instance().query(
            query,
            limit=limit,
            budget=tokens or DEFAULT_DOC_TOKENS,
            expand=expand,
            filters={
                "project_path": str(root),
                "source_class": source_class,
                "project_docs": True,
            },
        )

    def get_project_docs(
        self,
        project_path: str,
        query: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
    ) -> ProjectDocsResult:
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)

        if not candidate_sources:
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="no_project_docs",
                reason="no_project_docs",
                answer_available=False,
                warnings=metadata.warnings,
                next_actions=[{
                    **self._create_project_docs_next_action(root, query),
                    "reason": "No project-owned docs candidates were discovered for this repository. Create a reviewable architecture doc before indexing.",
                }],
                message="No project-owned docs were found. Ask before creating a reviewable ARCHITECTURE.md, then run inspect_project_docs and ingest_project_docs.",
            )

        if not indexed_sources_all:
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="not_indexed",
                reason="project_docs_not_indexed",
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                next_actions=[{
                    "tool": "ingest_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root)},
                    "reason": "Project docs candidates were discovered but have not been indexed.",
                }],
                message="Project docs candidates exist but are not indexed. Run ingest_project_docs, then retry get_project_docs.",
            )

        chunks = self.query_project_docs(str(root), query, tokens=tokens, limit=limit, expand=expand)
        seen_sources: set[str] = set()
        result_indexed_sources = []
        for chunk in chunks:
            source = chunk.source
            if source in seen_sources:
                continue
            seen_sources.add(source)
            result_indexed_sources.append({
                "source": source,
                "path": (chunk.metadata or {}).get("project_doc_path"),
                "source_class": (chunk.metadata or {}).get("source_class"),
                "content_hash": (chunk.metadata or {}).get("project_doc_content_hash"),
                "mtime_ns": (chunk.metadata or {}).get("project_doc_mtime_ns"),
            })
        stale_paths = {item.get("path") for item in stale_sources}
        results = [
            ProjectDocsChunk(
                title=(chunk.metadata or {}).get("title"),
                content=chunk.text,
                source=chunk.source,
                url=None,
                metadata=chunk.metadata or {},
                source_class=(chunk.metadata or {}).get("source_class"),
                path=(chunk.metadata or {}).get("project_doc_path") or (chunk.metadata or {}).get("source_path"),
                heading_path=(chunk.metadata or {}).get("anchor") or (chunk.metadata or {}).get("title"),
                content_hash=(chunk.metadata or {}).get("project_doc_content_hash"),
                mtime_ns=(chunk.metadata or {}).get("project_doc_mtime_ns"),
                stale=((chunk.metadata or {}).get("project_doc_path") in stale_paths),
            )
            for chunk in chunks
        ]
        next_actions: list[dict[str, Any]] = []
        if stale_sources:
            next_actions.append({
                "tool": "ingest_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root)},
                "reason": "Some indexed project docs are stale; re-index before relying on repo-specific answers.",
            })
        if results:
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="stale" if stale_sources else "success",
                reason="project_docs_stale" if stale_sources else None,
                answer_available=True,
                results=results,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=result_indexed_sources or indexed_sources,
                stale_sources=stale_sources,
                next_actions=next_actions,
                message=f"Returned {len(results)} project docs result(s)." + (" Some indexed project docs are stale." if stale_sources else ""),
            )
        return ProjectDocsResult(
            project_path=str(root),
            query=query,
            status="stale" if stale_sources else "no_results",
            reason="project_docs_stale" if stale_sources else "no_project_docs_results",
            answer_available=False,
            warnings=metadata.warnings,
            candidate_sources=candidate_sources,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            next_actions=[{
                "tool": "ingest_project_docs" if stale_sources else "inspect_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root)},
                "reason": "Project docs are stale; re-index and retry." if stale_sources else "Project docs are indexed, but no indexed project docs matched this query. Inspect candidates or refine the query.",
            }],
            message="Indexed project docs exist, but no results matched this query." + (" Some indexed docs are stale." if stale_sources else ""),
        )

    def get_project_context(
        self,
        project_path: str,
        question: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        library: str | None = None,
        libraries: list[str] | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        mode: str = "auto",
    ) -> ProjectContextResult:
        """Return a repo-grounded context pack with a compact Trust Contract.

        MVP behavior is deliberately small: always query project-owned docs and,
        when a dependency is requested or detectable from the question, include one
        dependency docs query through the existing library-docs resolver.
        """
        mode = mode.lower()
        if mode not in {"auto", "project-only", "deps-only", "public-docs"}:
            raise ValueError("mode must be one of: auto, project-only, deps-only, public-docs")
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        project_docs = None
        if mode in {"auto", "project-only"}:
            project_docs = self.get_project_docs(str(root), question, tokens=tokens, limit=limit, expand=expand)

        selected_dependency = library or (libraries[0] if libraries else None) or self._dependency_mentioned_in_question(metadata, question)
        dependency_docs: DocsResult | None = None
        if selected_dependency and mode in {"auto", "deps-only", "public-docs"}:
            dependency_docs = self.get_docs(
                selected_dependency,
                topic=question,
                tokens=tokens,
                ecosystem=ecosystem,
                version=version,
                project_path=str(root),
            )

        trust_contract = self._project_context_trust_contract(
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            requested_library=selected_dependency,
            mode=mode,
        )
        warnings = [*(project_docs.warnings if project_docs else [])]
        if dependency_docs:
            warnings.extend(dependency_docs.warnings)
        next_actions = [*(project_docs.next_actions if project_docs else [])]
        if dependency_docs:
            next_actions.extend(
                {"tool": dependency_docs.tool, "reason": action}
                for action in dependency_docs.next_actions
            )
        context_pack = self._project_context_pack(project_docs=project_docs, dependency_docs=dependency_docs)
        metrics = self._project_context_metrics(context_pack=context_pack, project_docs=project_docs, dependency_docs=dependency_docs)
        answer_available = bool(project_docs and project_docs.answer_available) or bool(dependency_docs and dependency_docs.results)
        status = "success" if answer_available else (project_docs.status if project_docs else dependency_docs.status if dependency_docs else "no_results")
        if (project_docs and project_docs.status == "stale") or (dependency_docs and dependency_docs.stale_before_refresh):
            status = "stale"
        reason = "trusted_context_available" if answer_available else "no_trusted_context"
        return ProjectContextResult(
            project_path=str(root),
            question=question,
            status=status,
            answer_available=answer_available,
            mode=mode,
            reason=reason,
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            trust_contract=trust_contract,
            warnings=warnings,
            next_actions=next_actions,
            metrics=metrics,
            message="Returned project context with Trust Contract." if answer_available else (project_docs.message if project_docs else "No trusted context matched this question."),
        )

    @staticmethod
    def _project_context_pack(
        *,
        project_docs: ProjectDocsResult | None,
        dependency_docs: DocsResult | None,
    ) -> list[dict[str, Any]]:
        pack: list[dict[str, Any]] = []
        if project_docs:
            for item in project_docs.results:
                token_estimate = max(1, len(item.content) // 4) if item.content else 0
                pack.append({
                    "source_class": "project_doc",
                    "path": item.path,
                    "url": item.url,
                    "title": item.title,
                    "heading_path": item.heading_path,
                    "freshness": "stale" if item.stale else "current",
                    "why_selected": "matches repo-owned project documentation for the question",
                    "content": item.content,
                    "token_estimate": token_estimate,
                })
                snippet = LibraryDocsService._context_pack_snippet(item)
                if snippet:
                    pack[-1]["snippet"] = snippet
                    pack[-1]["surrounding_context"] = item.content
        if dependency_docs:
            for item in dependency_docs.results:
                token_estimate = max(1, len(item.content) // 4) if item.content else 0
                pack.append({
                    "source_class": "dependency_doc",
                    "dependency": dependency_docs.library,
                    "requested_version": dependency_docs.requested_version,
                    "resolved_version": dependency_docs.resolved_version or dependency_docs.version,
                    "version_source": dependency_docs.version_source,
                    "docs_exactness": dependency_docs.docs_exactness,
                    "docs_binding_source": dependency_docs.docs_binding_source,
                    "confidence": dependency_docs.confidence,
                    "url": item.url,
                    "source": item.source,
                    "title": item.title,
                    "freshness": "stale" if dependency_docs.stale_before_refresh else "current",
                    "why_selected": "dependency docs resolved through Docmancer registry/project metadata",
                    "content": item.content,
                    "token_estimate": token_estimate,
                })
                snippet = LibraryDocsService._context_pack_snippet(item)
                if snippet:
                    pack[-1]["snippet"] = snippet
                    pack[-1]["surrounding_context"] = item.content
        return pack

    @staticmethod
    def _context_pack_snippet(item: DocsChunk) -> dict[str, Any] | None:
        metadata = item.metadata or {}
        snippets = metadata.get("code_snippets") or []
        snippet = snippets[0] if snippets and isinstance(snippets[0], dict) else None
        if not snippet:
            return None
        code = str(snippet.get("code") or "").strip()
        if not code:
            return None
        language = str(snippet.get("language") or "").strip() or None
        title = item.title or metadata.get("title") or "section"
        return {
            "language": language,
            "code": code,
            "why_relevant": f"code example extracted from matching {title} section",
        }

    @staticmethod
    def _project_context_metrics(
        *,
        context_pack: list[dict[str, Any]],
        project_docs: ProjectDocsResult | None,
        dependency_docs: DocsResult | None,
    ) -> dict[str, Any]:
        source_classes = [item.get("source_class") for item in context_pack]
        return {
            "context_pack_items": len(context_pack),
            "selected_source_count": len(context_pack),
            "project_result_count": len(project_docs.results) if project_docs else 0,
            "dependency_result_count": len(dependency_docs.results) if dependency_docs else 0,
            "token_estimate": sum(int(item.get("token_estimate") or 0) for item in context_pack),
            "source_classes": sorted({str(item) for item in source_classes if item}),
        }

    @staticmethod
    def _dependency_mentioned_in_question(metadata: ProjectMetadata, question: str) -> str | None:
        normalized_question = question.lower().replace("-", "_")
        for dependency in metadata.dependencies:
            name = dependency.package_name
            if name.lower() in normalized_question or name.lower().replace("-", "_") in normalized_question:
                return name
        return None

    @staticmethod
    def _project_context_trust_contract(
        *,
        project_docs: ProjectDocsResult | None,
        dependency_docs: DocsResult | None,
        requested_library: str | None,
        mode: str,
    ) -> dict[str, Any]:
        selected_sources: list[dict[str, Any]] = []
        rejected_sources: list[dict[str, Any]] = []
        risky_sources: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        next_actions: list[dict[str, Any]] = []

        if project_docs:
            for source in project_docs.indexed_sources:
                selected_sources.append({
                    "source_class": "project_file",
                    "path": source.get("path"),
                    "source": source.get("source"),
                    "freshness": "current",
                    "reason": "repo-owned project docs matched the question",
                    "why_selected": "repo-owned project docs matched the question",
                    "trust_level": "trusted",
                })
            for source in project_docs.stale_sources:
                risky = {
                    "source_class": "project_file",
                    "path": source.get("path"),
                    "reason_code": "project_docs_stale",
                    "reason": "Indexed project docs differ from current repo files.",
                    "risk_level": "medium",
                }
                risky_sources.append(risky)
                warnings.append(risky)
            next_actions.extend(project_docs.next_actions)
        elif mode in {"deps-only", "public-docs"}:
            risky_sources.append({
                "source_class": "project_file",
                "reason_code": "project_docs_skipped",
                "reason": f"Project docs were skipped because mode={mode}.",
                "risk_level": "low",
            })

        if dependency_docs:
            if dependency_docs.results:
                selected_sources.append({
                    "source_class": "dependency_docs",
                    "library": dependency_docs.library,
                    "requested_version": dependency_docs.requested_version,
                    "version": dependency_docs.resolved_version or dependency_docs.version,
                    "resolved_version": dependency_docs.resolved_version or dependency_docs.version,
                    "version_source": dependency_docs.version_source,
                    "docs_exactness": dependency_docs.docs_exactness,
                    "docs_binding_source": dependency_docs.docs_binding_source,
                    "confidence": dependency_docs.confidence,
                    "freshness": "stale" if dependency_docs.stale_before_refresh else "current",
                    "reason": "dependency docs resolved through Docmancer registry/project metadata",
                    "why_selected": "dependency docs resolved through Docmancer registry/project metadata",
                    "trust_level": "trusted" if dependency_docs.docs_exactness == "exact" else "best_effort",
                })
            for warning in dependency_docs.warnings:
                risky = {
                    "source_class": "dependency_docs",
                    "library": dependency_docs.library,
                    "reason_code": warning,
                    "reason": warning,
                    "risk_level": "medium",
                }
                risky_sources.append(risky)
                warnings.append(risky)
            if dependency_docs.status in {"needs_input", "ambiguous", "error"}:
                rejected_sources.append({
                    "source_class": "dependency_docs",
                    "library": dependency_docs.library,
                    "reason_code": dependency_docs.status,
                    "reason": dependency_docs.warning or "Dependency docs were not safe to use.",
                    "risk_level": "high",
                })
            next_actions.extend({"tool": dependency_docs.tool, "reason": action} for action in dependency_docs.next_actions)
        elif requested_library:
            rejected_sources.append({
                "source_class": "dependency_docs",
                "library": requested_library,
                "reason_code": "not_resolved",
                "reason": "Requested dependency docs were not resolved.",
                "risk_level": "high",
            })
            next_actions.append({
                "tool": "prefetch_project_docs",
                "requires_confirmation": True,
                "reason": "Fetch dependency docs before retrying project context.",
            })

        return {
            "schema_version": "trust-contract-1.0-mvp",
            "selected_sources": selected_sources,
            "trusted_sources": selected_sources,
            "rejected_sources": rejected_sources,
            "risky_sources": risky_sources,
            "rejected_or_risky_sources": [*rejected_sources, *risky_sources],
            "warnings": warnings,
            "next_actions": next_actions,
            "policy": {
                "direct_webfetch": "forbidden" if selected_sources else "discovery_only",
                "reason_code": "trusted_context_available" if selected_sources else "no_trusted_context",
            },
        }

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

    @staticmethod
    def _docs_exactness(docs_snapshot_exact: bool | None, docs_url: str | None, docs_url_template: str | None) -> str:
        if docs_snapshot_exact:
            return "exact_snapshot"
        if docs_url or docs_url_template:
            return "exact_version_url"
        return "no_docs"

    @staticmethod
    def _project_resolution_summary(metadata: ProjectMetadata) -> dict[str, int]:
        exact_versions = sum(1 for item in metadata.dependencies if item.resolved_version and item.version_source.endswith("exact"))
        best_effort_docs = sum(1 for item in metadata.dependencies if item.source_kind != "registry")
        return {
            "dependencies_seen": len(metadata.dependencies),
            "exact_versions": exact_versions,
            "best_effort_docs": best_effort_docs,
            "no_docs": 0,
        }

    def _dependency_observation_for(self, metadata: ProjectMetadata, library: str, ecosystem: str | None) -> Any | None:
        candidates = [item for item in metadata.dependencies if item.package_name == library]
        if ecosystem:
            candidates = [item for item in candidates if item.ecosystem == ecosystem]
        if candidates:
            return next((item for item in candidates if item.resolved_version), candidates[0])
        rust_key = metadata.packages.get(f"rust:{library}")
        if rust_key and ecosystem in {None, "rust"}:
            return next((item for item in metadata.dependencies if item.ecosystem == "rust" and item.package_name == library), None)
        return None

    def _project_version_for(
        self,
        *,
        library: str,
        ecosystem: str | None,
        project_path: str | None,
    ) -> tuple[str | None, str | None, str | None, list[str], str | None, bool | None, str | None, str | None]:
        if not project_path:
            return None, None, None, [], None, None, None, None
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
                    "project_flutter_sdk",
                    "flutter_api_current_channel",
                )
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None, None, None

        observation = self._dependency_observation_for(metadata, library, ecosystem)
        if observation and observation.ecosystem == "rust":
            if observation.source_kind != "registry":
                warnings.append(f"{library}: Rust path/git dependencies cannot be bound to docs.rs exactly.")
                return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"
            if observation.resolved_version:
                return (
                    observation.resolved_version,
                    f"https://docs.rs/{library}/{observation.resolved_version}/",
                    None,
                    warnings,
                    observation.specifier_raw or observation.resolved_version,
                    True,
                    observation.version_source,
                    "docs_rs",
                )
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"

        if ecosystem == "pub" or library in metadata.packages:
            version = metadata.packages.get(library)
            if version:
                source = observation.version_source if observation else "lockfile_exact"
                return version, None, PUB_DOCS_URL_TEMPLATE, warnings, version, True, source, "pub_dartdoc"
            warnings.append(PACKAGE_NOT_FOUND_WARNING)
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None, None, None

        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, None, None, None, None

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
            doc_format=value.get("doc_format"),
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
            "doc_format": target.doc_format,
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
            doc_format=spec.get("doc_format"),
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

    def _progress_callback_for(self, job_id: str | None, canonical_id: str):
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

    def _discover_pub_dartdoc_target(self, target: DocsTarget, warnings: list[str], job_id: str | None = None, canonical_id: str | None = None) -> DocsTarget:
        if not is_pub_dartdoc_target(target):
            return target
        target = normalize_pub_dartdoc_target(target)
        if job_id:
            # Async jobs should reach indexing promptly. Keep live Dartdoc seed
            # discovery on the synchronous path where callers wait for the full result.
            return target
        version = normalize_version(target.version) or "latest"
        root_url = pub_dartdoc_root_url(target.library, version)
        if job_id:
            self.jobs.update(job_id, phase="discovering", current_target=canonical_id, current_url=root_url, message=f"Discovering Dartdoc seed URLs for {target.library}.")
            self.jobs.append_event(job_id, {"phase": "discovering", "message": f"Discovering Dartdoc seed URLs for {target.library}", "url": root_url})
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "docmancer/1.0"}) as client:
                resp = client.get(root_url)
            if resp.status_code != 200:
                raise ValueError(f"status {resp.status_code}")
            seeds = discover_pub_dartdoc_seed_urls(target.library, version, resp.text, root_url, max_seed_urls=target.max_pages or 50)
        except Exception as exc:
            warning = f"{target.library}: could not discover pub.dev Dartdoc seed URLs ({exc}); falling back to root URL."
            warnings.append(warning)
            target = replace(target, warnings=[*target.warnings, warning])
            return target
        if not seeds:
            warning = f"{target.library}: no pub.dev Dartdoc seed URLs discovered; falling back to root URL."
            warnings.append(warning)
            target = replace(target, warnings=[*target.warnings, warning])
            return target
        if job_id:
            self.jobs.update(job_id, discovered_pages=len(seeds), total_pages=max((self.jobs.get(job_id).total_pages if self.jobs.get(job_id) else 0), len(seeds)), message=f"Discovered {len(seeds)} Dartdoc seed URLs for {target.library}.")
            self.jobs.append_event(job_id, {"phase": "discovering", "message": f"Discovered {len(seeds)} Dartdoc seed URLs", "url": root_url, "discovered_pages": len(seeds), "total_pages": len(seeds)})
        return replace(target, docs_url=None, docs_url_template=None, seed_urls=seeds)


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
                target_summaries.append(self._target_result_summary(result))
                if job_id:
                    self.jobs.append_error(job_id, f"{canonical_id}: duplicate canonical target id")
                    self.jobs.update(job_id, failed_targets=targets_failed, message="duplicate canonical target id")
                if not continue_on_error:
                    aborted = True
                    break
                continue
            seen.add(canonical_id)

            target = self._discover_pub_dartdoc_target(target, warnings, job_id=job_id, canonical_id=canonical_id)
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
                    progress_callback = self._progress_callback_for(job_id, record.library_id)
                    for url_index, url in enumerate(urls, start=1):
                        if self.jobs.cancellation_requested(job_id):
                            aborted = True
                            raise KeyboardInterrupt("Docs prefetch job cancelled.")
                        add_kwargs: dict[str, Any] = {
                            "max_pages": per_url_max_pages,
                            "browser": target.browser,
                        }
                        if target.doc_format:
                            add_kwargs["doc_format"] = target.doc_format
                        if progress_callback:
                            add_kwargs["progress_callback"] = progress_callback
                            progress_callback({"phase": "fetching", "message": f"Fetching seed URL {url_index}/{len(urls)}", "url": url, "total_pages": len(urls)})
                        pages = self._agent_instance(record).add(
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
        input_args = {
            "library": library,
            "topic": topic,
            "tokens": tokens,
            "ecosystem": ecosystem,
            "version": version,
            "source_type": source_type,
            "docs_url": docs_url,
            "docs_url_template": docs_url_template,
            "force_refresh": force_refresh,
            "project_path": project_path,
        }
        input_docs_url = docs_url
        input_docs_url_template = docs_url_template
        project_warnings: list[str] = []
        requested_version = version
        version_source = "explicit" if version is not None else None
        docs_snapshot_exact: bool | None = None
        docs_binding_source: str | None = None
        if version is None and project_path:
            project_version, project_docs_url, project_template, project_warnings, requested_version, docs_snapshot_exact, project_version_source, docs_binding_source = self._project_version_for(
                library=library,
                ecosystem=ecosystem,
                project_path=project_path,
            )
            if project_version:
                version = project_version
                version_source = project_version_source or "project"
                docs_url = docs_url or project_docs_url
                docs_url_template = docs_url_template or project_template
        elif version is not None and ecosystem == "pub":
            docs_snapshot_exact = True
            docs_binding_source = "pub_dartdoc" if docs_url or docs_url_template else None
        elif version is not None and ecosystem == "rust":
            docs_snapshot_exact = True
            docs_binding_source = "docs_rs" if docs_url or docs_url_template else None
        if ecosystem is None and self._is_flutter_library(library):
            ecosystem = "flutter"

        resolution = self._resolve_docs_source(
            library,
            ecosystem,
            version,
            docs_url,
            docs_url_template,
            source_type,
            input_docs_url=input_docs_url,
            input_docs_url_template=input_docs_url_template,
        )
        info = resolution.info
        docs_url_source = resolution.docs_url_source
        if info.status == "ambiguous":
            warnings = self._join_warnings("ambiguous_library", extra=project_warnings)
            return DocsResult(
                library_id="",
                library=library,
                version=version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=True,
                warning=warnings,
                last_refreshed_at=None,
                results=[],
                warnings=[warnings] if warnings else [],
                requested_version=requested_version,
                resolved_version=version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=self._docs_exactness(docs_snapshot_exact, docs_url, docs_url_template),
                docs_binding_source=docs_binding_source,
                confidence="high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None,
                status="ambiguous",
                decision="choose_candidate",
                request=self._docs_request(input_args),
                identity=self._docs_identity(info),
                policy=self._docs_policy("ambiguous", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "ambiguous_library", "blocking": True}]},
                next_actions=["Choose one candidate and retry get_library_docs with its arguments_patch."],
                candidates=info.candidates,
            )
        if info.status == "docs_url_conflict":
            warning = self._join_warnings("docs_url_conflict", extra=project_warnings)
            return DocsResult(
                library_id=info.library_id or "",
                library=info.library,
                version=info.version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=info.stale,
                warning=warning,
                last_refreshed_at=info.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=[warning] if warning else [],
                requested_version=requested_version if requested_version is not None else info.requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source if version_source is not None else info.version_source,
                docs_snapshot_exact=docs_snapshot_exact if docs_snapshot_exact is not None else info.docs_snapshot_exact,
                docs_exactness=self._docs_exactness(info.docs_snapshot_exact, info.docs_url, info.docs_url_template),
                docs_binding_source=docs_binding_source or "registry",
                confidence=info.version_confidence,
                status="needs_input",
                decision="retry_same_tool",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source="registry"),
                policy=self._docs_policy("needs_input", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "docs_url_conflict", "blocking": True}]},
                next_actions=["Retry get_library_docs without docs_url to use the registered source, or explicitly refresh/re-register the docs target."],
            )
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
                docs_exactness=self._docs_exactness(docs_snapshot_exact, docs_url, docs_url_template),
                docs_binding_source=docs_binding_source,
                confidence="high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None,
                status="needs_input",
                decision="retry_same_tool",
                request=self._docs_request(input_args),
                identity=self._docs_identity(info),
                policy=self._docs_policy("needs_input", has_registered_source=resolution.has_registered_source),
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "needs_docs_url", "blocking": True}]},
                next_actions=["Retry get_library_docs with docs_url, or call prefetch_library_docs/prefetch_docs_targets to register this source."],
            )

        requested_version = requested_version if requested_version is not None else info.requested_version
        version_source = version_source if version_source is not None else info.version_source
        docs_snapshot_exact = docs_snapshot_exact if docs_snapshot_exact is not None else info.docs_snapshot_exact
        docs_binding_source = docs_binding_source or ("registry" if info.docs_url or info.docs_url_template else None)
        docs_exactness = self._docs_exactness(docs_snapshot_exact, info.docs_url, info.docs_url_template)
        confidence = info.version_confidence or ("high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None)
        if info.library_id and (
            requested_version != info.requested_version
            or version_source != info.version_source
            or docs_snapshot_exact != info.docs_snapshot_exact
        ):
            updated_record = self.registry.upsert(
                library=info.library,
                ecosystem=info.ecosystem,
                version=info.version,
                docs_url=info.docs_url,
                docs_url_template=info.docs_url_template,
                source_type=info.source_type,
                now=self._now(),
                status=info.status,
                last_refreshed_at=info.last_refreshed_at,
                requested_version=requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source,
                version_confidence=confidence,
                version_inferred=version_source != "explicit",
                docs_snapshot_exact=docs_snapshot_exact,
            )
            info = self.resolve_library(updated_record.library_id, source_type=updated_record.source_type)

        stale_before = info.stale
        refreshed = False
        warning = None
        if version is None and info.version == "latest":
            warning = "No version was provided; using latest/default docs."
        if project_warnings:
            warning = self._join_warnings(warning, extra=project_warnings)
        warnings = [warning] if warning else []
        diagnostic_warnings: list[dict[str, Any]] = []
        if docs_url_source == "registry":
            diagnostic_warnings.append({"code": "used_registry_docs_url", "blocking": False})
        if warning:
            diagnostic_warnings.append({"code": warning, "blocking": False})
        if force_refresh or stale_before:
            result = self.refresh_docs(
                info.library_id,
                ecosystem=None,
                docs_url=info.docs_url,
                docs_url_template=info.docs_url_template,
                source_type=info.source_type,
                force=force_refresh,
            )
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
                        docs_exactness=docs_exactness,
                        docs_binding_source=docs_binding_source,
                        confidence=confidence,
                        status="error",
                        decision="stop",
                        request=self._docs_request(input_args, info),
                        identity=self._docs_identity(info, docs_url_source=docs_url_source),
                        policy=self._docs_policy("error", has_registered_source=True),
                        diagnostics={**resolution.diagnostics, "warnings": diagnostic_warnings},
                        next_actions=["Retry get_library_docs with force_refresh=false if local docs are usable, or refresh/register the source again."],
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
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status="success",
                decision="answer_returned",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("success", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": diagnostic_warnings},
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
                    metadata=chunk.metadata or {},
                )
                for chunk in chunks
            ],
            warnings=warnings,
            requested_version=requested_version,
            resolved_version=latest.resolved_version or latest.version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
            docs_exactness=docs_exactness,
            docs_binding_source=docs_binding_source,
            confidence=confidence,
            status="success",
            decision="answer_returned",
            request=self._docs_request(input_args, info),
            identity=self._docs_identity(info, docs_url_source=docs_url_source),
            policy=self._docs_policy("success", has_registered_source=True),
            diagnostics={**resolution.diagnostics, "warnings": diagnostic_warnings},
        )

    def prefetch_project_docs(
        self,
        project_path: str,
        include_flutter: bool = True,
        include_dart: bool = False,
        include_rust: bool = True,
        include_packages: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> ProjectPrefetchResult | DocsJobStartResult:
        metadata = self.read_project_metadata(project_path)
        warnings = list(metadata.warnings)
        targets: list[DocsTarget] = []

        if include_flutter:
            flutter_version = self._flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if flutter_version:
                if metadata.flutter_version and flutter_version == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                targets.append(DocsTarget(
                    library="flutter-api",
                    ecosystem="flutter",
                    version=flutter_version,
                    source_type="api",
                    docs_url=self._flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                    allowed_domains=["api.flutter.dev", "main-api.flutter.dev"],
                    doc_format="dartdoc",
                ))
            else:
                warnings.append(NO_PROJECT_VERSION_WARNING)
                if not continue_on_error:
                    return ProjectPrefetchResult(
                        project=metadata,
                        results=[],
                        warnings=warnings,
                        detected_ecosystems=metadata.detected_ecosystems,
                        resolution_summary=self._project_resolution_summary(metadata),
                    )

        if include_dart:
            warnings.append("Dart SDK documentation version detection is not implemented.")

        for package in include_packages or []:
            rust_version = metadata.packages.get(f"rust:{package}")
            if rust_version and include_rust:
                targets.append(DocsTarget(
                    library=package,
                    ecosystem="rust",
                    version=rust_version,
                    docs_url=f"https://docs.rs/{package}/{rust_version}/",
                    source_type="api",
                    allowed_domains=["docs.rs"],
                    path_prefixes=[f"/{package}/{rust_version}/"],
                ))
                continue
            version = metadata.packages.get(package)
            if not version:
                warnings.append(f"{package}: Package was not found in project lockfiles.")
                if not continue_on_error:
                    break
                continue
            targets.append(DocsTarget(
                library=package,
                ecosystem="pub",
                version=version,
                docs_url=pub_dartdoc_root_url(package, version),
                source_type="api",
                doc_format="dartdoc",
                allowed_domains=["pub.dev"],
                path_prefixes=[f"/documentation/{package}/{version}/"],
            ))

        if async_:
            job = self.jobs.create("prefetch_project_docs")
            self.jobs.update(job.job_id, status="running", message="Started project docs prefetch job.", total_targets=len(targets))
            threading.Thread(
                target=self._run_prefetch_docs_targets_job,
                args=(job.job_id, targets, force_refresh, continue_on_error),
                daemon=True,
            ).start()
            return DocsJobStartResult(job_id=job.job_id, status="running", message="Started project docs prefetch job.")

        batch = self._prefetch_docs_targets_sync(targets, force_refresh=force_refresh, continue_on_error=continue_on_error)
        results = [
            RefreshResult(
                library_id=item.canonical_id,
                status=item.status,
                docs_url=item.docs_url,
                last_refreshed_at=None,
                version=item.version,
                source_type=item.source_type,
                message=item.message,
                pages_indexed=item.pages_indexed,
                targets_completed=1 if item.status in {"ready", "skipped"} else 0,
                targets_failed=1 if item.status == "failed" else 0,
            )
            for item in batch.results
        ]
        return ProjectPrefetchResult(
            project=metadata,
            results=results,
            warnings=[*warnings, *batch.warnings],
            detected_ecosystems=metadata.detected_ecosystems,
            resolution_summary=self._project_resolution_summary(metadata),
        )


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
            source_id=record.source_id,
            status=record.status or "available",
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
