"""Pure occurrence-aware query reference resolution."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Sequence
import hashlib
from pathlib import PurePosixPath
import re

from .query_terms import documentation_technical_anchors, _looks_like_source_path
Role = Literal["source_locator", "symbol_identity", "semantic_subject", "retrieval_anchor", "unresolved"]
ResolutionState = Literal["resolved", "ambiguous", "missing", "unresolved"]
@dataclass(frozen=True, slots=True)
class ScopeKey:
    project_id: str
    version: str
    snapshot_id: str
@dataclass(frozen=True, slots=True)
class CatalogSource:
    document_id: str
    scope: ScopeKey
    canonical_path: str
    content_sha256: str
@dataclass(frozen=True, slots=True)
class QueryMention:
    mention_id: str
    start: int
    end: int
    text: str
    syntax_role: Role
    explicit: bool
@dataclass(frozen=True, slots=True)
class ResolvedReference:
    mention: QueryMention
    role: Role
    state: ResolutionState
    source_ids: tuple[str, ...]
    reason: str
@dataclass(frozen=True, slots=True)
class ReferencePlan:
    question: str
    references: tuple[ResolvedReference, ...]
    scope: ScopeKey
    catalog_complete: bool


# Shared with the source catalog. Unknown extensions never create stem aliases.
DOCUMENT_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_NAME = r'(?:`(?P<quoted>[^`\n]{1,160})`|"(?P<double>[^"\n]{1,160})"|(?P<bare>[\w~./\\:+-]+))'
_CONTEXT = re.compile(
    r"(?<!\w)(?P<context>file|document|файл(?:е|а|у|ом)?|документ(?:е|а|у|ом)?|"
    r"constant|class|function|method|symbol|flag|key|констант(?:а|ы|е|у)|"
    r"класс(?:а|е)?|функци(?:я|и|ю)|метод(?:а|е)?|library|package|"
    r"библиотек(?:а|и|е|у)|пакет(?:а|е)?)(?!\w)\s+" + _NAME, re.I,
)
_SOURCE_CONTEXT = re.compile(r"(?:file|document|файл\w*|документ\w*)\Z", re.I)
_SUBJECT_CONTEXT = re.compile(r"(?:library|package|библиотек\w*|пакет\w*)\Z", re.I)
_SOURCE_PREFIX = re.compile(
    r"(?:\b(?:in|from|within|according\s+to|read|open|for|about|and|or|в|из|согласно)\s+(?:the\s+)?|^)$", re.I,
)
_WEAK_SOURCE = re.compile(r"(?<!\w)(?:in|from|according\s+to)\s+the\s+" + _NAME, re.I)
_PATH = re.compile(r"(?<![\w/\\])(?:~?[/\\]|\.{1,2}[/\\])?(?:[\w.-]+[/\\])+[\w.-]+")
_QUOTED = re.compile(r'`([^`\n]{1,160})`|"([^"\n]{1,160})"')
_PREDICATES = frozenset({"is", "are", "was", "were", "does", "do", "returns", "return", "raises", "raise", "has", "have"})
_ROLE_WORDS = frozenset({"file", "document", "constant", "class", "library", "package", "function", "method"})


def _name_span(match: re.Match[str]) -> tuple[int, int]:
    group = next(key for key in ("quoted", "double", "bare") if match.group(key) is not None)
    start, end = match.span(group)
    if group == "bare":
        end = start + len(match[group].rstrip(".:,"))
    return start, end


def query_mentions(question: str) -> tuple[QueryMention, ...]:
    """Extract only declared grammatical relations; preserve original offsets.

    Role priority is contextual role > full path/quoted identity > lexical
    nomination. Bare capitalization nominates an unresolved occurrence, never
    a semantic subject. Unsupported natural-language forms remain unresolved.
    """
    spans: list[tuple[int, int, Role, bool]] = []

    def add(start: int, end: int, role: Role, explicit: bool) -> None:
        if start < end and not any(start < b and a < end for a, b, _, _ in spans):
            spans.append((start, end, role, explicit))

    for match in _CONTEXT.finditer(question):
        start, end = _name_span(match)
        if match.group("bare") and question[start:end].casefold() in _PREDICATES:
            continue
        if _SOURCE_CONTEXT.fullmatch(match["context"]):
            literal = match.group("quoted") is not None or match.group("double") is not None
            if not (literal or _SOURCE_PREFIX.search(question[:match.start()])):
                continue  # "document headings" is not a named document.
            role: Role = "source_locator"
        elif _SUBJECT_CONTEXT.fullmatch(match["context"]):
            role = "semantic_subject"
        else:
            role = "symbol_identity"
        add(start, end, role, True)
    for match in _WEAK_SOURCE.finditer(question):
        start, end = _name_span(match)
        if question[start:end].casefold() not in _ROLE_WORDS:
            add(start, end, "source_locator", False)
    for match in _QUOTED.finditer(question):
        start, end = match.span(1 if match[1] is not None else 2)
        value = question[start:end]
        path = ("/" in value or "\\" in value) and _looks_like_source_path(value)
        add(start, end, "source_locator" if path else "symbol_identity", True)
    for match in _PATH.finditer(question):
        value = match[0].rstrip(".:,")
        if _looks_like_source_path(value):
            add(match.start(), match.start() + len(value), "source_locator", True)
    for value in sorted(documentation_technical_anchors(question), key=lambda value: (-len(value), value)):
        for match in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", question):
            role = "symbol_identity" if any(c in value for c in "._/:+-") else "unresolved"
            add(*match.span(), role, role != "unresolved")
    query_id = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return tuple(QueryMention(f"{query_id}:{a}:{b}", a, b, question[a:b], role, explicit)
                 for a, b, role, explicit in sorted(spans))


def normalize_reference_path(value: str) -> str:
    """Separator normalization, not case folding, traversal collapse or rebasing."""
    return value.replace("\\", "/").removeprefix("./")


def _source_ids(name: str, catalog: Sequence[CatalogSource], suffixes: frozenset[str]) -> tuple[str, ...]:
    requested = normalize_reference_path(name)
    if (requested.startswith(("/", "~/")) or ".." in requested.split("/")
            or re.match(r"^[A-Za-z]:", requested)):
        return ()
    paths = [(source.document_id, normalize_reference_path(source.canonical_path)) for source in catalog]
    tiers = [paths]
    if "/" not in requested:
        tiers.extend((
            [(identity, PurePosixPath(path).name) for identity, path in paths],
            [(identity, PurePosixPath(path).stem) for identity, path in paths
             if PurePosixPath(path).suffix.casefold() in suffixes],
        ))
    for casefold in (False, True):
        for tier in tiers:
            found = {identity for identity, alias in tier if
                     (alias.casefold() == requested.casefold() if casefold else alias == requested)}
            if found:
                return tuple(sorted(found))
    return ()


def resolve_references(
    question: str, *, catalog: Sequence[CatalogSource], scope: ScopeKey,
    catalog_complete: bool = True, document_suffixes: frozenset[str] = DOCUMENT_SUFFIXES,
) -> ReferencePlan:
    """Link occurrences to a complete already-allowed snapshot, never top-k."""
    allowed = tuple(source for source in catalog if source.scope == scope)
    references = []
    for mention in query_mentions(question):
        role = mention.syntax_role
        ids: tuple[str, ...] = ()
        state: ResolutionState = "resolved"
        reason = "explicit_reference_role"
        if role == "source_locator":
            if not catalog_complete or not scope.project_id or not scope.snapshot_id:
                state, reason = "unresolved", "incomplete_source_catalog"
            else:
                ids = _source_ids(mention.text, allowed, document_suffixes)
                state = "resolved" if len(ids) == 1 else "ambiguous" if ids else "missing"
                reason = {"resolved": "unique_catalog_source", "ambiguous": "ambiguous_source_locator", "missing": "missing_source_locator"}[state]
                if not mention.explicit and not ids:
                    role, state, reason = "unresolved", "unresolved", "unresolved_reference_role"
        elif role == "unresolved":
            state, reason = "unresolved", "unresolved_reference_role"
        references.append(ResolvedReference(mention, role, state, ids, reason))
    return ReferencePlan(question, tuple(references), scope, catalog_complete)
