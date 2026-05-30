from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LibraryInfo:
    library_id: str | None
    library: str
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = None
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
    source_type: str | None = None
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
    source_type: str | None = None
    message: str | None = None
    duration_ms: int = 0
    pages_indexed: int = 0
    pages_failed: int = 0
    chunks_indexed: int = 0
    targets_completed: int = 0
    targets_failed: int = 0


@dataclass(frozen=True)
class DocsTarget:
    library: str
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = "api"
    docs_url: str | None = None
    docs_url_template: str | None = None
    seed_urls: list[str] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    path_prefixes: list[str] = field(default_factory=list)
    max_pages: int = 200
    browser: bool = False
    doc_format: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocsTargetResult:
    canonical_id: str | None
    status: str
    library: str
    ecosystem: str | None
    version: str | None
    source_type: str | None
    docs_url: str | None = None
    pages_indexed: int = 0
    warnings: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True)
class DocsTargetsPrefetchResult:
    status: str
    results: list[DocsTargetResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str | None = None
    duration_ms: int = 0
    pages_indexed: int = 0
    pages_failed: int = 0
    chunks_indexed: int = 0
    targets_completed: int = 0
    targets_failed: int = 0


@dataclass(frozen=True)
class DocsJob:
    job_id: str
    kind: str
    status: str = "pending"
    phase: str = "validating"
    total_targets: int = 0
    completed_targets: int = 0
    failed_targets: int = 0
    current_target: str | None = None
    total_pages: int = 0
    completed_pages: int = 0
    failed_pages: int = 0
    total_chunks: int = 0
    completed_chunks: int = 0
    message: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    target_results: list[dict[str, Any]] = field(default_factory=list)
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True)
class DocsJobStartResult:
    job_id: str
    status: str
    message: str


@dataclass(frozen=True)
class DocsJobCancelResult:
    job_id: str
    status: str
    message: str


@dataclass(frozen=True)
class DocsManifestValidationResult:
    valid: bool
    manifest_path: str
    targets: list[DocsTarget] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocsInspectResult:
    canonical_id: str
    status: str
    library: str | None = None
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = None
    docs_url: str | None = None
    last_refreshed_at: str | None = None
    stale: bool = False
    pages: int = 0
    chunks: int = 0
    size_bytes: int = 0
    warnings: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True)
class DocsRemoveResult:
    canonical_id: str
    removed: bool
    chunks_removed: int = 0
    message: str | None = None


@dataclass(frozen=True)
class DocsPruneResult:
    dry_run: bool
    would_remove: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


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
