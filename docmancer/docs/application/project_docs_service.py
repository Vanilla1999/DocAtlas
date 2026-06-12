from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json
import shutil
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.application.project_docs_state import ProjectDocsState

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)

class ProjectDocsService:
    def __init__(self, facade: Any):
        self.facade = facade
        self.project_state = ProjectDocsState(facade)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.facade, name)

    def _indexed_project_doc_sources(self, project_path: str) -> list[dict[str, Any]]:
        return self.project_state.indexed_project_doc_sources(project_path)

    @staticmethod

    def _source_state_guidance() -> dict[str, Any]:
        return ProjectDocsState.source_state_guidance()

    @staticmethod

    def _partition_project_doc_state(
        candidates: list[dict[str, Any]],
        indexed_sources: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        return ProjectDocsState.partition_project_doc_state(candidates, indexed_sources)

    @staticmethod

    def _has_high_level_project_overview(candidates: list[dict[str, Any]]) -> bool:
        return ProjectDocsState.has_high_level_project_overview(candidates)

    def _project_dependency_docs_state(self, metadata: ProjectMetadata) -> dict[str, Any]:
        return self.project_state.project_dependency_docs_state(metadata)

    @staticmethod

    def _create_project_docs_next_action(root: Path, query: str | None = None, *, reason: str | None = None) -> dict[str, Any]:
        return create_project_docs_next_action(root, query, reason=reason)

    @staticmethod

    def _project_docs_structured_next_action(
        *,
        reason_code: str,
        root: Path,
        query: str | None = None,
    ) -> tuple[dict[str, Any], bool, str | None, dict[str, Any], str, str | None]:
        return project_docs_structured_next_action(reason_code=reason_code, root=root, query=query)

    def inspect_project_docs(self, project_path: str) -> ProjectDocsInspectResult:
        if hasattr(self.facade, "_project_inspect_project_docs_impl"):
            return self.facade._project_inspect_project_docs_impl(project_path)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
        has_high_level_overview = self._has_high_level_project_overview(candidate_sources)
        manifests_found = [name for name in ("pubspec.yaml", "Cargo.toml") if (root / name).exists()]
        lockfiles_found = [name for name in ("pubspec.lock", "Cargo.lock") if (root / name).exists()]
        dependency_docs_state = self._project_dependency_docs_state(metadata)
        exact_versions_available = dependency_docs_state["dependency_docs_available"]
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
        elif not has_high_level_overview:
            recommended_next_actions.append(self._create_project_docs_next_action(
                root,
                reason="Project docs exist, but no high-level architecture or overview document was discovered. Ask the user before creating a reviewable ARCHITECTURE.md file.",
            ))
        if stale_sources:
            reason_code = "project_docs_stale"
        elif not candidate_sources:
            reason_code = "no_project_docs"
        elif not has_high_level_overview:
            reason_code = "architecture_doc_creation_recommended"
        elif len(indexed_sources) < len(candidate_sources):
            reason_code = "project_docs_found_not_indexed"
        else:
            reason_code = "project_docs_ready"
        next_action, requires_confirmation, confirmation_reason, arguments_patch, agent_message, user_message = self._project_docs_structured_next_action(
            reason_code=reason_code,
            root=root,
        )
        project_docs = {
            "found": candidate_sources,
            "indexed": indexed_sources,
            "stale": stale_sources,
            "ignored": ignored_sources,
            "high_level_overview_found": has_high_level_overview,
        }
        dependency_sources = {
            "manifests_found": manifests_found,
            "lockfiles_found": lockfiles_found,
            "exact_versions_available": exact_versions_available,
            "network_fetch_required": exact_versions_available,
            **dependency_docs_state,
        }
        return ProjectDocsInspectResult(
            project_detected=root.exists() and root.is_dir(),
            project_path=str(root),
            reason_code=reason_code,
            next_action=next_action,
            requires_confirmation=requires_confirmation,
            confirmation_reason=confirmation_reason,
            project_type=metadata.detected_ecosystems,
            project_docs=project_docs,
            dependency_sources=dependency_sources,
            candidate_sources=candidate_sources,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            ignored_sources=ignored_sources,
            recommended_next_actions=recommended_next_actions,
            arguments_patch=arguments_patch,
            agent_message=agent_message,
            user_message=user_message,
            agent_guidance="Call get_project_docs for repo-specific questions after project docs are indexed. If docs are missing, ask before creating a reviewable ARCHITECTURE.md, then inspect and ingest it. If docs are stale, call ingest_project_docs first. Ask before network dependency docs fetches.",
            source_state_guidance=self._source_state_guidance(),
            warnings=metadata.warnings,
        )

    def ingest_project_docs(
        self,
        project_path: str,
        *,
        skip_known: bool = True,
        with_vectors: bool = True,
    ) -> ProjectDocsIngestResult:
        if hasattr(self.facade, "_project_ingest_project_docs_impl"):
            return self.facade._project_ingest_project_docs_impl(project_path, skip_known=skip_known, with_vectors=with_vectors)
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

    def bootstrap_project_docs(self, project_path: str, question: str | None = None) -> ProjectDocsBootstrapResult:
        root = Path(project_path).expanduser().resolve()
        actions_taken: list[dict[str, Any]] = []
        initial = self.inspect_project_docs(str(root))
        actions_taken.append({"tool": "inspect_project_docs", "arguments_patch": {"project_path": str(root)}})
        inspect_result = initial
        ingest_result: ProjectDocsIngestResult | None = None
        warnings = list(initial.warnings)

        if initial.reason_code in {"project_docs_found_not_indexed", "project_docs_stale"}:
            ingest_result = self.ingest_project_docs(str(root), skip_known=False, with_vectors=True)
            actions_taken.append({
                "tool": "ingest_project_docs",
                "arguments_patch": {"project_path": str(root), "skip_known": False, "with_vectors": True},
                "status": ingest_result.status,
            })
            warnings.extend(ingest_result.warnings)
            inspect_result = self.inspect_project_docs(str(root))
            actions_taken.append({"tool": "inspect_project_docs", "arguments_patch": {"project_path": str(root)}, "reason": "post_ingest_verification"})

        dependency_action = inspect_result.dependency_sources.get("dependency_next_action") if inspect_result.dependency_sources else None
        metadata = self.read_project_metadata(str(root))
        dependency_requested = bool(question and self._dependency_mentioned_in_question(metadata, question))
        if dependency_requested and dependency_action:
            return ProjectDocsBootstrapResult(
                project_path=str(root),
                question=question,
                status="confirmation_required",
                reason_code="dependency_docs_prefetch_confirmation_required",
                actions_taken=actions_taken,
                next_action=dependency_action,
                requires_confirmation=True,
                confirmation_reason="network_fetch",
                arguments_patch=dependency_action.get("arguments_patch") or {"project_path": str(root)},
                inspect_result=inspect_result,
                ingest_result=ingest_result,
                agent_message="Project docs are ready, but this question mentions a dependency whose exact docs are not prefetched. Ask before fetching dependency docs from the network.",
                user_message=dependency_action.get("user_message"),
                warnings=warnings,
            )

        if inspect_result.requires_confirmation:
            return ProjectDocsBootstrapResult(
                project_path=str(root),
                question=question,
                status="confirmation_required",
                reason_code=inspect_result.reason_code,
                actions_taken=actions_taken,
                next_action=inspect_result.next_action,
                requires_confirmation=True,
                confirmation_reason=inspect_result.confirmation_reason,
                arguments_patch=inspect_result.arguments_patch,
                inspect_result=inspect_result,
                ingest_result=ingest_result,
                agent_message=inspect_result.agent_message,
                user_message=inspect_result.user_message,
                warnings=warnings,
            )

        if inspect_result.reason_code == "project_docs_ready":
            next_action, _, _, arguments_patch, agent_message, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_ready",
                root=root,
                query=question,
            )
            return ProjectDocsBootstrapResult(
                project_path=str(root),
                question=question,
                status="ready",
                reason_code="project_docs_ready",
                actions_taken=actions_taken,
                next_action=next_action,
                requires_confirmation=False,
                arguments_patch=arguments_patch,
                inspect_result=inspect_result,
                ingest_result=ingest_result,
                agent_message=agent_message,
                warnings=warnings,
            )

        return ProjectDocsBootstrapResult(
            project_path=str(root),
            question=question,
            status="blocked",
            reason_code=inspect_result.reason_code,
            actions_taken=actions_taken,
            next_action=inspect_result.next_action,
            requires_confirmation=inspect_result.requires_confirmation,
            confirmation_reason=inspect_result.confirmation_reason,
            arguments_patch=inspect_result.arguments_patch,
            inspect_result=inspect_result,
            ingest_result=ingest_result,
            agent_message=inspect_result.agent_message or "Project docs are not ready after safe bootstrap actions.",
            user_message=inspect_result.user_message,
            warnings=warnings,
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
        if hasattr(self.facade, "_project_get_project_docs_impl"):
            return self.facade._project_get_project_docs_impl(project_path, query, tokens=tokens, limit=limit, expand=expand)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)

        if not candidate_sources:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, user_message = self._project_docs_structured_next_action(
                reason_code="no_project_docs",
                root=root,
                query=query,
            )
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="no_project_docs",
                reason_code="no_project_docs",
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason="no_project_docs",
                answer_available=False,
                warnings=metadata.warnings,
                next_actions=[{
                    **self._create_project_docs_next_action(root, query),
                    "reason": "No project-owned docs candidates were discovered for this repository. Create a reviewable architecture doc before indexing.",
                }],
                message=user_message or "No project-owned docs were found. Ask before creating a reviewable ARCHITECTURE.md, then run inspect_project_docs and ingest_project_docs.",
            )

        if not indexed_sources_all:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_found_not_indexed",
                root=root,
                query=query,
            )
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="not_indexed",
                reason_code="project_docs_found_not_indexed",
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
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
        next_action: dict[str, Any] = {}
        requires_confirmation = False
        confirmation_reason = None
        arguments_patch: dict[str, Any] = {}
        if stale_sources:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_stale",
                root=root,
                query=query,
            )
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
                reason_code="project_docs_stale" if stale_sources else "project_docs_ready",
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason="project_docs_stale" if stale_sources else None,
                answer_available=True,
                results=results,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=result_indexed_sources or indexed_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                source_state_guidance=self._source_state_guidance(),
                next_actions=next_actions,
                message=f"Returned {len(results)} project docs result(s)." + (" Some indexed project docs are stale." if stale_sources else ""),
            )
        reason_code = "project_docs_stale" if stale_sources else "no_project_docs_results"
        if stale_sources:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_stale",
                root=root,
                query=query,
            )
        else:
            next_action = {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
            requires_confirmation = False
            confirmation_reason = None
            arguments_patch = {"project_path": str(root)}
        return ProjectDocsResult(
            project_path=str(root),
            query=query,
            status="stale" if stale_sources else "no_results",
            reason_code=reason_code,
            next_action=next_action,
            requires_confirmation=requires_confirmation,
            confirmation_reason=confirmation_reason,
            arguments_patch=arguments_patch,
            reason="project_docs_stale" if stale_sources else "no_project_docs_results",
            answer_available=False,
            warnings=metadata.warnings,
            candidate_sources=candidate_sources,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            ignored_sources=ignored_sources,
            source_state_guidance=self._source_state_guidance(),
            next_actions=[{
                "tool": "ingest_project_docs" if stale_sources else "inspect_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root)},
                "reason": "Project docs are stale; re-index and retry." if stale_sources else "Project docs are indexed, but no indexed project docs matched this query. Inspect candidates or refine the query.",
            }],
            message="Indexed project docs exist, but no results matched this query." + (" Some indexed docs are stale." if stale_sources else ""),
        )
