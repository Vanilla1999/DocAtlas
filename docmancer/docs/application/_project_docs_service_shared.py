from __future__ import annotations

import configparser
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import shutil
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.evidence_selection import requirement_probe_query
from docmancer.docs.domain.lifecycle_policy import (
    lifecycle_allows,
    lifecycle_filters_for_intent,
    lifecycle_intent,
    temporal_relevance_for_status,
)
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_path_validation import validate_project_path
from docmancer.docs.domain.project_doc_ranking import normalize_doc_path
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectDocsSyncResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.project import DOC_FILE_EXTENSIONS, ROOT_DOC_FILES
from docmancer.docs.section_metadata import SECTION_METADATA_SCHEMA_VERSION, extract_section_metadata_result
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.application.project_docs_state import ProjectDocsState
from docmancer.docs.infrastructure.storage_mutation_lock import storage_mutation_lock, storage_writer_lease

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)
PLACEHOLDER_PROJECT_DOC_RE = re.compile(
    r"\b(todo|tbd|placeholder|coming soon|lorem ipsum|under construction|work in progress|wip)\b|"
    r"TODO:\s*Put a short description|const\s+like\s*=\s*['\"]sample['\"]",
    re.IGNORECASE,
)

__all__ = [name for name in globals() if not name.startswith('__')]
