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
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectDocsSyncResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
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
    def _module_summaries(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        modules: dict[str, dict[str, Any]] = {}
        for source in sources:
            if source.get("doc_scope") != "module" or not source.get("module_path"):
                continue
            module_path = str(source["module_path"])
            summary = modules.setdefault(
                module_path,
                {
                    "module_id": source.get("module_id") or module_path,
                    "module_name": source.get("module_name") or Path(module_path).name,
                    "module_path": module_path,
                    "module_type": source.get("module_type") or "module",
                    "doc_count": 0,
                    "docs": [],
                },
            )
            summary["doc_count"] += 1
            summary["docs"].append(source.get("path"))
        return sorted(modules.values(), key=lambda item: item["module_path"])

    @staticmethod
    def _resolve_module_filter(
        module_summaries: list[dict[str, Any]],
        *,
        module: str | None = None,
        module_path: str | None = None,
    ) -> tuple[str | None, dict[str, Any] | None]:
        requested = module_path or module
        if not requested:
            return None, None
        matches = [
            item for item in module_summaries
            if item.get("module_path") == requested
            or item.get("module_id") == requested
            or (module_path is None and item.get("module_name") == requested)
        ]
        if not matches:
            return None, {
                "reason_code": "module_not_found",
                "message": f"Module {requested!r} was not found in discovered project docs.",
                "available_modules": module_summaries,
            }
        paths = {str(item.get("module_path")) for item in matches if item.get("module_path")}
        if len(paths) > 1:
            return None, {
                "reason_code": "module_ambiguous",
                "message": f"Module name {requested!r} matches multiple module paths. Retry with module_path.",
                "matches": matches,
                "available_modules": module_summaries,
            }
        return next(iter(paths)), None

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
        candidate_paths = {item.get("path") for item in candidate_sources if item.get("path")}
        indexed_paths = {item.get("path") for item in [*indexed_sources, *stale_sources] if item.get("path")}
        missing_candidate_count = len(candidate_paths - indexed_paths)
        has_high_level_overview = self._has_high_level_project_overview(candidate_sources)
        manifests_found = [name for name in ("pubspec.yaml", "Cargo.toml") if (root / name).exists()]
        lockfiles_found = [name for name in ("pubspec.lock", "Cargo.lock") if (root / name).exists()]
        dependency_docs_state = self._project_dependency_docs_state(metadata)
        exact_versions_available = dependency_docs_state["dependency_docs_available"]
        recommended_next_actions: list[dict[str, Any]] = []
        if stale_sources or ignored_sources:
            recommended_next_actions.append({
                "tool": "sync_project_docs",
                "requires_confirmation": False,
                "reason": "Project docs index has stale or orphaned entries; reconcile it with the current repository docs snapshot.",
                "arguments_patch": {"project_path": str(root), "with_vectors": True},
            })
        elif candidate_sources and missing_candidate_count:
            recommended_next_actions.append({
                "tool": "sync_project_docs",
                "requires_confirmation": False,
                "reason": "Project docs found but not indexed; reconcile the index with current docs.",
                "arguments_patch": {"project_path": str(root), "with_vectors": True},
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
        if stale_sources or ignored_sources:
            reason_code = "project_docs_stale"
        elif not candidate_sources:
            reason_code = "no_project_docs"
        elif not has_high_level_overview:
            reason_code = "architecture_doc_creation_recommended"
        elif missing_candidate_count:
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
            "modules": self._module_summaries(candidate_sources),
            "indexed_modules": self._module_summaries(indexed_sources),
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
            agent_guidance="Call get_project_docs for repo-specific questions after project docs are synced. If docs are missing, ask before creating a reviewable ARCHITECTURE.md, then inspect and sync it. If docs are stale or orphaned, call sync_project_docs first. Ask before network dependency docs fetches.",
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
        extensionless_text_names = tuple(
            Path(item.path).name
            for item in candidates
            if not Path(item.path).suffix
        )

        def _verified_state() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
            candidate_sources = [asdict(item) for item in candidates]
            indexed_sources_all = self._indexed_project_doc_sources(str(root))
            current, stale, ignored = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
            verified_by_path = {
                item.get("path"): item
                for item in [*current, *stale]
                if item.get("path")
            }
            missing = [item for item in candidate_sources if item.get("path") not in verified_by_path]
            return current, stale, ignored, missing

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
                    "doc_scope": candidate.doc_scope,
                    "module_id": candidate.module_id,
                    "module_name": candidate.module_name,
                    "module_path": candidate.module_path,
                    "module_type": candidate.module_type,
                })
            return result

        agent = self._agent_instance()
        try:
            sections_indexed = agent.ingest(
                root,
                include_exact=include,
                extensionless_text_names=extensionless_text_names,
                recursive=True,
                skip_known=skip_known,
                with_vectors=with_vectors,
                metadata={"project_path": str(root), "source_class": "project_file", "project_docs": True},
                metadata_for_file=_metadata_for_file,
            )
        except ValueError as exc:
            indexed_sources, stale_sources, _ignored_sources, missing_sources = _verified_state()
            if indexed_sources and not missing_sources and not stale_sources:
                return ProjectDocsIngestResult(
                    status="success",
                    project=metadata,
                    candidate_count=len(candidates),
                    indexed_sources=indexed_sources,
                    missing_sources=[],
                    skipped_sources=getattr(agent, "last_ingest_skips", []),
                    sections_indexed=0,
                    warnings=warnings,
                    message=f"Verified {len(indexed_sources)} indexed project docs candidate(s); no re-indexing was needed.",
                )
            return ProjectDocsIngestResult(
                status="failed",
                project=metadata,
                candidate_count=len(candidates),
                indexed_sources=indexed_sources,
                missing_sources=missing_sources,
                skipped_sources=getattr(agent, "last_ingest_skips", []),
                sections_indexed=0,
                warnings=[*warnings, str(exc)],
                message=str(exc),
            )

        indexed_sources, stale_sources, _ignored_sources, missing_sources = _verified_state()
        status = "success"
        if missing_sources or stale_sources:
            status = "partial"
        message = f"Indexed {len(indexed_sources)} project docs candidate(s). Verified {len(indexed_sources)} indexed project docs candidate(s)."
        if missing_sources:
            message += f" Missing {len(missing_sources)} project docs candidate(s) from the index."
        if stale_sources:
            message += f" {len(stale_sources)} project docs candidate(s) remain stale after ingest."
        return ProjectDocsIngestResult(
            status=status,
            project=metadata,
            candidate_count=len(candidates),
            indexed_sources=indexed_sources,
            missing_sources=missing_sources,
            skipped_sources=getattr(agent, "last_ingest_skips", []),
            sections_indexed=sections_indexed,
            warnings=warnings,
            message=message,
        )

    def sync_project_docs(
        self,
        project_path: str,
        *,
        with_vectors: bool = True,
    ) -> ProjectDocsSyncResult:
        if hasattr(self.facade, "_project_sync_project_docs_impl"):
            return self.facade._project_sync_project_docs_impl(project_path, with_vectors=with_vectors)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        warnings = list(metadata.warnings)
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        before_indexed_all = self._indexed_project_doc_sources(str(root))
        agent = self._agent_instance()
        dedup_removed = 0
        path_groups: dict[str, list[dict[str, Any]]] = {}
        for s in before_indexed_all:
            p = s.get("path")
            if p:
                path_groups.setdefault(p, []).append(s)
        for p, items in path_groups.items():
            if len(items) > 1:
                items.sort(key=lambda x: x.get("ingested_at") or "", reverse=True)
                for dup in items[1:]:
                    src = dup.get("source")
                    if src and agent.store.delete_source(str(src)):
                        dedup_removed += 1
        if dedup_removed:
            before_indexed_all = self._indexed_project_doc_sources(str(root))
        before_current, before_stale, before_ignored = self._partition_project_doc_state(candidate_sources, before_indexed_all)
        candidate_paths = {item.get("path") for item in candidate_sources if item.get("path")}
        current_paths = {item.get("path") for item in before_current if item.get("path")}
        stale_paths = {item.get("path") for item in before_stale if item.get("path")}
        new_count = len(candidate_paths - current_paths - stale_paths)
        changed_count = len(stale_paths)
        removed_sources: list[dict[str, Any]] = []
        for source in [*before_stale, *before_ignored]:
            source_name = source.get("source")
            if not source_name:
                continue
            if agent.store.delete_source(str(source_name)):
                removed_sources.append(source)

        if not candidate_sources:
            after_indexed_all = self._indexed_project_doc_sources(str(root))
            _indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, after_indexed_all)
            orphaned_removed = len(removed_sources)
            status = "success" if orphaned_removed else "no_project_docs"
            message = (
                f"Synced project docs: current=0, new=0, changed=0, "
                f"orphaned_removed={orphaned_removed}, missing=0."
            )
            if not orphaned_removed:
                message += " No project-owned docs candidates were discovered."
            return ProjectDocsSyncResult(
                status=status,
                project=metadata,
                candidate_count=0,
                current_count=0,
                new_count=0,
                changed_count=0,
                orphaned_count=len(before_ignored),
                orphaned_removed=orphaned_removed,
                dedup_removed=dedup_removed,
                stale_removed=0,
                sections_indexed=0,
                indexed_sources=[],
                stale_sources=stale_sources,
                missing_sources=[],
                removed_sources=removed_sources,
                skipped_sources=[],
                warnings=warnings,
                message=message,
            )

        ingest_result = self.ingest_project_docs(str(root), skip_known=True, with_vectors=with_vectors)
        after_indexed_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, _ignored_sources = self._partition_project_doc_state(candidate_sources, after_indexed_all)
        indexed_paths = {item.get("path") for item in [*indexed_sources, *stale_sources] if item.get("path")}
        missing_sources = [item for item in candidate_sources if item.get("path") not in indexed_paths]
        status = "success"
        if missing_sources or stale_sources:
            status = "partial"
        if ingest_result.status in {"failed", "no_project_docs"} and not indexed_sources:
            status = ingest_result.status
        stale_removed = sum(1 for item in removed_sources if item.get("path") in stale_paths)
        orphaned_removed = len(removed_sources) - stale_removed
        message = (
            f"Synced project docs: current={len(indexed_sources)}, new={new_count}, "
            f"changed={changed_count}, orphaned_removed={orphaned_removed}, missing={len(missing_sources)}."
        )
        if stale_sources:
            message += f" {len(stale_sources)} project docs remain stale after sync."
        return ProjectDocsSyncResult(
            status=status,
            project=metadata,
            candidate_count=len(candidate_sources),
            current_count=len(indexed_sources),
            new_count=new_count,
            changed_count=changed_count,
            orphaned_count=len(before_ignored),
            orphaned_removed=orphaned_removed,
            dedup_removed=dedup_removed,
            stale_removed=stale_removed,
            sections_indexed=ingest_result.sections_indexed,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            missing_sources=missing_sources,
            removed_sources=removed_sources,
            skipped_sources=ingest_result.skipped_sources,
            warnings=[*warnings, *ingest_result.warnings],
            message=message,
        )

    def bootstrap_project_docs(self, project_path: str, question: str | None = None) -> ProjectDocsBootstrapResult:
        root = Path(project_path).expanduser().resolve()
        actions_taken: list[dict[str, Any]] = []
        initial = self.inspect_project_docs(str(root))
        actions_taken.append({"tool": "inspect_project_docs", "arguments_patch": {"project_path": str(root)}})
        inspect_result = initial
        ingest_result: ProjectDocsIngestResult | None = None
        sync_result: ProjectDocsSyncResult | None = None
        warnings = list(initial.warnings)

        if initial.reason_code in {"project_docs_found_not_indexed", "project_docs_stale"}:
            sync_result = self.sync_project_docs(str(root), with_vectors=True)
            actions_taken.append({
                "tool": "sync_project_docs",
                "arguments_patch": {"project_path": str(root), "with_vectors": True},
                "status": sync_result.status,
            })
            warnings.extend(sync_result.warnings)
            inspect_result = self.inspect_project_docs(str(root))
            actions_taken.append({"tool": "inspect_project_docs", "arguments_patch": {"project_path": str(root)}, "reason": "post_sync_verification"})

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
                sync_result=sync_result,
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
                sync_result=sync_result,
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
                sync_result=sync_result,
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
            sync_result=sync_result,
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
        scope: str | None = None,
        module_path: str | None = None,
    ):
        root = Path(project_path).expanduser().resolve()
        filters: dict[str, Any] = {
            "project_path": str(root),
            "source_class": source_class,
            "project_docs": True,
        }
        if scope:
            filters["doc_scope"] = scope
        if module_path:
            filters["module_path"] = module_path
        return self._agent_instance().query(
            query,
            limit=limit,
            budget=tokens or DEFAULT_DOC_TOKENS,
            expand=expand,
            filters=filters,
        )

    def get_project_docs(
        self,
        project_path: str,
        query: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        module: str | None = None,
        module_path: str | None = None,
        scope: str | None = None,
    ) -> ProjectDocsResult:
        if hasattr(self.facade, "_project_get_project_docs_impl"):
            return self.facade._project_get_project_docs_impl(project_path, query, tokens=tokens, limit=limit, expand=expand, module=module, module_path=module_path, scope=scope)
        root = Path(project_path).expanduser().resolve()
        if scope and scope not in {"project", "module", "all"}:
            raise ValueError("scope must be one of: project, module, all")
        metadata = self.read_project_metadata(str(root))
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        module_summaries = self._module_summaries(candidate_sources)
        resolved_module_path, module_error = self._resolve_module_filter(module_summaries, module=module, module_path=module_path)
        if module_error:
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status=module_error["reason_code"],
                reason_code=module_error["reason_code"],
                next_action={"type": "inspect_project_docs", "tool": "inspect_project_docs"},
                arguments_patch={"project_path": str(root)},
                reason=module_error["reason_code"],
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                source_state_guidance=self._source_state_guidance(),
                next_actions=[{
                    "tool": "inspect_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root)},
                    "reason": "Inspect available modules, then retry with an exact module_path.",
                }],
                message=module_error["message"],
            )
        query_scope = scope if scope != "all" else None
        if resolved_module_path:
            query_scope = "module"
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
        if query_scope:
            candidate_sources = [item for item in candidate_sources if item.get("doc_scope") == query_scope]
            indexed_sources = [item for item in indexed_sources if item.get("doc_scope") == query_scope]
            stale_sources = [item for item in stale_sources if (item.get("candidate") or item).get("doc_scope") == query_scope]
            ignored_sources = [item for item in ignored_sources if item.get("doc_scope") == query_scope]
        if resolved_module_path:
            candidate_sources = [item for item in candidate_sources if item.get("module_path") == resolved_module_path]
            indexed_sources = [item for item in indexed_sources if item.get("module_path") == resolved_module_path]
            stale_sources = [item for item in stale_sources if (item.get("candidate") or item).get("module_path") == resolved_module_path]
            ignored_sources = [item for item in ignored_sources if item.get("module_path") == resolved_module_path]
            if not candidate_sources:
                return ProjectDocsResult(
                    project_path=str(root),
                    query=query,
                    status="no_module_docs",
                    reason_code="no_module_docs",
                    next_action={"type": "inspect_project_docs", "tool": "inspect_project_docs"},
                    arguments_patch={"project_path": str(root)},
                    reason="no_module_docs",
                    answer_available=False,
                    warnings=metadata.warnings,
                    candidate_sources=[asdict(item) for item in metadata.docs_candidates],
                    source_state_guidance=self._source_state_guidance(),
                    message=f"Module {resolved_module_path!r} exists, but no module docs were discovered for this scope.",
                )

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
                message=user_message or "No project-owned docs were found. Ask before creating a reviewable ARCHITECTURE.md, then run inspect_project_docs and sync_project_docs.",
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
                    "tool": "sync_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root), "with_vectors": True},
                    "reason": "Project docs candidates were discovered but have not been indexed; reconcile the index.",
                }],
                message="Project docs candidates exist but are not indexed. Run sync_project_docs, then retry get_project_docs.",
            )

        chunks = self.query_project_docs(str(root), query, tokens=tokens, limit=limit, expand=expand, scope=query_scope, module_path=resolved_module_path)
        current_by_path = {
            item.get("path"): item
            for item in indexed_sources
            if item.get("path")
        }
        safe_chunks = []
        for chunk in chunks:
            metadata_for_chunk = chunk.metadata or {}
            chunk_path = metadata_for_chunk.get("project_doc_path") or metadata_for_chunk.get("source_path")
            current_source = current_by_path.get(chunk_path)
            if not current_source:
                continue
            if metadata_for_chunk.get("project_doc_content_hash") != current_source.get("content_hash"):
                continue
            safe_chunks.append(chunk)
        chunks = safe_chunks
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
                "doc_scope": (chunk.metadata or {}).get("doc_scope") or "project",
                "module_id": (chunk.metadata or {}).get("module_id"),
                "module_name": (chunk.metadata or {}).get("module_name"),
                "module_path": (chunk.metadata or {}).get("module_path"),
                "module_type": (chunk.metadata or {}).get("module_type"),
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
                doc_scope=(chunk.metadata or {}).get("doc_scope") or "project",
                module_id=(chunk.metadata or {}).get("module_id"),
                module_name=(chunk.metadata or {}).get("module_name"),
                module_path=(chunk.metadata or {}).get("module_path"),
                module_type=(chunk.metadata or {}).get("module_type"),
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
                "tool": "sync_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root), "with_vectors": True},
                "reason": "Some indexed project docs are stale; reconcile before relying on repo-specific answers.",
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
                "tool": "sync_project_docs" if stale_sources else "inspect_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root), **({"with_vectors": True} if stale_sources else {})},
                "reason": "Project docs are stale; sync and retry." if stale_sources else "Project docs are indexed, but no indexed project docs matched this query. Inspect candidates or refine the query.",
            }],
            message="Indexed project docs exist, but no results matched this query." + (" Some indexed docs are stale." if stale_sources else ""),
        )
