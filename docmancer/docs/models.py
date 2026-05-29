from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LibraryInfo:
    library_id: str | None
    library: str
    ecosystem: str | None = None
    version: str | None = None
    docs_url: str | None = None
    docs_url_template: str | None = None
    status: str = "needs_docs_url"
    local: bool = False
    stale: bool = False
    last_refreshed_at: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class DocsChunk:
    title: str | None
    content: str
    source: str | None
    url: str | None


@dataclass(frozen=True)
class DocsResult:
    library_id: str
    library: str
    version: str | None
    topic: str | None
    refreshed: bool
    stale_before_refresh: bool
    warning: str | None
    last_refreshed_at: str | None
    results: list[DocsChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requested_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None
    docs_snapshot_exact: bool | None = None


@dataclass(frozen=True)
class RefreshResult:
    library_id: str | None
    status: str
    docs_url: str | None
    last_refreshed_at: str | None
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class ProjectMetadata:
    project_path: str
    flutter_version: str | None = None
    flutter_channel: str | None = None
    dart_version: str | None = None
    packages: dict[str, str] = field(default_factory=dict)
    direct_dependencies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectPrefetchResult:
    project: ProjectMetadata
    results: list[RefreshResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
