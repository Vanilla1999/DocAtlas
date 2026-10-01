"""Native project pool replay over a saved SQLite snapshot, without retrieval."""
from __future__ import annotations

from contextlib import nullcontext
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from .adapters import ReadPort, SQLTrace, _eligible_rows
from .packet import ProjectPacketPort
from .structure import source_structure_parser


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_pool(store, result, sources, queries, output, *, commonmark=False):
    """Persist exactly the exposed ranked B pool and its complete source index."""
    if result['execution_status'] != 'EXECUTED' or result['assembly'] != 'none':
        raise ValueError('an executed unassembled native pool is required')
    output = Path(output)
    output.mkdir(exist_ok=False)
    with store._connect() as source, sqlite3.connect(output / 'snapshot.db') as target:
        source.backup(target)
    payload = {'schema_version': 1, 'commonmark': commonmark, 'queries': list(queries),
               'sources': sources, 'result': result}
    (output / 'pool.json').write_text(json.dumps(payload, ensure_ascii=False))
    (output / 'manifest.json').write_text(json.dumps({
        name: _hash(output / name) for name in ('snapshot.db', 'pool.json')}))


def replay_pool(root):
    """Revalidate saved units, then run B and D on the identical saved order."""
    from docmancer.core.sqlite_store import SQLiteStore
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    if set(manifest) != {'snapshot.db', 'pool.json'}:
        raise ValueError('invalid saved pool inventory')
    for name, digest in manifest.items():
        if (root / name).is_symlink() or _hash(root / name) != digest:
            raise ValueError('saved pool hash mismatch')
    payload = json.loads((root / 'pool.json').read_text())
    if payload['schema_version'] != 1 or type(payload['commonmark']) is not bool:
        raise ValueError('unsupported saved pool schema')
    saved = payload['result']
    if saved['execution_status'] != 'EXECUTED' or saved['assembly'] != 'none':
        raise ValueError('saved pool was not executed unassembled')
    connection = sqlite3.connect((root / 'snapshot.db').resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    connection.execute('BEGIN')
    # Fail closed even if a future packer starts issuing FTS queries.
    connection.set_authorizer(lambda action, arg1, arg2, db, trigger:
        sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_FUNCTION and
        str(arg2 or arg1).casefold() in ('bm25', 'match') else sqlite3.SQLITE_OK)
    trace = SQLTrace()
    store = SQLiteStore.__new__(SQLiteStore)
    port = ReadPort(store, connection, trace)
    parser = source_structure_parser() if payload['commonmark'] else nullcontext()
    try:
        with parser:
            _, allowed, _, _, _, _ = _eligible_rows(store, connection, trace, saved['filters'], payload['sources'])
            packet = ProjectPacketPort(port, filters=saved['filters'], queries=payload['queries'])
            candidates, lanes = saved['candidates'], saved['lanes']
            expected, identities = [], set()
            for lane_index, lane in enumerate(lanes):
                for rank, row in enumerate(lane['rows'], 1):
                    identity = store._lexical_row_identity(row)
                    if identity in identities:
                        continue
                    identities.add(identity)
                    if len(expected) < saved['unique_limit']:
                        expected.append({'lane': lane_index, 'rank_in_lane': rank,
                            'stable_chunk_id': identity, 'bm25_cost': row['rank'], 'row': row})
            if candidates != expected:
                raise ValueError('saved ranked pool is incomplete or reordered')
            seen = set()
            for candidate in candidates:
                row = candidate['row']
                key = row['hydration_id']
                actual = allowed.get(key)
                # Native search exposes hydration_id as `id`; physical child id
                # remains internal to the snapshot. All evidence fields match.
                if actual is None or any(row.get(k) != v for k, v in actual.items() if k != 'id'):
                    raise ValueError('candidate differs from eligible saved snapshot')
                identity = candidate['stable_chunk_id']
                if identity != row['stable_chunk_id'] or identity in seen:
                    raise ValueError('invalid or duplicate saved candidate')
                seen.add(identity)
                lane = lanes[candidate['lane']]
                rank = candidate['rank_in_lane']
                if rank < 1 or lane['rows'][rank - 1] != row or candidate['bm25_cost'] != row['rank']:
                    raise ValueError('saved lane/rank mismatch')
                _, reason = packet.prepare(row, lane['query'])
                if reason:
                    raise ValueError('saved candidate admission failed: ' + reason)
            b = packet.pack(candidates, lanes)
            if b['model_visible_packet'] != saved['model_visible_packet']:
                raise ValueError('saved B packet did not reproduce')
            d = packet.pack_structural(candidates, lanes,
                hard_eligible_ids={row['stable_chunk_id'] for row in allowed.values()})
            if trace.lanes:
                raise ValueError('saved replay issued retrieval')
            if any(_hash(root / name) != digest for name, digest in manifest.items()):
                raise ValueError('saved pool changed during replay')
            return {'kind': 'saved_native_pool_replay', 'new_search_count': 0,
                    'saved_candidate_count': len(candidates), 'B': b, 'D_L': d,
                    'quality_status': 'UNJUDGED'}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    print(json.dumps(replay_pool(args.bundle), ensure_ascii=False))


if __name__ == '__main__':
    main()
