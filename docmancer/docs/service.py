from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DOCS_JOB_SERVICE, DocsJobService, DocsJobTracker
from docmancer.docs.application.docs_manifest_service import DocsManifestService
from docmancer.docs.application.docs_prefetch_service import DocsPrefetchService
from docmancer.docs.application.docs_target_service import DocsTargetService, target_result_summary
from docmancer.docs.application.dependency_docs_service import DependencyDocsService
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.application.project_context_service import ProjectContextService, context_pack_snippet, project_context_metrics, project_context_pack
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.domain.policies import is_stale
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from docmancer.docs.infrastructure.filesystem_locks import FilesystemLockGateway
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJob, DocsJobCancelResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectContextResult, ProjectDocsBootstrapResult, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRecord, LibraryRegistry

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000


class LibraryDocsService:
    def __init__(self, *, config: DocmancerConfig | None = None, registry: LibraryRegistry | None = None, agent: Any | None = None, project_reader: ProjectMetadataReader | None = None, job_tracker: DocsJobTracker | None = None, stale_after_days: int = STALE_AFTER_DAYS):
        self.config = config or DocmancerConfig()
        self.registry = registry or LibraryRegistry(self.config.index.db_path)
        self.agent_gateway = AgentIndexGateway(self.config, default_agent=agent)
        self.lock_gateway = FilesystemLockGateway()
        self.project_reader = project_reader or ProjectMetadataReader()
        self.stale_after_days = stale_after_days
        self.jobs = DocsJobService(job_tracker) if job_tracker is not None else DOCS_JOB_SERVICE
        self.library_docs = LibraryDocsApplicationService(self)
        self.project_docs = ProjectDocsService(self)
        self.project_context = ProjectContextService(self)
        self.dependency_docs = DependencyDocsService(self)
        self.docs_targets = DocsTargetService(self._render_docs_url, self.jobs)
        self.docs_prefetch = DocsPrefetchService(self)
        self.docs_manifest = DocsManifestService(self)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _is_stale(self, last_refreshed_at: str | None) -> bool:
        return is_stale(last_refreshed_at, stale_after_days=self.stale_after_days)

    def _index_config_for(self, record: LibraryRecord) -> DocmancerConfig:
        return self.agent_gateway.index_config_for(record)

    def _agent_instance(self, record: LibraryRecord | None = None) -> Any:
        return self.agent_gateway.agent_instance(record)

    def _lock_for(self, library_id: str):
        return self.lock_gateway.lock_for(library_id)

    @staticmethod
    def _render_docs_url(template: str, library: str, version: str) -> str:
        return template.format(library=library, version=version)

    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return self.project_reader.read(project_path)

    def get_docs_job_status(self, job_id: str) -> DocsJob | None:
        return self.jobs.get_docs_job_status(job_id)

    def list_docs_jobs(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        return self.jobs.list_docs_jobs(status=status, limit=limit)

    def cancel_docs_job(self, job_id: str) -> DocsJobCancelResult:
        return self.jobs.cancel_docs_job(job_id)

    def resolve_library(self, *args: Any, **kwargs: Any):
        return self.library_docs.resolve_library(*args, **kwargs)

    def _candidate_payload(self, *args: Any, **kwargs: Any):
        return self.library_docs._candidate_payload(*args, **kwargs)

    def _docs_policy(self, *args: Any, **kwargs: Any):
        return self.library_docs._docs_policy(*args, **kwargs)

    def _docs_identity(self, *args: Any, **kwargs: Any):
        return self.library_docs._docs_identity(*args, **kwargs)

    def _docs_request(self, *args: Any, **kwargs: Any):
        return self.library_docs._docs_request(*args, **kwargs)

    def _record_from_info(self, *args: Any, **kwargs: Any):
        return self.library_docs._record_from_info(*args, **kwargs)

    def _resolve_docs_source(self, *args: Any, **kwargs: Any):
        return self.library_docs.resolve_docs_source(*args, **kwargs)

    def _docs_exactness(self, *args: Any, **kwargs: Any):
        return self.library_docs._docs_exactness(*args, **kwargs)

    def _join_warnings(self, *args: Any, **kwargs: Any):
        return self.library_docs._join_warnings(*args, **kwargs)

    def _refresh_record(self, *args: Any, **kwargs: Any):
        return self.library_docs._refresh_record(*args, **kwargs)

    def refresh_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.refresh_docs(*args, **kwargs)

    def prefetch_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.prefetch_docs(*args, **kwargs)

    def get_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.get_docs(*args, **kwargs)

    def inspect_library_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.inspect_library_docs(*args, **kwargs)

    def remove_library_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.remove_library_docs(*args, **kwargs)

    def prune_library_docs(self, *args: Any, **kwargs: Any):
        return self.library_docs.prune_library_docs(*args, **kwargs)

    def list_libraries(self, *args: Any, **kwargs: Any):
        return self.library_docs.list_libraries(*args, **kwargs)

    def _index_size_for(self, *args: Any, **kwargs: Any):
        return self.library_docs._index_size_for(*args, **kwargs)

    def _delete_index_for(self, *args: Any, **kwargs: Any):
        return self.library_docs._delete_index_for(*args, **kwargs)

    def _record_age_cutoff_value(self, *args: Any, **kwargs: Any):
        return self.library_docs._record_age_cutoff_value(*args, **kwargs)

    def inspect_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.inspect_project_docs(*args, **kwargs)

    def ingest_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.ingest_project_docs(*args, **kwargs)

    def sync_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.sync_project_docs(*args, **kwargs)

    def bootstrap_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.bootstrap_project_docs(*args, **kwargs)

    def query_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.query_project_docs(*args, **kwargs)

    def get_project_docs(self, *args: Any, **kwargs: Any):
        return self.project_docs.get_project_docs(*args, **kwargs)

    def _indexed_project_doc_sources(self, *args: Any, **kwargs: Any):
        return self.project_docs._indexed_project_doc_sources(*args, **kwargs)

    def _source_state_guidance(self, *args: Any, **kwargs: Any):
        return self.project_docs._source_state_guidance(*args, **kwargs)

    def _partition_project_doc_state(self, *args: Any, **kwargs: Any):
        return self.project_docs._partition_project_doc_state(*args, **kwargs)

    def _has_high_level_project_overview(self, *args: Any, **kwargs: Any):
        return self.project_docs._has_high_level_project_overview(*args, **kwargs)

    def _project_dependency_docs_state(self, *args: Any, **kwargs: Any):
        return self.project_docs._project_dependency_docs_state(*args, **kwargs)

    def _create_project_docs_next_action(self, *args: Any, **kwargs: Any):
        return self.project_docs._create_project_docs_next_action(*args, **kwargs)

    def _project_docs_structured_next_action(self, *args: Any, **kwargs: Any):
        return self.project_docs._project_docs_structured_next_action(*args, **kwargs)

    def get_project_context(self, *args: Any, **kwargs: Any):
        return self.project_context.get_project_context(*args, **kwargs)

    def _dependency_mentioned_in_question(self, *args: Any, **kwargs: Any):
        return self.project_context.dependency_mentioned_in_question(*args, **kwargs)

    def prefetch_project_docs(self, *args: Any, **kwargs: Any):
        return self.dependency_docs.prefetch_project_docs(*args, **kwargs)

    def prefetch_project_dependency_docs(self, *args: Any, **kwargs: Any):
        return self.dependency_docs.prefetch_project_dependency_docs(*args, **kwargs)

    def _is_flutter_library(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._is_flutter_library(*args, **kwargs)

    def _flutter_docs_url_for(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._flutter_docs_url_for(*args, **kwargs)

    def _flutter_docs_version_for(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._flutter_docs_version_for(*args, **kwargs)

    def _project_resolution_summary(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._project_resolution_summary(*args, **kwargs)

    def _dependency_observation_for(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._dependency_observation_for(*args, **kwargs)

    def _project_version_for(self, *args: Any, **kwargs: Any):
        return self.dependency_docs._project_version_for(*args, **kwargs)

    def _target_from_record(self, *args: Any, **kwargs: Any):
        return self.docs_targets.target_from_record(*args, **kwargs)

    def _record_urls(self, *args: Any, **kwargs: Any):
        return self.docs_targets.record_urls(*args, **kwargs)

    def _target_urls(self, *args: Any, **kwargs: Any):
        return self.docs_targets.target_urls(*args, **kwargs)

    def _discover_pub_dartdoc_target(self, *args: Any, **kwargs: Any):
        return self.docs_targets.discover_pub_dartdoc_target(*args, **kwargs)

    def _progress_callback_for(self, *args: Any, **kwargs: Any):
        return self.docs_prefetch.progress_callback_for(*args, **kwargs)

    def prefetch_docs_targets(self, *args: Any, **kwargs: Any):
        return self.docs_prefetch.prefetch_docs_targets(*args, **kwargs)

    def _prefetch_docs_targets_sync(self, *args: Any, **kwargs: Any):
        return self.docs_prefetch.prefetch_docs_targets_sync(*args, **kwargs)

    def _run_prefetch_docs_targets_job(self, *args: Any, **kwargs: Any):
        return self.docs_prefetch._run_prefetch_docs_targets_job(*args, **kwargs)

    def _resolve_manifest_project_version(self, *args: Any, **kwargs: Any):
        return self.docs_manifest.resolve_manifest_project_version(*args, **kwargs)

    def validate_docs_manifest(self, *args: Any, **kwargs: Any):
        return self.docs_manifest.validate_docs_manifest(*args, **kwargs)

    def prefetch_docs_manifest(self, *args: Any, **kwargs: Any):
        return self.docs_manifest.prefetch_docs_manifest(*args, **kwargs)

    @staticmethod
    def _target_from_dict(value: dict[str, Any] | DocsTarget) -> DocsTarget:
        return DocsTargetService.target_from_dict(value)

    @staticmethod
    def _target_to_spec(target: DocsTarget, urls: list[str] | None = None) -> dict[str, Any]:
        return DocsTargetService.target_to_spec(target, urls)

    @staticmethod
    def _is_remote_url(url: str) -> bool:
        return is_remote_url(url)

    @staticmethod
    def _url_security_error(url: str) -> str | None:
        return url_security_error(url)

    @staticmethod
    def _host_allowed(url: str, allowed_domains: list[str]) -> bool:
        return host_allowed(url, allowed_domains)

    @staticmethod
    def _path_allowed(url: str, path_prefixes: list[str]) -> bool:
        return path_allowed(url, path_prefixes)

    @staticmethod
    def _dependency_docs_url_guidance(target: DocsTarget) -> list[str]:
        return DocsTargetService.dependency_docs_url_guidance(target)

    @staticmethod
    def _merge_manifest_defaults(defaults: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        return DocsManifestService.merge_manifest_defaults(defaults, target)

    @staticmethod
    def _project_context_pack(*, project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None) -> list[dict[str, Any]]:
        return project_context_pack(project_docs=project_docs, dependency_docs=dependency_docs)

    @staticmethod
    def _context_pack_snippet(item: DocsChunk) -> dict[str, Any] | None:
        return context_pack_snippet(item)

    @staticmethod
    def _project_context_metrics(*, context_pack: list[dict[str, Any]], project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None) -> dict[str, Any]:
        return project_context_metrics(context_pack=context_pack, project_docs=project_docs, dependency_docs=dependency_docs)

    @staticmethod
    def _project_context_trust_contract(*, project_docs: ProjectDocsResult | None, dependency_docs: DocsResult | None, requested_library: str | None, mode: str) -> dict[str, Any]:
        return build_project_context_trust_contract(project_docs=project_docs, dependency_docs=dependency_docs, requested_library=requested_library, mode=mode)

    @staticmethod
    def _target_result_summary(result: DocsTargetResult) -> dict[str, Any]:
        return target_result_summary(result)
