"""Bounded canonical identities for technical terms in project questions.

The answer pipeline must treat a small set of spelling variants as one
technical identity without weakening local proof to arbitrary substring
matching.  This module is query/proof scoped: it never rewrites indexed text or
changes global FTS token statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Literal


MAX_TECHNICAL_TERMS = 12
MAX_TERM_CHARS = 160
MAX_TERM_ALIASES = 8

TechnicalTermKind = Literal[
    "cli_command", "cli_flag", "env_var", "config_key", "code_symbol", "plain_term",
]

_CLI_FLAG_RE = re.compile(r"(?<![\w-])--[A-Za-z][A-Za-z0-9-]{1,118}(?![\w-])")
_ENV_VAR_RE = re.compile(r"(?<!\w)[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?!\w)")
_DOTTED_RE = re.compile(
    r"(?<!\w)[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+(?!\w)"
)
_SNAKE_RE = re.compile(r"(?<!\w)[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+(?!\w)")
_CLI_COMMAND_RE = re.compile(r"(?<![\w-])[a-z][a-z0-9]*(?:-[a-z0-9]+)+(?![\w-])")
_QUOTED_RE = re.compile(r"[`\"']([^`\"'\n]{2,160})[`\"']")

# A hyphen is ambiguous in ordinary prose. Bind unquoted command identities
# to local command syntax instead of maintaining exceptions for known words.
def _explicit_command_context(source: str, start: int, end: int) -> bool:
    before, after = source[:start], source[end:]
    return bool(
        not before.strip() and not after.strip(" ?.!\n\t")
        or re.match(r"^\s+--[A-Za-z]", after) is not None
    )


def _bounded(value: object) -> str:
    return " ".join(str(value or "").strip().strip("`\"'").split())[:MAX_TERM_CHARS]


def _tokens(value: object) -> tuple[str, ...]:
    raw = _bounded(value).removeprefix("--")
    return tuple(token.casefold() for token in re.split(r"[\s_-]+", raw) if token)


def canonical_technical_term(
    value: object,
    kind: TechnicalTermKind | None = None,
) -> str:
    """Return a bounded literal identity; separators are significant."""
    raw = _bounded(value)
    return raw if kind == "env_var" else raw.casefold()


def infer_technical_kind(value: object, *, context: str = "") -> TechnicalTermKind:
    raw = _bounded(value)
    if raw.startswith("--"):
        return "cli_flag"
    if _ENV_VAR_RE.fullmatch(raw):
        return "env_var"
    if _DOTTED_RE.fullmatch(raw):
        return "config_key" if raw.casefold() == raw and "." in raw else "code_symbol"
    if _SNAKE_RE.fullmatch(raw):
        return "code_symbol"
    if _CLI_COMMAND_RE.fullmatch(raw):
        return "cli_command"
    return "plain_term"


def _preferred_spelling(raw: str, kind: TechnicalTermKind) -> str:
    return raw


def _aliases(raw: str, kind: TechnicalTermKind) -> tuple[str, ...]:
    return (raw,) if raw else ()


@dataclass(frozen=True, slots=True)
class TechnicalTerm:
    raw: str
    canonical: str
    kind: TechnicalTermKind
    aliases: tuple[str, ...]
    query_span_start: int | None = None
    query_span_end: int | None = None

    def __post_init__(self) -> None:
        if not self.raw or not self.canonical or not self.aliases:
            raise ValueError("invalid technical term")
        if (self.query_span_start is None) != (self.query_span_end is None):
            raise ValueError("technical term query span must be complete")
        if self.query_span_start is not None and (
            self.query_span_start < 0
            or self.query_span_end is None
            or self.query_span_end <= self.query_span_start
        ):
            raise ValueError("invalid technical term query span")


def coerce_technical_term(
    value: object,
    preferred_kind: TechnicalTermKind | None = None,
    *,
    context: str = "",
    query_span_start: int | None = None,
    query_span_end: int | None = None,
) -> TechnicalTerm:
    raw_input = _bounded(value)
    kind = preferred_kind or infer_technical_kind(raw_input, context=context)
    raw = _preferred_spelling(raw_input, kind)
    return TechnicalTerm(
        raw=raw,
        canonical=canonical_technical_term(raw, kind),
        kind=kind,
        aliases=_aliases(raw_input, kind),
        query_span_start=query_span_start,
        query_span_end=query_span_end,
    )


def controlled_noun_forms(value: object) -> tuple[str, ...]:
    """Literal noun spelling only; no inferred singulars."""
    raw = _bounded(value).casefold()
    return (raw,) if raw else ()


def _term_pattern(value: object, *, kind: TechnicalTermKind | None = None) -> str:
    raw = _bounded(value)
    if not raw:
        return r"(?!)"
    return rf"(?<![\w.:-]){re.escape(raw)}(?![\w.:-])"


def term_sequence_spans(value: object, text: object) -> tuple[tuple[int, int], ...]:
    """Return exact token-sequence spans without substring fallback."""

    raw = _bounded(value)
    haystack = str(text or "")
    if not raw or not haystack:
        return ()
    return tuple(match.span() for match in re.finditer(_term_pattern(raw), haystack, re.I))


def term_sequence_present(value: object, text: object) -> bool:
    """Match an exact token sequence; never fall back to substring matching."""

    return bool(term_sequence_spans(value, text))


def technical_term_spans(
    term: TechnicalTerm,
    text: object,
    *,
    require_kind_shape: bool = True,
) -> tuple[tuple[int, int], ...]:
    """Return alias-aware spans that preserve the technical identifier shape."""

    haystack = str(text or "")
    spans: list[tuple[int, int]] = []
    for alias in term.aliases:
        for match in re.finditer(_term_pattern(alias, kind=term.kind), haystack, re.I):
            surface = match.group(0)
            if require_kind_shape:
                if term.kind == "cli_flag" and not (
                    surface.startswith("--") or "_" in surface or "-" in surface
                ):
                    continue
                if term.kind == "cli_command" and not ("-" in surface or "_" in surface):
                    continue
                if term.kind == "env_var" and not (
                    "_" in surface and surface.upper() == surface
                ):
                    continue
                if term.kind in {"code_symbol", "config_key"}:
                    raw = term.raw
                    # Retrieval may use separator aliases, but proof must keep
                    # code/config shape so ordinary prose (``foo bar``) cannot
                    # impersonate ``foo_bar`` or ``foo.bar``.
                    if "_" in raw and "_" not in surface:
                        continue
                    if "." in raw and "." not in surface:
                        continue
                    if "::" in raw and "::" not in surface:
                        continue
            spans.append(match.span())
    return tuple(dict.fromkeys(spans))


def technical_term_present(
    term: TechnicalTerm,
    text: object,
    *,
    require_kind_shape: bool = True,
) -> bool:
    return bool(technical_term_spans(
        term, text, require_kind_shape=require_kind_shape,
    ))


def extract_technical_terms(question: str) -> tuple[TechnicalTerm, ...]:
    """Extract bounded technical identities without promoting ordinary prose."""

    source = str(question or "")
    candidates: list[tuple[int, int, str, TechnicalTermKind | None]] = []
    occupied: list[tuple[int, int]] = []

    def add(match: re.Match[str], kind: TechnicalTermKind | None = None, *, group: int = 0) -> None:
        start, end = match.span(group)
        if any(left <= start and end <= right for left, right in occupied):
            return
        candidates.append((start, end, match.group(group), kind))
        occupied.append((start, end))

    for match in _QUOTED_RE.finditer(source):
        add(match, group=1)
    for pattern, kind in (
        (_CLI_FLAG_RE, "cli_flag"),
        (_ENV_VAR_RE, "env_var"),
        (_DOTTED_RE, None),
        (_SNAKE_RE, None),
        (_CLI_COMMAND_RE, "cli_command"),
    ):
        for match in pattern.finditer(source):
            candidate_kind = kind
            if kind == "cli_command" and not _explicit_command_context(source, *match.span()):
                # Keep lexical recall without inferring a CLI identity from
                # punctuation. This applies equally to prose and borrowed terms.
                candidate_kind = "plain_term"
            add(match, candidate_kind)  # type: ignore[arg-type]

    results: list[TechnicalTerm] = []
    seen: set[tuple[str, str]] = set()
    for start, end, value, kind in sorted(candidates, key=lambda item: (item[0], item[1], item[2])):
        term = coerce_technical_term(
            value,
            kind,
            context=source,
            query_span_start=start,
            query_span_end=end,
        )
        key = (term.kind, term.canonical.casefold())
        if key in seen:
            continue
        seen.add(key)
        results.append(term)
        if len(results) >= MAX_TECHNICAL_TERMS:
            break
    return tuple(results)


def aliases_for_terms(values: Iterable[object]) -> tuple[str, ...]:
    aliases: list[str] = []
    for value in values:
        aliases.extend(coerce_technical_term(value).aliases)
    return tuple(dict.fromkeys(aliases))


__all__ = [
    "MAX_TECHNICAL_TERMS", "TechnicalTerm", "TechnicalTermKind",
    "aliases_for_terms", "canonical_technical_term", "coerce_technical_term",
    "controlled_noun_forms", "extract_technical_terms", "infer_technical_kind",
    "technical_term_present", "technical_term_spans", "term_sequence_present",
    "term_sequence_spans",
]
