from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import re
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.discovery_candidates import discovery_candidates_for
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.quality import is_trivial_section
from docmancer.docs.domain.library_source_options import library_docs_source_next_actions, library_docs_source_options, source_required_diagnostics
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.snippets import build_snippet_presentation, validate_response_style
from docmancer.docs.curated_sources import curated_source_for, curated_target_spec
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, docs_snapshot_is_exact, legacy_library_id, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.dart_official_docs import (
    allowed_domains_for_urls,
    build_dart_diagnostics,
    canonical_dart_ecosystem,
    get_seed_urls_for_package,
    has_official_docs,
    resolve_dart_official_docs,
)
from docmancer.docs.application.library_registry_ops import LibraryRegistryOps
from docmancer.docs.application.library_refresh_ops import LibraryRefreshOps
from docmancer.docs.application.library_job_executor import LibraryJobExecutor, shared_library_job_executor
from docmancer.docs.application.library_ingest_orchestrator import LibraryIngestOrchestrator
from docmancer.docs.application.library_ingest_ports import LibraryIngestPorts, LibraryPublicationPorts, LibraryRefreshPorts
from docmancer.docs.application.evidence_selection import (
    build_requirements,
    library_docs_selection_config,
    requirement_value_visible,
    select_evidence,
)

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
MAX_CHUNKS_PER_SOURCE = 2
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)



def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def _drop_low_value_library_section(content: str, title: str | None = None) -> bool:
    if not is_trivial_section(content, title):
        return False
    text = (content or "").strip()
    return not text or text.lower() == (title or "").strip().lower()


_CODE_BLOCK_RE = re.compile(r"```([A-Za-z0-9_+.#-]*)\s*\n(.*?)```", re.DOTALL)
_ANCHOR_RE = re.compile(r"\s*\[¶\]")
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF]")
_TERM_RE = re.compile(r"[A-Za-z0-9_]+")
_RST_SYMBOL_DIRECTIVE_RE = re.compile(
    r"^\.\.\s+(module|function|method|attribute|class|exception)::\s+(.+?)\s*$",
    re.MULTILINE,
)


def _query_terms(query: str | None) -> set[str]:
    return {term.lower() for term in _TERM_RE.findall(query or "") if len(term) > 1}


def _explicit_library_query_analysis(query: str) -> tuple[list[str], bool]:
    """ABI only: question prose is not an explicit requirement contract.

    No parsed values is unknown, not proof that a plain list was completed.
    """
    return [], False


def _explicit_library_query_values(query: str) -> list[str]:
    return _explicit_library_query_analysis(query)[0]


def _clean_library_section(content: str) -> str:
    """Compatibility name: source witnesses and delivered windows are verbatim."""
    return content


def _code_snippets(content: str) -> list[dict[str, str]]:
    snippets = []
    for match in _CODE_BLOCK_RE.finditer(content or ""):
        snippets.append({"language": match.group(1).strip(), "code": match.group(2).strip()})
    return snippets


def _copy_chunk(chunk: Any, *, text: str, metadata: dict[str, Any]) -> Any:
    if hasattr(chunk, "model_copy"):
        return chunk.model_copy(update={"text": text, "metadata": metadata})
    if hasattr(chunk, "copy"):
        return chunk.copy(update={"text": text, "metadata": metadata})
    chunk.text = text
    chunk.metadata = metadata
    return chunk


def _rst_symbol_sections(content: str) -> list[dict[str, Any]]:
    matches = list(_RST_SYMBOL_DIRECTIVE_RE.finditer(content))
    modules = [match.group(2).strip() for match in matches if match.group(1) == "module"]
    module = modules[0] if len(set(modules)) == 1 else ""
    sections = []
    for index, match in enumerate(matches):
        if match.group(1) == "module":
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        raw_symbol = match.group(2).strip().split("(", 1)[0]
        qualified_symbol = (
            raw_symbol
            if not module or raw_symbol.startswith(module + ".")
            else f"{module}.{raw_symbol}"
        )
        sections.append({
            "start": match.start(),
            "text": content[match.start():end].strip(),
            "symbols": (raw_symbol, qualified_symbol),
        })
    return sections


def _bounded_library_evidence_chunks(
    chunks: list[Any],
    *,
    requirements: Any,
    max_tokens: int,
) -> tuple[list[Any], dict[str, Any]]:
    # These windows have already passed acquisition/source guards. Presentation
    # size cannot derive a new identity, excerpt them, or discard their lineage.
    return list(chunks), {
        "bounded_evidence": {
            "available_tokens": None,
            "derived_excerpts": 0,
            "rejected_oversized_sources": 0,
        }
    }


def _postprocess_library_chunks(chunks: list[Any], query: str) -> tuple[list[Any], dict[str, Any]]:
    selected = []
    snippet_count = 0
    for chunk in chunks:
        # Presentation metadata must not strip anchors, emoji or whitespace
        # from an acquired evidence window.
        snippets = _code_snippets(chunk.text)
        snippet_count += len(snippets)
        metadata = dict(chunk.metadata or {})
        metadata["code_snippets"] = snippets
        metadata["code_snippet_count"] = len(snippets)
        if snippets:
            metadata["top_code_language"] = snippets[0]["language"] or None
        selected.append(_copy_chunk(chunk, text=chunk.text, metadata=metadata))
    return selected, {
        "code_snippets": snippet_count,
        "selection_method": "native_acquisition_rank",
        "relevance_unassessed": True,
        "max_chunks_per_source": None,
        "chunks_dropped_for_diversity": 0,
        "unique_sources@5": len({chunk.source for chunk in selected[:5]}),
    }

def _age_days(last_refreshed_at: str | None) -> int | None:
    if not last_refreshed_at:
        return None
    try:
        refreshed = datetime.fromisoformat(last_refreshed_at)
    except ValueError:
        return None
    if refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - refreshed).days)


def _freshness_diagnostics(last_refreshed_at: str | None, stale_after_days: int, stale: bool) -> dict[str, Any]:
    return {
        "last_refreshed_at": last_refreshed_at,
        "stale": stale,
        "stale_after_days": stale_after_days,
        "age_days": _age_days(last_refreshed_at),
    }


def _stale_docs_warning(last_refreshed_at: str | None, stale_after_days: int) -> str:
    age = _age_days(last_refreshed_at)
    if age is None:
        return f"Documentation freshness is unknown (stale after {stale_after_days} days). Call refresh_library_docs to update."
    return f"Documentation is {age} days old (stale after {stale_after_days} days). Call refresh_library_docs to update."

__all__ = [name for name in globals() if not name.startswith('__')]
