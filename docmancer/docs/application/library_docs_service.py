from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import re
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.discovery_candidates import discovery_candidates_for
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.quality import is_trivial_section
from docmancer.docs.domain.library_source_options import library_docs_source_next_actions, library_docs_source_options, source_required_diagnostics
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.snippets import build_snippet_presentation, validate_response_style
from docmancer.docs.curated_sources import curated_source_for, curated_target_spec
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, docs_snapshot_is_exact, legacy_library_id, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.dart_official_docs import (
    allowed_domains_for_urls,
    build_dart_diagnostics,
    canonical_dart_ecosystem,
    get_seed_urls_for_package,
    has_official_docs,
    resolve_dart_official_docs,
)
from docmancer.docs.application.library_registry_ops import LibraryRegistryOps
from docmancer.docs.application.library_refresh_ops import LibraryRefreshOps
from docmancer.docs.application.library_job_executor import LibraryJobExecutor, shared_library_job_executor
from docmancer.docs.application.library_ingest_orchestrator import LibraryIngestOrchestrator
from docmancer.docs.application.library_ingest_ports import LibraryIngestPorts, LibraryPublicationPorts, LibraryRefreshPorts
from docmancer.docs.application.evidence_selection import (
    build_requirements,
    library_docs_selection_config,
    requirement_value_visible,
    select_evidence,
)

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
MAX_CHUNKS_PER_SOURCE = 2
MMR_LAMBDA = 0.7
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)

class LibraryDocsApplicationService:
    def __init__(self, facade: Any, job_executor: LibraryJobExecutor | None = None):
        self.facade = facade
        self.registry_ops = LibraryRegistryOps(facade)
        self._refresh_ops: LibraryRefreshOps | None = None
        self._ingest_orchestrator: LibraryIngestOrchestrator | None = None
        jobs_config = getattr(getattr(facade, "config", None), "docs_jobs", None)
        max_running = getattr(jobs_config, "library_max_running", 2)
        max_queued = getattr(jobs_config, "library_max_queued", 8)
        grace = getattr(jobs_config, "terminalization_grace_seconds", 2.0)
        self.job_executor = job_executor or shared_library_job_executor(
            max_workers=max_running if isinstance(max_running, int) else 2,
            max_queued=max_queued if isinstance(max_queued, int) else 8,
            terminalization_grace_seconds=grace if isinstance(grace, (int, float)) else 2.0,
        )
        # Preserve startup cleanup for real services while lightweight facade doubles
        # can still construct the public read delegates without ingest dependencies.
        if getattr(facade, "config", None) is not None:
            _ = self.refresh_ops

    @property
    def refresh_ops(self) -> LibraryRefreshOps:
        if self._refresh_ops is None:
            ports = LibraryRefreshPorts(
                staging_parent=lambda: Path(self.config.index.db_path).expanduser().resolve().parent,
                jobs=self.jobs,
                registry=self.registry,
                registry_ops=self.registry_ops,
                agent_gateway=self.agent_gateway,
                resolve_library=self.resolve_library,
                record_from_info=self._record_from_info,
                target_from_record=self._target_from_record,
                record_urls=self._record_urls,
                agent_instance=self._agent_instance,
                is_stale=self._is_stale,
                now=self._now,
                index_config_for=self._index_config_for,
                lock_for=self._lock_for,
                resolve_github_directory_target=self.facade._resolve_github_directory_target,
                target_urls=self.facade._target_urls,
                target_to_spec=self.facade._target_to_spec,
                monotonic=time.monotonic,
                utc_now=lambda: datetime.now(timezone.utc),
                publication=LibraryPublicationPorts(
                    index_config_for=self._index_config_for,
                    lock_for=self._lock_for,
                    restore_record=self.registry.restore,
                    drop_library_agent=self.agent_gateway.drop_library_agent,
                    monotonic=time.monotonic,
                ),
            )
            self._refresh_ops = LibraryRefreshOps(ports)
        return self._refresh_ops

    @property
    def ingest_orchestrator(self) -> LibraryIngestOrchestrator:
        if self._ingest_orchestrator is None:
            self._ingest_orchestrator = LibraryIngestOrchestrator(
                LibraryIngestPorts(
                    jobs=self.jobs,
                    prefetch=self.refresh_ops.prefetch_docs,
                    timeout_seconds=self._library_job_timeout_seconds,
                    executor=lambda: self.job_executor,
                    prefetch_targets=lambda *args, **kwargs: self.facade.docs_prefetch.prefetch_docs_targets_sync(
                        *args, **kwargs
                    ),
                )
            )
        return self._ingest_orchestrator

    def __getattr__(self, name: str) -> Any:
        return getattr(self.facade, name)

    def _target_from_record(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._target_from_record(*args, **kwargs)

    def _record_urls(self, *args: Any, **kwargs: Any) -> list[str]:
        return self.facade._record_urls(*args, **kwargs)

    def _agent_instance(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._agent_instance(*args, **kwargs)

    def _is_stale(self, *args: Any, **kwargs: Any) -> bool:
        return self.facade._is_stale(*args, **kwargs)

    def _now(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._now(*args, **kwargs)

    def _index_config_for(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._index_config_for(*args, **kwargs)

    def _record_from_info(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._record_from_info(*args, **kwargs)

    def _lock_for(self, *args: Any, **kwargs: Any) -> Any:
        return self.facade._lock_for(*args, **kwargs)

    def _render_docs_url(self, *args: Any, **kwargs: Any) -> str:
        return self.facade._render_docs_url(*args, **kwargs)

    def resolve_library(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
    ) -> LibraryInfo:
        if hasattr(self.facade, "_library_resolve_library_impl"):
            return self.facade._library_resolve_library_impl(library, ecosystem, version, docs_url, docs_url_template, source_type)
        normalized_version = normalize_version(version)
        original_ecosystem = ecosystem
        canonical_ecosystem = canonical_dart_ecosystem(ecosystem)
        if canonical_ecosystem in {"dart"}:
            ecosystem = canonical_ecosystem
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
            discovery_candidates = discovery_candidates_for(library, ecosystem)
            
            # Check if Dart/Flutter package has real official docs (non-pub.dev)
            normalized_ecosystem = (canonical_dart_ecosystem(original_ecosystem) or "").lower().strip()
            is_dart_flutter = normalized_ecosystem == "dart"
            if is_dart_flutter and (source_type or "").lower() == "api":
                dart_resolution = resolve_dart_official_docs(library, version=normalized_version)
                pubdev_url = dart_resolution.pubdev_docs_url
                is_exact_snapshot = docs_snapshot_is_exact(normalized_version, pubdev_url)
                target_spec = {
                    "id": f"dart:{library}:api",
                    "library": library,
                    "ecosystem": "dart",
                    "version": normalized_version or "latest",
                    "docs_url": pubdev_url,
                    "source_type": "api",
                    "doc_format": "dartdoc",
                    "allowed_domains": allowed_domains_for_urls([pubdev_url]),
                    "seed_urls": [],
                    "max_pages": 100,
                    "dart_docs": {
                        "requested_ecosystem": original_ecosystem,
                        "docs_strategy": "pubdev_only",
                        "version_binding": "pubdev_api_snapshot" if is_exact_snapshot else "latest_pubdev_api",
                    },
                }
                record = self.registry.upsert(
                    library=library,
                    ecosystem="dart",
                    version=normalized_version or "latest",
                    docs_url=pubdev_url,
                    source_type="api",
                    now=self._now(),
                    status="available",
                    target_spec=target_spec,
                    requested_version=normalized_version,
                    resolved_version=normalized_version or "latest",
                    version_source="pubdev_api" if is_exact_snapshot else None,
                    version_confidence="high" if is_exact_snapshot else None,
                    version_inferred=not is_exact_snapshot,
                    docs_snapshot_exact=is_exact_snapshot,
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
                    status="needs_refresh" if stale else "available",
                    local=record.last_refreshed_at is not None,
                    stale=stale,
                    last_refreshed_at=record.last_refreshed_at,
                    message=None,
                )

            has_real_official_docs = False
            dart_docs_url = None
            
            if is_dart_flutter and has_official_docs(library):
                dart_resolution = resolve_dart_official_docs(library, version=normalized_version)
                if dart_resolution.official_docs_available and dart_resolution.official_docs_urls:
                    primary = next((url for url in dart_resolution.official_docs_urls if "pub.dev" not in url), None)
                    primary_host = urlparse(primary).hostname if primary else None
                    package_owned_host = primary_host in {"riverpod.dev", "bloclibrary.dev"}
                    if primary and package_owned_host:
                        has_real_official_docs = True
                        dart_docs_url = primary
            
            if has_real_official_docs and dart_docs_url:
                seed_urls = [
                    url for url in get_seed_urls_for_package(library, normalized_version, max_urls=100)
                    if url != dart_docs_url
                ]
                urls_for_domains = [dart_docs_url, *seed_urls]
                target_spec = {
                    "id": f"dart:{library}",
                    "library": library,
                    "ecosystem": "dart",
                    "version": normalized_version or "latest",
                    "docs_url": dart_docs_url,
                    "source_type": source_type or "web",
                    "doc_format": "html",
                    "allowed_domains": allowed_domains_for_urls(urls_for_domains),
                    "seed_urls": seed_urls,
                    "max_pages": 100,
                    "dart_docs": {
                        "requested_ecosystem": original_ecosystem,
                        "docs_strategy": dart_resolution.docs_strategy,
                        "version_binding": "unversioned_official_guide" if normalized_version else "latest_or_unversioned",
                    },
                }
                record = self.registry.upsert(
                    library=library,
                    ecosystem="dart",
                    version=normalized_version or "latest",
                    docs_url=dart_docs_url,
                    source_type=source_type or "web",
                    now=self._now(),
                    status="available",
                    target_spec=target_spec,
                    requested_version=normalized_version,
                    resolved_version=None if normalized_version else "latest",
                    version_source="official_docs" if normalized_version else None,
                    version_confidence="low" if normalized_version else None,
                    version_inferred=normalized_version is None,
                    docs_snapshot_exact=False,
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
                    status="needs_refresh" if stale else "available",
                    local=record.last_refreshed_at is not None,
                    stale=stale,
                    last_refreshed_at=record.last_refreshed_at,
                    message=None,
                )
            
            curated = curated_source_for(library, ecosystem, normalized_version)
            if curated:
                target_spec = curated_target_spec(curated, version=normalized_version)
                assert target_spec is not None
                docs_url = target_spec["docs_url"]
                record = self.registry.upsert(
                    library=library,
                    ecosystem=ecosystem,
                    version=normalized_version or "latest",
                    docs_url=docs_url,
                    source_type=source_type or "api",
                    now=self._now(),
                    status="available",
                    target_spec=target_spec,
                    requested_version=normalized_version,
                    resolved_version=normalized_version if curated.exact_snapshot else None,
                    version_source="curated_source_manifest",
                    version_confidence="high" if curated.exact_snapshot else "low",
                    version_inferred=normalized_version is None,
                    docs_snapshot_exact=curated.exact_snapshot,
                )
            else:
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
                    candidates=discovery_candidates,
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
        return docs_policy(status, has_registered_source=has_registered_source)

    @staticmethod

    def _docs_identity(info: LibraryInfo | None, *, docs_url_source: str | None = None) -> dict[str, Any]:
        return docs_identity(info, docs_url_source=docs_url_source)

    @staticmethod

    def _docs_request(input_args: dict[str, Any], info: LibraryInfo | None = None) -> dict[str, Any]:
        return docs_request(input_args, info)

    @staticmethod
    def _url_within_root(value: str | None, roots: set[str]) -> bool:
        if not roots:
            return bool(value)
        if not value:
            return False
        normalized = str(value).rstrip("/")
        return any(normalized == root.rstrip("/") or normalized.startswith(root.rstrip("/") + "/") for root in roots if root)

    def _library_chunk_rejection_reason(self, chunk: Any, info: LibraryInfo, allowed_ids: set[str], expected_roots: set[str]) -> str | None:
        metadata = chunk.metadata or {}
        library_id = metadata.get("library_id")
        if library_id not in allowed_ids:
            return "missing_library_metadata" if not library_id else "wrong_library_id"
        canonical_id = metadata.get("canonical_id")
        if canonical_id and canonical_id != info.canonical_id:
            return "wrong_canonical_id"
        ecosystem = metadata.get("ecosystem")
        if ecosystem and info.ecosystem and ecosystem != info.ecosystem:
            return "wrong_ecosystem"
        version = metadata.get("version") or metadata.get("resolved_version")
        if version and info.version and version != info.version:
            return "wrong_version"
        source_type = metadata.get("source_type")
        if source_type and info.source_type and source_type != info.source_type:
            return "wrong_source_type"
        if metadata.get("project_path"):
            return "project_doc_leak"
        source = getattr(chunk, "source", None)
        source_matches_exact_root = bool(source) and any(
            str(source).rstrip("/") == root.rstrip("/")
            for root in expected_roots
            if root
        )
        docset_root = metadata.get("docset_root")
        broad_docset_root_contains_source = bool(docset_root) and self._url_within_root(
            source,
            {str(docset_root)},
        )
        has_complete_exact_identity = bool(canonical_id) and canonical_id == info.canonical_id
        has_complete_exact_identity = (
            has_complete_exact_identity
            and bool(ecosystem)
            and ecosystem == info.ecosystem
            and bool(version)
            and version == info.version
            and bool(source_type)
            and source_type == info.source_type
        )
        if (
            docset_root
            and expected_roots
            and not self._url_within_root(str(docset_root), expected_roots)
            and not (
                source_matches_exact_root
                and broad_docset_root_contains_source
                and has_complete_exact_identity
            )
        ):
            return "wrong_docset_root"
        if not self._url_within_root(source, expected_roots):
            return "wrong_docset_root"
        for url_key in ("url", "source_url"):
            url = metadata.get(url_key)
            if url and not self._url_within_root(url, expected_roots):
                return "wrong_docset_root"
        return None

    def _library_chunk_allowed(self, chunk: Any, info: LibraryInfo, allowed_ids: set[str], expected_roots: set[str]) -> bool:
        return self._library_chunk_rejection_reason(chunk, info, allowed_ids, expected_roots) is None

    def _expected_docset_roots(self, info: LibraryInfo, record: LibraryRecord | None) -> set[str]:
        roots = {root for root in {info.docs_url_resolved, info.docs_url} if root}
        spec = record.target_spec if record else None
        if isinstance(spec, dict):
            roots.update(str(url) for url in spec.get("seed_urls") or [] if url)
            roots.update(str(url) for url in spec.get("resolved_urls") or [] if url)
        return roots

    def _empty_library_index_result(
        self,
        *,
        info: LibraryInfo,
        latest: LibraryInfo,
        topic: str | None,
        refreshed: bool,
        stale_before: bool,
        warning: str | None,
        warnings: list[str],
        requested_version: str | None,
        version_source: str | None,
        docs_snapshot_exact: bool | None,
        docs_exactness: str | None,
        docs_binding_source: str | None,
        confidence: str | None,
        input_args: dict[str, Any],
        docs_url_source: str | None,
        diagnostics: dict[str, Any],
        diagnostic_warnings: list[dict[str, Any]],
    ) -> DocsResult:
        diagnostics_with_dart = self._with_dart_diagnostics(
            diagnostics,
            info=info,
            pages_discovered=0,
            pages_extracted=0,
            chunks_created=0,
        )
        inspection_action = self._inspection_recovery_action(info)
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
            results=[],
            warnings=warnings,
            requested_version=requested_version,
            resolved_version=latest.resolved_version or latest.version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
            docs_exactness=docs_exactness,
            docs_binding_source=docs_binding_source,
            confidence=confidence,
            status="empty_library_index",
            decision="stop",
            request=self._docs_request(input_args, info),
            identity=self._docs_identity(info, docs_url_source=docs_url_source),
            policy=self._docs_policy("error", has_registered_source=True),
            diagnostics={**diagnostics_with_dart, "reason_code": "empty_index", "warnings": diagnostic_warnings},
            next_actions=(
                [inspection_action]
                if inspection_action
                else ["Call refresh_library_docs to ingest this library's docs."]
            ),
        )

    def _inspection_recovery_action(self, info: LibraryInfo) -> dict[str, Any] | None:
        record = self._record_from_info(info)
        if record is None:
            return None
        spec = dict(record.target_spec or {})
        docs_url = spec.get("docs_url") or record.docs_url
        seed_urls = list(spec.get("seed_urls") or [])[:5]
        if not docs_url and not seed_urls:
            return None
        return {
            "tool": "prepare_docs",
            "type": "prepare_docs",
            "arguments_patch": {
                "action": "prefetch_library_docs",
                "library": spec.get("library") or info.library,
                "ecosystem": spec.get("ecosystem") or info.ecosystem,
                "version": spec.get("version") or info.version,
            },
            "reason": "The registered source produced no usable indexed evidence.",
            "observations": {
                "source_status": record.status,
                "last_error": (record.last_error or "")[:300],
                "indexed_pages": info.pages,
                "indexed_chunks": info.chunks,
            },
            "security_scope": {
                "scope_expansion_allowed": False,
                "registered_source_only": True,
            },
            "decision_options": [
                {"id": "retry_registered_source", "requires_confirmation": True},
                {"id": "stop_with_partial_results", "requires_confirmation": False},
            ],
            "agent_question": (
                "Retry preparation of the registered documentation source without expanding its scope?"
            ),
            "requires_confirmation": True,
            "confirmation_reason": "Retrying documentation preparation performs network requests and writes the index.",
        }

    def _with_dart_diagnostics(
        self,
        diagnostics: dict[str, Any],
        *,
        info: LibraryInfo,
        reason_code: str | None = None,
        pages_discovered: int | None = None,
        pages_extracted: int | None = None,
        chunks_created: int | None = None,
    ) -> dict[str, Any]:
        if canonical_dart_ecosystem(info.ecosystem) != "dart":
            return diagnostics
        used_official_docs = bool(info.docs_url and "pub.dev" not in info.docs_url)
        return {
            **diagnostics,
            "dartdoc": build_dart_diagnostics(
                package=info.library,
                version=info.version,
                root_url=info.docs_url,
                pages_discovered=pages_discovered,
                pages_extracted=pages_extracted,
                chunks_created=chunks_created,
                used_official_docs=used_official_docs,
                reason_code=reason_code,
            ),
        }

    def _record_from_info(self, info: LibraryInfo) -> LibraryRecord | None:
        if info.library_id is None:
            return None
        return self.registry.get(info.library_id, None, source_type=info.source_type)

    def resolve_docs_source(
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

    def _docs_exactness(docs_snapshot_exact: bool | None, docs_url: str | None, docs_url_template: str | None) -> str:
        return docs_exactness(docs_snapshot_exact, docs_url, docs_url_template)

    @staticmethod

    def _join_warnings(*items: str | None, extra: list[str] | None = None) -> str | None:
        values = [item for item in items if item]
        if extra:
            values.extend(extra)
        return " ".join(values) if values else None

    def _refresh_record(self, record: LibraryRecord, *, force: bool) -> RefreshResult:
        return self.refresh_ops.refresh_record(record, force=force)

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
        return self.refresh_ops.refresh_docs(
            library,
            ecosystem=ecosystem,
            version=version,
            docs_url=docs_url,
            versions=versions,
            docs_url_template=docs_url_template,
            source_type=source_type,
            force=force,
            continue_on_error=continue_on_error,
        )

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
        async_: bool = False,
    ) -> RefreshResult | DocsTargetsPrefetchResult | DocsJobStartResult:
        flutter_targets = self._flutter_targets_for_request(
            library,
            ecosystem,
            versions,
            docs_url,
            docs_url_template,
        )
        if flutter_targets:
            return self.ingest_orchestrator.prefetch_docs(
                library,
                ecosystem="flutter",
                versions=versions,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                async_=async_,
                target_plan=flutter_targets,
            )
        return self.ingest_orchestrator.prefetch_docs(
            library,
            ecosystem=ecosystem,
            versions=versions,
            docs_url=docs_url,
            docs_url_template=docs_url_template,
            source_type=source_type,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
            async_=async_,
        )

    @staticmethod
    def _flutter_targets_for_request(
        library: str,
        ecosystem: str | None,
        versions: list[str] | None,
        docs_url: str | None,
        docs_url_template: str | None,
    ) -> list[DocsTarget] | None:
        if docs_url_template is not None:
            return None
        normalized_library = re.sub(r"[\s_-]+", " ", library.strip().casefold())
        normalized_ecosystem = (ecosystem or "flutter").strip().casefold()
        if normalized_ecosystem not in {"dart", "flutter"}:
            return None
        targets = LibraryDocsApplicationService._flutter_source_targets(versions)
        if docs_url is None:
            return targets if normalized_library == "flutter" else None
        host = (urlparse(docs_url).hostname or "").rstrip(".").casefold()
        if host == "docs.flutter.dev" and normalized_library in {"flutter", "flutter guides"}:
            return targets[:1]
        if host == "api.flutter.dev" and normalized_library in {"flutter", "flutter api"}:
            return targets[1:]
        return None

    @staticmethod
    def _flutter_source_targets(versions: list[str] | None) -> list[DocsTarget]:
        version = versions[0] if versions else "latest"
        return [
            DocsTarget(
                library="Flutter",
                ecosystem="flutter",
                version=version,
                source_type="guides",
                docs_url="https://docs.flutter.dev/",
                allowed_domains=["docs.flutter.dev"],
                path_prefixes=["/"],
                max_pages=40,
            ),
            DocsTarget(
                library="Flutter",
                ecosystem="flutter",
                version=version,
                source_type="api",
                docs_url="https://api.flutter.dev/index.html",
                allowed_domains=["api.flutter.dev"],
                path_prefixes=["/"],
                max_pages=40,
                doc_format="dartdoc",
            ),
        ]

    def _library_job_timeout_seconds(self) -> float:
        return float(getattr(self.config.web_fetch, "library_job_timeout_seconds", 120.0))

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
        response_style: str | None = None,
        library_requirement_contract: dict[str, list[str]] | None = None,
    ) -> DocsResult:
        response_style = validate_response_style(response_style)
        if hasattr(self.facade, "_library_get_docs_impl"):
            hook_kwargs = {
                "topic": topic,
                "tokens": tokens,
                "ecosystem": ecosystem,
                "version": version,
                "docs_url": docs_url,
                "docs_url_template": docs_url_template,
                "source_type": source_type,
                "force_refresh": force_refresh,
                "project_path": project_path,
                "response_style": response_style,
            }
            if library_requirement_contract is not None:
                hook_kwargs["library_requirement_contract"] = library_requirement_contract
            return self.facade._library_get_docs_impl(
                library,
                **hook_kwargs,
            )
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
        exact_version_resolution = None  # Will be set if exact-version logic triggers
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
            # Check exact-version resolver for Python libraries without registered source
            exact_version_resolution = None
            if ecosystem == "python" and version is not None and version not in ("latest", "*", "") and not docs_url:
                from docmancer.docs.exact_version import resolve_python_versioned_docs
                normalized_lib = library.lower().replace("-", "_").replace(" ", "_")
                exact_version_resolution = resolve_python_versioned_docs(normalized_lib, version)
                
                if exact_version_resolution and exact_version_resolution.status == "exact_version_not_supported":
                    # Return structured unsupported response without silent fallback
                    return DocsResult(
                        library_id="",
                        library=library,
                        version=version,
                        topic=topic,
                        refreshed=False,
                        stale_before_refresh=False,
                        warning=f"Exact version {version} not supported: {exact_version_resolution.reason_code}",
                        last_refreshed_at=None,
                        source_type=source_type,
                        results=[],
                        warnings=[f"exact_version_not_supported: {exact_version_resolution.reason_code}"],
                        requested_version=version,
                        resolved_version=None,
                        version_source=version_source,
                        docs_snapshot_exact=False,
                        docs_exactness="exact_version_not_supported",
                        docs_binding_source=None,
                        confidence="high",
                        status="exact_version_not_supported",
                        decision="stop",
                        request=self._docs_request(input_args),
                        identity=self._docs_identity(None),
                        policy=self._docs_policy("exact_version_not_supported", has_registered_source=False),
                        diagnostics={
                            "exact_version": {
                                "expected": version,
                                "used": None,
                                "match": None,
                                "status": exact_version_resolution.status,
                                "fallback": False,
                                "reason_code": exact_version_resolution.reason_code,
                                "fallback_available": exact_version_resolution.fallback_docs_url is not None,
                                "fallback_docs_url": exact_version_resolution.fallback_docs_url,
                            }
                        },
                        next_actions=[
                            "Retry without version to use latest docs, or use fallback_docs_url if available."
                        ],
                    )
            
            warning = self._join_warnings("library_docs_source_required", extra=project_warnings)
            warnings = [warning] if warning else []
            candidates = info.candidates
            source_options = library_docs_source_options(library, ecosystem, version, source_type, candidates)
            arguments_patch = dict(candidates[0].get("arguments_patch") or {}) if candidates else {}
            if candidates and candidates[0].get("docs_url"):
                arguments_patch.setdefault("docs_url", candidates[0]["docs_url"])
            if candidates and candidates[0].get("source_type"):
                arguments_patch.setdefault("source_type", candidates[0]["source_type"])
            if candidates and candidates[0].get("ecosystem"):
                arguments_patch.setdefault("ecosystem", candidates[0]["ecosystem"])
            next_actions_list = library_docs_source_next_actions(library, ecosystem, version, source_type, candidates, source_options)
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
                reason_code="library_docs_source_required",
                message="Documentation source is not registered locally. Ask the user which library documentation to use; if they do not know, use best-effort web discovery with quality not guaranteed.",
                requires_confirmation=True,
                arguments_patch=arguments_patch or None,
                request=self._docs_request(input_args),
                identity=self._docs_identity(info),
                policy=self._docs_policy("needs_input", has_registered_source=resolution.has_registered_source),
                diagnostics=source_required_diagnostics({
                    **resolution.diagnostics,
                    "warnings": [{"code": "library_docs_source_required", "blocking": True}],
                    "question": f"Which documentation source should be used for {library}?",
                    "source_options": source_options,
                    "discovery_candidates": candidates,
                    "quality_warning": "Best-effort web discovery may choose an incomplete or unofficial documentation source; prefer an explicit docs_url.",
                }),
                next_actions=next_actions_list,
                candidates=candidates,
                discovery_candidates=candidates,
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
        if info.status == "failed" and not force_refresh:
            failed_warning = info.message or "registered documentation source is marked failed"
            diagnostic_warnings.append({"code": "registered_source_failed", "blocking": True, "message": failed_warning})
            return DocsResult(
                library_id=info.library_id,
                library=info.library,
                version=info.version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=stale_before,
                warning=failed_warning,
                last_refreshed_at=info.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=[failed_warning],
                requested_version=requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status="error",
                decision="stop",
                reason_code="registered_source_failed",
                message="Registered documentation source is failed; refusing automatic refresh during get_library_docs to avoid long MCP timeouts.",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("error", has_registered_source=True),
                diagnostics=self._with_dart_diagnostics(
                    {**resolution.diagnostics, "reason_code": "registered_source_failed", "warnings": diagnostic_warnings},
                    info=info,
                    reason_code="registered_source_failed",
                    pages_discovered=info.pages,
                    pages_extracted=0,
                    chunks_created=0,
                ),
                next_actions=[
                    {"tool": "refresh_library_docs", "requires_confirmation": True, "arguments_patch": {"library": info.library, "ecosystem": info.ecosystem, "version": info.version, "force": True}, "reason": "Refresh the failed docs target explicitly after confirming network/indexing cost."}
                ],
            )

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
                        diagnostics={**resolution.diagnostics, **((result.preindex or {}) if result.preindex else {}), "warnings": diagnostic_warnings},
                        next_actions=["Retry get_library_docs with force_refresh=false if local docs are usable, or refresh/register the source again."],
                    )
                if stale_before:
                    stale_warning = _stale_docs_warning(info.last_refreshed_at, self.stale_after_days)
                    warnings = [*warnings, stale_warning]
                    diagnostic_warnings.append({"code": "stale_docs_used", "blocking": False})

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
        pages, chunks = self.registry_ops.count_index_entries(record)
        index_db_exists = Path(self._index_config_for(record).index.db_path).exists()
        if self._index_size_for(record) == 0 or (pages == 0 and chunks == 0 and index_db_exists):
            return self._empty_library_index_result(
                info=info,
                latest=latest,
                topic=topic,
                refreshed=refreshed,
                stale_before=stale_before,
                warning=warning,
                warnings=warnings,
                requested_version=requested_version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                input_args=input_args,
                docs_url_source=docs_url_source,
                diagnostics=resolution.diagnostics,
                diagnostic_warnings=diagnostic_warnings,
            )
        query = topic.strip() if topic else info.library
        retrieval_filters = {"library_id": record.library_id}
        resolved_version = record.resolved_version or record.version
        # The index deliberately normalizes the floating ``latest`` version to
        # an empty promoted field.  Its canonical library ID still contains the
        # version and source identity, so applying that unrepresentable filter
        # would hide the same isolated corpus immediately after refresh.
        if resolved_version and resolved_version.casefold() != "latest":
            retrieval_filters["resolved_version"] = resolved_version
        if record.docs_snapshot_exact is True:
            retrieval_filters["exact_snapshot_required"] = True
        requirements = build_requirements(
            query,
            exact_version=resolved_version,
            profile="library_docs_answer",
            library_requirement_contract=library_requirement_contract,
        )
        explicit_query_values, has_unqualified_explicit_query_list = (
            _explicit_library_query_analysis(query)
        )
        existing_requirement_values = {
            requirement.value.casefold() for requirement in requirements
        }
        missing_explicit_values = [
            value for value in explicit_query_values
            if value.casefold() not in existing_requirement_values
        ]
        if missing_explicit_values:
            requirements = build_requirements(
                query,
                public_requirements=missing_explicit_values,
                exact_version=resolved_version,
                profile="library_docs_answer",
                library_requirement_contract=library_requirement_contract,
            )
        dispatch_result = self.facade.agent_gateway.query_library(
            record,
            query,
            budget=tokens or DEFAULT_DOC_TOKENS,
            filters=retrieval_filters,
            requirements=requirements,
        )
        chunks = getattr(dispatch_result, "chunks", dispatch_result)
        if has_unqualified_explicit_query_list:
            chunks = []
            diagnostic_warnings.append({
                "code": "unqualified_explicit_query_list",
                "blocking": True,
            })
        retrieval_diagnostics = {
            "requested": {
                "mode": "lexical",
                "raw_topic_sha256": hashlib.sha256(query.encode()).hexdigest(),
                "filters": retrieval_filters,
                "record": {
                    "library_id": record.library_id,
                    "canonical_id": record.canonical_id,
                    "resolved_version": resolved_version,
                    "docs_snapshot_exact": record.docs_snapshot_exact,
                },
            },
            "used": {
                "mode": getattr(dispatch_result, "mode_used", "legacy_agent_query"),
                "candidate_counts": getattr(dispatch_result, "candidate_counts", {"legacy": len(chunks)}),
                "failures": getattr(dispatch_result, "failures", {}),
                "query_plan_hash": getattr(dispatch_result, "query_plan_hash", ""),
                "component_ranks": {},
            },
        }
        allowed_ids = {info.library_id}
        if info.version:
            allowed_ids.add(legacy_library_id(info.library, info.version))
        expected_roots = self._expected_docset_roots(info, record)
        chunks_before_guard = list(chunks)
        filtered_chunks = []
        rejection_counts: dict[str, int] = {}
        for chunk in chunks_before_guard:
            reason = self._library_chunk_rejection_reason(chunk, info, allowed_ids, expected_roots)
            if reason is None:
                filtered_chunks.append(chunk)
            else:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        chunks = filtered_chunks
        dropped = len(chunks_before_guard) - len(chunks)
        if dropped:
            diagnostic_warnings.append({"code": "cross_source_contamination_filtered", "blocking": False, "dropped": dropped})
            for code, count in sorted(rejection_counts.items()):
                diagnostic_warnings.append({"code": code, "blocking": False, "dropped": count})
        chunks_before_low_value_guard = list(chunks)
        chunks = [chunk for chunk in chunks_before_low_value_guard if not _drop_low_value_library_section(chunk.text, (chunk.metadata or {}).get("title"))]
        retrieval_diagnostics["used"]["component_ranks"] = {
            str((chunk.metadata or {}).get("section_id") or index):
            dict(((chunk.metadata or {}).get("retrieval_trace") or {}).get("component_ranks") or {})
            for index, chunk in enumerate(chunks, start=1)
        }
        retrieval_diagnostics["post_guard"] = {
            "before": len(chunks_before_guard),
            "accepted": len(filtered_chunks),
            "rejected": rejection_counts,
            "low_value_dropped": len(chunks_before_low_value_guard) - len(chunks),
        }
        if not chunks:
            reason_code = (
                "unqualified_explicit_query_list"
                if has_unqualified_explicit_query_list
                else "guard_dropped_all" if dropped > 0
                else "no_library_docs_results"
            )
            reason_diagnostics = {**resolution.diagnostics, "retrieval": retrieval_diagnostics, "reason_code": reason_code, "warnings": diagnostic_warnings}
            reason_diagnostics = self._with_dart_diagnostics(
                reason_diagnostics,
                info=latest,
                pages_discovered=pages,
                pages_extracted=pages,
                chunks_created=0,
            )
            status = "empty_library_index" if dropped > 0 else "no_results"
            record = self._record_from_info(latest)
            inspection_action = (
                self._inspection_recovery_action(latest)
                if dropped > 0
                or (record is not None and (record.last_error or "").startswith("partial ingestion:"))
                else None
            )
            next_actions = (
                ["Qualify at least one requested symbol with backticks or a dotted, underscored, or colon-qualified name."]
                if has_unqualified_explicit_query_list
                else [inspection_action] if inspection_action
                else ["Call refresh_library_docs to ingest this library's docs."] if dropped > 0
                else ["Narrow or rephrase the topic, or inspect_library_docs to verify indexed coverage before refreshing."]
            )
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
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=latest.resolved_version or latest.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status=status,
                decision="stop",
                reason_code=reason_code,
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("error", has_registered_source=True),
                diagnostics=reason_diagnostics,
                next_actions=next_actions,
            )
        chunks, quality_diagnostics = _postprocess_library_chunks(chunks, query)
        chunks, excerpt_diagnostics = _bounded_library_evidence_chunks(
            chunks,
            requirements=requirements,
            max_tokens=tokens or DEFAULT_DOC_TOKENS,
        )
        quality_diagnostics.update(excerpt_diagnostics)
        if not chunks:
            return self._empty_library_index_result(
                info=info,
                latest=latest,
                topic=topic,
                refreshed=refreshed,
                stale_before=stale_before,
                warning=warning,
                warnings=warnings,
                requested_version=requested_version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                input_args=input_args,
                docs_url_source=docs_url_source,
                diagnostics={
                    **resolution.diagnostics,
                    **quality_diagnostics,
                    "retrieval": retrieval_diagnostics,
                },
                diagnostic_warnings=[
                    *diagnostic_warnings,
                    {"code": "no_qualifying_bounded_passage", "blocking": True},
                ],
            )
        latest_stale = self._is_stale(latest.last_refreshed_at)
        freshness = _freshness_diagnostics(latest.last_refreshed_at, self.stale_after_days, latest_stale)
        
        # Build exact-version diagnostics if applicable
        final_diagnostics = {**resolution.diagnostics, **quality_diagnostics, "retrieval": retrieval_diagnostics, "freshness": freshness, "warnings": diagnostic_warnings}
        resolved_version = latest.resolved_version or latest.version
        exact_version_match = docs_snapshot_is_exact(requested_version, latest.docs_url_resolved or latest.docs_url) and resolved_version == requested_version if requested_version else None
        if exact_version_resolution and requested_version:
            final_diagnostics["exact_version"] = {
                "expected": requested_version,
                "used": resolved_version,
                "match": exact_version_match,
                "status": "exact_version_indexed" if exact_version_match else "exact_version_fallback_latest",
                "fallback": not exact_version_match,
                "reason_code": None if exact_version_match else "version_mismatch",
            }
        
        final_diagnostics = self._with_dart_diagnostics(
            final_diagnostics,
            info=latest,
            pages_discovered=pages,
            pages_extracted=pages,
            chunks_created=len(chunks),
        )
        
        result_chunks = [
            DocsChunk(
                title=(chunk.metadata or {}).get("title"),
                content=chunk.text,
                source=chunk.source,
                url=chunk.source if chunk.source.startswith(("http://", "https://")) else None,
                metadata={**(chunk.metadata or {}), "stale": latest_stale},
            )
            for chunk in chunks
        ]
        snippet_chunks = [
            {
                "title": chunk.title,
                "content": chunk.content,
                "source": chunk.source,
                "url": chunk.url,
                "metadata": {
                    **(chunk.metadata or {}),
                    "source_class": "library_doc",
                    "doc_scope": "library",
                    "origin_lane": "library",
                    "canonical_id": info.library_id,
                    "library_id": info.library_id,
                    "version": resolved_version,
                    "requested_version": requested_version,
                    "docs_exactness": docs_exactness,
                    "docs_binding_source": docs_binding_source,
                    "exact_version_match": exact_version_match,
                },
            }
            for chunk in result_chunks
        ]
        selection_candidates = []
        chunks_by_stable_id = {}
        for index, (chunk, item) in enumerate(zip(result_chunks, snippet_chunks, strict=True)):
            metadata = item["metadata"]
            stable_id = str(
                metadata.get("stable_chunk_id")
                or metadata.get("section_id")
                or metadata.get("chunk_id")
                or "library-" + hashlib.sha256(
                    f"{chunk.source}\0{chunk.title}\0{chunk.content}".encode("utf-8")
                ).hexdigest()[:16]
            )
            candidate = {
                **item,
                "stable_chunk_id": stable_id,
                "parent_logical_id": str(
                    metadata.get("parent_logical_id")
                    or metadata.get("source_id")
                    or chunk.source
                ),
                "display_content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                "authority": metadata.get("authority") or "official",
                "docs_exactness": metadata.get("docs_exactness") or docs_exactness,
                "resolved_version": metadata.get("version") or resolved_version,
                "version": metadata.get("version") or resolved_version,
                "docs_snapshot_exact": docs_snapshot_exact,
                "retrieval_rank": index + 1,
            }
            chunk.metadata["stable_chunk_id"] = stable_id
            selection_candidates.append(candidate)
            chunks_by_stable_id[stable_id] = chunk
        selection_decision = select_evidence(
            selection_candidates,
            question=query,
            config=library_docs_selection_config(tokens or DEFAULT_DOC_TOKENS),
            requirements=requirements,
        )
        support_decision = selection_decision.support_decision
        witness_diagnostics = self._bounded_library_index_witness(
            record=record,
            info=info,
            requirements=requirements,
            support_decision=support_decision,
            retrieval_filters=retrieval_filters,
            allowed_ids=allowed_ids,
            expected_roots=expected_roots,
            dispatcher_candidate_ids={item["stable_chunk_id"] for item in selection_candidates},
            resolved_version=resolved_version,
            requested_version=requested_version,
            docs_exactness=docs_exactness,
            docs_snapshot_exact=docs_snapshot_exact,
            exact_version_match=exact_version_match,
        )
        retrieval_diagnostics["index_witness"] = witness_diagnostics
        if witness_diagnostics.get("status") == "witness_found":
            support_decision = support_decision.with_insufficient_reason_code("retrieval_miss")
            selection_decision = replace(
                selection_decision,
                support_decision=support_decision,
            )
        selected_stable_ids = set(support_decision.selected_evidence_ids)
        selected_snippet_chunks = [
            item for item in selection_candidates
            if item["stable_chunk_id"] in selected_stable_ids
        ]
        snippet_presentation = build_snippet_presentation(
            selected_snippet_chunks,
            question=topic or library,
            response_style=response_style,
            lane_priority=["library"],
            support_decision=support_decision,
            requirements=requirements,
        )
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
            results=result_chunks,
            warnings=[*warnings, *[warning["code"] for warning in snippet_presentation.warnings]],
            requested_version=requested_version,
            resolved_version=resolved_version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
            docs_exactness=docs_exactness,
            docs_binding_source=docs_binding_source,
            confidence=confidence,
            status="success",
            request=self._docs_request(input_args, info),
            identity=self._docs_identity(info, docs_url_source=docs_url_source),
            policy=self._docs_policy("success", has_registered_source=True),
            diagnostics=final_diagnostics,
            response_style=snippet_presentation.response_style,
            primary_snippet=snippet_presentation.primary_snippet,
            supporting_snippets=snippet_presentation.supporting_snippets,
            primary_snippets=snippet_presentation.primary_snippets,
            primary_snippet_confidence=snippet_presentation.primary_snippet_confidence,
            primary_snippet_selection_reason=snippet_presentation.primary_snippet_selection_reason,
            primary_snippet_alternatives=snippet_presentation.primary_snippet_alternatives,
            snippet_metrics=snippet_presentation.metrics,
            requirements=requirements,
            selection_decision=selection_decision,
            support_decision=support_decision,
            context_available=bool(result_chunks),
            answer_supported=support_decision.answer_supported,
            answer_available=support_decision.answer_supported,
            support_status=support_decision.support_status,
            reason_code=support_decision.reason_code,
            decision=(
                "answer_returned"
                if support_decision.answer_supported
                else "insufficient_evidence"
            ),
            missing_requirement_ids=list(support_decision.missing_requirement_ids),
            satisfied_requirement_ids=list(support_decision.satisfied_requirement_ids),
            mandatory_requirement_ids=list(support_decision.mandatory_requirement_ids),
            mandatory_coverage=support_decision.mandatory_coverage,
            selected_evidence_ids=list(support_decision.selected_evidence_ids),
            decision_hash=support_decision.decision_hash,
        )

    def _bounded_library_index_witness(
        self,
        *,
        record: LibraryRecord,
        info: LibraryInfo,
        requirements: Any,
        support_decision: Any,
        retrieval_filters: dict[str, Any],
        allowed_ids: set[str],
        expected_roots: set[str],
        dispatcher_candidate_ids: set[str],
        resolved_version: str | None,
        requested_version: str | None,
        docs_exactness: str | None,
        docs_snapshot_exact: bool | None,
        exact_version_match: bool | None,
    ) -> dict[str, Any]:
        """Prove an omission only from a complete manifest-owned corpus.

        The probe is diagnostic-only and retains no text in public diagnostics.
        It never upgrades a support verdict; it only replaces the insufficiency
        reason after finding a missing requirement outside dispatcher results.
        """

        if support_decision.answer_supported or not support_decision.missing_requirement_ids:
            return {"status": "not_needed"}
        if not self._library_manifest_is_complete(record):
            return {"status": "not_attempted", "reason_code": "corpus_not_proven_complete"}
        probe = self.facade.agent_gateway.probe_library_requirements(
            record,
            requirements,
            missing_requirement_ids=support_decision.missing_requirement_ids,
            filters=retrieval_filters,
        )
        summary: dict[str, Any] = {
            "status": probe.status,
            "queried_requirement_ids": list(probe.queried_requirement_ids),
            "candidate_count": len(probe.chunks),
            "failure_count": probe.failure_count,
        }
        if probe.status != "ok":
            return summary
        candidates: list[dict[str, Any]] = []
        for index, chunk in enumerate(probe.chunks, start=1):
            if self._library_chunk_rejection_reason(chunk, info, allowed_ids, expected_roots):
                continue
            metadata = dict(getattr(chunk, "metadata", None) or {})
            if _drop_low_value_library_section(str(getattr(chunk, "text", "")), metadata.get("title")):
                continue
            content = str(getattr(chunk, "text", ""))
            source = str(getattr(chunk, "source", ""))
            stable_id = str(
                metadata.get("stable_chunk_id")
                or metadata.get("section_id")
                or metadata.get("chunk_id")
                or "library-witness-" + hashlib.sha256(
                    f"{source}\0{metadata.get('title')}\0{content}".encode("utf-8")
                ).hexdigest()[:16]
            )
            candidates.append({
                "title": metadata.get("title"),
                "content": content,
                "source": source,
                "url": source if source.startswith(("http://", "https://")) else None,
                "metadata": {
                    **metadata,
                    "source_class": "library_doc",
                    "doc_scope": "library",
                    "origin_lane": "library_index_witness",
                    "canonical_id": info.library_id,
                    "library_id": info.library_id,
                    "version": resolved_version,
                    "requested_version": requested_version,
                    "docs_exactness": docs_exactness,
                    "exact_version_match": exact_version_match,
                },
                "stable_chunk_id": stable_id,
                "parent_logical_id": str(metadata.get("parent_logical_id") or metadata.get("source_id") or source),
                "display_content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "authority": metadata.get("authority") or "official",
                "docs_exactness": metadata.get("docs_exactness") or docs_exactness,
                "resolved_version": metadata.get("version") or resolved_version,
                "version": metadata.get("version") or resolved_version,
                "docs_snapshot_exact": docs_snapshot_exact,
                "retrieval_rank": index,
            })
        if not candidates:
            summary["status"] = "no_witness"
            return summary
        witness_selection = select_evidence(
            candidates,
            question="",
            config=library_docs_selection_config(DEFAULT_DOC_TOKENS),
            requirements=requirements,
        )
        missing = set(support_decision.missing_requirement_ids)
        witnesses = [
            {
                "evidence_id": candidate.stable_id,
                "covered_requirement_ids": sorted(
                    set(candidate.covered_requirement_ids) & missing
                ),
            }
            for candidate in witness_selection.selected_candidates
            if candidate.stable_id not in dispatcher_candidate_ids
            and set(candidate.covered_requirement_ids) & missing
        ]
        summary["witnesses"] = witnesses
        summary["status"] = "witness_found" if witnesses else "no_witness"
        return summary

    def _library_manifest_is_complete(self, record: LibraryRecord) -> bool:
        manifest = ((record.target_spec or {}).get("source_manifest") or {})
        if manifest.get("schema_version") != 2 or manifest.get("complete") is not True:
            return False
        if manifest.get("truncated") is True:
            return False
        pages, _ = self.registry_ops.count_index_entries(record)
        expected, indexed, missing, stale_orphans, _ = self.registry_ops.manifest_coverage(
            record, pages,
        )
        return bool(expected) and indexed == expected and not missing and not stale_orphans

    def _index_size_for(self, record: LibraryRecord) -> int:
        return self.registry_ops.index_size_for(record)

    def _delete_index_for(self, record: LibraryRecord) -> int:
        return self.registry_ops.delete_index_for(record)

    def inspect_library_docs(self, canonical_id: str) -> DocsInspectResult:
        return self.registry_ops.inspect_library_docs(canonical_id)

    def remove_library_docs(self, canonical_id: str) -> DocsRemoveResult:
        return self.registry_ops.remove_library_docs(canonical_id)

    def _record_age_cutoff_value(self, record: LibraryRecord) -> str | None:
        return self.registry_ops.record_age_cutoff_value(record)

    def prune_library_docs(
        self,
        *,
        library: str | None = None,
        keep_versions: list[str] | None = None,
        older_than_days: int = 90,
        dry_run: bool = True,
    ) -> DocsPruneResult:
        if hasattr(self.facade, "_library_prune_library_docs_impl"):
            return self.facade._library_prune_library_docs_impl(
                library=library,
                keep_versions=keep_versions,
                older_than_days=older_than_days,
                dry_run=dry_run,
            )
        return self.registry_ops.prune_library_docs(library=library, keep_versions=keep_versions, older_than_days=older_than_days, dry_run=dry_run)

    def list_libraries(self, stale_only: bool = False, limit: int | None = None) -> list[LibraryInfo]:
        return self.registry_ops.list_libraries(stale_only=stale_only, limit=limit)


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def _drop_low_value_library_section(content: str, title: str | None = None) -> bool:
    if not is_trivial_section(content, title):
        return False
    text = (content or "").strip()
    return not text or text.lower() == (title or "").strip().lower()


_CODE_BLOCK_RE = re.compile(r"```([A-Za-z0-9_+.#-]*)\s*\n(.*?)```", re.DOTALL)
_ANCHOR_RE = re.compile(r"\s*\[¶\]")
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF]")
_TERM_RE = re.compile(r"[A-Za-z0-9_]+")
_EXPLICIT_QUERY_LIST_RE = re.compile(
    r"\b(?:"
    r"what\s+do|explain|(?:give\s+)?(?:the\s+)?(?:meaning|semantics)\s+of|"
    r"describe\s+(?:these\s+)?(?:[A-Za-z_][A-Za-z0-9_.]*\s+)?"
    r"(?:attributes?|properties?|symbols?|fields?)"
    r")\s*:?\s+([^?;.]{1,200}?)(?=\s+(?:mean|for|in|when|while|after|before|using|with)\b|[?;.]|$)",
    re.IGNORECASE | re.DOTALL,
)
_EXPLICIT_QUERY_LIST_SEPARATOR_RE = re.compile(
    r"\s*(?:,\s*(?:and\b|or\b)?|/|\bplus\b|\band\b|\bor\b)\s*",
    re.IGNORECASE,
)
_EXPLICIT_QUERY_SYMBOL_RE = re.compile(r"`?([A-Za-z_][A-Za-z0-9_.:]*)`?")
_RST_SYMBOL_DIRECTIVE_RE = re.compile(
    r"^\.\.\s+(module|function|method|attribute|class|exception)::\s+(.+?)\s*$",
    re.MULTILINE,
)
_NOISE_LINES = {
    "copy",
    "copy code",
    "download",
    "download file",
    "select language",
    "translation",
    "translations",
}


def _query_terms(query: str | None) -> set[str]:
    return {term.lower() for term in _TERM_RE.findall(query or "") if len(term) > 1}


def _explicit_library_query_analysis(query: str) -> tuple[list[str], bool]:
    values: set[str] = set()
    has_unqualified_list = False
    for match in _EXPLICIT_QUERY_LIST_RE.finditer(query):
        items = [
            item.strip()
            for item in _EXPLICIT_QUERY_LIST_SEPARATOR_RE.split(match.group(1).strip())
        ]
        if len(items) < 2:
            continue
        symbols = [_EXPLICIT_QUERY_SYMBOL_RE.fullmatch(item) for item in items]
        has_qualified_symbol = any(
            (item.startswith("`") and item.endswith("`"))
            or any(marker in symbol.group(1) for marker in (".", "_", ":"))
            for item, symbol in zip(items, symbols, strict=True)
            if symbol is not None
        )
        if all(symbols) and has_qualified_symbol:
            values.update(symbol.group(1) for symbol in symbols if symbol is not None)
        else:
            has_unqualified_list = True
    return sorted(values, key=str.casefold), has_unqualified_list


def _explicit_library_query_values(query: str) -> list[str]:
    return _explicit_library_query_analysis(query)[0]


def _clean_library_section(content: str) -> str:
    text = _ANCHOR_RE.sub("", content or "")
    text = _EMOJI_RE.sub("", text)
    cleaned_lines = []
    for line in text.splitlines():
        normalized = line.strip().lower().strip(":")
        if normalized in _NOISE_LINES:
            continue
        if normalized.startswith(("translated by ", "translation missing")):
            continue
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _code_snippets(content: str) -> list[dict[str, str]]:
    snippets = []
    for match in _CODE_BLOCK_RE.finditer(content or ""):
        snippets.append({"language": match.group(1).strip(), "code": match.group(2).strip()})
    return snippets


def _code_relevance(snippets: list[dict[str, str]], terms: set[str]) -> int:
    if not snippets or not terms:
        return 0
    score = 0
    for snippet in snippets:
        snippet_terms = _query_terms(snippet["code"])
        score += len(terms & snippet_terms)
    return score


def _text_similarity(left: str, right: str) -> float:
    left_terms = _query_terms(left)
    right_terms = _query_terms(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def _chunk_relevance(content: str, snippets: list[dict[str, str]], terms: set[str]) -> float:
    if not terms:
        return 0.0
    text_terms = _query_terms(content)
    lexical = len(terms & text_terms) / len(terms)
    code = min(1.0, _code_relevance(snippets, terms) / len(terms))
    return lexical + code


def _copy_chunk(chunk: Any, *, text: str, metadata: dict[str, Any]) -> Any:
    if hasattr(chunk, "model_copy"):
        return chunk.model_copy(update={"text": text, "metadata": metadata})
    if hasattr(chunk, "copy"):
        return chunk.copy(update={"text": text, "metadata": metadata})
    chunk.text = text
    chunk.metadata = metadata
    return chunk


def _rst_symbol_sections(content: str) -> list[dict[str, Any]]:
    matches = list(_RST_SYMBOL_DIRECTIVE_RE.finditer(content))
    modules = [match.group(2).strip() for match in matches if match.group(1) == "module"]
    module = modules[0] if len(set(modules)) == 1 else ""
    sections = []
    for index, match in enumerate(matches):
        if match.group(1) == "module":
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        raw_symbol = match.group(2).strip().split("(", 1)[0]
        qualified_symbol = (
            raw_symbol
            if not module or raw_symbol.startswith(module + ".")
            else f"{module}.{raw_symbol}"
        )
        sections.append({
            "start": match.start(),
            "text": content[match.start():end].strip(),
            "symbols": (raw_symbol, qualified_symbol),
        })
    return sections


def _bounded_library_evidence_chunks(
    chunks: list[Any],
    *,
    requirements: Any,
    max_tokens: int,
) -> tuple[list[Any], dict[str, Any]]:
    config = library_docs_selection_config(max_tokens)
    available_tokens = max(1, config.hard_tokens - config.wrapper_reserve_tokens)
    available_bytes = available_tokens * 4
    bounded = []
    derived = 0
    rejected = 0
    mandatory = [
        requirement
        for requirement in requirements
        if requirement.mandatory and requirement.kind != "exact_version"
    ]
    for chunk in chunks:
        if len(chunk.text.encode("utf-8")) <= available_bytes:
            bounded.append(chunk)
            continue
        ranked = []
        for section in _rst_symbol_sections(chunk.text):
            haystack = "\n".join([section["text"], *section["symbols"]])
            covered = {
                requirement.requirement_id
                for requirement in mandatory
                if requirement_value_visible(requirement.value, haystack)
            }
            if covered:
                ranked.append((section, covered))
        selected = []
        remaining = {requirement.requirement_id for requirement in mandatory}
        spent = 0
        while remaining:
            options = [
                (section, covered)
                for section, covered in ranked
                if section not in selected and covered & remaining
            ]
            if not options:
                break
            section, covered = min(options, key=lambda item: (
                -len(item[1] & remaining),
                len(item[0]["text"].encode("utf-8")),
                item[0]["start"],
            ))
            section_bytes = len(section["text"].encode("utf-8"))
            if spent + section_bytes > available_bytes:
                break
            selected.append(section)
            spent += section_bytes
            remaining -= covered
        if remaining:
            rejected += 1
            continue
        selected.sort(key=lambda section: section["start"])
        excerpt = "\n\n".join(section["text"] for section in selected)
        metadata = dict(chunk.metadata or {})
        parent_id = str(
            metadata.get("stable_chunk_id")
            or metadata.get("section_id")
            or metadata.get("chunk_id")
            or chunk.source
        )
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        metadata.update({
            "stable_chunk_id": f"{parent_id}:excerpt:{digest[:16]}",
            "parent_logical_id": parent_id,
            "symbols": sorted({symbol for section in selected for symbol in section["symbols"]}),
            "source_excerpt": True,
            "source_excerpt_sha256": digest,
        })
        bounded.append(_copy_chunk(chunk, text=excerpt, metadata=metadata))
        derived += 1
    return bounded, {
        "bounded_evidence": {
            "available_tokens": available_tokens,
            "derived_excerpts": derived,
            "rejected_oversized_sources": rejected,
        }
    }


def _postprocess_library_chunks(chunks: list[Any], query: str) -> tuple[list[Any], dict[str, Any]]:
    terms = _query_terms(query)
    candidates: list[dict[str, Any]] = []
    snippet_count = 0
    for index, chunk in enumerate(chunks):
        cleaned = _clean_library_section(chunk.text)
        snippets = _code_snippets(cleaned)
        snippet_count += len(snippets)
        metadata = dict(chunk.metadata or {})
        metadata["code_snippets"] = snippets
        metadata["code_snippet_count"] = len(snippets)
        if snippets:
            metadata["top_code_language"] = snippets[0]["language"] or None
        candidates.append(
            {
                "index": index,
                "relevance": _chunk_relevance(cleaned, snippets, terms),
                "chunk": _copy_chunk(chunk, text=cleaned, metadata=metadata),
            }
        )

    selected = []
    source_counts: dict[str, int] = {}
    dropped_for_diversity = 0
    while candidates:
        scored = []
        for candidate in candidates:
            diversity = max(_text_similarity(candidate["chunk"].text, chunk.text) for chunk in selected) if selected else 0.0
            mmr_score = MMR_LAMBDA * candidate["relevance"] - (1 - MMR_LAMBDA) * diversity
            scored.append((mmr_score, candidate["relevance"], -candidate["index"], candidate))
        _mmr_score, _relevance, _negative_index, best = max(scored, key=lambda item: item[:3])
        candidates.remove(best)
        chunk = best["chunk"]
        source = chunk.source or ""
        count = source_counts.get(source, 0)
        if count >= MAX_CHUNKS_PER_SOURCE:
            dropped_for_diversity += 1
            continue
        source_counts[source] = count + 1
        selected.append(chunk)

    top_relevance = max((candidate["relevance"] for candidate in candidates), default=None)
    if top_relevance is None:
        top_relevance = max((_chunk_relevance(chunk.text, _code_snippets(chunk.text), terms) for chunk in selected), default=0.0)
    return selected, {
        "code_snippets": snippet_count,
        "top_relevance": top_relevance,
        "mmr_lambda": MMR_LAMBDA,
        "max_chunks_per_source": MAX_CHUNKS_PER_SOURCE,
        "chunks_dropped_for_diversity": dropped_for_diversity,
        "unique_sources@5": len({chunk.source for chunk in selected[:5]}),
    }

def _age_days(last_refreshed_at: str | None) -> int | None:
    if not last_refreshed_at:
        return None
    try:
        refreshed = datetime.fromisoformat(last_refreshed_at)
    except ValueError:
        return None
    if refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - refreshed).days)


def _freshness_diagnostics(last_refreshed_at: str | None, stale_after_days: int, stale: bool) -> dict[str, Any]:
    return {
        "last_refreshed_at": last_refreshed_at,
        "stale": stale,
        "stale_after_days": stale_after_days,
        "age_days": _age_days(last_refreshed_at),
    }


def _stale_docs_warning(last_refreshed_at: str | None, stale_after_days: int) -> str:
    age = _age_days(last_refreshed_at)
    if age is None:
        return f"Documentation freshness is unknown (stale after {stale_after_days} days). Call refresh_library_docs to update."
    return f"Documentation is {age} days old (stale after {stale_after_days} days). Call refresh_library_docs to update."
