"""Conservative request-intent ABI; free-form prose grants no mutation authority."""

from __future__ import annotations

from dataclasses import dataclass
import re


MAX_INTENT_SCAN_CHARS = 4_000
MAX_INTENT_CLAUSES = 12

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


def _looks_like_narrative_action_label(
    source: str,
    *,
    verb_start: int,
    verb_end: int,
    clause_end: int,
) -> bool:
    """Legacy semantic hook, disabled; syntax helpers remain available."""

    return False


def find_change_clause(question: str) -> ChangeIntentClause | None:
    """Return no inferred change clause; explicit SDK contracts are separate."""

    # Free-form text is data, not an explicit mutation contract. Preserve the
    # syntax/masking helpers for callers without synthesizing an operation.
    return None


def is_change_request(question: str) -> bool:
    """Text alone is never an explicit mutation contract."""

    return find_change_clause(question) is not None


__all__ = [
    "ChangeIntentClause",
    "find_change_clause",
    "is_change_request",
]
