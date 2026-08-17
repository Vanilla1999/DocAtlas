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
MMR_LAMBDA = 0.7
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
_EXPLICIT_QUERY_LIST_RE = re.compile(
    r"\b(?:"
    r"what\s+do|explain|(?:give\s+)?(?:the\s+)?(?:meaning|semantics)\s+of|"
    r"describe\s+(?:these\s+)?(?:[A-Za-z_][A-Za-z0-9_.]*\s+)?"
    r"(?:attributes?|properties?|symbols?|fields?)"
    r")\s*:?\s+([^?;.]{1,200}?)(?=\s+(?:mean|for|in|when|while|after|before|using|with)\b|[?;.]|$)",
    re.IGNORECASE | re.DOTALL,
)
_EXPLICIT_QUERY_LIST_SEPARATOR_RE = re.compile(
    r"\s*(?:,\s*(?:and\b|or\b)?|/|\bplus\b|\band\b|\bor\b)\s*",
    re.IGNORECASE,
)
_EXPLICIT_QUERY_SYMBOL_RE = re.compile(r"`?([A-Za-z_][A-Za-z0-9_.:]*)`?")
_RST_SYMBOL_DIRECTIVE_RE = re.compile(
    r"^\.\.\s+(module|function|method|attribute|class|exception)::\s+(.+?)\s*$",
    re.MULTILINE,
)
_NOISE_LINES = {
    "copy",
    "copy code",
    "download",
    "download file",
    "select language",
    "translation",
    "translations",
}


def _query_terms(query: str | None) -> set[str]:
    return {term.lower() for term in _TERM_RE.findall(query or "") if len(term) > 1}


def _explicit_library_query_analysis(query: str) -> tuple[list[str], bool]:
    values: set[str] = set()
    has_unqualified_list = False
    for match in _EXPLICIT_QUERY_LIST_RE.finditer(query):
        items = [
            item.strip()
            for item in _EXPLICIT_QUERY_LIST_SEPARATOR_RE.split(match.group(1).strip())
        ]
        if len(items) < 2:
            continue
        symbols = [_EXPLICIT_QUERY_SYMBOL_RE.fullmatch(item) for item in items]
        has_qualified_symbol = any(
            (item.startswith("`") and item.endswith("`"))
            or any(marker in symbol.group(1) for marker in (".", "_", ":"))
            for item, symbol in zip(items, symbols, strict=True)
            if symbol is not None
        )
        if all(symbols) and has_qualified_symbol:
            values.update(symbol.group(1) for symbol in symbols if symbol is not None)
        else:
            has_unqualified_list = True
    return sorted(values, key=str.casefold), has_unqualified_list


def _explicit_library_query_values(query: str) -> list[str]:
    return _explicit_library_query_analysis(query)[0]


def _clean_library_section(content: str) -> str:
    text = _ANCHOR_RE.sub("", content or "")
    text = _EMOJI_RE.sub("", text)
    cleaned_lines = []
    for line in text.splitlines():
        normalized = line.strip().lower().strip(":")
        if normalized in _NOISE_LINES:
            continue
        if normalized.startswith(("translated by ", "translation missing")):
            continue
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _code_snippets(content: str) -> list[dict[str, str]]:
    snippets = []
    for match in _CODE_BLOCK_RE.finditer(content or ""):
        snippets.append({"language": match.group(1).strip(), "code": match.group(2).strip()})
    return snippets


def _code_relevance(snippets: list[dict[str, str]], terms: set[str]) -> int:
    if not snippets or not terms:
        return 0
    score = 0
    for snippet in snippets:
        snippet_terms = _query_terms(snippet["code"])
        score += len(terms & snippet_terms)
    return score


def _text_similarity(left: str, right: str) -> float:
    left_terms = _query_terms(left)
    right_terms = _query_terms(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def _chunk_relevance(content: str, snippets: list[dict[str, str]], terms: set[str]) -> float:
    if not terms:
        return 0.0
    text_terms = _query_terms(content)
    lexical = len(terms & text_terms) / len(terms)
    code = min(1.0, _code_relevance(snippets, terms) / len(terms))
    return lexical + code


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
    config = library_docs_selection_config(max_tokens)
    available_tokens = max(1, config.hard_tokens - config.wrapper_reserve_tokens)
    available_bytes = available_tokens * 4
    bounded = []
    derived = 0
    rejected = 0
    mandatory = [
        requirement
        for requirement in requirements
        if requirement.mandatory and requirement.kind != "exact_version"
    ]
    for chunk in chunks:
        if len(chunk.text.encode("utf-8")) <= available_bytes:
            bounded.append(chunk)
            continue
        ranked = []
        for section in _rst_symbol_sections(chunk.text):
            haystack = "\n".join([section["text"], *section["symbols"]])
            covered = {
                requirement.requirement_id
                for requirement in mandatory
                if requirement_value_visible(requirement.value, haystack)
            }
            if covered:
                ranked.append((section, covered))
        selected = []
        remaining = {requirement.requirement_id for requirement in mandatory}
        spent = 0
        while remaining:
            options = [
                (section, covered)
                for section, covered in ranked
                if section not in selected and covered & remaining
            ]
            if not options:
                break
            section, covered = min(options, key=lambda item: (
                -len(item[1] & remaining),
                len(item[0]["text"].encode("utf-8")),
                item[0]["start"],
            ))
            section_bytes = len(section["text"].encode("utf-8"))
            if spent + section_bytes > available_bytes:
                break
            selected.append(section)
            spent += section_bytes
            remaining -= covered
        if remaining:
            rejected += 1
            continue
        selected.sort(key=lambda section: section["start"])
        excerpt = "\n\n".join(section["text"] for section in selected)
        metadata = dict(chunk.metadata or {})
        parent_id = str(
            metadata.get("stable_chunk_id")
            or metadata.get("section_id")
            or metadata.get("chunk_id")
            or chunk.source
        )
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        metadata.update({
            "stable_chunk_id": f"{parent_id}:excerpt:{digest[:16]}",
            "parent_logical_id": parent_id,
            "symbols": sorted({symbol for section in selected for symbol in section["symbols"]}),
            "source_excerpt": True,
            "source_excerpt_sha256": digest,
        })
        bounded.append(_copy_chunk(chunk, text=excerpt, metadata=metadata))
        derived += 1
    return bounded, {
        "bounded_evidence": {
            "available_tokens": available_tokens,
            "derived_excerpts": derived,
            "rejected_oversized_sources": rejected,
        }
    }


def _postprocess_library_chunks(chunks: list[Any], query: str) -> tuple[list[Any], dict[str, Any]]:
    terms = _query_terms(query)
    candidates: list[dict[str, Any]] = []
    snippet_count = 0
    for index, chunk in enumerate(chunks):
        cleaned = _clean_library_section(chunk.text)
        snippets = _code_snippets(cleaned)
        snippet_count += len(snippets)
        metadata = dict(chunk.metadata or {})
        metadata["code_snippets"] = snippets
        metadata["code_snippet_count"] = len(snippets)
        if snippets:
            metadata["top_code_language"] = snippets[0]["language"] or None
        candidates.append(
            {
                "index": index,
                "relevance": _chunk_relevance(cleaned, snippets, terms),
                "chunk": _copy_chunk(chunk, text=cleaned, metadata=metadata),
            }
        )

    selected = []
    source_counts: dict[str, int] = {}
    dropped_for_diversity = 0
    while candidates:
        scored = []
        for candidate in candidates:
            diversity = max(_text_similarity(candidate["chunk"].text, chunk.text) for chunk in selected) if selected else 0.0
            mmr_score = MMR_LAMBDA * candidate["relevance"] - (1 - MMR_LAMBDA) * diversity
            scored.append((mmr_score, candidate["relevance"], -candidate["index"], candidate))
        _mmr_score, _relevance, _negative_index, best = max(scored, key=lambda item: item[:3])
        candidates.remove(best)
        chunk = best["chunk"]
        source = chunk.source or ""
        count = source_counts.get(source, 0)
        if count >= MAX_CHUNKS_PER_SOURCE:
            dropped_for_diversity += 1
            continue
        source_counts[source] = count + 1
        selected.append(chunk)

    top_relevance = max((candidate["relevance"] for candidate in candidates), default=None)
    if top_relevance is None:
        top_relevance = max((_chunk_relevance(chunk.text, _code_snippets(chunk.text), terms) for chunk in selected), default=0.0)
    return selected, {
        "code_snippets": snippet_count,
        "top_relevance": top_relevance,
        "mmr_lambda": MMR_LAMBDA,
        "max_chunks_per_source": MAX_CHUNKS_PER_SOURCE,
        "chunks_dropped_for_diversity": dropped_for_diversity,
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
