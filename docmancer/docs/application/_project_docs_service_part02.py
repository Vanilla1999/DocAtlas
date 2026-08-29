"""ProjectDocsService implementation shard 2."""
from __future__ import annotations

from ._project_docs_service_shared import *  # noqa: F401,F403


class _ProjectDocsServicePart02:
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
                _coordination_held=True,
            )
        else:
            ingest_result = ProjectDocsIngestResult(
                status="success",
                project=metadata,
                candidate_count=0,
                message="No changed project docs required indexing.",
            )

        indexed_after = self._indexed_project_doc_sources(str(root))
        vector_sync: dict[str, Any] = {"status": "not_requested"}
        if with_vectors:
            sync_result = None
            if changed_candidates:
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
                    sync_result = sync_chunks(changed_section_ids)
                elif changed_section_ids:
                    raise RuntimeError(
                        "incremental vector sync requires an agent with scoped chunk support"
                    )
            else:
                sync_vectors = getattr(agent, "sync_vectors", None)
                if not callable(sync_vectors):
                    raise RuntimeError(
                        "unchanged vector parity requires an agent with full sync support"
                    )
                sync_result = sync_vectors()
            vector_sync = dict(getattr(agent, "last_vector_sync_metrics", {}))
            vector_sync.setdefault("requested", True)
            vector_sync.setdefault("retrieval_mode", self.config.retrieval.default_mode)
            if sync_result is None or vector_sync.get("status") != "success":
                raise RuntimeError(
                    "requested vector sync did not complete successfully: "
                    + str(vector_sync.get("reason") or vector_sync.get("status") or "unknown")
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
            "vector_sync": vector_sync,
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
        with_vectors: bool = False,
        changed_paths: list[str] | tuple[str, ...] | None = None,
        deleted_paths: list[str] | tuple[str, ...] | None = None,
        renamed_paths: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
        _coordination_held: bool = False,
    ) -> ProjectDocsSyncResult:
        root = validate_project_path(project_path).path
        mutation_config = getattr(self.facade, "config", None)
        mutation_index = getattr(mutation_config, "index", None)
        mutation_db_path = getattr(mutation_index, "db_path", None)
        if not _coordination_held and mutation_db_path:
            with storage_writer_lease(
                mutation_db_path, timeout=0, operation="project docs sync",
            ):
                with storage_mutation_lock(
                    mutation_db_path, timeout=0, operation="project docs sync",
                ):
                    return self.sync_project_docs(
                    str(root), with_vectors=with_vectors,
                    changed_paths=changed_paths, deleted_paths=deleted_paths,
                    renamed_paths=renamed_paths, _coordination_held=True,
                )
        if hasattr(self.facade, "_project_sync_project_docs_impl"):
            kwargs: dict[str, Any] = {"with_vectors": with_vectors}
            if changed_paths is not None:
                kwargs["changed_paths"] = changed_paths
            if deleted_paths is not None:
                kwargs["deleted_paths"] = deleted_paths
            if renamed_paths is not None:
                kwargs["renamed_paths"] = renamed_paths
            return self.facade._project_sync_project_docs_impl(str(root), **kwargs)
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

        ingest_result = self.ingest_project_docs(
            str(root), skip_known=True, with_vectors=with_vectors, _coordination_held=True,
        )
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
            diagnostics={
                "active_index": self.active_index_diagnostics(str(root)),
                "vector_sync": ingest_result.vector_sync,
            },
            warnings=[*warnings, *ingest_result.warnings],
            message=message,
        )

    def bootstrap_project_docs(
        self, project_path: str, question: str | None = None, *, allow_sync: bool = True,
    ) -> ProjectDocsBootstrapResult:
        root = validate_project_path(project_path).path
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

        if allow_sync and initial.reason_code in {"project_docs_found_not_indexed", "project_docs_stale"}:
            with_vectors = self._vector_sync_enabled()
            sync_result = self.sync_project_docs(str(root), with_vectors=with_vectors)
            actions_taken.append({
                "tool": "sync_project_docs",
                "arguments_patch": self._project_sync_arguments(root),
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
