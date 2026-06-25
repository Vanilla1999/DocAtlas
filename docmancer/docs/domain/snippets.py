from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any
import re

from docmancer.docs.domain.quality import internal_noise_score, looks_like_code_or_command

RESPONSE_STYLES = {"auto", "snippet-first", "evidence-first"}
MAX_PRIMARY_SNIPPET_CHARS = 4000
MAX_SUPPORTING_SNIPPET_CHARS = 2400
MAX_SNIPPETS_PER_SOURCE = 1

_FENCED_CODE_RE = re.compile(r"```([A-Za-z0-9_+.#-]*)\s*\n(.*?)```", re.DOTALL)
_TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[A-Za-z0-9][A-Za-z0-9_.:-]*")
_NOISE_TEXT = ("[¶]", "Copy code", "Copy", "Download", "Open in new tab", "Edit this page", "Other versions and variants")
_FLOATING_VERSION_ALIASES = {"latest", "stable", "main", "master", "beta", "next"}
_LANGUAGE_ALIASES = {"py": "python", "python3": "python", "sh": "bash", "shell": "bash", "console": "bash", "rs": "rust"}


@dataclass
class SnippetCandidate:
    code: str
    language: str | None
    title: str | None
    heading_path: str | None
    source: str | None
    source_url: str | None
    canonical_id: str | None
    library_id: str | None
    version: str | None
    requested_version: str | None
    exact_version_match: bool | None
    doc_scope: str | None
    origin_lane: str | None
    source_class: str | None
    why_relevant: str | None
    relevance_score: float
    source_score: float
    completeness_score: float
    final_score: float
    block_index: int | None
    complete: bool
    truncated: bool
    surrounding_context: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SnippetPresentation:
    response_style: str
    primary_snippet: dict[str, Any] | None
    supporting_snippets: list[dict[str, Any]]
    snippet_count: int
    warnings: list[dict[str, Any]]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class SnippetQueryIntent:
    wants_code: bool
    wants_command: bool
    wants_config: bool
    expected_languages: list[str]
    symbols: list[str]


def validate_response_style(response_style: str | None) -> str:
    style = (response_style or "auto").strip().lower()
    if style not in RESPONSE_STYLES:
        raise ValueError("response_style must be one of: auto, snippet-first, evidence-first")
    return style


def infer_snippet_query_intent(question: str) -> SnippetQueryIntent:
    text = question or ""
    lowered = text.lower()
    wants_command = bool(re.search(r"\b(command|cli|terminal|curl|shell|bash|run)\b", lowered))
    wants_config = bool(re.search(r"\b(config|configure|yaml|toml|json|ini|setting)\b", lowered))
    coding_context = bool(re.search(r"\b(anyhow|with_context|error context|context trait)\b", lowered))
    wants_code = bool(re.search(r"\b(how do i use|example|snippet|code|api|function|class|decorator|provider|depends|with_context|autodispose|blocprovider|click\.group|command group)\b", lowered)) or coding_context or wants_command or wants_config
    language_hints = {
        "python": ("python", "fastapi", "click", "depends"),
        "dart": ("dart", "flutter", "riverpod", "bloc", "blocprovider", "autodispose"),
        "rust": ("rust", "anyhow", "with_context", "context trait"),
        "yaml": ("yaml", "yml"),
        "toml": ("toml", "cargo.toml"),
        "json": ("json",),
        "bash": ("bash", "shell", "cli", "command", "curl"),
    }
    expected_languages = [language for language, hints in language_hints.items() if any(hint in lowered for hint in hints)]
    symbols = [_canonical_symbol(term) for term in _TERM_RE.findall(text) if _is_symbol_like(term)]
    if "click" in lowered and "group" in lowered:
        symbols.extend(["click.group", "@click.group"])
    if "fastapi" in lowered and "depends" in lowered:
        symbols.append("Depends")
    if "riverpod" in lowered and "autodispose" in lowered:
        symbols.extend(["autoDispose", "keepAlive", "ref.watch"])
    if "blocprovider" in lowered:
        symbols.append("BlocProvider")
    return SnippetQueryIntent(wants_code, wants_command, wants_config, _dedupe(expected_languages), _dedupe([s for s in symbols if s]))


def extract_snippet_candidates(chunk: Any, *, origin_lane: str, question: str) -> list[SnippetCandidate]:
    metadata = _metadata(chunk)
    snippets = _metadata_snippets(metadata) or _fenced_snippets(_content(chunk))
    candidates: list[SnippetCandidate] = []
    for index, snippet in enumerate(snippets):
        code = str(snippet.get("code") or "")
        language = _normalize_language(snippet.get("language")) or _infer_language(code, metadata)
        if not code.strip() or (not looks_like_code_or_command(code) and language not in {"json", "yaml", "toml"}):
            continue
        candidate = SnippetCandidate(
            code=code.strip("\n"),
            language=language,
            title=clean_snippet_title(snippet.get("title") or _title(chunk, metadata)),
            heading_path=_heading_path(chunk, metadata),
            source=_source(chunk, metadata),
            source_url=_source_url(chunk, metadata),
            canonical_id=_string(metadata.get("canonical_id")),
            library_id=_string(metadata.get("library_id") or metadata.get("dependency")),
            version=_string(metadata.get("version") or metadata.get("resolved_version")),
            requested_version=_string(metadata.get("requested_version")),
            exact_version_match=_exact_version_match(metadata),
            doc_scope=_string(metadata.get("doc_scope")),
            origin_lane=_string(metadata.get("origin_lane") or origin_lane),
            source_class=_string(metadata.get("source_class")),
            why_relevant=None,
            relevance_score=0.0,
            source_score=0.0,
            completeness_score=0.0,
            final_score=0.0,
            block_index=index,
            complete=bool(snippet.get("complete", True)) and not bool(snippet.get("truncated", False)),
            truncated=bool(snippet.get("truncated", False)),
            surrounding_context=clean_surrounding_context(_content(chunk)),
            metadata={**metadata, "snippet_index": index},
        )
        candidates.append(candidate)
    return candidates


def build_snippet_presentation(chunks: list[Any], *, question: str, response_style: str, lane_priority: list[str] | None = None, max_supporting: int = 3) -> SnippetPresentation:
    requested_style = validate_response_style(response_style)
    intent = infer_snippet_query_intent(question)
    raw_candidates: list[SnippetCandidate] = []
    for chunk in chunks or []:
        raw_candidates.extend(extract_snippet_candidates(chunk, origin_lane=_chunk_origin_lane(chunk), question=question))
    if requested_style == "evidence-first" or (requested_style == "auto" and not intent.wants_code):
        return SnippetPresentation("evidence-first", None, [], len(raw_candidates), [], _snippet_metrics(raw_candidates, [], 0, 0, False, requested_style))
    scored = [_score_candidate(candidate, question=question, intent=intent, lane_priority=lane_priority) for candidate in raw_candidates]
    usable = [candidate for candidate in scored if candidate.final_score > 0 and not _is_noisy(candidate)]
    if not usable:
        warning = {"code": "snippet_not_available", "message": "No usable code example was found in the selected trusted sources."}
        return SnippetPresentation("evidence-first", None, [], len(raw_candidates), [warning], _snippet_metrics(raw_candidates, [], 0, 0, False, requested_style))
    usable.sort(key=lambda c: (-c.final_score, c.block_index or 0, c.source or ""))
    selected: list[SnippetCandidate] = []
    seen_hashes: set[str] = set()
    source_counts: dict[str, int] = {}
    duplicates_dropped = 0
    for candidate in usable:
        digest = _snippet_hash(candidate)
        if digest in seen_hashes:
            duplicates_dropped += 1
            continue
        source_key = candidate.source_url or candidate.source or candidate.canonical_id or ""
        if source_counts.get(source_key, 0) >= MAX_SNIPPETS_PER_SOURCE:
            continue
        seen_hashes.add(digest)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        selected.append(candidate)
        if len(selected) >= max_supporting + 1:
            break
    if not selected:
        warning = {"code": "snippet_not_available", "message": "No usable code example was found in the selected trusted sources."}
        return SnippetPresentation("evidence-first", None, [], len(raw_candidates), [warning], _snippet_metrics(raw_candidates, [], duplicates_dropped, 0, False, requested_style))
    primary = _snippet_payload(selected[0], max_chars=MAX_PRIMARY_SNIPPET_CHARS)
    supporting = [_snippet_payload(candidate, max_chars=MAX_SUPPORTING_SNIPPET_CHARS) for candidate in selected[1:]]
    truncations = int(bool(primary.get("truncated"))) + sum(1 for item in supporting if item.get("truncated"))
    warnings = [{"code": "snippet_truncated", "message": "One or more snippets were truncated for presentation."}] if truncations else []
    return SnippetPresentation("snippet-first", primary, supporting, len(raw_candidates), warnings, _snippet_metrics(raw_candidates, selected, duplicates_dropped, truncations, True, requested_style))


def best_context_pack_snippet(item: Any, *, question: str = "") -> dict[str, Any] | None:
    candidates = extract_snippet_candidates(item, origin_lane=_chunk_origin_lane(item), question=question)
    if not candidates:
        return None
    intent = infer_snippet_query_intent(question)
    scored = [_score_candidate(candidate, question=question, intent=intent, lane_priority=None) for candidate in candidates]
    scored.sort(key=lambda c: (-c.final_score, c.block_index or 0))
    candidate = scored[0]
    return {"language": candidate.language, "code": candidate.code, "why_relevant": f"code example extracted from matching {candidate.title or 'section'} section"}


def clean_snippet_title(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = _remove_ui_noise(text)
    text = re.sub(r"\s+", " ", text).strip(" -|")
    return text or None


def clean_surrounding_context(value: str | None) -> str | None:
    text = str(value or "")
    if not text.strip():
        return None
    lines = []
    for line in text.splitlines():
        normalized = line.strip().lower().strip(":")
        if normalized in {"copy", "copy code", "download", "open in new tab", "edit this page"}:
            continue
        lines.append(_remove_ui_noise(line).rstrip())
    return "\n".join(lines).strip() or None


def normalize_code_for_dedupe(code: str) -> str:
    text = (code or "").strip()
    fence = re.fullmatch(r"```[A-Za-z0-9_+.#-]*\s*\n(.*?)```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def to_snippet_dicts(presentation: SnippetPresentation) -> dict[str, Any]:
    return asdict(presentation)


def _score_candidate(candidate: SnippetCandidate, *, question: str, intent: SnippetQueryIntent, lane_priority: list[str] | None) -> SnippetCandidate:
    query_terms = _query_terms(question)
    code_terms = _query_terms(candidate.code)
    title_terms = _query_terms(" ".join(part for part in [candidate.title, candidate.heading_path] if part))
    overlap = len(query_terms & (code_terms | title_terms)) / max(1, len(query_terms))
    symbol_score = _symbol_score(candidate, intent)
    language_score = _language_score(candidate.language, intent.expected_languages)
    title_score = len(query_terms & title_terms) / max(1, len(query_terms))
    candidate.relevance_score = min(1.0, 0.55 * overlap + 0.25 * symbol_score + 0.10 * language_score + 0.10 * title_score)
    candidate.source_score = _source_score(candidate, lane_priority)
    candidate.completeness_score = 1.0 if candidate.complete and not candidate.truncated else 0.35
    version_score = _version_score(candidate)
    usability_score = _usability_score(candidate)
    noise_penalty = internal_noise_score(candidate.code) * 0.2 + (0.25 if len(candidate.code.strip()) < 8 else 0.0)
    candidate.final_score = max(0.0, 0.35 * candidate.relevance_score + 0.20 * symbol_score + 0.15 * candidate.source_score + 0.10 * version_score + 0.10 * candidate.completeness_score + 0.10 * usability_score - noise_penalty)
    why = []
    if query_terms & code_terms:
        why.append("matches query symbols in code")
    if language_score:
        why.append(f"matches expected {candidate.language} example")
    if candidate.exact_version_match is True:
        why.append("matches exact requested version")
    candidate.why_relevant = "; ".join(why) or "code example extracted from selected trusted source"
    return candidate


def _snippet_payload(candidate: SnippetCandidate, *, max_chars: int) -> dict[str, Any]:
    code, truncated = _truncate_code(candidate.code, max_chars)
    fallback = bool(candidate.metadata.get("fallback")) or (candidate.exact_version_match is False and (candidate.version or "").lower() == "latest")
    risk_flags = list(candidate.metadata.get("risk_flags") or [])
    if fallback and "not_exact_version" not in risk_flags:
        risk_flags.append("not_exact_version")
    return {
        "language": candidate.language,
        "code": code,
        "title": candidate.title,
        "source": candidate.source_url or candidate.source,
        "source_url": candidate.source_url,
        "why_relevant": candidate.why_relevant,
        "canonical_id": candidate.canonical_id,
        "library_id": candidate.library_id or candidate.canonical_id,
        "version": candidate.version,
        "requested_version": candidate.requested_version,
        "doc_scope": candidate.doc_scope,
        "origin_lane": candidate.origin_lane,
        "source_class": candidate.source_class,
        "exact_version_match": candidate.exact_version_match,
        "version_binding": "latest_fallback" if fallback else candidate.metadata.get("docs_exactness") or candidate.metadata.get("version_binding"),
        "risk_flags": risk_flags,
        "complete": candidate.complete and not truncated,
        "truncated": truncated or candidate.truncated,
        "block_index": candidate.block_index,
        "score": round(candidate.final_score, 4),
        "surrounding_context": candidate.surrounding_context,
        "metadata": {k: v for k, v in candidate.metadata.items() if k in {"freshness", "docs_exactness", "docs_binding_source", "confidence", "snippet_index"}},
    }


def _snippet_metrics(raw: list[SnippetCandidate], selected: list[SnippetCandidate], duplicates: int, truncations: int, applied: bool, requested_style: str) -> dict[str, Any]:
    primary = selected[0] if selected else None
    return {
        "candidates_found": len(raw),
        "usable_candidates": len([c for c in raw if looks_like_code_or_command(c.code)]),
        "primary_selected": primary is not None,
        "supporting_selected": max(0, len(selected) - 1),
        "duplicates_dropped": duplicates,
        "noise_dropped": len([c for c in raw if _is_noisy(c)]),
        "truncations": truncations,
        "primary_language": primary.language if primary else None,
        "primary_lane": primary.origin_lane if primary else None,
        "primary_source_correct": True if primary else None,
        "primary_exact_version_match": primary.exact_version_match if primary else None,
        "snippet_first_applied": applied,
        "requested_response_style": requested_style,
    }


def _metadata_snippets(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    snippets = metadata.get("code_snippets") or []
    return [snippet for snippet in snippets if isinstance(snippet, dict)] if isinstance(snippets, list) else []


def _fenced_snippets(content: str) -> list[dict[str, Any]]:
    return [{"language": m.group(1).strip() or None, "code": m.group(2), "complete": True} for m in _FENCED_CODE_RE.finditer(content or "")]


def _truncate_code(code: str, max_chars: int) -> tuple[str, bool]:
    if len(code) <= max_chars:
        return code, False
    cutoff = code.rfind("\n", 0, max_chars)
    if cutoff < max(80, max_chars // 2):
        cutoff = max_chars
    return code[:cutoff].rstrip(), True


def _query_terms(value: str | None) -> set[str]:
    return {_canonical_symbol(term).lower() for term in _TERM_RE.findall(value or "") if len(term) > 1}


def _canonical_symbol(term: str) -> str:
    return (term or "").strip("`'\".,:;()[]{}")


def _is_symbol_like(term: str) -> bool:
    return bool(re.search(r"[A-Z_@.]|dispose|provider|depends|context|group|watch|yaml|toml", term))


def _symbol_score(candidate: SnippetCandidate, intent: SnippetQueryIntent) -> float:
    if not intent.symbols:
        return 0.0
    code = candidate.code.lower()
    return min(1.0, sum(1 for symbol in intent.symbols if symbol.lower() in code) / max(1, len(intent.symbols)))


def _language_score(language: str | None, expected_languages: list[str]) -> float:
    if not expected_languages:
        return 0.5
    return 1.0 if language and _normalize_language(language) in expected_languages else 0.0


def _source_score(candidate: SnippetCandidate, lane_priority: list[str] | None) -> float:
    score = 0.6
    if candidate.source_url and candidate.source_url.startswith(("http://", "https://")):
        score += 0.15
    if candidate.source_class in {"project_doc", "dependency_doc", "library_doc", "project_file", "dependency_docs", "public_docs"}:
        score += 0.10
    if lane_priority and candidate.origin_lane in lane_priority:
        score += max(0.0, 0.15 - 0.04 * lane_priority.index(candidate.origin_lane))
    return min(1.0, score)


def _version_score(candidate: SnippetCandidate) -> float:
    if candidate.exact_version_match is True:
        return 1.0
    if candidate.requested_version and candidate.version and candidate.version == candidate.requested_version:
        return 0.9
    if candidate.exact_version_match is False:
        return 0.25
    if candidate.version and candidate.version.lower() not in {"latest", "stable", "main"}:
        return 0.75
    return 0.5


def _usability_score(candidate: SnippetCandidate) -> float:
    length = len(candidate.code)
    if 20 <= length <= 1200:
        return 1.0
    if 1200 < length <= MAX_PRIMARY_SNIPPET_CHARS:
        return 0.75
    return 0.35 if length < 20 else 0.45


def _is_noisy(candidate: SnippetCandidate) -> bool:
    lowered = candidate.code.strip().lower()
    if not lowered or lowered in {"copy", "download", "open in new tab"}:
        return True
    if "](" in candidate.code and candidate.code.count("\n") < 3:
        return True
    return internal_noise_score(candidate.code) >= 0.8


def _snippet_hash(candidate: SnippetCandidate) -> str:
    return sha256(f"{candidate.language or ''}\n{normalize_code_for_dedupe(candidate.code)}".encode("utf-8")).hexdigest()



def _infer_language(code: str, metadata: dict[str, Any]) -> str | None:
    source = " ".join(str(metadata.get(key) or "") for key in ("source", "url", "source_url", "library_id", "canonical_id", "library", "dependency", "ecosystem")).lower()
    stripped = code.lstrip()
    if "docs.rs" in source or "rust" in source or re.search(r"\b(fn|let|impl|pub struct|use anyhow|Result<)\b", code):
        return "rust"
    if "riverpod" in source or "bloc" in source or "flutter" in source or re.search(r"\b(final|Widget|BuildContext|ref\.watch|BlocProvider|FutureProvider)\b", code):
        return "dart"
    if "fastapi" in source or "click" in source or re.search(r"(^|\n)\s*(from\s+\w+\s+import|import\s+\w+|def\s+\w+|class\s+\w+|@\w+(?:\.\w+)?\()", code):
        return "python"
    if re.search(r"(^|\n)\s*(uv|pytest|python|git|curl|npm|dart|flutter)\s+", code):
        return "bash"
    if stripped.startswith(("{", "[")):
        return "json"
    return None

def _normalize_language(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return _LANGUAGE_ALIASES.get(text, text) if text else None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    return [value for value in values if value and not (value in seen or seen.add(value))]


def _metadata(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        source = chunk.get("source") if isinstance(chunk.get("source"), dict) else {}
        section = chunk.get("section") if isinstance(chunk.get("section"), dict) else {}
        metadata = dict(chunk.get("metadata") or {})
        for key in ("source_class", "doc_scope", "origin_lane", "canonical_id", "library_id", "dependency", "version", "resolved_version", "requested_version", "docs_exactness", "docs_binding_source", "freshness", "path", "url", "source_url", "title", "heading_path"):
            if key in chunk and key not in metadata:
                metadata[key] = chunk.get(key)
        for key in ("url", "source_url", "path", "title"):
            if key in source and key not in metadata:
                metadata[key] = source.get(key)
        if "heading_path" in section and "heading_path" not in metadata:
            metadata["heading_path"] = section.get("heading_path")
        snippet = chunk.get("snippet")
        if isinstance(snippet, dict) and "code_snippets" not in metadata:
            metadata["code_snippets"] = [snippet]
        return metadata
    metadata = getattr(chunk, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _content(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("content") or chunk.get("text") or "")
    return str(getattr(chunk, "content", None) or getattr(chunk, "text", None) or "")


def _title(chunk: Any, metadata: dict[str, Any]) -> str | None:
    return _string((chunk.get("title") if isinstance(chunk, dict) else getattr(chunk, "title", None)) or metadata.get("title"))


def _heading_path(chunk: Any, metadata: dict[str, Any]) -> str | None:
    if isinstance(chunk, dict):
        section = chunk.get("section") if isinstance(chunk.get("section"), dict) else {}
        return _string(chunk.get("heading_path") or section.get("heading_path") or metadata.get("heading_path"))
    return _string(getattr(chunk, "heading_path", None) or metadata.get("heading_path"))


def _source(chunk: Any, metadata: dict[str, Any]) -> str | None:
    if isinstance(chunk, dict):
        source = chunk.get("source")
        if isinstance(source, dict):
            return _string(source.get("url") or source.get("path") or source.get("source"))
        return _string(source or chunk.get("path") or metadata.get("source"))
    return _string(getattr(chunk, "source", None) or metadata.get("source"))


def _source_url(chunk: Any, metadata: dict[str, Any]) -> str | None:
    if isinstance(chunk, dict):
        source = chunk.get("source") if isinstance(chunk.get("source"), dict) else {}
        return _string(chunk.get("url") or chunk.get("source_url") or source.get("url") or metadata.get("url") or metadata.get("source_url"))
    return _string(getattr(chunk, "url", None) or metadata.get("url") or metadata.get("source_url"))


def _chunk_origin_lane(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("origin_lane") or chunk.get("doc_scope") or "")
    metadata = _metadata(chunk)
    return str(metadata.get("origin_lane") or metadata.get("doc_scope") or "")


def _exact_version_match(metadata: dict[str, Any]) -> bool | None:
    if "exact_version_match" in metadata:
        value = metadata.get("exact_version_match")
        return bool(value) if value is not None else None
    if metadata.get("docs_snapshot_exact") is not None:
        return bool(metadata.get("docs_snapshot_exact"))
    requested = metadata.get("requested_version")
    version = metadata.get("version") or metadata.get("resolved_version")
    if requested and version:
        if str(requested).strip().lower() in _FLOATING_VERSION_ALIASES:
            return False
        return str(requested) == str(version)
    if metadata.get("docs_exactness") in {"exact_version_url", "exact_snapshot"}:
        return True
    if metadata.get("fallback") or (str(version or "").lower() == "latest" and requested):
        return False
    return None


def _remove_ui_noise(value: str) -> str:
    text = value.replace("[¶]", "")
    text = re.sub(r"(?i)(?:^|\s)(copy code|copy|download|open in new tab|edit this page)(?=\s*$)", "", text)
    return text


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
