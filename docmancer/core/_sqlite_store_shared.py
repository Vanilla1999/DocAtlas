from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from docmancer.core.chunking import chunk_paragraphs
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.structured_chunking import (
    SCHEMA_VERSION as PARENT_CHILD_SCHEMA_VERSION,
    ChunkingConfig,
    chunk_markdown_parent_child,
    estimate_utf8_tokens,
)
from docmancer.docs.domain.quality import looks_like_code_or_command
from docmancer.retrieval.contextual_indexing import (
    build_context_prefix,
    embedding_input,
    normalized_filter_metadata,
)
from docmancer.retrieval.contracts import ContextConfig, canonical_hash


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)\n(.*?)^ {0,3}\1\s*$", re.MULTILINE | re.DOTALL)

# Keywords that indicate boilerplate/legal content.  Matched against
# normalized title words so numbered headings like "12. Miscellaneous"
# and subsections like "Privacy Policy" are caught.
_BOILERPLATE_KEYWORDS = frozenset({
    "terms", "conditions", "privacy", "policy", "legal", "disclaimer",
    "eula", "license", "agreement", "dmca", "copyright", "sla",
    "miscellaneous", "modifications", "indemnification", "severability",
    "arbitration", "jurisdiction", "governing", "waiver", "warranties",
    "limitation", "liability",
})

# Query stopwords that inflate BM25 scores for legal text without
# carrying search intent.
_QUERY_STOPWORDS = frozenset({
    "how", "do", "i", "a", "an", "the", "to", "is", "it", "in", "on",
    "of", "for", "my", "can", "what", "where", "when", "why", "does",
    "should", "would", "could", "which", "with", "this", "that", "are", "was",
    "be", "have", "has", "will", "we", "you", "your", "me",
    "как", "каково", "на", "для", "и", "или", "что", "это", "его",
    "ответь", "только", "основании", "проектной", "документации", "укажи",
    "утверждений", "модуль", "модуля", "модуле", "модулю", "модули", "модулей",
})

_GENERIC_QUERY_TERMS = frozenset({
    "add", "build", "configure", "configuration", "create", "docs",
    "documentation", "enable", "generate", "guide", "index", "indexing",
    "install", "overview", "reference", "request", "setup", "start", "use",
    "which", "workflow", "где", "какая", "какие", "какой", "когда", "может",
    "почему",
})

INDEX_SCHEMA_VERSION = "sqlite-sections-v1"


@dataclass(frozen=True, slots=True)
class RankingCandidate:
    """Auditable lexical candidate with one explicit score direction.

    SQLite FTS5 exposes BM25 as a lower-is-better cost.  DocAtlas converts
    that cost to a higher-is-better utility before applying named features;
    callers never have to infer whether adding a value is a boost or penalty.
    """

    stable_id: str
    section_id: int
    raw_component_ranks: tuple[tuple[str, float], ...]
    base_utility: float
    feature_contributions: tuple[tuple[str, float], ...]
    final_utility: float

    def trace(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "section_id": self.section_id,
            "score_direction": "higher_is_better",
            "raw_component_ranks": {
                name: round(value, 12) for name, value in self.raw_component_ranks
            },
            "base_utility": round(self.base_utility, 12),
            "feature_contributions": {
                name: round(value, 12) for name, value in self.feature_contributions
            },
            "final_utility": round(self.final_utility, 12),
        }


@dataclass(slots=True)
class IndexResult:
    sources: int
    sections: int
    generation_id: str | None = None


@dataclass(frozen=True, slots=True)
class _StagedExtraction:
    markdown_temp: Path
    json_temp: Path
    markdown_path: Path
    json_path: Path


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _slug(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:72] or "source"
    return f"{stem}-{digest}"


def _normalize_source_like(value: str | Path) -> str:
    return str(value).replace("\\", "/").rstrip("/")


def _stable_source_identity(doc: Document) -> str:
    metadata = dict(doc.metadata or {})
    explicit = str(metadata.get("source_identity") or "").strip()
    if explicit:
        return _normalize_source_like(explicit)
    canonical = str(metadata.get("canonical_url") or metadata.get("source_url") or "").strip()
    if canonical:
        return _normalize_source_like(canonical)
    relative = str(
        metadata.get("project_doc_path")
        or metadata.get("source_path")
        or ""
    ).strip()
    namespace = str(
        metadata.get("source_identity_namespace")
        or metadata.get("library_id")
        or metadata.get("source_class")
        or "document"
    ).strip()
    project_identity = str(
        metadata.get("repository_identity")
        or metadata.get("canonical_project_id")
        or metadata.get("project_id")
        or metadata.get("repository_url")
        or ""
    ).strip()
    if project_identity and not metadata.get("source_identity_namespace"):
        namespace = f"{namespace}:{_normalize_source_like(project_identity)}"
    if relative:
        return f"{namespace}:{_normalize_source_like(relative).lstrip('/')}"
    # Direct callers may not have loader metadata. Keep their logical source,
    # but never inject a machine-specific resolved path into the stable ID.
    return _normalize_source_like(doc.source)


def _split_sections(content: str) -> list[tuple[str, int, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        return [("Document", 1, content.strip())] if content.strip() else []

    sections: list[tuple[str, int, str]] = []
    if matches[0].start() > 0:
        intro = content[: matches[0].start()].strip()
        if intro:
            sections.append(("Introduction", 1, intro))

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        level = len(match.group(1))
        title = match.group(2).strip()
        text = content[start:end].strip()
        if text:
            sections.append((title, level, text))
    return sections


def _split_sections_with_anchors(content: str) -> list[tuple[str, int, str, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        stripped = content.strip()
        return [("Document", 1, stripped, "Document")] if stripped else []

    sections: list[tuple[str, int, str, str]] = []
    if matches[0].start() > 0:
        intro = content[: matches[0].start()].strip()
        if intro:
            sections.append(("Introduction", 1, intro, "Introduction"))

    heading_stack: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, title))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        text = content[start:end].strip()
        if text:
            sections.append((title, level, text, " > ".join(item for _, item in heading_stack)))
    return sections


def _sections_for_document(doc: Document) -> list[tuple[str, int, str, dict[str, str]]]:
    metadata = dict(doc.metadata or {})
    strategy = str(metadata.get("chunking_strategy") or "heading")
    chunk_size = int(metadata.get("chunk_size") or 800)
    chunk_overlap = int(metadata.get("chunk_overlap") or 100)

    if strategy == "paragraph":
        title = str(metadata.get("title") or Path(doc.source).stem or "Document")
        chunks = chunk_paragraphs(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        sections: list[tuple[str, int, str, dict[str, str]]] = []
        for index, text in enumerate(chunks):
            page_match = re.search(r"##\s+Page\s+(\d+)", text)
            anchor = f"Page {page_match.group(1)}" if page_match else f"{title} chunk {index + 1}"
            sections.append((title, 1, text, {"anchor": anchor}))
        return sections

    if strategy == "single":
        # Atomic-record sources (e.g. USPTO case files): the whole document is one
        # section. We do not split on headings — heading-aware splitting would
        # otherwise carve each record into two or three sub-sections, which is
        # the wrong shape for "match the mark against every case file".
        title = str(metadata.get("title") or Path(doc.source).stem or "Document")
        anchor = str(metadata.get("anchor") or title)
        text = doc.content.strip()
        if not text:
            return []
        return [(title, 1, text, {"anchor": anchor})]

    return [
        (title, level, text, {"anchor": anchor})
        for title, level, text, anchor in _split_sections_with_anchors(doc.content)
    ]


def document_section_count(doc: Document) -> int:
    """Return the exact number of SQLite sections that ingest will create."""
    return len(_sections_for_document(doc))


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _code_snippets(text: str, *, limit: int = 3, max_chars: int = 1200) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    for match in FENCED_CODE_RE.finditer(text):
        language = match.group(2).strip().split()[0] if match.group(2).strip() else ""
        code = match.group(3).strip()
        if not code:
            continue
        snippets.append({"language": language, "code": code[:max_chars]})
        if len(snippets) >= limit:
            break
    return snippets or _code_like_snippets(text, max_chars=max_chars)


def _code_like_snippets(text: str, *, max_chars: int = 1200) -> list[dict[str, str]]:
    if not looks_like_code_or_command(text):
        return []
    lines = [line.strip() for line in text.splitlines()]
    code_lines: list[str] = []
    for line in lines:
        stripped = line.strip("`").strip()
        if not stripped:
            if code_lines and code_lines[-1] != "":
                code_lines.append("")
            continue
        if _looks_like_code_line(stripped):
            code_lines.append(stripped)
        elif code_lines and code_lines[-1] != "":
            code_lines.append("")

    while code_lines and code_lines[-1] == "":
        code_lines.pop()
    compact = "\n".join(code_lines).strip()
    meaningful = [line for line in code_lines if line]
    if len(meaningful) < 3 or len(compact) < 40:
        return []
    return [{"language": "", "code": compact[:max_chars]}]


def _looks_like_code_line(line: str) -> bool:
    code_tokens = (
        "=>", "{", "}", ";", "(", ")", "=", "<", ">", "//",
        "final ", "class ", "Future", "Provider", "ref.", "return ", "await ", "async",
    )
    if line.startswith(("#", "- ", "* ", "|")):
        return False
    return any(token in line for token in code_tokens)

__all__ = [name for name in globals() if not name.startswith('__')]
