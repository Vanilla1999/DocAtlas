"""Map search hits to whole original Markdown owners, without an admission rule.

Search order/score and source identity are not semantic proof. This module only
changes the unit materialized BEFORE the usual snapshot/current-catalog/read
checks. No extra reads, guessed parents, query parsing or post-rejection rescue.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
from typing import Any, Iterable

from docmancer.core.structured_chunking import parse_markdown_parents


@lru_cache(maxsize=16)
def _owner_bounds(raw: str, document_id: str) -> tuple[tuple[int, int], ...]:
    """Cache immutable parse inputs, never eligibility or a query decision."""
    return tuple((p.char_start, p.char_end)
                 for p in parse_markdown_parents(raw, document_id))


def owner_envelope(raw: str, document_id: str, start: int, end: int) -> tuple[int, int]:
    """Smallest contiguous union of parser sections touched by [start, end).

    Existing parser sections partition the source; they are not inferred
    semantic scopes. Do not promote to a same-named or ancestor heading, and
    do not search for the same text elsewhere in the document.
    """
    if (not isinstance(raw, str) or not isinstance(document_id, str) or not document_id
            or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(raw)):
        raise ValueError('invalid source hit coordinates')
    touched = [(a, b) for a, b in _owner_bounds(raw, document_id)
               if a < end and start < b]
    if not touched or touched[0][0] > start or touched[-1][1] < end:
        raise ValueError('hit has no complete parser-owned range')
    if any(left[1] != right[0] for left, right in zip(touched, touched[1:])):
        raise ValueError('noncontiguous parser-owned ranges')
    return touched[0][0], touched[-1][1]


def delivery_spans(raw: str, document_id: str,
                   search_spans: Iterable[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    """Recompute canonical units from source bytes, not trusted metadata flags."""
    return frozenset(owner_envelope(raw, document_id, a, b) for a, b in search_spans)


def materialize_hit(row: dict[str, Any]) -> dict[str, Any]:
    """Preserve a ranked hit and materialize its complete source unit.

    The result is still a proposal. The existing preparation path must bind the
    new exact bytes to the authenticated snapshot and rerun all source checks.
    """
    raw, identity = row['raw'], row['identity']
    start, end = row['start'], row['end']
    first, last = owner_envelope(raw, identity, start, end)
    if (row.get('source_sha256') != hashlib.sha256(raw.encode('utf-8')).hexdigest()
            or row.get('content') != raw[start:end]):
        raise ValueError('retrieval hit differs from its source snapshot')
    return {
        **row,
        'retrieval_span': [start, end],
        'retrieval_content': row['content'],
        'delivery_unit_kind': 'whole_parser_owners_v1',
        'start': first, 'end': last, 'content': raw[first:last],
        'byte_start': len(raw[:first].encode('utf-8')),
        'byte_end': len(raw[:last].encode('utf-8')),
        'owner_spans': [[a, b] for a, b in _owner_bounds(raw, identity)
                        if first <= a < b <= last],
    }
