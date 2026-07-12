"""Deterministic, bounded section metadata for project-owned Markdown docs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_PATH = re.compile(r"(?<![\w.-])(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]*[A-Za-z0-9_]")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*$")
_MAX_SECTIONS = 256
_MAX_REFERENCES_PER_SECTION = 64
_MAX_HEADING_CHARACTERS = 512
_MAX_REFERENCE_CHARACTERS = 4096
_MAX_SYMBOL_CHARACTERS = 512
SECTION_METADATA_MAX_JSON_BYTES = 1024 * 1024
SECTION_METADATA_SCHEMA_VERSION = "project-sections-3"
SECTION_PARSE_REASON_CODES = {
    "parsed": "section_metadata_parsed",
    "empty": "section_document_empty",
    "unsupported": "section_format_unsupported",
    "read_error": "section_document_read_error",
}
SECTION_PARSE_STATUSES = frozenset(SECTION_PARSE_REASON_CODES)


@dataclass(frozen=True)
class SectionMetadataResult:
    sections: list[dict[str, object]]
    status: str
    reason_code: str


def extract_section_metadata(path: Path, *, source_document_path: str) -> list[dict[str, object]]:
    """Return evidence-only metadata for Markdown headings in *path*.

    Only explicit repository-like paths and inline-code symbols/config keys are
    recorded.  Other documentation formats deliberately return no sections so
    callers can retain their file-level fallback rather than inventing claims.
    """

    return extract_section_metadata_result(path, source_document_path=source_document_path).sections


def extract_section_metadata_result(path: Path, *, source_document_path: str) -> SectionMetadataResult:
    """Return sections plus an explicit parse outcome.

    An empty result is safe only when the document was read successfully and
    was genuinely empty. Unsupported formats and read failures remain visible
    so impact analysis cannot mistake missing evidence for proof of no impact.
    """

    if path.suffix.lower() not in {".md", ".mdx"}:
        return SectionMetadataResult([], "unsupported", "section_format_unsupported")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return SectionMetadataResult([], "read_error", "section_document_read_error")
    if not text.strip():
        return SectionMetadataResult([], "empty", "section_document_empty")
    return SectionMetadataResult(
        extract_markdown_section_metadata(text, source_document_path=source_document_path),
        "parsed",
        "section_metadata_parsed",
    )


def extract_markdown_section_metadata(text: str, *, source_document_path: str) -> list[dict[str, object]]:
    """Extract heading-scoped evidence without parsing prose semantically."""

    sections: list[tuple[list[str], list[str]]] = []
    heading_stack: list[str] = []
    # Content before the first heading is a real document section. This also
    # covers headingless Markdown instead of silently discarding all evidence.
    current_lines: list[str] | None = []
    fence_marker: tuple[str, int] | None = None
    sections_truncated = False
    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker = (marker[0], len(marker))
            elif marker[0] == fence_marker[0] and len(marker) >= fence_marker[1]:
                fence_marker = None
            if current_lines is not None:
                current_lines.append(line)
            continue
        if fence_marker is not None:
            if current_lines is not None:
                current_lines.append(line)
            continue
        match = _HEADING.match(line)
        if match:
            if current_lines:
                sections.append((heading_stack.copy(), current_lines))
                if len(sections) >= _MAX_SECTIONS:
                    sections_truncated = True
                    break
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_lines = [line]
        elif current_lines is not None:
            current_lines.append(line)
    if current_lines is not None and current_lines and len(sections) < _MAX_SECTIONS:
        sections.append((heading_stack.copy(), current_lines))

    metadata: list[dict[str, object]] = []
    metadata_json_bytes = 2  # JSON list brackets.
    metadata_budget_truncated = False
    for heading_path, lines in sections:
        content = "\n".join(lines)
        all_paths = _explicit_paths(content)
        all_symbols = _unique(
            token.strip()
            for token in _INLINE_CODE.findall(content)
            if "/" not in token and _SYMBOL.fullmatch(token.strip())
        )
        bounded_heading = [value[:_MAX_HEADING_CHARACTERS] for value in heading_path]
        bounded_paths = [value for value in all_paths if len(value) <= _MAX_REFERENCE_CHARACTERS]
        bounded_symbols = [value for value in all_symbols if len(value) <= _MAX_SYMBOL_CHARACTERS]
        fields_truncated = (
            bounded_heading != heading_path
            or len(bounded_paths) != len(all_paths)
            or len(bounded_symbols) != len(all_symbols)
        )
        row: dict[str, object] = {
            "source_document_path": source_document_path,
            "heading_path": bounded_heading,
            "mentioned_paths": bounded_paths[:_MAX_REFERENCES_PER_SECTION],
            "mentioned_symbols": bounded_symbols[:_MAX_REFERENCES_PER_SECTION],
            "paths_truncated": len(bounded_paths) > _MAX_REFERENCES_PER_SECTION,
            "symbols_truncated": len(bounded_symbols) > _MAX_REFERENCES_PER_SECTION,
            "fields_truncated": fields_truncated,
            "document_sections_truncated": sections_truncated,
            "content_hash": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        }
        # Match SQLiteStore's JSON representation so this budget is a real
        # storage/read boundary rather than only a compact-JSON estimate.
        row_bytes = len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
        separator_bytes = 2 if metadata else 0
        if metadata_json_bytes + separator_bytes + row_bytes > SECTION_METADATA_MAX_JSON_BYTES:
            metadata_budget_truncated = True
            break
        metadata.append(row)
        metadata_json_bytes += separator_bytes + row_bytes
    if metadata_budget_truncated:
        for row in metadata:
            row["document_sections_truncated"] = True
    return metadata


def _unique(values: object) -> list[str]:
    return list(dict.fromkeys(str(value).replace("\\", "/") for value in values if str(value)))


def _explicit_paths(content: str) -> list[str]:
    paths: list[str] = []
    for match in _PATH.finditer(content):
        # A URL host/path is external evidence, not a repository path.
        if content[max(0, match.start() - 2):match.start()] == "//":
            continue
        value = match.group(0).replace("\\", "/")
        if value.startswith("./"):
            value = value[2:]
        paths.append(value.lstrip("/"))
    return _unique(paths)
