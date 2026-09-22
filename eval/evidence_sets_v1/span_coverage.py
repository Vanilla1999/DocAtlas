"""Exact occurrence coverage, independent of fragment boundaries.

Inputs are original character offsets, not UTF-8 offsets. The caller must first
validate source/project/snapshot identity and each visible fragment's bytes.
This helper cannot grant source permission or infer semantic equivalence.
"""
from __future__ import annotations
from collections.abc import Iterable


def _interval(raw: str, span: tuple[int, int]) -> tuple[int, int]:
    if (len(span) != 2 or any(type(x) is not int for x in span)
            or not 0 <= span[0] < span[1] <= len(raw)):
        raise ValueError(f'invalid source interval: {span}')
    return span[0], span[1]


def witness_bytes_covered(raw: str, required: tuple[int, int],
                          visible: Iterable[tuple[int, int]], *,
                          ignored_gaps: Iterable[tuple[int, int]] = ()) -> bool:
    """Cover a required occurrence using exact spans and pre-annotated gaps."""
    start, end = _interval(raw, required)
    intervals = [_interval(raw, span) for span in visible]
    gaps = [_interval(raw, span) for span in ignored_gaps]
    for left, right in gaps:
        if not start <= left < right <= end or not raw[left:right].isspace():
            raise ValueError('ignored gap must be annotated whitespace inside witness')
    # No broad strip/normalization. An unannotated code space remains required.
    cursor = start
    for left, right in sorted((*intervals, *gaps)):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return False
