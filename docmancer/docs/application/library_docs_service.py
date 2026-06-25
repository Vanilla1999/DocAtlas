from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.discovery_candidates import discovery_candidates_for
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.quality import is_trivial_section
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, legacy_library_id, normalize_version
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
    def __init__(self, facade: Any):
        self.facade = facade
        self.registry_ops = LibraryRegistryOps(facade)
        self.refresh_ops = LibraryRefreshOps(self)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.facade, name)

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
        docset_root = metadata.get("docset_root")
        if docset_root and expected_roots and not self._url_within_root(str(docset_root), expected_roots):
            return "wrong_docset_root"
        source = getattr(chunk, "source", None)
        url = metadata.get("url") or metadata.get("source_url")
        if not self._url_within_root(source, expected_roots):
            return "wrong_docset_root"
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
            next_actions=["Call refresh_library_docs to ingest this library's docs."],
        )

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
    ) -> RefreshResult:
        return self.refresh_ops.prefetch_docs(
            library,
            ecosystem=ecosystem,
            versions=versions,
            docs_url=docs_url,
            docs_url_template=docs_url_template,
            source_type=source_type,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
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
        if hasattr(self.facade, "_library_get_docs_impl"):
            return self.facade._library_get_docs_impl(
                library,
                topic=topic,
                tokens=tokens,
                ecosystem=ecosystem,
                version=version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                source_type=source_type,
                force_refresh=force_refresh,
                project_path=project_path,
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
            
            warning = self._join_warnings("needs_docs_url", extra=project_warnings)
            warnings = [warning] if warning else []
            candidates = info.candidates
            next_actions = ["Retry get_library_docs with docs_url from discovery_candidates[0]."] if candidates else ["Retry get_library_docs with docs_url, or call prefetch_library_docs/prefetch_docs_targets to register this source."]
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
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "needs_docs_url", "blocking": True}], "discovery_candidates": candidates},
                next_actions=next_actions,
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
        query = f"{info.library} {topic}".strip() if topic else info.library
        chunks = self._agent_instance(record).query(query, budget=tokens or DEFAULT_DOC_TOKENS)
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
        chunks = [chunk for chunk in chunks if not _drop_low_value_library_section(chunk.text, (chunk.metadata or {}).get("title"))]
        if not chunks:
            reason_code = "guard_dropped_all" if dropped > 0 else "missing_chunks"
            reason_diagnostics = {**resolution.diagnostics, "reason_code": reason_code, "warnings": diagnostic_warnings}
            reason_diagnostics = self._with_dart_diagnostics(
                reason_diagnostics,
                info=latest,
                pages_discovered=pages,
                pages_extracted=pages,
                chunks_created=0,
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
                status="empty_library_index",
                decision="stop",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("error", has_registered_source=True),
                diagnostics=reason_diagnostics,
                next_actions=["Call refresh_library_docs to ingest this library's docs."],
            )
        chunks, quality_diagnostics = _postprocess_library_chunks(chunks, query)
        latest_stale = self._is_stale(latest.last_refreshed_at)
        freshness = _freshness_diagnostics(latest.last_refreshed_at, self.stale_after_days, latest_stale)
        
        # Build exact-version diagnostics if applicable
        final_diagnostics = {**resolution.diagnostics, **quality_diagnostics, "freshness": freshness, "warnings": diagnostic_warnings}
        if exact_version_resolution and requested_version:
            exact_version_match = (latest.resolved_version or latest.version) == requested_version
            final_diagnostics["exact_version"] = {
                "expected": requested_version,
                "used": latest.resolved_version or latest.version,
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
                    metadata={**(chunk.metadata or {}), "stale": latest_stale},
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
            diagnostics=final_diagnostics,
        )

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


def _postprocess_library_chunks(chunks: list[Any], query: str) -> tuple[list[Any], dict[str, Any]]:
    terms = _query_terms(query)
    candidates: list[dict[str, Any]] = []
    snippet_count = 0
    for index, chunk in enumerate(chunks):
        cleaned = _clean_library_section(chunk.text)
        snippets = _code_snippets(cleaned)
        snippet_count += len(snippets)
        metadata = dict(chunk.metadata or {})
        metadata["code_snippets"] = len(snippets)
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

    return selected, {
        "code_snippets": snippet_count,
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
