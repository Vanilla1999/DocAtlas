"""Shared deterministic request-intent predicates for routing and patch planning."""

from __future__ import annotations

from dataclasses import dataclass
import re


MAX_INTENT_SCAN_CHARS = 4_000
MAX_INTENT_CLAUSES = 12

_ACTION_HEAD = re.compile(
    r"\s*(?:[-*]\s+)?(?:(?:please|пожалуйста)\s+)?(?P<verb>"
    r"implement|create|build|write|develop|introduce|replace|add|change|edit|modify|fix|"
    r"refactor|delete|remove|rename|update|patch|migrate|code|make|"
    r"реализ\w*|созда\w*|сдела\w*|напиш\w*|разработ\w*|добав\w*|измен\w*|"
    r"исправ\w*|(?:от)?рефактор\w*|замен\w*|удал\w*|переимен\w*|обнов\w*)\b",
    re.IGNORECASE,
)
_FENCE_LINE = re.compile(r"(?m)^[ \t]*(?P<fence>```|~~~)[^\n]*(?:\n|$)")


@dataclass(frozen=True, slots=True)
class ChangeIntentClause:
    """One top-level imperative clause with offsets into the original request."""

    start: int
    end: int
    verb: str
    verb_start: int
    verb_end: int


def _mask_non_top_level_text(text: str) -> str:
    """Mask quoted/code content while preserving offsets.

    Commands shown as examples in fenced code, inline code, or quoted prose are
    data rather than user mutation intent. Replacing their bytes with spaces
    lets the sentence scanner keep exact offsets without accidentally routing
    on those examples. An unclosed fenced block is masked to end-of-input so a
    malformed example cannot manufacture mutation authority.
    """

    chars = list(text)
    masked = [False] * len(chars)

    def hide(start: int, end: int) -> None:
        for index in range(max(0, start), min(len(chars), end)):
            if chars[index] not in "\r\n":
                chars[index] = " "
            masked[index] = True

    fence_matches = list(_FENCE_LINE.finditer(text))
    index = 0
    while index < len(fence_matches):
        opener = fence_matches[index]
        if any(masked[opener.start():opener.end()]):
            index += 1
            continue
        fence = opener.group("fence")
        closer = next(
            (
                candidate
                for candidate in fence_matches[index + 1:]
                if candidate.group("fence") == fence
            ),
            None,
        )
        if closer is None:
            hide(opener.start(), len(text))
            break
        hide(opener.start(), closer.end())
        index = fence_matches.index(closer) + 1

    for match in re.finditer(r"`[^`\n]*`", text):
        if not any(masked[match.start():match.end()]):
            hide(match.start(), match.end())
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', text):
        if not any(masked[match.start():match.end()]):
            hide(match.start(), match.end())
    return "".join(chars)


def _top_level_clause_spans(masked: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    start = 0
    index = 0
    while index < len(masked):
        char = masked[index]
        boundary = char in "\r\n"
        if char in ".!?":
            boundary = index + 1 == len(masked) or masked[index + 1].isspace()
        if boundary:
            end = index + 1
            if masked[start:end].strip():
                spans.append((start, end))
                if len(spans) >= MAX_INTENT_CLAUSES:
                    return tuple(spans)
            while end < len(masked) and masked[end].isspace():
                end += 1
            start = end
            index = end
            continue
        index += 1
    if start < len(masked) and masked[start:].strip() and len(spans) < MAX_INTENT_CLAUSES:
        spans.append((start, len(masked)))
    return tuple(spans)


def find_change_clause(question: str) -> ChangeIntentClause | None:
    """Find a real top-level change imperative, including after a short preamble.

    The scanner is deliberately clause-aware instead of searching arbitrary
    substrings: a request may describe a defect in sentence one and say
    ``Fix ...`` in sentence two, while quoted/code examples must never create
    mutation authority.
    """

    source = str(question or "")[:MAX_INTENT_SCAN_CHARS]
    if not source.strip():
        return None
    masked = _mask_non_top_level_text(source)
    for start, end in _top_level_clause_spans(masked):
        match = _ACTION_HEAD.match(masked, start, end)
        if match is None:
            continue
        verb_start, verb_end = match.span("verb")
        return ChangeIntentClause(
            start=match.start(),
            end=end,
            verb=source[verb_start:verb_end],
            verb_start=verb_start,
            verb_end=verb_end,
        )
    return None


def is_change_request(question: str) -> bool:
    """Return true only for an explicit top-level change imperative."""

    return find_change_clause(question) is not None


def model_projection_kind(question: str) -> str:
    return "patch_context" if is_change_request(question) else "docs_answer"


__all__ = [
    "ChangeIntentClause",
    "find_change_clause",
    "is_change_request",
    "model_projection_kind",
]
