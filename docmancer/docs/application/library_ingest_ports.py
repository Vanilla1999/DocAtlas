"""Named application ports for the external-library ingest boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from docmancer.docs.models import RefreshResult


class LibraryJobStorePort(Protocol):
    def create(self, kind: str, **kwargs: Any) -> Any: ...
    def get(self, job_id: str) -> Any: ...
    def update(self, job_id: str, **kwargs: Any) -> Any: ...
    def append_error(self, job_id: str, message: str) -> Any: ...
    def generation_active(self, job_id: str, generation_id: str | None) -> bool: ...
    def cancellation_requested(self, job_id: str) -> bool: ...


class LibraryJobExecutorPort(Protocol):
    def try_reserve(self) -> bool: ...
    def release_reservation(self) -> None: ...
    def capacity(self) -> Any: ...
    def submit_reserved(self, work: Callable[[], None], **kwargs: Any) -> Any: ...


class LibraryRegistryPort(Protocol):
    def get(self, *args: Any, **kwargs: Any) -> Any: ...
    def upsert(self, **kwargs: Any) -> Any: ...
    def restore(self, record: Any) -> None: ...


class LibraryRegistryOpsPort(Protocol):
    def count_index_entries(self, record: Any) -> tuple[int, int]: ...
    def manifest_coverage(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]: ...


class LibraryAgentGatewayPort(Protocol):
    def agent_for_config(self, config: Any) -> Any: ...
    def drop_library_agent(self, record: Any) -> None: ...


@dataclass(frozen=True)
class LibraryPublicationPorts:
    index_config_for: Callable[[Any], Any]
    lock_for: Callable[[str], Any]
    restore_record: Callable[[Any], None]
    drop_library_agent: Callable[[Any], None]
    monotonic: Callable[[], float]


@dataclass(frozen=True)
class LibraryRefreshPorts:
    staging_parent: Callable[[], Path]
    jobs: LibraryJobStorePort
    registry: LibraryRegistryPort
    registry_ops: LibraryRegistryOpsPort
    agent_gateway: LibraryAgentGatewayPort
    resolve_library: Callable[..., Any]
    record_from_info: Callable[[Any], Any]
    target_from_record: Callable[[Any], Any]
    record_urls: Callable[[Any], list[str]]
    agent_instance: Callable[[Any], Any]
    is_stale: Callable[[str | None], bool]
    now: Callable[[], Any]
    index_config_for: Callable[[Any], Any]
    lock_for: Callable[[str], Any]
    resolve_github_directory_target: Callable[[Any], Any]
    target_urls: Callable[[Any], tuple[list[str], str | None]]
    target_to_spec: Callable[[Any, list[str]], dict[str, Any]]
    monotonic: Callable[[], float]
    utc_now: Callable[[], datetime]
    publication: LibraryPublicationPorts


@dataclass(frozen=True)
class LibraryIngestPorts:
    jobs: LibraryJobStorePort
    prefetch: Callable[..., RefreshResult]
    timeout_seconds: Callable[[], float]
    executor: Callable[[], LibraryJobExecutorPort]
