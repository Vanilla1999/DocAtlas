"""Exact source coordinates; no text search, normalization or semantic claims."""
from __future__ import annotations

from bisect import bisect_right


def source_line_range(raw: str, start: int, end: int) -> tuple[int, int]:
    """One-based inclusive lines for a nonempty half-open character span.

    Keep CRLF and final newlines. A newline belongs to the line it terminates.
    Character offsets are Python string offsets, never UTF-8 byte offsets.
    """
    if (not isinstance(raw, str) or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(raw)):
        raise ValueError('invalid source character span')
    starts, cursor = [], 0
    for line in raw.splitlines(keepends=True):
        starts.append(cursor)
        cursor += len(line)
    return bisect_right(starts, start), bisect_right(starts, end - 1)


def source_line_text(raw: str, start: int, end: int) -> str:
    """Exact bytes-as-text covered by an inclusive range; never repair a range."""
    if not isinstance(raw, str):
        raise ValueError('source must be text')
    lines = raw.splitlines(keepends=True)
    if (type(start) is not int or type(end) is not int
            or not 1 <= start <= end <= len(lines)):
        raise ValueError('invalid source line range')
    return ''.join(lines[start - 1:end])
