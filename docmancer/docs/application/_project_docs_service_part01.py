"""ProjectDocsService implementation shard 1."""
from __future__ import annotations

import hashlib

from ._project_docs_service_shared import *  # noqa: F401,F403
from docmancer.docs.impact import git_worktree_state


class _ProjectDocsServicePart01:
    @staticmethod
    def _clean_git_sync_digest(head: str) -> str:
        return hashlib.sha256(f"clean_git_auto:{head.lower()}".encode()).hexdigest()

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

    def _vector_sync_enabled(self) -> bool:
        """Return whether the configured retrieval path can consume vectors."""
        config = getattr(self.facade, "config", None)
        retrieval = getattr(config, "retrieval", None)
        mode = str(getattr(retrieval, "default_mode", "lexical") or "lexical").lower()
        return mode in {"dense", "sparse", "hybrid"}

    def _project_sync_arguments(self, root: Path) -> dict[str, Any]:
        return {
            "project_path": str(root),
            "with_vectors": self._vector_sync_enabled(),
        }

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

    def _project_docs_structured_next_action(
        self,
        *,
        reason_code: str,
        root: Path,
        query: str | None = None,
    ) -> tuple[dict[str, Any], bool, str | None, dict[str, Any], str, str | None]:
        return project_docs_structured_next_action(
            reason_code=reason_code,
            root=root,
            query=query,
            with_vectors=self._vector_sync_enabled(),
        )

    def _project_docs_preflight_next_action(self, root: Path, preflight: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        risk_codes = [str(item.get("code")) for item in preflight.get("risks", []) if item.get("code")]
        sync_args = self._project_sync_arguments(root)
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

    def _project_docs_preflight_recommended_action(self, root: Path, preflight: dict[str, Any]) -> dict[str, Any]:
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
                "arguments_patch": self._project_sync_arguments(root),
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
        lifecycle_conditions: list[dict[str, Any]] = []
        git_state = git_worktree_state(root)
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
            stale_condition = {
                "code": "stale_project_doc_sources",
                "severity": "major",
                "count": len(stale_sources),
                "paths": [str(item.get("path")) for item in stale_sources[:5] if item.get("path")],
                "message": "Indexed project docs differ from the current files on disk.",
                "recommended_action": "Ask before reconciling stale indexed docs with the current repository snapshot.",
            }
            if git_state.get("status") == "clean":
                lifecycle_conditions.append(stale_condition)
            else:
                risks.append(stale_condition)
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
                    "message": warning.get("message") or "Repo-local docatlas.yaml is shadowed by the active service config.",
                    "recommended_action": "Ask the user to confirm which Docmancer DB/config should be used before indexing.",
                    "active_db_path": warning.get("active_db_path"),
                    "project_config_db_path": warning.get("project_config_db_path"),
                })
        needs_sync = base_reason_code in {"project_docs_found_not_indexed", "project_docs_stale"}
        if needs_sync and git_state.get("status") in {"dirty", "indeterminate"}:
            risks.append({
                "code": "git_worktree_not_clean",
                "severity": "major",
                "git_status": git_state.get("status"),
                "message": "Automatic project-doc synchronization requires a clean, committed Git snapshot.",
                "recommended_action": "Commit or discard worktree changes, or explicitly confirm synchronization of the current snapshot.",
            })
        auto_sync_eligible = bool(needs_sync and git_state.get("status") == "clean" and not risks)
        return {
            "status": "confirmation_required" if risks else "ok",
            "requires_confirmation": bool(risks),
            "confirmation_reason": "project_docs_preflight" if risks else None,
            "safe_to_sync_without_confirmation": not risks,
            "auto_sync_eligible": auto_sync_eligible,
            "git": git_state,
            "base_reason_code": base_reason_code,
            "risk_count": len(risks),
            "risks": risks,
            "lifecycle_conditions": lifecycle_conditions,
        }

    def inspect_project_docs(self, project_path: str) -> ProjectDocsInspectResult:
        root = validate_project_path(project_path).path
        if hasattr(self.facade, "_project_inspect_project_docs_impl"):
            return self.facade._project_inspect_project_docs_impl(str(root))
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
            sync_arguments = self._project_sync_arguments(root)
            if preflight.get("auto_sync_eligible"):
                sync_arguments.update({
                    "plan_digest": self._clean_git_sync_digest(preflight["git"]["head"]),
                })
            recommended_next_actions.append({
                "tool": "prepare_docs" if preflight.get("auto_sync_eligible") else "sync_project_docs",
                "requires_confirmation": False,
                "reason": "Project docs index has stale or orphaned entries; reconcile it with the current repository docs snapshot.",
                "arguments_patch": (
                    {"action": "sync_project_docs", **sync_arguments}
                    if preflight.get("auto_sync_eligible") else sync_arguments
                ),
            })
        elif candidate_sources and missing_candidate_count:
            sync_arguments = self._project_sync_arguments(root)
            if preflight.get("auto_sync_eligible"):
                sync_arguments.update({
                    "plan_digest": self._clean_git_sync_digest(preflight["git"]["head"]),
                })
            recommended_next_actions.append({
                "tool": "prepare_docs" if preflight.get("auto_sync_eligible") else "sync_project_docs",
                "requires_confirmation": False,
                "reason": "Project docs found but not indexed; reconcile the index with current docs.",
                "arguments_patch": (
                    {"action": "sync_project_docs", **sync_arguments}
                    if preflight.get("auto_sync_eligible") else sync_arguments
                ),
            })
        if exact_versions_available:
            recommended_next_actions.append({
                "tool": "prefetch_project_dependency_docs",
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
            if preflight.get("auto_sync_eligible") and reason_code in {"project_docs_found_not_indexed", "project_docs_stale"}:
                arguments_patch = {
                    "action": "sync_project_docs",
                    **self._project_sync_arguments(root),
                    "plan_digest": self._clean_git_sync_digest(preflight["git"]["head"]),
                }
                next_action = {
                    "type": "prepare_docs",
                    "tool": "prepare_docs",
                    "requires_confirmation": False,
                    "arguments_patch": arguments_patch,
                }
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
        with_vectors: bool = False,
        _candidate_paths: set[str] | None = None,
        _coordination_held: bool = False,
    ) -> ProjectDocsIngestResult:
        root = validate_project_path(project_path).path
        mutation_config = getattr(self.facade, "config", None)
        mutation_index = getattr(mutation_config, "index", None)
        mutation_db_path = getattr(mutation_index, "db_path", None)
        if not _coordination_held and mutation_db_path:
            with storage_writer_lease(
                mutation_db_path, timeout=0, operation="project docs ingest",
            ):
                with storage_mutation_lock(
                    mutation_db_path, timeout=0, operation="project docs ingest",
                ):
                    return self.ingest_project_docs(
                    str(root), skip_known=skip_known, with_vectors=with_vectors,
                    _candidate_paths=_candidate_paths, _coordination_held=True,
                )
        if hasattr(self.facade, "_project_ingest_project_docs_impl"):
            kwargs: dict[str, Any] = {"skip_known": skip_known, "with_vectors": with_vectors}
            if _candidate_paths is not None:
                kwargs["_candidate_paths"] = _candidate_paths
            return self.facade._project_ingest_project_docs_impl(str(root), **kwargs)
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
                    "lifecycle_status": candidate.lifecycle_status,
                    "temporal_relevance": temporal_relevance_for_status(candidate.lifecycle_status),
                    "index_freshness": "synchronized",
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
            from docmancer.docs.application.library_refresh_policy import bounded_exception_diagnostics
            safe = bounded_exception_diagnostics(exc, failure_phase="ingest", failure_operation="project_docs")
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
                warnings=[*warnings, safe["exception_message"]],
                message=safe["exception_message"],
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
            vector_sync=dict(getattr(agent, "last_vector_sync_metrics", {})),
            warnings=warnings,
            message=message,
        )
