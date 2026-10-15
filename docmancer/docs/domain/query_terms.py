"""Documentation-query terms owned by the project-context domain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


# A shaped command followed by one explicit long-option value is a literal
# retrieval hypothesis, not a claim about option arity or answer sufficiency.
# Do not consume natural-language connectors or cross a physical line.
_COMMAND_OPTION_VALUE_RE = re.compile(
    r"(?<![\w./-])[a-z][a-z0-9]*(?:-[a-z0-9]+)+[ \t]+"
    r"--[A-Za-z][A-Za-z0-9-]{1,118}(?:[ \t]+|=)"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9_.:/-]{0,79})(?![\w.-])"
)
_TECHNICAL_TERM_PATTERNS = (
    re.compile(r"[`\"]([^`\"\n]{1,160})[`\"]"),
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
    ("quoted", re.compile(r"[`\"]([^`\"\n]{1,160})[`\"]")),
    ("flag", re.compile(r"(?<![\w.-])--[A-Za-z][A-Za-z0-9-]{1,118}")),
    ("error_code", re.compile(r"\b(?:ERR(?:OR)?[_-]?\d+|[A-Z][A-Z0-9]+[_-]\d+)\b")),
    ("config_key", re.compile(r"\b[A-Z][A-Z0-9_]{2,119}\b")),
    ("symbol", re.compile(r"\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+\b")),
    ("symbol", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("path", re.compile(r"(?<![\w/])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")),
)


@dataclass(frozen=True, slots=True)
class DocumentationExactTerm:
    value: str
    normalized_value: str
    kind: str


def is_exact_technical_token(token: str) -> bool:
    """Classify lexical identity without treating request framing as identity."""
    return (
        any(char in token for char in "._/:+-")
        or any(char.isupper() for char in token[1:])
        or (token[:1].isupper() and len(token) > 2)
    )


def documentation_technical_anchors(question: str, *, limit: int = 12) -> tuple[str, ...]:
    """Extract bounded exact anchors without depending on retrieval infrastructure."""
    values: list[str] = []
    for match in _COMMAND_OPTION_VALUE_RE.finditer(question):
        # Use the existing quoted-exact constraint so a wrong option value,
        # split mentions, or another command cannot qualify this extra probe.
        literal = "`" + " ".join(match.group(0).split()) + "`"
        if len(literal) - 2 > 160:
            continue
        if literal not in values:
            values.append(literal)
        if len(values) >= min(4, limit):
            break
    if len(values) >= limit:
        return tuple(values)
    # A filename/qualified symbol is one identity, not independent identifiers
    # for each uppercase or dotted substring inside the same source span.
    # Keep a separately mentioned token: containment is positional, not textual.
    whole_spans = [match.span() for match in _TECHNICAL_TERM_PATTERNS[6].finditer(question)]
    for pattern in _TECHNICAL_TERM_PATTERNS:
        for match in pattern.finditer(question):
            if any(start <= match.start() and match.end() <= end
                   and match.span() != (start, end) for start, end in whole_spans):
                continue
            value = (match.group(1) if match.lastindex else match.group(0)).strip()
            if (
                value
                and value not in values
                and f"`{value}`" not in values
            ):
                values.append(value)
            if len(values) >= limit:
                return tuple(values)
    return tuple(values)


@lru_cache(maxsize=512)
def documentation_query_terms(question: str) -> tuple[str, ...]:
    """Bounded literal lexical terms, retaining connectors and negation."""
    return tuple(dict.fromkeys(
        token.casefold()
        for token in re.findall(r"[\w.:/+-]+", question)
        if token
    ))[:32]


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



@dataclass(frozen=True, slots=True)
class QueryConstraintRoles:
    hard_exact: tuple[str, ...]
    bound_subjects: tuple[str, ...]
    retrieval_anchors: tuple[str, ...]


@lru_cache(maxsize=512)
def query_constraint_roles(question: str) -> QueryConstraintRoles:
    """Exact syntactic constraints only; no inferred semantic subject roles."""
    hard = tuple(dict.fromkeys(term.normalized_value for term in documentation_exact_terms(question)))
    return QueryConstraintRoles(hard, (), documentation_technical_anchors(question))


def _looks_like_source_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    leaf = normalized.rsplit("/", 1)[-1]
    return (
        normalized.startswith(("./", "../", "/"))
        or bool(Path(leaf).suffix)
    )


__all__ = [
    "DocumentationExactTerm",
    "QueryConstraintRoles",
    "documentation_exact_terms",
    "documentation_query_terms",
    "documentation_technical_anchors",
    "query_constraint_roles",
    "is_exact_technical_token",
]


def supplemental_query_is_useful(text: str) -> bool:
    """Explicit lookups need no topic/function-word approval."""
    return bool(str(text or "").strip())
