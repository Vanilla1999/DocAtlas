"""Pure source-local window rules; no retrieval or answer-authorization decisions."""
from __future__ import annotations

import re
from typing import Any

from .context_blocks import source_block_alternatives
from .technical_tokens import technical_term_pattern


_QUERY_STOP_WORDS = frozenset({
    "about", "after", "does", "from", "have", "into", "project", "that",
    "their", "then", "these", "this", "what", "when", "where", "which",
    "with", "работает", "какие", "когда", "проект", "этот",
})


_BASE_WINDOW_LIMITS = (160, 320, 520)
_SHORT_COMPLETE_SOURCE_MAX_CHARS = 704

# A chunk may start below its table header. Protect every unescaped pipe-bearing
# source line, including rows with either optional edge omitted and pipelines.
# Escaped literal pipes remain ordinary prose; even backslashes do not escape it.
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)(?:\\\\)*\|")


def _projection_limits(text: str) -> tuple[int, ...]:
    """Return only ordinary bounded rolling-window sizes.

    Complete structural blocks are separate exact-span candidates. Their lengths
    must not widen every unrelated window or subsequent snippet expansion.
    """
    limits = set(_BASE_WINDOW_LIMITS)
    compact_length = len(text.strip())
    if _BASE_WINDOW_LIMITS[-1] < compact_length <= _SHORT_COMPLETE_SOURCE_MAX_CHARS:
        limits.add(compact_length)
    return tuple(sorted(limits))


def _query_terms(queries: tuple[str, ...]) -> set[str]:
    return {
        token.casefold()
        for query in queries
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.-]{4,}", query)
        if token.casefold() not in _QUERY_STOP_WORDS
    }


def _is_complete_source_span(text: str, snippet: str) -> bool:
    """Return whether *snippet* ends at a source-local semantic boundary.

    This is a projection preference only. It never creates query attribution or
    answer proof; it prevents a mid-sentence prefix from outranking a bounded,
    contiguous alternative carrying the same qualified evidence.
    """
    if not snippet:
        return False
    resolved = source_local_span(text, snippet)
    if resolved is None:
        return False
    start, end = resolved

    # Sentence punctuation is not an item boundary.  A list item's trailing
    # sentence can carry a default, restriction, or precondition that changes
    # the meaning of an otherwise plausible prefix.  Reuse the structural
    # alternatives already derived from the authorized source span and accept
    # an item (or a contiguous run of items) only on complete item boundaries.
    item_start, item_end = start, end
    while item_start < item_end and text[item_start].isspace():
        item_start += 1
    while item_end > item_start and text[item_end - 1].isspace():
        item_end -= 1

    structural_spans = source_block_alternatives(text).spans
    list_spans = [
        span for span in structural_spans
        if re.match(r"(?:[-+*]\s+|\d+[.)]\s+)", text[span[0]:span[1]].lstrip())
    ]
    atomic_items = [
        span for span in list_spans
        if not any(
            other != span
            and span[0] <= other[0] < other[1] <= span[1]
            and (span[0], span[1]) != (other[0], other[1])
            for other in list_spans
        )
    ]
    touched_items = [
        span for span in atomic_items
        if span[0] < item_end and item_start < span[1]
    ]
    if touched_items:
        return (
            item_start == touched_items[0][0]
            and item_end == touched_items[-1][1]
        )

    left = text[:start]
    right = text[end:]
    left_complete = not left.strip() or left.endswith("\n\n")
    stripped = snippet.rstrip()
    right_complete = (
        not right.strip()
        or right.startswith("\n\n")
        or stripped.endswith((".", "!", "?", "|", "```", "~~~"))
    )
    return left_complete and right_complete


def _focused_snippet(
    text: str, queries: tuple[str, ...], *, limit: int = 520,
) -> tuple[str, int, int]:
    leading = len(text) - len(text.lstrip())
    value = text.strip()
    if len(value) <= limit:
        start, end = _include_complete_code_fence(value, 0, len(value), limit=limit)
        return value[start:end], leading + start, leading + end
    terms = _query_terms(queries)
    # A numbered list marker is not a sentence. Keep each list item together
    # so its subject/step number cannot be separated from the returned body.
    spans = _source_unit_spans(value)
    if not spans:
        return "", leading, leading
    best_index = max(range(len(spans)), key=lambda index: sum(
        bool(re.search(technical_term_pattern(term, exact=False), value[spans[index][0]:spans[index][1]], re.I)) for term in terms))
    start = end = best_index
    selected_start, selected_end = spans[best_index]
    if selected_end - selected_start > limit:
        selected_start, selected_end = _bounded_text_window(
            value, selected_start, selected_end, terms=terms, limit=limit,
        )
        selected_start, selected_end = _include_complete_table_row(
            value, selected_start, selected_end, terms=terms, limit=limit,
        )
    for distance in range(1, len(spans)):
        for index in (best_index - distance, best_index + distance):
            if index < 0 or index >= len(spans):
                continue
            adjacent = value[spans[index][0]:spans[index][1]].casefold()
            if terms and not any(re.search(technical_term_pattern(term, exact=False), adjacent, re.I) for term in terms):
                continue
            candidate_start = min(start, index)
            candidate_end = max(end, index)
            char_start = spans[candidate_start][0]
            char_end = spans[candidate_end][1]
            if char_end - char_start <= limit:
                selected_start, selected_end = char_start, char_end
                start = candidate_start
                end = candidate_end
        if selected_end - selected_start >= limit * 0.7:
            break
    selected_start, selected_end = _include_complete_table_row(
        value, selected_start, selected_end, terms=terms, limit=limit,
    )
    # Score structurally valid windows, not a prefix that will lose its last row.
    # A tied first sentence must not hide additional witnesses across a short gap.
    hits = [(match.start(), match.end(), term) for term in terms
            for match in re.finditer(technical_term_pattern(term, exact=False), value, re.I)]
    for _, boundary in spans:
        row_end = value.find("\n", boundary)
        boundary = (len(value) if row_end < 0 else row_end) if "|" in value[value.rfind("\n", 0, boundary) + 1:boundary] else boundary
        start_at = max(0, boundary - limit)
        # A richer rolling window must not start in the middle of a short
        # sentence/list item and silently remove who a statement is about.
        # Overlong individual spans retain the bounded initial-window policy.
        start_at = next((left for left, _ in spans if start_at <= left < boundary), boundary)
        start_at, boundary = _include_complete_table_row(
            value, start_at, boundary, terms=terms, limit=limit,
        )
        if len({term for a, b, term in hits if start_at <= a < b <= boundary}) > len({
            term for a, b, term in hits if selected_start <= a < b <= selected_end
        }):
            selected_start, selected_end = start_at, boundary
    selected_start, selected_end = _include_complete_table_row(
        value, selected_start, selected_end, terms=terms, limit=limit,
    )
    # A short lead-in ending with ':' is semantically incomplete without the
    # contiguous list it introduces. Prefer that forward block over a richer
    # backward window when it fits; this is source-local projection only and
    # does not create query attribution or answer proof.
    intro_start, intro_end = spans[best_index]
    intro = value[intro_start:intro_end].strip()
    if intro.endswith(":") and best_index + 1 < len(spans):
        # ``_source_unit_spans`` intentionally splits prose sentences, so one
        # markdown list item may occupy several adjacent spans. Treat the list
        # marker plus its following non-marker spans as one structural item;
        # otherwise a lead-in can keep only the first sentence of the first
        # bullet and crowd out later query-bearing bullets even when they fit.
        list_end = intro_end
        saw_item = False
        cursor = best_index + 1
        while cursor < len(spans):
            item_start, item_end = spans[cursor]
            item = value[item_start:item_end].lstrip()
            if not re.match(r"(?:[-*+]\s+|\d+[.)]\s+)", item):
                break
            group_end = item_end
            next_index = cursor + 1
            while next_index < len(spans):
                continuation_start, continuation_end = spans[next_index]
                continuation = value[continuation_start:continuation_end].lstrip()
                if re.match(r"(?:[-*+]\s+|\d+[.)]\s+)", continuation):
                    break
                group_end = continuation_end
                next_index += 1
            if group_end - intro_start > limit:
                break
            list_end = group_end
            saw_item = True
            cursor = next_index
        if saw_item:
            selected_start, selected_end = intro_start, list_end
    selected_start, selected_end = _include_complete_code_fence(value, selected_start, selected_end, limit=limit)
    # Overlong prose still keeps whole tokens at both edges.
    if selected_start and not value[selected_start - 1].isspace():
        selected_start += len(re.match(r"\S*\s*", value[selected_start:selected_end])[0])
    if selected_end < len(value) and not value[selected_end - 1:selected_end].isspace() and not value[selected_end].isspace():
        tail = re.search(r"\s+\S*$", value[selected_start:selected_end])
        selected_end = selected_start + tail.start() if tail else selected_start
    snippet = value[selected_start:selected_end].strip()
    adjusted_start = value.find(snippet, selected_start, selected_end + 1)
    return snippet, leading + adjusted_start, leading + adjusted_start + len(snippet)


def _source_unit_spans(value: str) -> list[tuple[int, int]]:
    """Keep pipe rows atomic before scoring, not only after clipping a winner."""
    prose = re.compile(
        r"\S(?:.*?\S)?(?=(?:\n{2,}|(?<!\d\.)(?<=[.!?])\s+|"
        r"\n(?=[ \t]*(?:\d+[.)]|[-*+])\s)|$))", re.S,
    )
    spans: list[tuple[int, int]] = []
    cursor = 0
    for line in re.finditer(r"[^\n]+", value):
        if not _UNESCAPED_PIPE_RE.search(line[0]):
            continue
        spans.extend((match.start(), match.end())
                     for match in prose.finditer(value, cursor, line.start()))
        spans.append((line.start(), line.end()))
        cursor = line.end()
    spans.extend((match.start(), match.end()) for match in prose.finditer(value, cursor))
    return spans


def _include_complete_table_row(
    text: str, start: int, end: int, *, terms: set[str], limit: int,
) -> tuple[int, int]:
    """Keep whole table rows, including subject and restriction cells.

    A suffix of a row is not an independent statement even when it contains
    more query terms. If the whole row cannot fit, omit it rather than guessing
    whether its missing cells change the meaning. All offsets stay contiguous.
    """
    def row_at(position: int) -> tuple[int, int, bool]:
        left = text.rfind("\n", 0, position) + 1
        right = text.find("\n", position)
        right = len(text) if right < 0 else right
        row = text[left:right].strip()
        return left, right, bool(_UNESCAPED_PIPE_RE.search(row))

    # The last cells can contain restrictions; never expose their partial row.
    if start < end:
        left, right, is_row = row_at(end - 1)
        if is_row and end < right:
            end = right if right - start <= limit else left
    if start >= end:
        return start, start
    left, right, is_row = row_at(start)
    if is_row and start > left:
        if end - left <= limit:
            start = left
        else:
            start = min(len(text), right + 1)
    return start, max(start, end)


def _bounded_text_window(
    text: str, start: int, end: int, *, terms: set[str], limit: int,
) -> tuple[int, int]:
    segment = text[start:end]
    matched_positions = [
        match.start() for term in terms
        if (match := re.search(technical_term_pattern(term, exact=False), segment, re.I)) is not None
    ]
    anchor = min((position for position in matched_positions if position >= 0), default=0)
    window_start = start + max(0, anchor - limit // 3)
    window_end = min(end, window_start + limit)
    window_start = max(start, window_end - limit)
    return window_start, window_end


def _include_complete_code_fence(
    text: str, start: int, end: int, *, limit: int,
) -> tuple[int, int]:
    blocks = []
    opening = None
    for match in re.finditer(r"^[ \t]*(`{3,}|~{3,})([^\n]*)", text, re.M):
        if opening is None:
            opening = match
        elif (
            match.group(1)[0] == opening.group(1)[0]
            and len(match.group(1)) >= len(opening.group(1))
            and not match.group(2).strip()
        ):
            blocks.append((opening.start(), match.end(), True))
            opening = None
    if opening is not None:
        blocks.append((opening.start(), len(text), False))
    for fence_start, fence_end, closed in blocks:
        if (
            closed and end <= fence_start and not text[end:fence_start].strip()
            and re.search(r"\b(?:following|command|example)\b", text[start:end], re.I)
            and fence_end - start <= limit
        ):
            end = fence_end
        if start < fence_end and end > fence_start:
            expanded_start = min(start, fence_start)
            expanded_end = max(end, fence_end)
            if closed and expanded_end - expanded_start <= limit:
                start, end = expanded_start, expanded_end
                continue
            # A bounded payload must not expose a syntactically broken fence.
            before = text.rfind("\n\n", 0, fence_start)
            safe_start = 0 if before < 0 else before + 2
            if fence_start - safe_start <= limit and fence_start > safe_start:
                return safe_start, fence_start
            return start, start
    return start, end


def _focused_line_range(
    text: str, start: int, end: int, source_line_start: Any,
) -> tuple[int | None, int | None]:
    if not isinstance(source_line_start, int) or source_line_start < 1:
        return None, None
    line_start = source_line_start + text[:start].count("\n")
    line_end = line_start + text[start:end].count("\n")
    return line_start, line_end


def source_local_span(
    text: str, snippet: str, *, source_line_start: int | None = None,
    line_start: int | None = None, line_end: int | None = None,
) -> tuple[int, int] | None:
    """Resolve one exact occurrence, using line provenance when available.

    Equal text at another offset is not the same witness. Without enough
    provenance to distinguish repeated occurrences, do not guess a range.
    """
    if not snippet or any(
        value is not None and (type(value) is not int or value < 1)
        for value in (source_line_start, line_start, line_end)
    ):
        return None
    if line_start is not None and line_end is not None and line_start > line_end:
        return None
    result = None
    start = text.find(snippet)
    while start >= 0:
        actual_line = (source_line_start + text.count("\n", 0, start)
                       if source_line_start is not None else None)
        if actual_line is None or (
            (line_start is None or line_start == actual_line)
            and (line_end is None or line_end == actual_line + snippet.count("\n"))
        ):
            if result is not None:
                return None
            result = (start, start + len(snippet))
        start = text.find(snippet, start + 1)
    return result
