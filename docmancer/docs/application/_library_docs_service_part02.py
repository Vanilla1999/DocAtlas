"""LibraryDocsApplicationService implementation shard 2."""
from __future__ import annotations

from ._library_docs_service_shared import *  # noqa: F401,F403


class _LibraryDocsApplicationServicePart02:
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
        query: str | None = None,
    ) -> RefreshResult | DocsTargetsPrefetchResult | DocsJobStartResult:
        flutter_targets = self._flutter_targets_for_request(
            library,
            ecosystem,
            versions,
            docs_url,
            docs_url_template,
        )
        if flutter_targets:
            if query:
                flutter_targets = [replace(target, query=query) for target in flutter_targets]
            return self.ingest_orchestrator.prefetch_docs(
                library,
                ecosystem="flutter",
                versions=versions,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                async_=async_,
                target_plan=flutter_targets,
            )
        if query and ecosystem in {"pub", "dart"} and versions:
            version = versions[0]
            query_target = DocsTarget(
                library=library,
                ecosystem="pub",
                version=version,
                source_type=source_type or "api",
                docs_url=docs_url or pub_dartdoc_root_url(library, version),
                allowed_domains=["pub.dev"],
                path_prefixes=[f"/documentation/{library}/{version}/"],
                max_pages=40,
                doc_format="dartdoc",
                query=query,
            )
            return self.ingest_orchestrator.prefetch_docs(
                library,
                ecosystem="pub",
                versions=versions,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                async_=async_,
                target_plan=[query_target],
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

    def resume_interrupted_jobs(self) -> list[str]:
        resumed: list[str] = []
        for interrupted in self.jobs.list(status="interrupted"):
            payload = dict(interrupted.request_payload or {})
            if (
                interrupted.kind != "prefetch_library_docs"
                or interrupted.reason_code != "job_interrupted"
                or interrupted.resumed_by_job_id
                or not payload.get("library")
            ):
                continue
            target_plan = [DocsTarget(**item) for item in payload.pop("target_plan", [])]
            started = self.ingest_orchestrator.prefetch_docs(
                str(payload.get("library")),
                ecosystem=payload.get("ecosystem"),
                versions=list(payload.get("versions") or []),
                docs_url=payload.get("docs_url"),
                docs_url_template=payload.get("docs_url_template"),
                source_type=payload.get("source_type"),
                force_refresh=bool(payload.get("force_refresh")),
                continue_on_error=bool(payload.get("continue_on_error", True)),
                async_=True,
                target_plan=target_plan or None,
            )
            if isinstance(started, DocsJobStartResult):
                self.jobs.update(
                    interrupted.job_id,
                    reason_code="job_resumed",
                    retryable=False,
                    resumed_by_job_id=started.job_id,
                    message=f"Interrupted job resumed as {started.job_id}.",
                )
                resumed.append(started.job_id)
        return resumed

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
