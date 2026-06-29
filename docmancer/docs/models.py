from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SOURCE_CLASS_PROJECT_FILE = "project_file"
SOURCE_CLASS_LOCAL_MEMORY = "local_memory"
SOURCE_CLASS_DEPENDENCY_DOCS = "dependency_docs"
SOURCE_CLASS_PUBLIC_DOCS = "public_docs"
SOURCE_CLASSES = {
    SOURCE_CLASS_PROJECT_FILE,
    SOURCE_CLASS_LOCAL_MEMORY,
    SOURCE_CLASS_DEPENDENCY_DOCS,
    SOURCE_CLASS_PUBLIC_DOCS,
}


@dataclass(frozen=True)
class LibraryInfo:
    library_id: str | None
    library: str
    source_id: str | None = None
    canonical_id: str | None = None
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = None
    docs_url: str | None = None
    docs_url_template: str | None = None
    docs_url_resolved: str | None = None
    docs_snapshot_exact: bool | None = None
    requested_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None
    version_confidence: str | None = None
    version_inferred: bool | None = None
    status: str = "needs_docs_url"
    local: bool = False
    stale: bool = False
    last_refreshed_at: str | None = None
    pages: int = 0
    chunks: int = 0
    reason_code: str | None = None
    message: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DocsChunk:
    title: str | None
    content: str
    source: str | None
    url: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectDocsChunk(DocsChunk):
    source_class: str | None = None
    path: str | None = None
    heading_path: str | None = None
    content_hash: str | None = None
    mtime_ns: int | None = None
    stale: bool = False
    doc_scope: str = "project"
    module_id: str | None = None
    module_name: str | None = None
    module_path: str | None = None
    module_type: str | None = None


@dataclass(frozen=True)
class DocsSourceResolution:
    """Effective documentation source selected for a docs tool call."""

    info: LibraryInfo
    docs_url_source: str | None = None
    has_registered_source: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


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
    docs_exactness: str | None = None
    docs_binding_source: str | None = None
    confidence: str | None = None
    tool: str = "get_library_docs"
    schema_version: str = "2.0-mvp"
    status: str = "success"
    decision: str = "answer_returned"
    request: dict[str, Any] = field(default_factory=dict)
    identity: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    response_style: str = "evidence-first"
    primary_snippet: dict[str, Any] | None = None
    supporting_snippets: list[dict[str, Any]] = field(default_factory=list)
    snippet_metrics: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    result: Any = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    discovery_candidates: list[dict[str, Any]] = field(default_factory=list)


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
    preindex: dict[str, Any] | None = None


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
    current_url: str | None = None
    discovered_pages: int = 0
    fetched_pages: int = 0
    indexed_pages: int = 0
    total_pages: int = 0
    completed_pages: int = 0
    failed_pages: int = 0
    total_chunks: int = 0
    completed_chunks: int = 0
    message: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    target_results: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str | None = None
    updated_at: str | None = None
    last_event_at: str | None = None
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
    source_id: str | None = None
    library: str | None = None
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = None
    docs_url: str | None = None
    docs_url_resolved: str | None = None
    docs_snapshot_exact: bool | None = None
    requested_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None
    version_confidence: str | None = None
    version_inferred: bool | None = None
    last_refreshed_at: str | None = None
    stale: bool = False
    pages: int = 0
    chunks: int = 0
    reason_code: str = ""
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
class DependencyObservation:
    ecosystem: str
    package_name: str
    workspace_member: str | None = None
    dependency_group: str = "dependencies"
    specifier_kind: str = "unknown"
    specifier_raw: str | None = None
    resolved_version: str | None = None
    version_source: str = "unknown"
    source_kind: str = "registry"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectDocsCandidate:
    path: str
    source_class: str = SOURCE_CLASS_PROJECT_FILE
    reason: str = "project_docs"
    size_bytes: int = 0
    mtime_ns: int | None = None
    content_hash: str | None = None
    doc_scope: str = "project"
    module_id: str | None = None
    module_name: str | None = None
    module_path: str | None = None
    module_type: str | None = None


@dataclass(frozen=True)
class ProjectMetadata:
    project_path: str
    flutter_version: str | None = None
    flutter_channel: str | None = None
    dart_version: str | None = None
    packages: dict[str, str] = field(default_factory=dict)
    direct_dependencies: list[str] = field(default_factory=list)
    dependencies: list[DependencyObservation] = field(default_factory=list)
    docs_candidates: list[ProjectDocsCandidate] = field(default_factory=list)
    detected_ecosystems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchConstraint:
    id: str
    type: str
    instruction: str
    source: str
    severity: str
    confidence: str
    evidence: str
    symbols: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchConstraintPacket:
    task: str
    constraints: list[PatchConstraint] = field(default_factory=list)
    forbidden_edits: list[PatchConstraint] = field(default_factory=list)
    dependency_contracts: list[PatchConstraint] = field(default_factory=list)
    source_of_truth_rules: list[PatchConstraint] = field(default_factory=list)
    suggested_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    symbol_candidates: list[dict[str, Any]] = field(default_factory=list)
    ignored_generated_artifact_sources: list[str] = field(default_factory=list)
    excluded_source_reasons: list[dict[str, str]] = field(default_factory=list)
    excluded_source_count: int = 0
    token_estimate: int = 0
    confidence: str = "low"


@dataclass(frozen=True)
class PatchConstraintValidationResult:
    constraint_id: str
    status: str
    reason: str
    files: list[str] = field(default_factory=list)
    evidence: str | None = None


@dataclass(frozen=True)
class PatchConstraintValidationPacket:
    task: str | None = None
    project_path: str | None = None
    total_constraints: int = 0
    satisfied: int = 0
    violated: int = 0
    unknown: int = 0
    results: list[PatchConstraintValidationResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: str = "low"


@dataclass(frozen=True)
class ProjectPrefetchResult:
    project: ProjectMetadata
    results: list[RefreshResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detected_ecosystems: list[str] = field(default_factory=list)
    resolution_summary: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectDocsInspectResult:
    project_detected: bool
    project_path: str
    reason_code: str | None = None
    next_action: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    project_type: list[str] = field(default_factory=list)
    project_docs: dict[str, Any] = field(default_factory=dict)
    dependency_sources: dict[str, Any] = field(default_factory=dict)
    candidate_sources: list[dict[str, Any]] = field(default_factory=list)
    indexed_sources: list[dict[str, Any]] = field(default_factory=list)
    stale_sources: list[dict[str, Any]] = field(default_factory=list)
    ignored_sources: list[dict[str, Any]] = field(default_factory=list)
    recommended_next_actions: list[dict[str, Any]] = field(default_factory=list)
    arguments_patch: dict[str, Any] = field(default_factory=dict)
    agent_message: str | None = None
    user_message: str | None = None
    agent_guidance: str | None = None
    source_state_guidance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectDocsIngestResult:
    status: str
    project: ProjectMetadata
    candidate_count: int = 0
    indexed_sources: list[dict[str, Any]] = field(default_factory=list)
    missing_sources: list[dict[str, Any]] = field(default_factory=list)
    skipped_sources: list[dict[str, Any]] = field(default_factory=list)
    sections_indexed: int = 0
    warnings: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True)
class ProjectDocsSyncResult:
    status: str
    project: ProjectMetadata
    candidate_count: int = 0
    current_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    orphaned_count: int = 0
    orphaned_removed: int = 0
    dedup_removed: int = 0
    stale_removed: int = 0
    sections_indexed: int = 0
    indexed_sources: list[dict[str, Any]] = field(default_factory=list)
    stale_sources: list[dict[str, Any]] = field(default_factory=list)
    missing_sources: list[dict[str, Any]] = field(default_factory=list)
    removed_sources: list[dict[str, Any]] = field(default_factory=list)
    skipped_sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True)
class ProjectDocsBootstrapResult:
    project_path: str
    question: str | None = None
    status: str = "ready"
    tool: str = "bootstrap_project_docs"
    reason_code: str | None = None
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    next_action: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    arguments_patch: dict[str, Any] = field(default_factory=dict)
    inspect_result: ProjectDocsInspectResult | None = None
    ingest_result: ProjectDocsIngestResult | None = None
    sync_result: ProjectDocsSyncResult | None = None
    agent_message: str | None = None
    user_message: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectDocsResult:
    project_path: str
    query: str
    status: str = "success"
    tool: str = "get_project_docs"
    reason_code: str | None = None
    next_action: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    arguments_patch: dict[str, Any] = field(default_factory=dict)
    results: list[ProjectDocsChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    candidate_sources: list[dict[str, Any]] = field(default_factory=list)
    indexed_sources: list[dict[str, Any]] = field(default_factory=list)
    stale_sources: list[dict[str, Any]] = field(default_factory=list)
    ignored_sources: list[dict[str, Any]] = field(default_factory=list)
    source_state_guidance: dict[str, Any] = field(default_factory=dict)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    answer_available: bool = True
    reason: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class ProjectContextResult:
    project_path: str
    question: str
    status: str = "success"
    tool: str = "get_project_context"
    schema_version: str = "1.0-mvp"
    answer_available: bool = True
    mode: str = "auto"
    reason: str | None = None
    context_pack: list[dict[str, Any]] = field(default_factory=list)
    project_docs: ProjectDocsResult | None = None
    dependency_docs: DocsResult | None = None
    trust_contract: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    response_style: str = "evidence-first"
    primary_snippet: dict[str, Any] | None = None
    supporting_snippets: list[dict[str, Any]] = field(default_factory=list)
    snippet_metrics: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    answer_outline: dict[str, Any] = field(default_factory=dict)
    message: str | None = None


@dataclass(frozen=True)
class UnifiedDocsContextResult:
    tool: str = "get_docs_context"
    status: str = "success"
    question: str = ""
    mode_requested: str = "auto"
    mode_selected: str = "auto"
    routing: dict[str, Any] = field(default_factory=dict)
    answer_available: bool = True
    context_pack: list[dict[str, Any]] = field(default_factory=list)
    lanes: dict[str, Any] = field(default_factory=dict)
    source_summary: dict[str, int] = field(default_factory=dict)
    trust_contract: dict[str, Any] = field(default_factory=dict)
    exact_version: dict[str, Any] | None = None
    reason_code: str | None = None
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    next_action: dict[str, Any] | None = None
    next_actions: list[Any] = field(default_factory=list)
    arguments_patch: dict[str, Any] | None = None
    warnings: list[Any] = field(default_factory=list)
    response_style: str = "evidence-first"
    primary_snippet: dict[str, Any] | None = None
    supporting_snippets: list[dict[str, Any]] = field(default_factory=list)
    snippet_metrics: dict[str, Any] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    contamination: dict[str, Any] = field(default_factory=dict)
    deduplication: dict[str, Any] = field(default_factory=dict)
    lane_details: dict[str, Any] = field(default_factory=dict)
