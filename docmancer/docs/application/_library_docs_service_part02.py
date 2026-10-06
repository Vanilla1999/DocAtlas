"""Explicit finite target callers and guarded library publication adapters."""
from __future__ import annotations

from typing import Callable
from copy import deepcopy
import sqlite3

from ._library_docs_service_shared import *  # noqa: F401,F403
from docmancer.docs.finite_membership import contains, finite_members, selected_robots
from docmancer.docs.infrastructure.storage_mutation_lock import storage_writer_lease
from docmancer.docs.application.library_refresh_policy import refresh_failure_code, retryable_failure, safe_failure_message
from docmancer.docs.resolver import normalize_library_name, normalize_version


class _FiniteStagingGateway:
    """Per-operation forwarding adapter; no shared gateway/agent mutation."""

    def __init__(self, gateway: Any, expected: tuple[str, ...]):
        self.gateway = gateway
        self.expected = set(expected)
        self.config = None
        self.failed = False
        self.calls = 0
        self.failure = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.gateway, name)

    def agent_for_config(self, config: Any) -> Any:
        agent = self.gateway.agent_for_config(config)
        self.config = config
        boundary = self

        class AgentForwarder:
            def __getattr__(self, name: str) -> Any:
                return getattr(agent, name)

            def add(self, *args: Any, **kwargs: Any) -> Any:
                boundary.calls += 1
                try:
                    result = agent.add(*args, **kwargs)
                except Exception as exc:
                    boundary.failed = True
                    boundary.failure = exc
                    raise
                diagnostics = getattr(agent, "last_discovery_diagnostics", {}) or {}
                if (type(result) is not int or result <= 0
                        or diagnostics.get("complete") is not True
                        or diagnostics.get("page_failure_count", 0)
                        or getattr(agent, "last_fetch_failure", None) is not None):
                    boundary.failed = True
                return result

        return AgentForwarder()

    def complete(self) -> bool:
        if self.failed or not self.calls or self.config is None:
            return False
        return self.sources_match(self.config, self.expected)

    @staticmethod
    def sources_match(config: Any, expected: set[str]) -> bool:
        path = Path(config.index.db_path).expanduser().resolve()
        try:
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
                sources = {row[0] for row in conn.execute(
                    "SELECT source FROM sources LIMIT ?", (len(expected) + 1,),
                )}
            return sources == expected
        except (OSError, sqlite3.Error):
            return False


class _LibraryDocsApplicationServicePart02:
    @staticmethod
    def _stored_refresh_identity_matches(spec: dict[str, Any], record: LibraryRecord) -> bool:
        """Bind each identity component, including those omitted by canonical IDs."""
        def identity(library: Any, ecosystem: Any, version: Any, source: Any) -> tuple | None:
            values = (library, ecosystem, version, source)
            if any(value is not None and (not isinstance(value, str)
                    or not value.strip() or any(ord(char) < 32 for char in value)) for value in values):
                return None
            if not isinstance(library, str) or not normalize_library_name(library):
                return None
            if ecosystem is not None and not normalize_library_name(ecosystem):
                return None
            if version is not None and (any(char.isspace() for char in version.strip())
                    or any(char in version for char in ":/@?#\\")):
                return None
            # Missing is the existing technical API default; blank/unknown is not.
            normalized_source = normalize_library_name(source if source is not None else "api")
            if normalized_source not in {"api", "guides", "tutorials", "migration", "reference", "specification"}:
                return None
            return (normalize_library_name(library),
                    normalize_library_name(ecosystem) if ecosystem is not None else None,
                    normalize_version(version), normalized_source)

        stored = identity(spec.get("library"), spec.get("ecosystem"), spec.get("version"), spec.get("source_type"))
        actual = identity(record.name, record.ecosystem, record.version, record.source_type)
        return (stored is not None and stored == actual
                and canonical_library_id(*stored) == record.library_id)

    def refresh_docs(
        self, library: str, ecosystem: str | None = None,
        version: str | None = None, docs_url: str | None = None,
        versions: list[str] | None = None, docs_url_template: str | None = None,
        source_type: str | None = None, force: bool = True,
        continue_on_error: bool = True, target: DocsTarget | None = None,
    ) -> RefreshResult:
        if target is None:
            record = self.registry.get(library, ecosystem, version, source_type)
            spec = deepcopy(record.target_spec) if record is not None else None
            required = {"library", "ecosystem", "version", "source_type", "docs_url", "docs_url_template", "seed_urls", "allowed_domains", "path_prefixes", "max_pages", "source_manifest"}
            if isinstance(spec, dict) and spec:
                if (not {"library", "ecosystem", "version", "source_type"}.issubset(spec)
                        or not self._stored_refresh_identity_matches(spec, record)):
                    return LibraryIngestOrchestrator.unresolved(library, "explicit_target_identity_mismatch")
            if isinstance(spec, dict) and required.issubset(spec):
                target = DocsTarget(**{key: value for key, value in spec.items() if key in DocsTarget.__dataclass_fields__})
                if library == record.library_id:
                    library = target.library
        if version is not None and isinstance(target, DocsTarget) and target.version != version:
            return LibraryIngestOrchestrator.unresolved(library, "explicit_target_identity_mismatch")
        selected_versions = versions if versions is not None else ([version] if version is not None else None)
        return self.ingest_orchestrator.prefetch_docs(
            library, ecosystem=ecosystem, versions=selected_versions,
            docs_url=docs_url, docs_url_template=docs_url_template,
            source_type=source_type, force_refresh=force,
            continue_on_error=continue_on_error,
            target_plan=[target] if target is not None else None,
        )

    def prefetch_docs(
        self, library: str, ecosystem: str | None = None,
        versions: list[str] | None = None, docs_url: str | None = None,
        docs_url_template: str | None = None, source_type: str | None = None,
        force_refresh: bool = False, continue_on_error: bool = True,
        async_: bool = False, query: str | None = None,
        target: DocsTarget | None = None,
    ) -> RefreshResult | DocsTargetsPrefetchResult | DocsJobStartResult:
        # Runtime query is not selection, identity or network permission.
        if isinstance(target, DocsTarget) and query is not None:
            target = replace(target, query=query)
        return self.ingest_orchestrator.prefetch_docs(
            library, ecosystem=ecosystem, versions=versions,
            docs_url=docs_url, docs_url_template=docs_url_template,
            source_type=source_type, force_refresh=force_refresh,
            continue_on_error=continue_on_error, async_=async_,
            target_plan=[target] if target is not None else None,
        )

    def _prefetch_explicit_targets(
        self, targets: list[DocsTarget], *, force_refresh: bool = False,
        continue_on_error: bool = True, job_id: str | None = None,
        deadline_at: float | None = None,
        should_cancel: Callable[[], bool] | None = None,
        begin_commit: Callable[[], bool] | None = None,
        staging_owner: dict[str, str] | None = None,
    ) -> RefreshResult:
        """Persist only explicit selection; reuse the existing guarded transaction.

        One target cannot authorize extra versions or sibling sources. Both sync
        and async use staging; cancellation/deadline/generation guards reach the
        unchanged refresh/publication implementation, rather than the old target
        prefetch adapter which did not accept commit guards.
        """
        if len(targets) != 1 or not isinstance(targets[0], DocsTarget):
            return LibraryIngestOrchestrator.unresolved("", "explicit_target_required")
        target = targets[0]
        if (type(target.max_pages) is not int or target.max_pages <= 0
                or not isinstance(target.source_manifest, dict)
                or any(not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                       for values in (target.seed_urls, target.allowed_domains, target.path_prefixes))):
            return LibraryIngestOrchestrator.unresolved(target.library, "invalid_explicit_target")
        urls, error = self.facade._target_urls(target)
        if error:
            return LibraryIngestOrchestrator.unresolved(target.library, "invalid_explicit_target")
        try:
            members = finite_members(urls, target.max_pages)
            manifest = target.source_manifest
            if manifest:
                target = self.facade.docs_targets.resolve_github_directory_target(target)
            else:
                if any(urlparse(url).hostname in {"github.com", "raw.githubusercontent.com"} for url in members):
                    raise ValueError("resolved_github_manifest_required")
                controls = tuple(selected_robots(urls))
                if any(not contains(controls, f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt") for url in members):
                    raise ValueError("explicit_robots_member_required")
            spec = self.facade._target_to_spec(target, list(members))
        except ValueError as exc:
            return LibraryIngestOrchestrator.unresolved(target.library, str(exc))

        def cancelled() -> bool:
            return bool((should_cancel and should_cancel())
                        or (deadline_at is not None and time.monotonic() >= deadline_at))

        def commit_guard() -> bool:
            if cancelled():
                return False
            if not gateway.complete():
                refused[0] = True
                return False
            return begin_commit is None or begin_commit()

        if cancelled():
            return RefreshResult(library_id=None, status="cancelled", docs_url=target.docs_url, last_refreshed_at=None)
        library_id = canonical_library_id(target.library, target.ecosystem, target.version, target.source_type)
        with storage_writer_lease(
            str(Path(self.config.index.db_path).expanduser().resolve()), timeout=1.0,
            operation=f"explicit target refresh {library_id}",
        ), self._lock_for(library_id):
            if cancelled():
                return RefreshResult(library_id=library_id, status="cancelled", docs_url=target.docs_url, last_refreshed_at=None)
            previous = self.registry.get(library_id, source_type=target.source_type)
            if previous is not None and previous.library_id != library_id:
                return LibraryIngestOrchestrator.unresolved(target.library, "explicit_target_identity_mismatch")
            if previous and previous.target_spec:
                for key in ("active_source_manifest", "active_manifest_digest", "last_complete_manifest_digest"):
                    if key in previous.target_spec:
                        spec[key] = previous.target_spec[key]
            unchanged = previous is not None and all((previous.target_spec or {}).get(key) == value for key, value in spec.items())
            active_members_match = previous is not None and _FiniteStagingGateway.sources_match(self._index_config_for(previous), set(members))
            record = self.registry.upsert(
                library=target.library, ecosystem=target.ecosystem,
                version=target.version, source_type=target.source_type,
                docs_url=target.docs_url or members[0],
                docs_url_template=target.docs_url_template, target_spec=spec,
                now=self._now(), status=previous.status if unchanged else "pending",
            )
            gateway = _FiniteStagingGateway(self.agent_gateway, members)
            refused = [False]
            scoped_refresh = LibraryRefreshOps(replace(self.refresh_ops.ports, agent_gateway=gateway))

            def refused_result() -> RefreshResult:
                if gateway.failure is None:
                    return LibraryIngestOrchestrator.unresolved(target.library, "finite_staging_incomplete")
                exc = gateway.failure
                reason = refresh_failure_code(exc)
                return RefreshResult(
                    library_id=record.library_id, status="failed", docs_url=target.docs_url,
                    last_refreshed_at=previous.last_refreshed_at if previous else None,
                    version=target.version, source_type=target.source_type,
                    targets_failed=1, pages_failed=1, reason_codes=[reason],
                    message=safe_failure_message(exc, reason),
                    preindex={"reason_code": reason, "failure_phase": getattr(exc, "phase", "indexing"),
                              "failed_url": getattr(exc, "failed_url", None),
                              "http_status": getattr(exc, "status_code", None),
                              "retryable": retryable_failure(exc, reason)},
                )
            try:
                result = scoped_refresh.refresh_record(
                    record, force=force_refresh or not unchanged or not active_members_match,
                    should_cancel=cancelled, deadline_at=deadline_at,
                    begin_commit=commit_guard, staging_owner=staging_owner,
                    lock_held=True,
                )
            except Exception:
                if previous is not None:
                    self.registry.restore(previous)
                if refused[0]:
                    return refused_result()
                raise
            if result.status not in {"updated", "ok", "skipped"} and previous is not None:
                self.registry.restore(previous)
            if refused[0]:
                return refused_result()
            return result

    def resume_interrupted_jobs(self) -> list[str]:
        resumed: list[str] = []
        for interrupted in self.jobs.list(status="interrupted"):
            payload = dict(interrupted.request_payload or {})
            if (interrupted.kind != "prefetch_library_docs"
                    or interrupted.reason_code != "job_interrupted"
                    or interrupted.resumed_by_job_id or not payload.get("library")):
                continue
            target_plan = [DocsTarget(**item) for item in payload.pop("target_plan", [])]
            started = self.ingest_orchestrator.prefetch_docs(
                str(payload.get("library")), ecosystem=payload.get("ecosystem"),
                versions=list(payload.get("versions") or []) or None,
                docs_url=payload.get("docs_url"), docs_url_template=payload.get("docs_url_template"),
                source_type=payload.get("source_type"),
                force_refresh=bool(payload.get("force_refresh")),
                continue_on_error=bool(payload.get("continue_on_error", True)),
                async_=True, target_plan=target_plan or None,
            )
            if isinstance(started, DocsJobStartResult):
                self.jobs.update(
                    interrupted.job_id, reason_code="job_resumed", retryable=False,
                    resumed_by_job_id=started.job_id,
                    message=f"Interrupted job resumed as {started.job_id}.",
                )
                resumed.append(started.job_id)
        return resumed

    def _library_job_timeout_seconds(self) -> float:
        return float(getattr(self.config.web_fetch, "library_job_timeout_seconds", 120.0))
