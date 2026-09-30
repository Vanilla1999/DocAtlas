"""Test-only adapters. Native A is a diagnostic, NOT a model-visible packet.

The real _search_rows frontend produces individual FTS5 lists. This adapter
changes their exposure limits, not preprocessing, field weights, or BM25.
No SQL score is compared across expressions. P uses the unchanged full handler.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Iterator
from unittest.mock import patch


@dataclass
class SQLTrace:
    lanes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Quota:
    remaining: int


class ReadConnection:
    """Consume each native cursor once; preserve every returned row and its order."""
    def __init__(self, connection, trace: SQLTrace, *, quota=None, allowed_ids=None,
                 owns_connection=False):
        self.connection, self.trace = connection, trace
        self.quota, self.allowed_ids = quota, allowed_ids
        self.owns_connection = owns_connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        if self.owns_connection:
            self.connection.__enter__()
        return self

    def __exit__(self, *exc):
        if not self.owns_connection:
            return False
        return self.connection.__exit__(*exc)

    def execute(self, sql, parameters=()):
        if 'bm25(retrieval_children_fts,' not in sql:
            return self.connection.execute(sql, parameters)
        # Fail closed on an unreviewed scorer/ordering/schema change.
        if ('bm25(retrieval_children_fts, 6.0, 2.0, 0.5)' not in sql
                or 'ORDER BY rank, sections.source, sections.chunk_index,' not in sql
                or 'sections.stable_chunk_id' not in sql
                or not sql.strip().endswith('LIMIT ?')):
            raise RuntimeError('unreviewed native FTS boundary')
        requested = parameters[-1]
        effective = requested if self.quota is None else min(requested, self.quota.remaining)
        parameters = (*parameters[:-1], effective)
        if self.allowed_ids is not None:
            sql = sql.replace('ORDER BY rank,',
                'AND sections.hydration_id IN (SELECT value FROM json_each(?))\nORDER BY rank,', 1)
            parameters = (*parameters[:-1], json.dumps(self.allowed_ids), effective)
        lane = {'expression': parameters[0], 'requested_limit': requested,
                'limit': effective, 'sql': sql, 'parameters': list(parameters),
                'weights': [6.0, 2.0, 0.5], 'score_direction': 'lower_is_better',
                'rows': [], 'uncapped_complete': False}
        self.trace.lanes.append(lane)
        try:
            rows = list(self.connection.execute(sql, parameters))
        except Exception as exc:
            lane['error_type'] = type(exc).__name__
            raise
        lane['rows'] = deepcopy([dict(row) for row in rows])
        lane['uncapped_complete'] = effective > 0 and len(rows) < effective
        if self.quota is not None:
            self.quota.remaining -= len(rows)  # Duplicates consume exposure too.
        return rows


class ReadPort:
    """Borrow one read transaction while invoking actual SQLiteStore methods."""
    def __init__(self, store, connection, trace, *, quota=None, allowed_ids=None):
        self.store, self.connection, self.trace = store, connection, trace
        self.quota, self.allowed_ids = quota, allowed_ids

    def __getattr__(self, name):
        return getattr(self.store, name)

    def _connect(self):
        return ReadConnection(self.connection, self.trace, quota=self.quota,
                              allowed_ids=self.allowed_ids)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _canonical_reason(row: dict, snapshot: dict | None, sources: dict[str, str]) -> str | None:
    """Mechanical index integrity only; this does NOT certify API ownership."""
    text = sources.get(row.get('source_path') or row['source'])
    if text is None or snapshot is None:
        return 'source_not_in_frozen_corpus'
    digest = _digest(text)
    metadata = json.loads(row['metadata_json'])
    if (snapshot['content'] != text or snapshot['content_hash'] != digest
            or metadata.get('source_content_hash') != digest
            or snapshot['source_identity'] != row['source_identity']):
        return 'source_snapshot_mismatch'
    start, end = row['char_start'], row['char_end']
    if not (type(start) is int and type(end) is int and 0 <= start < end <= len(text)):
        return 'invalid_span'
    quote = row['display_text']
    if text[start:end] != quote or _digest(quote) != row['display_content_hash']:
        return 'modified_quote'
    if (row['byte_start'] != len(text[:start].encode('utf-8'))
            or row['byte_end'] != len(text[:end].encode('utf-8'))
            or row['line_start'] != text.count('\n', 0, start) + 1
            or row['line_end'] != text.count('\n', 0, end - 1) + 1):
        return 'invalid_span'
    if _digest(row['retrieval_text']) != row['retrieval_content_hash']:
        return 'retrieval_hash_mismatch'
    return None


def _eligible_rows(store, connection, trace, filters, sources):
    from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
    from docmancer.retrieval.query_planning import metadata_matches_filters

    generation = store._active_generation_id(connection)
    rows = [dict(row) for row in connection.execute(
        'SELECT * FROM retrieval_children WHERE generation_id = ? ORDER BY hydration_id', (generation,))]
    snapshots = {row['source']: dict(row) for row in connection.execute(
        'SELECT * FROM generation_sources WHERE generation_id = ?', (generation,))}
    port = ReadPort(store, connection, trace)
    metadata = type(store).section_filter_metadata_for(port, [row['hydration_id'] for row in rows])
    allowed, rejected = {}, []
    for row in rows:
        candidate = metadata.get(row['hydration_id'], {})
        reason = None
        if not metadata_matches_filters(candidate, filters, source=row['source']):
            reason = 'source_filter_mismatch'
        if reason is None:
            reason = evidence_policy_rejection_reason({}, visible_text=row['display_text'],
                candidate=candidate, expected_project_identity=filters['project_identity'])
        if reason is None:
            reason = _canonical_reason(row, snapshots.get(row['source']), sources)
        if reason:
            rejected.append({'stable_chunk_id': row['stable_chunk_id'], 'reason': reason})
        else:
            allowed[row['hydration_id']] = row
    return generation, allowed, snapshots, rejected, len(rows), sum(
        len(row['display_text'].encode('utf-8')) for row in rows)


def native_diagnostic(store, queries, *, filters, sources, raw_limit=40, unique_limit=20):
    """A's native scorer diagnostic, with policy BEFORE bounded exposure.

    Scope is intentionally limited to isolated, manifest-listed project docs.
    Full source scanning is accounted for and is NOT production latency.
    Caller owns sources/filters. No result may be sent to an answerer.
    """
    from docmancer.retrieval.query_planning import compile_backend_filters

    queries = tuple(queries)
    if not queries or any(not isinstance(q, str) or not q.strip() for q in queries):
        raise ValueError('nonempty frozen queries required')
    if (not isinstance(filters.get('project_identity'), str)
            or not filters['project_identity']):
        raise ValueError('explicit project identity required')
    if any(type(n) is not int or n <= 0 for n in (raw_limit, unique_limit)):
        raise ValueError('positive integer budgets required')
    filters, sources = deepcopy(filters), deepcopy(sources)
    trace = SQLTrace()
    connection = store._connect()
    try:
        connection.execute('BEGIN')
        generation, allowed, snapshots, rejected, scanned, scanned_bytes = _eligible_rows(
            store, connection, trace, filters, sources)
        projection = connection.execute(
            'SELECT generation_id FROM retrieval_fts_projection_state WHERE singleton = 1').fetchone()
        if projection is None or projection['generation_id'] != generation:
            raise ValueError('active FTS projection mismatch')
        schedule = [raw_limit // len(queries) + (i < raw_limit % len(queries)) for i in range(len(queries))]
        for query, quota in zip(queries, schedule):
            if not quota:
                continue
            start = len(trace.lanes)
            port = ReadPort(store, connection, trace, quota=Quota(quota), allowed_ids=list(allowed))
            # Reuse exact query preprocessing, filter compiler, joins, and weights.
            # Deliberately discard the merged return: individual SQL lanes are retained.
            type(store)._search_rows(port, query, quota, filters=compile_backend_filters(filters))
            for lane in trace.lanes[start:]:
                lane['query'] = query
        candidates, seen = [], set()
        for lane_index, lane in enumerate(trace.lanes):
            for rank, row in enumerate(lane['rows'], start=1):
                identity = store._lexical_row_identity(row)
                if identity in seen:
                    continue
                seen.add(identity)
                if _canonical_reason(row, snapshots.get(row['source']), sources):
                    raise ValueError('materialized candidate lost canonical integrity')
                if len(candidates) < unique_limit:
                    candidates.append({'lane': lane_index, 'rank_in_lane': rank,
                        'stable_chunk_id': identity, 'bm25_cost': row['rank'], 'row': row})
        return {'arm': 'A', 'execution_status': 'EXECUTED',
            'packet_status': 'BLOCKED_SAFE_PACKET_ADAPTER', 'quality_status': 'UNJUDGED',
            'evaluation_kind': 'native_fts_diagnostic_only', 'model_visible_packet': None,
            'agent_evaluation': 'ANSWER_EVALUATION_NOT_RUN', 'generation_id': generation,
            'merge': 'probe-order / AND-before-OR / first stable identity',
            'query_schedule': schedule, 'filters': filters,
            'raw_limit': raw_limit, 'unique_limit': unique_limit,
            'raw_hits': sum(len(lane['rows']) for lane in trace.lanes),
            'unique_exposed': len(seen), 'candidates': candidates, 'lanes': trace.lanes,
            'policy_scan_rows': scanned, 'policy_scan_display_bytes': scanned_bytes,
            'policy_rejections': rejected, 'search_count': len(trace.lanes),
            'source_text_bytes': sum(len(row['text'].encode('utf-8'))
                for lane in trace.lanes for row in lane['rows'])}
    finally:
        connection.rollback()
        connection.close()


@contextmanager
def observe_native_sql() -> Iterator[SQLTrace]:
    """Process-local, same-call observer. NEVER install in a concurrent server.

    Does not change SQL, limits, weights, returned rows, or execute extra searches.
    Saturated SQL limits remain explicitly incomplete for uncapped recall.
    """
    from docmancer.core.sqlite_store import SQLiteStore
    trace = SQLTrace()
    original = SQLiteStore._connect

    def connect(store):
        return ReadConnection(original(store), trace, owns_connection=True)

    with patch.object(SQLiteStore, '_connect', connect):
        yield trace


def product_probe(corpus, spec, request):
    from experiments.language_aware_context import baseline_probe
    with observe_native_sql() as trace:
        result = baseline_probe.run(corpus, spec, request)
    result.update(arm='P', raw_fts_lanes=trace.lanes, quality_status='UNJUDGED',
                  resource_matched=False)
    return result
