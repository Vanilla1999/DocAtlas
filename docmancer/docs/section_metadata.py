"""Deterministic, bounded section metadata for project-owned Markdown docs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_PATH = re.compile(r"(?<![\w.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_MAX_SECTIONS = 256
_MAX_REFERENCES_PER_SECTION = 64


def extract_section_metadata(path: Path, *, source_document_path: str) -> list[dict[str, object]]:
    """Return evidence-only metadata for Markdown headings in *path*.

    Only explicit repository-like paths and inline-code symbols/config keys are
    recorded.  Other documentation formats deliberately return no sections so
    callers can retain their file-level fallback rather than inventing claims.
    """

    if path.suffix.lower() not in {".md", ".mdx"}:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return extract_markdown_section_metadata(text, source_document_path=source_document_path)


def extract_markdown_section_metadata(text: str, *, source_document_path: str) -> list[dict[str, object]]:
    """Extract heading-scoped evidence without parsing prose semantically."""

    sections: list[tuple[list[str], list[str]]] = []
    heading_stack: list[str] = []
    current_lines: list[str] | None = None
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if current_lines is not None:
                sections.append((heading_stack.copy(), current_lines))
                if len(sections) >= _MAX_SECTIONS:
                    break
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_lines = [line]
        elif current_lines is not None:
            current_lines.append(line)
    if current_lines is not None and len(sections) < _MAX_SECTIONS:
        sections.append((heading_stack.copy(), current_lines))

    metadata: list[dict[str, object]] = []
    for heading_path, lines in sections:
        content = "\n".join(lines)
        mentioned_paths = _unique(_PATH.findall(content))[:_MAX_REFERENCES_PER_SECTION]
        mentioned_symbols = _unique(
            token.strip()
            for token in _INLINE_CODE.findall(content)
            if "/" not in token and _SYMBOL.fullmatch(token.strip())
        )[:_MAX_REFERENCES_PER_SECTION]
        metadata.append({
            "source_document_path": source_document_path,
            "heading_path": heading_path,
            "mentioned_paths": mentioned_paths,
            "mentioned_symbols": mentioned_symbols,
            "content_hash": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        })
    return metadata


def _unique(values: object) -> list[str]:
    return list(dict.fromkeys(str(value).replace("\\", "/") for value in values if str(value)))
