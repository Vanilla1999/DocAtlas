from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from filelock import FileLock

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.models import DocsChunk, DocsResult, LibraryInfo, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRecord, LibraryRegistry
from docmancer.docs.resolver import normalize_library_name, normalize_version
from docmancer.mcp import paths

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


class LibraryDocsService:
    def __init__(
        self,
        *,
        config: DocmancerConfig | None = None,
        registry: LibraryRegistry | None = None,
        agent: Any | None = None,
        project_reader: ProjectMetadataReader | None = None,
        stale_after_days: int = STALE_AFTER_DAYS,
    ):
        self.config = config or DocmancerConfig()
        self.registry = registry or LibraryRegistry(self.config.index.db_path)
        self._agent = agent
        self._agents: dict[str, Any] = {}
        self.project_reader = project_reader or ProjectMetadataReader()
        self.stale_after_days = stale_after_days

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _is_stale(self, last_refreshed_at: str | None) -> bool:
        if not last_refreshed_at:
            return True
        try:
            refreshed = datetime.fromisoformat(last_refreshed_at)
        except ValueError:
            return True
        if refreshed.tzinfo is None:
            refreshed = refreshed.replace(tzinfo=timezone.utc)
        return refreshed <= datetime.now(timezone.utc) - timedelta(days=self.stale_after_days)

    def _index_config_for(self, record: LibraryRecord) -> DocmancerConfig:
        config = self.config.model_copy(deep=True)
        root = paths.docmancer_home() / "docs-indexes"
        root.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(record.library_id) or "library"
        config.index.db_path = str(root / f"{safe}.db")
        config.index.extracted_dir = str(root / safe / "extracted")
        return config

    def _agent_instance(self, record: LibraryRecord | None = None) -> Any:
        if self._agent is None:
            if record is None:
                self._agent = DocmancerAgent(config=self.config)
            else:
                if record.library_id not in self._agents:
                    self._agents[record.library_id] = DocmancerAgent(config=self._index_config_for(record))
                return self._agents[record.library_id]
        return self._agent

    def _lock_for(self, library_id: str) -> FileLock:
        lock_dir = paths.docmancer_home() / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(library_id) or "library"
        return FileLock(str(lock_dir / f"docs-{safe}.lock"))

    def resolve_library(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
    ) -> LibraryInfo:
        normalized_version = normalize_version(version)
        if docs_url is None and docs_url_template and normalized_version:
            docs_url = self._render_docs_url(docs_url_template, library, normalized_version)

        record = self.registry.get(library, ecosystem, normalized_version)
        if record is None and docs_url:
            record = self.registry.upsert(
                library=library,
                ecosystem=ecosystem,
                version=normalized_version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                now=self._now(),
                status="available",
            )
        if record is None:
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
            )
        if docs_url and docs_url != record.docs_url:
            record = self.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=docs_url,
                docs_url_template=docs_url_template,
                now=self._now(),
                status="available",
            )
        stale = self._is_stale(record.last_refreshed_at)
        return LibraryInfo(
            library_id=record.library_id,
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            docs_url=record.docs_url,
            docs_url_template=record.docs_url_template,
            status=record.status or "available",
            local=record.last_refreshed_at is not None,
            stale=stale,
            last_refreshed_at=record.last_refreshed_at,
            message=record.last_error,
        )

    def _record_from_info(self, info: LibraryInfo) -> LibraryRecord | None:
        if info.library_id is None:
            return None
        return self.registry.get(info.library_id, None)

    @staticmethod
    def _render_docs_url(template: str, library: str, version: str) -> str:
        return template.format(library=library, version=version)

    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return self.project_reader.read(project_path)

    @staticmethod
    def _is_flutter_library(library: str) -> bool:
        return normalize_library_name(library) in {"flutter", "flutter-api"}

    @staticmethod
    def _flutter_docs_url_for(version: str | None, channel: str | None) -> str:
        selected = (channel or version or "").lower()
        if selected in {"main", "master"}:
            return "https://main-api.flutter.dev/"
        return "https://api.flutter.dev/"

    @staticmethod
    def _flutter_docs_version_for(version: str | None, channel: str | None) -> str | None:
        selected = (channel or version or "").lower()
        if selected in {"main", "master"}:
            return "main"
        if channel:
            return channel
        if version:
            return "stable"
        return None

    def _project_version_for(
        self,
        *,
        library: str,
        ecosystem: str | None,
        project_path: str | None,
    ) -> tuple[str | None, str | None, str | None, list[str], str | None, bool | None]:
        if not project_path:
            return None, None, None, [], None, None
        metadata = self.read_project_metadata(project_path)
        warnings = list(metadata.warnings)
        if self._is_flutter_library(library):
            selected = self._flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if selected:
                if metadata.flutter_version and selected == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                return (
                    selected,
                    self._flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                    None,
                    warnings,
                    metadata.flutter_version or metadata.flutter_channel,
                    False,
                )
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None

        if ecosystem == "pub" or library in metadata.packages:
            version = metadata.packages.get(library)
            if version:
                return version, None, PUB_DOCS_URL_TEMPLATE, warnings, version, True
            warnings.append(PACKAGE_NOT_FOUND_WARNING)
            warnings.append(NO_PROJECT_VERSION_WARNING)
            return None, None, None, warnings, None, None

        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, None, None

    @staticmethod
    def _join_warnings(*items: str | None, extra: list[str] | None = None) -> str | None:
        values = [item for item in items if item]
        if extra:
            values.extend(extra)
        return " ".join(values) if values else None

    def _refresh_record(self, record: LibraryRecord, *, force: bool) -> RefreshResult:
        if not record.docs_url:
            return RefreshResult(
                library_id=record.library_id,
                status="needs_docs_url",
                docs_url=None,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                message="Pass docs_url to ingest this library.",
            )
        if not force and not self._is_stale(record.last_refreshed_at):
            return RefreshResult(
                library_id=record.library_id,
                status="skipped",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
            )

        try:
            self._agent_instance(record).add(record.docs_url, recreate=False)
        except Exception as exc:
            self.registry.upsert(
                library=record.name,
                ecosystem=record.ecosystem,
                version=record.version,
                docs_url=record.docs_url,
                docs_url_template=record.docs_url_template,
                now=self._now(),
                status="failed",
                last_error=str(exc),
            )
            return RefreshResult(
                library_id=record.library_id,
                status="failed",
                docs_url=record.docs_url,
                last_refreshed_at=record.last_refreshed_at,
                version=record.version,
                message=str(exc),
            )

        refreshed_at = self._now()
        self.registry.upsert(
            library=record.name,
            ecosystem=record.ecosystem,
            version=record.version,
            docs_url=record.docs_url,
            docs_url_template=record.docs_url_template,
            now=refreshed_at,
            status="available",
            last_refreshed_at=refreshed_at,
            last_error="",
        )
        return RefreshResult(
            library_id=record.library_id,
            status="updated",
            docs_url=record.docs_url,
            last_refreshed_at=refreshed_at,
            version=record.version,
        )

    def refresh_docs(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        versions: list[str] | None = None,
        docs_url_template: str | None = None,
        force: bool = True,
    ) -> RefreshResult:
        if versions:
            updated = skipped = failed = needs_url = 0
            last: RefreshResult | None = None
            for item_version in versions:
                last = self.refresh_docs(
                    library,
                    ecosystem=ecosystem,
                    version=item_version,
                    docs_url=docs_url if len(versions) == 1 else None,
                    docs_url_template=docs_url_template,
                    force=force,
                )
                if last.status == "updated":
                    updated += 1
                elif last.status == "skipped":
                    skipped += 1
                elif last.status == "needs_docs_url":
                    needs_url += 1
                else:
                    failed += 1
            status = "failed" if failed else ("needs_docs_url" if needs_url else ("updated" if updated else "skipped"))
            return RefreshResult(
                library_id=None,
                status=status,
                docs_url=docs_url_template or docs_url,
                last_refreshed_at=last.last_refreshed_at if last else None,
                message=f"updated={updated} skipped={skipped} failed={failed} needs_docs_url={needs_url}",
            )

        info = self.resolve_library(library, ecosystem, version, docs_url, docs_url_template)
        record = self._record_from_info(info)
        if record is None:
            return RefreshResult(
                library_id=None,
                status="needs_docs_url",
                docs_url=docs_url,
                last_refreshed_at=None,
                version=version,
                message="Pass docs_url to ingest this library.",
            )
        with self._lock_for(record.library_id):
            record = self.registry.get(record.library_id, None) or record
            return self._refresh_record(record, force=force)

    def prefetch_docs(
        self,
        library: str,
        ecosystem: str | None = None,
        versions: list[str] | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
    ) -> RefreshResult:
        selected_versions = versions or ["latest"]
        result = self.refresh_docs(
            library,
            ecosystem=ecosystem,
            versions=selected_versions,
            docs_url=docs_url,
            docs_url_template=docs_url_template,
            force=force_refresh,
        )
        messages = []
        if not versions:
            messages.append("No versions were provided; defaulted to latest.")
        if continue_on_error is False:
            messages.append("continue_on_error=false requested; refresh currently reports per-version failures without aborting.")
        if result.message:
            messages.append(result.message)
        if messages:
            return RefreshResult(
                library_id=result.library_id,
                status=result.status,
                docs_url=result.docs_url,
                last_refreshed_at=result.last_refreshed_at,
                version=result.version,
                message=" ".join(messages),
            )
        return result

    def get_docs(
        self,
        library: str,
        topic: str | None = None,
        tokens: int | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        force_refresh: bool = False,
        project_path: str | None = None,
    ) -> DocsResult:
        project_warnings: list[str] = []
        requested_version = version
        version_source = "explicit" if version is not None else None
        docs_snapshot_exact: bool | None = None
        if version is None and project_path:
            project_version, project_docs_url, project_template, project_warnings, requested_version, docs_snapshot_exact = self._project_version_for(
                library=library,
                ecosystem=ecosystem,
                project_path=project_path,
            )
            if project_version:
                version = project_version
                version_source = "project"
                docs_url = docs_url or project_docs_url
                docs_url_template = docs_url_template or project_template
        elif version is not None and ecosystem == "pub":
            docs_snapshot_exact = True

        info = self.resolve_library(library, ecosystem, version, docs_url, docs_url_template)
        if info.library_id is None:
            warning = self._join_warnings("needs_docs_url", extra=project_warnings)
            warnings = [warning] if warning else []
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
            )

        stale_before = info.stale
        refreshed = False
        warning = None
        if version is None and info.version == "latest":
            warning = "No version was provided; using latest/default docs."
        if project_warnings:
            warning = self._join_warnings(warning, extra=project_warnings)
        warnings = [warning] if warning else []
        if force_refresh or stale_before:
            result = self.refresh_docs(info.library_id, ecosystem=None, docs_url=docs_url, force=force_refresh)
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
                        [],
                        warnings=warnings,
                        requested_version=requested_version,
                        resolved_version=info.version,
                        version_source=version_source,
                        docs_snapshot_exact=docs_snapshot_exact,
                    )

        latest = self.resolve_library(info.library_id)
        record = self.registry.get(info.library_id)
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
                [],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=info.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
            )
        query = f"{info.library} {topic}".strip() if topic else info.library
        chunks = self._agent_instance(record).query(query, budget=tokens or DEFAULT_DOC_TOKENS)
        if any((chunk.metadata or {}).get("library_id") for chunk in chunks):
            chunks = [chunk for chunk in chunks if (chunk.metadata or {}).get("library_id") == info.library_id]
        return DocsResult(
            library_id=info.library_id,
            library=latest.library,
            version=latest.version,
            topic=topic,
            refreshed=refreshed,
            stale_before_refresh=stale_before,
            warning=warning,
            last_refreshed_at=latest.last_refreshed_at,
            results=[
                DocsChunk(
                    title=(chunk.metadata or {}).get("title"),
                    content=chunk.text,
                    source=chunk.source,
                    url=chunk.source if chunk.source.startswith(("http://", "https://")) else None,
                )
                for chunk in chunks
            ],
            warnings=warnings,
            requested_version=requested_version,
            resolved_version=latest.version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
        )

    def prefetch_project_docs(
        self,
        project_path: str,
        include_flutter: bool = True,
        include_dart: bool = False,
        include_packages: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
    ) -> ProjectPrefetchResult:
        metadata = self.read_project_metadata(project_path)
        results: list[RefreshResult] = []
        warnings = list(metadata.warnings)

        if include_flutter:
            flutter_version = self._flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if flutter_version:
                if metadata.flutter_version and flutter_version == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                results.append(
                    self.refresh_docs(
                        "flutter-api",
                        version=flutter_version,
                        docs_url=self._flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                        force=force_refresh,
                    )
                )
            else:
                warnings.append(NO_PROJECT_VERSION_WARNING)
                results.append(
                    RefreshResult(
                        library_id="flutter-api",
                        status="needs_docs_url",
                        docs_url=None,
                        last_refreshed_at=None,
                        message=NO_PROJECT_VERSION_WARNING,
                    )
                )

        if include_dart:
            warnings.append("Dart SDK documentation version detection is not implemented.")

        for package in include_packages or []:
            version = metadata.packages.get(package)
            if not version:
                warnings.append(f"{package}: {PACKAGE_NOT_FOUND_WARNING}")
                results.append(
                    RefreshResult(
                        library_id=package,
                        status="needs_docs_url",
                        docs_url=None,
                        last_refreshed_at=None,
                        message=PACKAGE_NOT_FOUND_WARNING,
                    )
                )
                continue
            results.append(
                self.refresh_docs(
                    package,
                    ecosystem="pub",
                    version=version,
                    docs_url_template=PUB_DOCS_URL_TEMPLATE,
                    force=force_refresh,
                )
            )

        return ProjectPrefetchResult(project=metadata, results=results, warnings=warnings)

    def list_libraries(self, stale_only: bool = False, limit: int | None = None) -> list[LibraryInfo]:
        items: list[LibraryInfo] = []
        for record in self.registry.list(limit=limit):
            stale = self._is_stale(record.last_refreshed_at)
            if stale_only and not stale:
                continue
            items.append(
                LibraryInfo(
                    library_id=record.library_id,
                    library=record.name,
                    ecosystem=record.ecosystem,
                    version=record.version,
                    docs_url=record.docs_url,
                    docs_url_template=record.docs_url_template,
                    status=record.status,
                    local=record.last_refreshed_at is not None,
                    stale=stale,
                    last_refreshed_at=record.last_refreshed_at,
                    message=record.last_error,
                )
            )
        return items


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
