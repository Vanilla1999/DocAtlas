from __future__ import annotations

import configparser
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re
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
from docmancer.docs.project import DOC_FILE_EXTENSIONS, ROOT_DOC_FILES
from docmancer.docs.section_metadata import SECTION_METADATA_SCHEMA_VERSION, extract_section_metadata_result
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
PLACEHOLDER_PROJECT_DOC_RE = re.compile(
    r"\b(todo|tbd|placeholder|coming soon|lorem ipsum|under construction|work in progress|wip)\b|"
    r"TODO:\s*Put a short description|const\s+like\s*=\s*['\"]sample['\"]",
    re.IGNORECASE,
)

class ProjectDocsService:
    @staticmethod
    def _canonical_git_remote(remote: str) -> str:
        value = remote.strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme and parsed.hostname:
            host = parsed.hostname.lower()
            path = parsed.path.strip("/")
            if path.endswith(".git"):
                path = path[:-4]
            return f"{host}/{path}"
        scp_like = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", value)
        if scp_like:
            host, path = scp_like.groups()
            path = path.strip("/")
            if path.endswith(".git"):
                path = path[:-4]
            return f"{host.lower()}/{path}"
        return value

    @staticmethod
    def _repository_identity(root: Path) -> str:
        """Return a clone-stable identity when Git metadata is available.

        Unversioned directories have no portable identity by definition.  Keep
        them isolated in a deterministic local namespace instead of allowing
        equal relative paths from unrelated projects to collide in one index.
        """
        git_entry = root / ".git"
        config_path = git_entry / "config"
        if git_entry.is_file():
            try:
                marker = git_entry.read_text(encoding="utf-8").strip()
            except OSError:
                marker = ""
            if marker.lower().startswith("gitdir:"):
                git_dir = Path(marker.split(":", 1)[1].strip())
                if not git_dir.is_absolute():
                    git_dir = (root / git_dir).resolve()
                config_path = git_dir / "config"

        parser = configparser.RawConfigParser()
        try:
            if config_path.is_file():
                parser.read(config_path, encoding="utf-8")
        except (OSError, configparser.Error):
            parser = configparser.RawConfigParser()
        remote_sections = sorted(
            section for section in parser.sections()
            if section.startswith('remote "') and section.endswith('"')
        )
        preferred = 'remote "origin"'
        if preferred in remote_sections:
            remote_sections.remove(preferred)
            remote_sections.insert(0, preferred)
        for section in remote_sections:
            remote = parser.get(section, "url", fallback="").strip().rstrip("/")
            if remote:
                return f"git:{ProjectDocsService._canonical_git_remote(remote)}"

        local_digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
        return f"local:{local_digest}"

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
    def _invalid_project_docs_catalog_action(root: Path, warnings: list[str]) -> dict[str, Any]:
        return {
            "type": "fix_project_docs_catalog",
            "action": "fix_project_docs_catalog",
            "handled_by": "coding_agent",
            "requires_confirmation": False,
            "path": str(root / "docatlas.project-docs.yaml"),
            "arguments_patch": {"project_path": str(root)},
            "reason": "The explicit project-doc catalog is invalid. Fix it before discovery, indexing, or synchronization.",
            "validation_errors": list(warnings),
        }

    @staticmethod

    def _project_docs_structured_next_action(
        *,
        reason_code: str,
        root: Path,
        query: str | None = None,
    ) -> tuple[dict[str, Any], bool, str | None, dict[str, Any], str, str | None]:
        return project_docs_structured_next_action(reason_code=reason_code, root=root, query=query)

    @staticmethod
    def _project_docs_preflight_next_action(root: Path, preflight: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        risk_codes = [str(item.get("code")) for item in preflight.get("risks", []) if item.get("code")]
        sync_args = {"project_path": str(root), "with_vectors": True}
        agent_message = (
            "Project docs preflight found suspicious or risky docs/index state. Ask the user to update the docs "
            "or explicitly confirm sync_project_docs before indexing/reconciling."
        )
        user_message = (
            "Project documentation looks incomplete, placeholder-like, unsupported, or risky to reconcile. "
            "Please update the docs, or confirm that I should index/reconcile the current files."
        )
        return (
            {
                "type": "ask_user_to_update_or_confirm_project_docs",
                "handled_by": "coding_agent",
                "requires_confirmation": True,
                "confirmation_reason": "project_docs_preflight",
                "risk_codes": risk_codes,
                "tool_after_confirmation": "sync_project_docs",
                "arguments_patch_after_confirmation": sync_args,
            },
            {"project_path": str(root)},
            agent_message,
            user_message,
        )

    @staticmethod
    def _project_docs_preflight_recommended_action(root: Path, preflight: dict[str, Any]) -> dict[str, Any]:
        risk_codes = [str(item.get("code")) for item in preflight.get("risks", []) if item.get("code")]
        return {
            "action": "ask_user_to_update_or_confirm_project_docs",
            "requires_confirmation": True,
            "confirmation_reason": "project_docs_preflight",
            "risk_codes": risk_codes,
            "reason": "Project docs preflight found suspicious or risky docs/index state; do not run blind indexing/reconciliation.",
            "agent_guidance": "Ask the user to update the project docs, or explicitly confirm sync_project_docs for the current snapshot.",
            "user_message": "Project docs may need updates before indexing. Update them, or confirm indexing/reconciliation of the current files?",
            "after_user_updates": [
                {"tool": "inspect_project_docs", "requires_confirmation": False, "arguments_patch": {"project_path": str(root)}},
            ],
            "after_confirmation": {
                "tool": "sync_project_docs",
                "requires_confirmation": False,
                "arguments_patch": {"project_path": str(root), "with_vectors": True},
            },
        }

    @staticmethod
    def _looks_like_placeholder_project_doc(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        return bool(PLACEHOLDER_PROJECT_DOC_RE.search(stripped))

    @classmethod
    def _looks_like_placeholder_search_result(cls, path: str | None, text: str) -> bool:
        name = Path(str(path or "")).name.lower()
        if not (name.startswith("readme") or name.startswith("architecture") or name in {"license", "copying"}):
            return False
        return cls._looks_like_placeholder_project_doc(text[:4096])

    @staticmethod
    def _read_text_prefix(path: Path, *, max_chars: int = 4096) -> str | None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return handle.read(max_chars)
        except OSError:
            return None
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _unsupported_root_doc_files(root: Path, candidate_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidate_paths = {str(item.get("path")) for item in candidate_sources if item.get("path")}
        risks: list[dict[str, Any]] = []
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            return risks
        for child in children:
            if not child.is_file():
                continue
            try:
                relative = child.relative_to(root).as_posix()
            except ValueError:
                continue
            if relative in candidate_paths:
                continue
            name = child.name.lower()
            stem = child.stem.lower()
            doc_like = stem in ROOT_DOC_FILES or stem.startswith("readme") or name in ROOT_DOC_FILES
            if not doc_like:
                continue
            suffix = child.suffix.lower()
            supported_extensionless = name in {"license", "copying"}
            if suffix in DOC_FILE_EXTENSIONS or supported_extensionless:
                continue
            risks.append({
                "code": "unsupported_project_doc_candidate",
                "severity": "major",
                "path": relative,
                "message": "A root documentation-looking file was found in a format project-doc ingest will not index automatically.",
                "recommended_action": "Convert or mirror it as Markdown/text, or confirm indexing only the currently supported docs.",
            })
        return risks

    def _project_docs_preflight(
        self,
        root: Path,
        *,
        base_reason_code: str,
        candidate_sources: list[dict[str, Any]],
        stale_sources: list[dict[str, Any]],
        ignored_sources: list[dict[str, Any]],
        active_index: dict[str, Any],
    ) -> dict[str, Any]:
        risks: list[dict[str, Any]] = []
        for candidate in candidate_sources:
            candidate_path = str(candidate.get("path") or "")
            if not candidate_path:
                continue
            path = Path(candidate_path)
            reason = str(candidate.get("reason") or "")
            if not (
                path.name.lower().startswith("readme")
                or reason in {"architecture", "overview", "project_architecture"}
            ):
                continue
            text = self._read_text_prefix(root / candidate_path)
            if text is not None and self._looks_like_placeholder_project_doc(text):
                risks.append({
                    "code": "placeholder_project_doc",
                    "severity": "major",
                    "path": candidate_path,
                    "message": "A high-level project doc appears to be placeholder/TODO content.",
                    "recommended_action": "Ask the user to update the project doc, or explicitly confirm indexing the current placeholder content.",
                })

        risks.extend(self._unsupported_root_doc_files(root, candidate_sources))

        if stale_sources:
            risks.append({
                "code": "stale_project_doc_sources",
                "severity": "major",
                "count": len(stale_sources),
                "paths": [str(item.get("path")) for item in stale_sources[:5] if item.get("path")],
                "message": "Indexed project docs differ from the current files on disk.",
                "recommended_action": "Ask before reconciling stale indexed docs with the current repository snapshot.",
            })
        if ignored_sources:
            risks.append({
                "code": "orphaned_project_doc_sources",
                "severity": "major",
                "count": len(ignored_sources),
                "paths": [str(item.get("path")) for item in ignored_sources[:5] if item.get("path")],
                "message": "The index contains project docs not selected by current discovery.",
                "recommended_action": "Ask before pruning or reconciling orphaned project-doc index entries.",
            })
        for warning in active_index.get("warnings") or []:
            if warning.get("code") == "project_local_config_shadowed":
                risks.append({
                    "code": "project_local_config_shadowed",
                    "severity": "major",
                    "message": warning.get("message") or "Repo-local docmancer.yaml is shadowed by the active service config.",
                    "recommended_action": "Ask the user to confirm which Docmancer DB/config should be used before indexing.",
                    "active_db_path": warning.get("active_db_path"),
                    "project_config_db_path": warning.get("project_config_db_path"),
                })
        return {
            "status": "confirmation_required" if risks else "ok",
            "requires_confirmation": bool(risks),
            "confirmation_reason": "project_docs_preflight" if risks else None,
            "safe_to_sync_without_confirmation": not risks,
            "base_reason_code": base_reason_code,
            "risk_count": len(risks),
            "risks": risks,
        }

    def inspect_project_docs(self, project_path: str) -> ProjectDocsInspectResult:
        if hasattr(self.facade, "_project_inspect_project_docs_impl"):
            return self.facade._project_inspect_project_docs_impl(project_path)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        catalog_invalid = metadata.docs_catalog_present and not metadata.docs_catalog_valid
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
        preserved_indexed_sources = indexed_sources_all if catalog_invalid else []
        if catalog_invalid:
            # An invalid authoritative catalog cannot classify existing index
            # rows as current, stale, or orphaned. Preserve them without
            # attaching lifecycle guidance that could trigger pruning.
            indexed_sources, stale_sources, ignored_sources = [], [], []
        candidate_paths = {item.get("path") for item in candidate_sources if item.get("path")}
        indexed_paths = {item.get("path") for item in [*indexed_sources, *stale_sources] if item.get("path")}
        missing_candidate_count = len(candidate_paths - indexed_paths)
        has_high_level_overview = self._has_high_level_project_overview(candidate_sources)
        manifests_found = [name for name in ("pubspec.yaml", "Cargo.toml", "package.json") if (root / name).exists()]
        lockfiles_found = [
            name
            for name in ("pubspec.lock", "Cargo.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")
            if (root / name).exists()
        ]
        dependency_docs_state = self._project_dependency_docs_state(metadata)
        exact_versions_available = dependency_docs_state["dependency_docs_available"]
        if catalog_invalid:
            base_reason_code = "invalid_project_docs_catalog"
        elif stale_sources or ignored_sources:
            base_reason_code = "project_docs_stale"
        elif not candidate_sources:
            base_reason_code = "no_project_docs"
        elif not catalog_invalid and not has_high_level_overview:
            base_reason_code = "architecture_doc_creation_recommended"
        elif missing_candidate_count:
            base_reason_code = "project_docs_found_not_indexed"
        else:
            base_reason_code = "project_docs_ready"
        active_index = self.active_index_diagnostics(str(root))
        preflight = (
            {
                "status": "blocked",
                "requires_confirmation": False,
                "safe_to_sync_without_confirmation": False,
                "base_reason_code": base_reason_code,
                "risk_count": 1,
                "risks": [{
                    "code": "invalid_project_docs_catalog",
                    "severity": "major",
                    "message": "The explicit project-doc catalog is invalid.",
                    "recommended_action": "Fix docatlas.project-docs.yaml before indexing or synchronization.",
                }],
            }
            if catalog_invalid
            else self._project_docs_preflight(
                root,
                base_reason_code=base_reason_code,
                candidate_sources=candidate_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                active_index=active_index,
            )
        )
        recommended_next_actions: list[dict[str, Any]] = []
        if catalog_invalid:
            recommended_next_actions.append(
                self._invalid_project_docs_catalog_action(root, metadata.warnings)
            )
        elif preflight["requires_confirmation"]:
            recommended_next_actions.append(self._project_docs_preflight_recommended_action(root, preflight))
        elif stale_sources or ignored_sources:
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
        if not candidate_sources and not catalog_invalid:
            recommended_next_actions.append(self._create_project_docs_next_action(root))
        elif not catalog_invalid and not has_high_level_overview:
            recommended_next_actions.append(self._create_project_docs_next_action(
                root,
                reason="Project docs exist, but no high-level architecture or overview document was discovered. Ask the user before creating a reviewable ARCHITECTURE.md file.",
            ))
        if catalog_invalid:
            reason_code = base_reason_code
            next_action = self._invalid_project_docs_catalog_action(root, metadata.warnings)
            arguments_patch = {"project_path": str(root)}
            agent_message = "Fix the invalid explicit project-doc catalog before indexing, synchronization, or project-doc retrieval."
            user_message = "docatlas.project-docs.yaml is invalid. Fix the reported catalog errors before continuing."
            requires_confirmation = False
            confirmation_reason = None
        elif preflight["requires_confirmation"]:
            reason_code = "project_docs_preflight_confirmation_required"
            next_action, arguments_patch, agent_message, user_message = self._project_docs_preflight_next_action(root, preflight)
            requires_confirmation = True
            confirmation_reason = "project_docs_preflight"
        else:
            reason_code = base_reason_code
            next_action, requires_confirmation, confirmation_reason, arguments_patch, agent_message, user_message = self._project_docs_structured_next_action(
                reason_code=reason_code,
                root=root,
            )
        project_docs = {
            "found": candidate_sources,
            "indexed": indexed_sources,
            "stale": stale_sources,
            "ignored": ignored_sources,
            "preserved_indexed": preserved_indexed_sources,
            "high_level_overview_found": has_high_level_overview,
            "modules": self._module_summaries(candidate_sources),
            "indexed_modules": self._module_summaries(indexed_sources),
            "preflight": preflight,
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
            agent_guidance=(
                "Fix docatlas.project-docs.yaml and re-run inspect_project_docs. Do not create docs, sync, or prune the existing index while the explicit catalog is invalid."
                if catalog_invalid
                else "Inspect diagnostics.preflight first. If it requires confirmation, ask the user to update docs or confirm before sync_project_docs. Otherwise call get_project_docs for repo-specific questions after project docs are synced. If docs are missing, ask before creating a reviewable ARCHITECTURE.md, then inspect and sync it. Ask before network dependency docs fetches."
            ),
            source_state_guidance=self._source_state_guidance(),
            diagnostics={
                "active_index": active_index,
                "preflight": preflight,
                "indexed_sources_preserved": len(preserved_indexed_sources),
            },
            warnings=metadata.warnings,
        )

    def ingest_project_docs(
        self,
        project_path: str,
        *,
        skip_known: bool = True,
        with_vectors: bool = True,
        _candidate_paths: set[str] | None = None,
    ) -> ProjectDocsIngestResult:
        if hasattr(self.facade, "_project_ingest_project_docs_impl"):
            kwargs: dict[str, Any] = {"skip_known": skip_known, "with_vectors": with_vectors}
            if _candidate_paths is not None:
                kwargs["_candidate_paths"] = _candidate_paths
            return self.facade._project_ingest_project_docs_impl(project_path, **kwargs)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        repository_identity = self._repository_identity(root)
        warnings = list(metadata.warnings)
        candidates = list(metadata.docs_candidates)
        if metadata.docs_catalog_present and not metadata.docs_catalog_valid:
            return ProjectDocsIngestResult(
                status="invalid_project_docs_catalog",
                project=metadata,
                candidate_count=0,
                warnings=warnings,
                message="docatlas.project-docs.yaml is invalid; no project docs were indexed.",
            )
        if _candidate_paths is not None:
            candidates = [item for item in candidates if item.path in _candidate_paths]
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
                "repository_identity": repository_identity,
                "source_class": "project_file",
                "project_docs": True,
            }
            if candidate:
                section_result = extract_section_metadata_result(path, source_document_path=candidate.path)
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
                    "project_doc_description": candidate.description,
                    "project_doc_authority": candidate.authority,
                    "project_doc_lifecycle_status": candidate.lifecycle_status,
                    "project_doc_impact_policy": candidate.impact_policy,
                    "project_doc_catalog_entry_hash": candidate.catalog_entry_hash,
                    "project_doc_sections": section_result.sections,
                    "project_doc_sections_status": section_result.status,
                    "project_doc_sections_reason": section_result.reason_code,
                    "project_doc_sections_schema": SECTION_METADATA_SCHEMA_VERSION,
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
                metadata={
                    "project_path": str(root),
                    "repository_identity": repository_identity,
                    "source_class": "project_file",
                    "project_docs": True,
                },
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

    @staticmethod
    def _normalize_incremental_doc_path(root: Path, value: Any, *, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} entries must be non-empty repository-relative paths")
        raw = value.strip().replace("\\", "/")
        if Path(raw).is_absolute():
            raise ValueError(f"{field} entries must be repository-relative paths")
        resolved = (root / raw).resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{field} path escapes project_path: {value}") from exc
        normalized = relative.as_posix()
        if normalized in {"", "."}:
            raise ValueError(f"{field} entries must identify a file")
        return normalized

    @staticmethod
    def _bounded_sync_tombstones(
        values: list[dict[str, Any]], *, max_bytes: int = 8192, max_items: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        bounded: list[dict[str, Any]] = []
        used = 2
        for value in values[:max_items]:
            item: dict[str, Any] = {}
            for key in ("path", "reason", "content_hash", "renamed_to"):
                if value.get(key) is None:
                    continue
                raw = str(value[key])
                item[key] = raw[:512]
                if len(raw) > 512 and key in {"path", "renamed_to"}:
                    item[f"{key}_truncated"] = True
                    item[f"{key}_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            item_bytes = len(json.dumps(item, ensure_ascii=False).encode("utf-8")) + 1
            if used + item_bytes > max_bytes:
                break
            bounded.append(item)
            used += item_bytes
        return bounded, len(values) - len(bounded)

    def _sync_project_docs_incremental(
        self,
        root: Path,
        metadata: ProjectMetadata,
        *,
        with_vectors: bool,
        changed_paths: list[str] | tuple[str, ...] | None,
        deleted_paths: list[str] | tuple[str, ...] | None,
        renamed_paths: list[dict[str, str]] | tuple[dict[str, str], ...] | None,
    ) -> ProjectDocsSyncResult:
        started_at = time.perf_counter()
        for field, value in (
            ("changed_paths", changed_paths),
            ("deleted_paths", deleted_paths),
            ("renamed_paths", renamed_paths),
        ):
            if value is not None and not isinstance(value, (list, tuple)):
                raise ValueError(f"{field} must be a list or tuple")
            if value is not None and len(value) > 500:
                raise ValueError(f"{field} accepts at most 500 entries")
        changed = {
            self._normalize_incremental_doc_path(root, path, field="changed_paths")
            for path in (changed_paths or [])
        }
        deleted = {
            self._normalize_incremental_doc_path(root, path, field="deleted_paths")
            for path in (deleted_paths or [])
        }
        renames: list[tuple[str, str]] = []
        rename_targets_by_old: dict[str, str] = {}
        rename_sources_by_new: dict[str, str] = {}
        for index, item in enumerate(renamed_paths or []):
            if not isinstance(item, dict) or set(item) != {"old_path", "new_path"}:
                raise ValueError(
                    f"renamed_paths[{index}] must contain exactly old_path and new_path"
                )
            old_path = self._normalize_incremental_doc_path(
                root, item["old_path"], field=f"renamed_paths[{index}].old_path"
            )
            new_path = self._normalize_incremental_doc_path(
                root, item["new_path"], field=f"renamed_paths[{index}].new_path"
            )
            if old_path == new_path:
                raise ValueError(f"renamed_paths[{index}] old_path and new_path must differ")
            if old_path in rename_targets_by_old and rename_targets_by_old[old_path] != new_path:
                raise ValueError(f"renamed_paths[{index}] conflicts with another rename from {old_path}")
            if new_path in rename_sources_by_new and rename_sources_by_new[new_path] != old_path:
                raise ValueError(f"renamed_paths[{index}] conflicts with another rename to {new_path}")
            rename_targets_by_old[old_path] = new_path
            rename_sources_by_new[new_path] = old_path
            if (old_path, new_path) in renames:
                continue
            renames.append((old_path, new_path))
            deleted.add(old_path)
            changed.add(new_path)

        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        candidate_by_path = {item["path"]: item for item in candidate_sources}
        still_present_deleted = sorted(
            path for path in deleted if (root / path).exists()
        )
        if still_present_deleted:
            raise ValueError(
                "deleted_paths still exist as project documentation candidates: "
                + ", ".join(still_present_deleted)
            )
        indexed_before = self._indexed_project_doc_sources(str(root))
        indexed_by_path: dict[str, list[dict[str, Any]]] = {}
        for source in indexed_before:
            if source.get("path"):
                indexed_by_path.setdefault(str(source["path"]), []).append(source)
        affected_orphaned_count = sum(
            len(indexed_by_path.get(path, [])) for path in deleted
        )

        agent = self._agent_instance()
        dedup_removed = 0
        vector_chunks_pruned = 0

        def delete_source_with_vector_cleanup(source_name: str) -> bool:
            nonlocal vector_chunks_pruned
            chunk_ids = set(agent.store.section_ids_for_source(source_name))
            prune = getattr(agent, "prune_vector_chunks", None)
            if chunk_ids and callable(prune):
                vector_chunks_pruned += int(prune(chunk_ids) or 0)
            return bool(agent.store.delete_source(source_name))

        for path in sorted(changed | deleted):
            sources = indexed_by_path.get(path, [])
            if len(sources) <= 1:
                continue
            sources.sort(key=lambda item: item.get("ingested_at") or "", reverse=True)
            for duplicate in sources[1:]:
                source_name = duplicate.get("source")
                if source_name and delete_source_with_vector_cleanup(str(source_name)):
                    dedup_removed += 1
            indexed_by_path[path] = sources[:1]
        removed_sources: list[dict[str, Any]] = []
        tombstones: list[dict[str, Any]] = []
        rename_targets = {old: new for old, new in renames}
        paths_to_remove = set(deleted)
        changed_candidates: set[str] = set()
        unchanged_count = 0
        new_count = 0
        changed_count = 0

        for path in changed:
            candidate = candidate_by_path.get(path)
            existing = indexed_by_path.get(path, [])
            if candidate is None:
                continue
            current, stale, _ignored = self._partition_project_doc_state([candidate], existing)
            if current and not stale:
                unchanged_count += 1
                continue
            changed_candidates.add(path)
            paths_to_remove.add(path)
            if existing:
                changed_count += 1
            else:
                new_count += 1

        for path in sorted(paths_to_remove):
            reason = "renamed" if path in rename_targets else ("deleted" if path in deleted else "changed")
            for source in indexed_by_path.get(path, []):
                source_name = source.get("source")
                if source_name and delete_source_with_vector_cleanup(str(source_name)):
                    removed_sources.append(source)
                    tombstone = {
                        "path": path,
                        "reason": reason,
                        "content_hash": source.get("content_hash"),
                    }
                    if path in rename_targets:
                        tombstone["renamed_to"] = rename_targets[path]
                    tombstones.append(tombstone)

        if changed_candidates:
            ingest_result = self.ingest_project_docs(
                str(root),
                skip_known=True,
                with_vectors=False,
                _candidate_paths=changed_candidates,
            )
        else:
            ingest_result = ProjectDocsIngestResult(
                status="success",
                project=metadata,
                candidate_count=0,
                message="No changed project docs required indexing.",
            )

        indexed_after = self._indexed_project_doc_sources(str(root))
        if with_vectors and changed_candidates:
            changed_source_names = {
                str(item["source"])
                for item in indexed_after
                if item.get("path") in changed_candidates and item.get("source")
            }
            changed_section_ids = {
                section_id
                for source_name in changed_source_names
                for section_id in agent.store.section_ids_for_source(source_name)
            }
            sync_chunks = getattr(agent, "sync_vector_chunks", None)
            if changed_section_ids and callable(sync_chunks):
                sync_chunks(changed_section_ids)
            elif changed_section_ids:
                raise RuntimeError(
                    "incremental vector sync requires an agent with scoped chunk support"
                )
        indexed_sources, stale_sources, _ignored_sources = self._partition_project_doc_state(
            candidate_sources, indexed_after
        )
        indexed_paths = {
            item.get("path") for item in [*indexed_sources, *stale_sources] if item.get("path")
        }
        missing_sources = [
            candidate_by_path[path]
            for path in sorted(changed_candidates)
            if path not in indexed_paths
        ]
        remaining_deleted = [
            item for item in indexed_after if item.get("path") in deleted
        ]
        unmatched_changed = sorted(changed - set(candidate_by_path))
        status = "partial" if missing_sources or remaining_deleted or unmatched_changed or any(
            item.get("path") in changed_candidates for item in stale_sources
        ) else "success"
        files_reprocessed = len(changed_candidates)
        diagnostics = {
            "active_index": self.active_index_diagnostics(str(root)),
            "mode": "incremental",
            "requested": {
                "changed": len(changed),
                "deleted": len(deleted),
                "renamed": len(renames),
            },
            "metrics": {
                "files_reprocessed": files_reprocessed,
                "sections_reprocessed": ingest_result.sections_indexed,
                "unchanged_files": unchanged_count,
                "derived_deletes": len(removed_sources) + dedup_removed,
                "derived_writes": ingest_result.sections_indexed,
                "vector_chunks_pruned": vector_chunks_pruned,
                "unrelated_files_reprocessed": 0,
                "unchanged_derived_writes": 0,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "unmatched_changed_paths": unmatched_changed,
            "unmatched_deleted_paths": sorted(deleted - set(indexed_by_path)),
            "remaining_deleted_sources": len(remaining_deleted),
        }
        bounded_tombstones, tombstones_omitted = self._bounded_sync_tombstones(tombstones)
        diagnostics["tombstones_omitted"] = tombstones_omitted
        message = (
            "Incrementally synced project docs: "
            f"reprocessed={files_reprocessed}, unchanged={unchanged_count}, "
            f"deleted={len(tombstones)}, missing={len(missing_sources)}."
        )
        return ProjectDocsSyncResult(
            status=status,
            project=metadata,
            candidate_count=len(changed | deleted),
            current_count=len(indexed_sources),
            new_count=new_count,
            changed_count=changed_count,
            orphaned_count=affected_orphaned_count,
            orphaned_removed=sum(1 for item in removed_sources if item.get("path") in deleted),
            dedup_removed=dedup_removed,
            stale_removed=sum(1 for item in removed_sources if item.get("path") in changed),
            sections_indexed=ingest_result.sections_indexed,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            missing_sources=missing_sources,
            removed_sources=removed_sources,
            tombstones=bounded_tombstones,
            skipped_sources=ingest_result.skipped_sources,
            diagnostics=diagnostics,
            warnings=list(dict.fromkeys([*metadata.warnings, *ingest_result.warnings])),
            message=message,
        )

    def sync_project_docs(
        self,
        project_path: str,
        *,
        with_vectors: bool = True,
        changed_paths: list[str] | tuple[str, ...] | None = None,
        deleted_paths: list[str] | tuple[str, ...] | None = None,
        renamed_paths: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    ) -> ProjectDocsSyncResult:
        if hasattr(self.facade, "_project_sync_project_docs_impl"):
            kwargs: dict[str, Any] = {"with_vectors": with_vectors}
            if changed_paths is not None:
                kwargs["changed_paths"] = changed_paths
            if deleted_paths is not None:
                kwargs["deleted_paths"] = deleted_paths
            if renamed_paths is not None:
                kwargs["renamed_paths"] = renamed_paths
            return self.facade._project_sync_project_docs_impl(project_path, **kwargs)
        root = Path(project_path).expanduser().resolve()
        metadata = self.read_project_metadata(str(root))
        warnings = list(metadata.warnings)
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        before_indexed_all = self._indexed_project_doc_sources(str(root))
        if metadata.docs_catalog_present and not metadata.docs_catalog_valid:
            return ProjectDocsSyncResult(
                status="invalid_project_docs_catalog",
                project=metadata,
                candidate_count=0,
                indexed_sources=before_indexed_all,
                diagnostics={
                    "active_index": self.active_index_diagnostics(str(root)),
                    "indexed_sources_preserved": len(before_indexed_all),
                    "catalog_valid": False,
                },
                warnings=warnings,
                message="docatlas.project-docs.yaml is invalid; the existing project-doc index was preserved unchanged.",
            )
        if any(value is not None for value in (changed_paths, deleted_paths, renamed_paths)):
            return self._sync_project_docs_incremental(
                root,
                metadata,
                with_vectors=with_vectors,
                changed_paths=changed_paths,
                deleted_paths=deleted_paths,
                renamed_paths=renamed_paths,
            )
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
                diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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
            diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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

        if initial.requires_confirmation:
            return ProjectDocsBootstrapResult(
                project_path=str(root),
                question=question,
                status="confirmation_required",
                reason_code=initial.reason_code,
                actions_taken=actions_taken,
                next_action=initial.next_action,
                requires_confirmation=True,
                confirmation_reason=initial.confirmation_reason,
                arguments_patch=initial.arguments_patch,
                inspect_result=initial,
                ingest_result=ingest_result,
                sync_result=sync_result,
                agent_message=initial.agent_message,
                user_message=initial.user_message,
                diagnostics={"active_index": self.active_index_diagnostics(str(root))},
                warnings=warnings,
            )

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
                diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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
                diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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
                diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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
            diagnostics={"active_index": self.active_index_diagnostics(str(root))},
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
        if metadata.docs_catalog_present and not metadata.docs_catalog_valid:
            next_action = self._invalid_project_docs_catalog_action(root, metadata.warnings)
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="invalid_project_docs_catalog",
                reason_code="invalid_project_docs_catalog",
                next_action=next_action,
                arguments_patch={"project_path": str(root)},
                answer_available=False,
                reason="invalid_project_docs_catalog",
                warnings=metadata.warnings,
                next_actions=[next_action],
                message="docatlas.project-docs.yaml is invalid; fix the catalog before retrieving project documentation.",
            )
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

        preflight_inspect: ProjectDocsInspectResult | None = None
        if not indexed_sources_all or stale_sources or ignored_sources:
            inspect_result = self.inspect_project_docs(str(root))
            if inspect_result.requires_confirmation and inspect_result.confirmation_reason == "project_docs_preflight":
                preflight_inspect = inspect_result

        def _confirmation_required_result(*, status: str, reason: str) -> ProjectDocsResult:
            assert preflight_inspect is not None
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status=status,
                reason_code=preflight_inspect.reason_code,
                next_action=preflight_inspect.next_action,
                requires_confirmation=True,
                confirmation_reason=preflight_inspect.confirmation_reason,
                arguments_patch=preflight_inspect.arguments_patch,
                reason=reason,
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=indexed_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                source_state_guidance=self._source_state_guidance(),
                diagnostics=preflight_inspect.diagnostics,
                next_actions=preflight_inspect.recommended_next_actions,
                message=preflight_inspect.user_message or preflight_inspect.agent_message,
            )

        if not candidate_sources:
            if preflight_inspect:
                return _confirmation_required_result(
                    status="confirmation_required",
                    reason="project_docs_preflight_confirmation_required",
                )
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
            if preflight_inspect:
                return _confirmation_required_result(
                    status="confirmation_required",
                    reason="project_docs_preflight_confirmation_required",
                )
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
        dropped_placeholder_chunks = 0
        history_requested = any(
            term in query.lower()
            for term in ("history", "historical", "roadmap", "completed", "superseded", "previous plan")
        )
        for chunk in chunks:
            metadata_for_chunk = chunk.metadata or {}
            chunk_path = metadata_for_chunk.get("project_doc_path") or metadata_for_chunk.get("source_path")
            current_source = current_by_path.get(chunk_path)
            if not current_source:
                continue
            if metadata_for_chunk.get("project_doc_content_hash") != current_source.get("content_hash"):
                continue
            lifecycle_status = metadata_for_chunk.get("project_doc_lifecycle_status") or "active"
            if lifecycle_status != "active" and not history_requested:
                continue
            if self._looks_like_placeholder_search_result(chunk_path, chunk.text):
                dropped_placeholder_chunks += 1
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
                "description": (chunk.metadata or {}).get("project_doc_description"),
                "authority": (chunk.metadata or {}).get("project_doc_authority"),
                "lifecycle_status": (chunk.metadata or {}).get("project_doc_lifecycle_status"),
                "impact_policy": (chunk.metadata or {}).get("project_doc_impact_policy"),
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
                description=(chunk.metadata or {}).get("project_doc_description"),
                authority=(chunk.metadata or {}).get("project_doc_authority"),
                lifecycle_status=(chunk.metadata or {}).get("project_doc_lifecycle_status"),
                impact_policy=(chunk.metadata or {}).get("project_doc_impact_policy"),
            )
            for chunk in chunks
        ]
        next_actions: list[dict[str, Any]] = []
        next_action: dict[str, Any] = {}
        requires_confirmation = False
        confirmation_reason = None
        arguments_patch: dict[str, Any] = {}
        preflight_diagnostics: dict[str, Any] = {}
        if dropped_placeholder_chunks:
            preflight_diagnostics["dropped_placeholder_project_docs"] = dropped_placeholder_chunks
        if preflight_inspect:
            next_action = preflight_inspect.next_action
            requires_confirmation = True
            confirmation_reason = preflight_inspect.confirmation_reason
            arguments_patch = preflight_inspect.arguments_patch
            next_actions.extend(preflight_inspect.recommended_next_actions)
            preflight_diagnostics = preflight_inspect.diagnostics
        elif stale_sources:
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
            status = "stale" if stale_sources else ("confirmation_required" if preflight_inspect else "success")
            reason_code = preflight_inspect.reason_code if preflight_inspect else ("project_docs_stale" if stale_sources else "project_docs_ready")
            reason = "project_docs_stale" if stale_sources else ("project_docs_preflight_confirmation_required" if preflight_inspect else None)
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status=status,
                reason_code=reason_code,
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason=reason,
                answer_available=True,
                results=results,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=result_indexed_sources or indexed_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                source_state_guidance=self._source_state_guidance(),
                diagnostics=preflight_diagnostics,
                next_actions=next_actions,
                message=f"Returned {len(results)} project docs result(s)." + (" Project docs preflight requires confirmation before sync/reconcile." if preflight_inspect else (" Some indexed project docs are stale." if stale_sources else "")),
            )
        if preflight_inspect:
            return _confirmation_required_result(
                status="stale" if stale_sources else "confirmation_required",
                reason="project_docs_stale" if stale_sources else "project_docs_preflight_confirmation_required",
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
