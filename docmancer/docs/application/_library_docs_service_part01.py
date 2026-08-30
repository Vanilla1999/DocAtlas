"""LibraryDocsApplicationService implementation shard 1."""
from __future__ import annotations

from ._library_docs_service_shared import *  # noqa: F401,F403


class _LibraryDocsApplicationServicePart01:
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
                storage_identity=lambda: str(Path(self.config.index.db_path).expanduser().resolve()),
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
