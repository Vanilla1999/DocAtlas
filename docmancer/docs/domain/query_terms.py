"""Documentation-query terms owned by the project-context domain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_REQUEST_FRAMING_TERMS = frozenset({
    "describe", "explain", "how", "please", "show", "tell", "what", "which",
})
_TECHNICAL_TERM_PATTERNS = (
    re.compile(r"[`\"]([^`\"\n]{2,160})[`\"]"),
    re.compile(r"(?<![\w.-])--[A-Za-z][A-Za-z0-9-]{1,118}"),
    re.compile(r"\b(?:ERR(?:OR)?[_-]?\d+|[A-Z][A-Z0-9]+[_-]\d+)\b"),
    re.compile(r"\b[A-Z][A-Z0-9_]{2,119}\b"),
    re.compile(r"\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+\b"),
    re.compile(r"\b[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*\b"),
    re.compile(r"(?<![\w/])(?:~?/|\.{1,2}/)?(?:[A-Za-z0-9_.-]+/)*"
               r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![\w/])"),
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
)
_EXACT_TERM_PATTERNS = (
    ("quoted", re.compile(r"[`\"]([^`\"\n]{2,160})[`\"]")),
    ("flag", re.compile(r"(?<![\w.-])--[A-Za-z][A-Za-z0-9-]{1,118}")),
    ("error_code", re.compile(r"\b(?:ERR(?:OR)?[_-]?\d+|[A-Z][A-Z0-9]+[_-]\d+)\b")),
    ("config_key", re.compile(r"\b[A-Z][A-Z0-9_]{2,119}\b")),
    ("symbol", re.compile(r"\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+\b")),
    ("path", re.compile(r"(?<![\w/])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")),
)
_PATH_ROOTS = frozenset({
    "app", "bin", "cmd", "config", "docmancer", "docs", "eval", "lib",
    "packages", "scripts", "src", "test", "tests", "tools", "wiki",
})


@dataclass(frozen=True, slots=True)
class DocumentationExactTerm:
    value: str
    normalized_value: str
    kind: str


def is_exact_technical_token(token: str) -> bool:
    """Classify lexical identity without treating request framing as identity."""
    if token.casefold() in _REQUEST_FRAMING_TERMS:
        return False
    return (
        any(char in token for char in "._/:+-")
        or any(char.isupper() for char in token[1:])
        or (token[:1].isupper() and len(token) > 2)
    )


def documentation_technical_anchors(question: str, *, limit: int = 12) -> tuple[str, ...]:
    """Extract bounded exact anchors without depending on retrieval infrastructure."""
    values: list[str] = []
    for pattern in _TECHNICAL_TERM_PATTERNS:
        for match in pattern.finditer(question):
            value = (match.group(1) if match.lastindex else match.group(0)).strip()
            if (
                value
                and value.casefold() not in {"docatlas", "docmancer"}
                and value not in values
            ):
                values.append(value)
            if len(values) >= limit:
                return tuple(values)
    return tuple(values)


def documentation_exact_terms(
    question: str, *, limit: int = 12,
) -> tuple[DocumentationExactTerm, ...]:
    """Extract typed exact terms without depending on retrieval infrastructure."""
    found: list[DocumentationExactTerm] = []
    seen: set[str] = set()
    path_spans = [
        match.span()
        for match in dict(_EXACT_TERM_PATTERNS)["path"].finditer(question)
        if _looks_like_source_path(match.group(0))
    ]
    for kind, pattern in _EXACT_TERM_PATTERNS:
        for match in pattern.finditer(question):
            if kind != "path" and any(
                start <= match.start() and match.end() <= end
                for start, end in path_spans
            ):
                continue
            value = " ".join(
                (match.group(1) if match.lastindex else match.group(0)).split()
            )[:160]
            if kind == "config_key" and "_" not in value:
                continue
            if kind == "path" and not _looks_like_source_path(value):
                continue
            normalized = value.casefold()
            if not normalized or normalized in seen:
                continue
            found.append(DocumentationExactTerm(value, normalized, kind))
            seen.add(normalized)
            if len(found) >= limit:
                return tuple(found)
    return tuple(found)


def _looks_like_source_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    first = normalized.partition("/")[0]
    leaf = normalized.rsplit("/", 1)[-1]
    return (
        normalized.startswith(("./", "../", "/"))
        or first.casefold() in _PATH_ROOTS
        or bool(Path(leaf).suffix)
    )


__all__ = [
    "DocumentationExactTerm",
    "documentation_exact_terms",
    "documentation_technical_anchors",
    "is_exact_technical_token",
]
