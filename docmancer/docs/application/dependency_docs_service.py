from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json
import shutil
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.application.dependency_project_prefetch import DependencyProjectPrefetch
from docmancer.docs.application.dependency_resolution import dependency_observation_for, flutter_docs_url_for, flutter_docs_version_for, is_flutter_library, project_resolution_summary, project_version_for

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)

class DependencyDocsService:
    def __init__(self, facade: Any):
        self.facade = facade
        self.project_prefetch = DependencyProjectPrefetch(facade)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.facade, name)

    @staticmethod
    def _is_flutter_library(library: str) -> bool:
        return is_flutter_library(library)

    @staticmethod
    def _flutter_docs_url_for(version: str | None, channel: str | None) -> str:
        return flutter_docs_url_for(version, channel)

    @staticmethod
    def _flutter_docs_version_for(version: str | None, channel: str | None) -> str | None:
        return flutter_docs_version_for(version, channel)

    @staticmethod
    def _project_resolution_summary(metadata: ProjectMetadata) -> dict[str, int]:
        return project_resolution_summary(metadata)

    def _dependency_observation_for(self, metadata: ProjectMetadata, library: str, ecosystem: str | None) -> Any | None:
        return dependency_observation_for(metadata, library, ecosystem)

    def _project_version_for(
        self,
        *,
        library: str,
        ecosystem: str | None,
        project_path: str | None,
    ) -> tuple[str | None, str | None, str | None, list[str], str | None, bool | None, str | None, str | None]:
        return project_version_for(library=library, ecosystem=ecosystem, project_path=project_path, read_project_metadata=self.read_project_metadata)

    def prefetch_project_docs(
        self,
        project_path: str,
        include_flutter: bool = True,
        include_dart: bool = False,
        include_rust: bool = True,
        include_packages: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> ProjectPrefetchResult | DocsJobStartResult:
        if hasattr(self.facade, "_dependency_prefetch_project_docs_impl"):
            return self.facade._dependency_prefetch_project_docs_impl(project_path, include_flutter=include_flutter, include_dart=include_dart, include_rust=include_rust, include_packages=include_packages, force_refresh=force_refresh, continue_on_error=continue_on_error, async_=async_)
        return self.project_prefetch.prefetch_project_docs(
            project_path,
            include_flutter=include_flutter,
            include_dart=include_dart,
            include_rust=include_rust,
            include_packages=include_packages,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
            async_=async_,
        )

    def prefetch_project_dependency_docs(
        self, project_path: str, include_flutter: bool = True, include_dart: bool = False, include_rust: bool = True, include_packages: list[str] | None = None, force_refresh: bool = False, continue_on_error: bool = True, async_: bool = False,
    ) -> ProjectPrefetchResult | DocsJobStartResult:
        return self.prefetch_project_docs(project_path, include_flutter=include_flutter, include_dart=include_dart, include_rust=include_rust, include_packages=include_packages, force_refresh=force_refresh, continue_on_error=continue_on_error, async_=async_)
