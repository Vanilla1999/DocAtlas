"""Verified source-local ranges for bounded evidence recovery."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .context_selection import visible_assignments


def _raw_text(source: Mapping[str, Any]) -> str:
    return next((
        value for value in (
            source.get("code"), source.get("snippet"), source.get("content"),
            source.get("display_text"),
        )
        if isinstance(value, str) and value
    ), "")


def _assignment_span(
    source: Mapping[str, Any], assignment: Mapping[str, Any], raw_text: str,
) -> tuple[int, int] | None:
    start, end = assignment.get("unit_char_start"), assignment.get("unit_char_end")
    if start is None and end is None:
        start, end = assignment.get("char_start"), assignment.get("char_end")
        source_start = source.get("char_start")
        if source_start is not None:
            if any(type(value) is not int for value in (source_start, start, end)):
                return None
            start, end = start - source_start, end - source_start
    if any(type(value) is not int for value in (start, end)):
        return None
    if not 0 <= start < end <= len(raw_text):
        return None
    return start, end


def unseen_adjacent_range(
    source: Mapping[str, Any], *, visible_start: int, visible_end: int, max_lines: int,
) -> tuple[int, int] | None:
    """Return a nonblank source-local range that excludes already-visible lines."""
    raw_start, raw_end = source.get("line_start"), source.get("line_end")
    if (
        any(type(value) is not int for value in (raw_start, raw_end, visible_start, visible_end, max_lines))
        or raw_start < 1 or raw_end < raw_start or max_lines < 1
        or not raw_start <= visible_start <= visible_end <= raw_end
    ):
        return None
    raw_text = _raw_text(source)
    lines = raw_text.splitlines()
    expected = raw_end - raw_start + 1
    if len(lines) < expected:
        return None
    lines = lines[:expected]

    def trimmed(start: int, end: int) -> tuple[int, int] | None:
        if start > end:
            return None
        values = lines[start - raw_start:end - raw_start + 1]
        nonblank = [index for index, value in enumerate(values) if value.strip()]
        if not nonblank:
            return None
        return start + nonblank[0], start + nonblank[-1]

    before = trimmed(max(raw_start, visible_start - max_lines), visible_start - 1)
    if before is not None:
        return before
    return trimmed(visible_end + 1, min(raw_end, visible_end + max_lines))


def verified_missing_ranges(
    source: dict[str, Any], assignments: tuple[dict[str, Any], ...],
    missing_ids: frozenset[str],
) -> tuple[tuple[str, int, int], ...]:
    """Return source-bound missing witness line ranges without reading files."""
    if not isinstance(source, Mapping) or not missing_ids:
        return ()
    source_line_start = source.get("line_start")
    if type(source_line_start) is not int or source_line_start < 1:
        return ()
    raw_text = _raw_text(source)
    visible_text = raw_text.rstrip("\n")
    if not visible_text:
        return ()
    projected = {
        "snippet": visible_text,
        "line_start": source_line_start,
        "line_end": source_line_start + visible_text.count("\n"),
    }
    verified = visible_assignments(source, projected, assignments)
    ranges: list[tuple[str, int, int]] = []
    seen: set[tuple[str, int, int]] = set()
    for assignment in verified:
        requirement_id = str(assignment.get("requirement_id") or "")
        if requirement_id not in missing_ids:
            continue
        span = _assignment_span(source, assignment, raw_text)
        if span is None:
            continue
        start, end = span
        first_line = source_line_start + raw_text.count("\n", 0, start)
        last_line = source_line_start + raw_text.count("\n", 0, end - 1)
        row = (requirement_id, first_line, last_line)
        if row not in seen:
            ranges.append(row)
            seen.add(row)
    return tuple(ranges)


__all__ = ["unseen_adjacent_range", "verified_missing_ranges"]
