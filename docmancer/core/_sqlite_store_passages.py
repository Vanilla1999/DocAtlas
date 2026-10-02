"""Opt-in passage representation owned by the existing generation transaction."""
import json
import re

from .retrieval_passages import build_retrieval_passages


class _SQLiteStorePassages:
    def query_passages(self, question, *, filters, limit=12, budget=2400,
                       max_per_source=2):
        """One native BM25 order, with policy checked before LIMIT/text fetch.

        Scope/version/path constraints belong in caller-provided filters. This
        API is current project-document search, not general library retrieval.
        """
        from docmancer.docs.domain.evidence_qualification import source_metadata_rejection_reason
        identity = (filters or {}).get('project_identity')
        if not isinstance(identity, str) or not identity:
            raise ValueError('project_identity filter required')
        if type(limit) is not int or type(budget) is not int or type(max_per_source) is not int:
            raise ValueError('integer resource limits required')
        limit, budget = max(0, min(20, limit)), max(0, min(2400, budget))
        max_per_source = max(0, min(2, max_per_source))
        terms = list(dict.fromkeys(re.findall(r'\w+(?:[.-]\w+)*', question)))
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        result = {'question': question, 'candidates': [], 'trace': {
            'fts_expression': expression, 'candidate_limit': limit,
            'hydrated_passage_bytes': 0, 'hydrated_payload_bytes': 0,
            'skipped_resource_ids': []}}
        with self._connect() as conn:
            status = self._passage_status(conn)
            if not status['ready']:
                raise ValueError('preparation_required')
            result['generation_id'] = status['generation_id']
            if not terms or not limit or not budget or not max_per_source:
                return result

            def source_allowed(serialized):
                metadata = json.loads(serialized)
                if not isinstance(metadata, dict):
                    raise ValueError('invalid source metadata')
                return int(metadata.get('source_class') == 'project_doc'
                    and not metadata.get('instruction_risk_flags')
                    and source_metadata_rejection_reason(candidate=metadata,
                        expected_project_identity=identity, lifecycle_intent='current') is None)

            conn.create_function('passage_source_allowed', 1, source_allowed)
            filter_sql, params = self._metadata_filter_sql(filters)
            rows = conn.execute(f'''WITH sections AS (
                    SELECT generation_id, source,
                        json_set(metadata_json, '$.source', source,
                                 '$.source_identity', source_identity) AS metadata_json
                    FROM generation_sources
                ) SELECT p.id, p.stable_id, p.source,
                    length(CAST(p.text AS BLOB)) AS text_bytes,
                    bm25(retrieval_passages_fts) AS bm25_cost
                FROM retrieval_passages_fts
                JOIN retrieval_passages p ON p.id=retrieval_passages_fts.rowid
                JOIN sections ON sections.generation_id=p.generation_id
                    AND sections.source=p.source
                WHERE retrieval_passages_fts MATCH ? AND p.generation_id=?
                    AND passage_source_allowed(sections.metadata_json)=1
                    AND length(CAST(p.text AS BLOB)) <= ?
                    {filter_sql}
                ORDER BY bm25_cost, p.stable_id LIMIT ?''',
                (expression, status['generation_id'], min(2048, budget * 4), *params, limit)).fetchall()
            used_units, counts = 0, {}
            for rank, row in enumerate(rows, 1):
                units = (row['text_bytes'] + 3) // 4
                if (used_units + units > budget
                        or counts.get(row['source'], 0) >= max_per_source):
                    result['trace']['skipped_resource_ids'].append(row['stable_id'])
                    continue
                serialized = conn.execute('SELECT payload_json FROM retrieval_passages WHERE id=?',
                                          (row['id'],)).fetchone()[0]
                payload = json.loads(serialized)
                payload.update(source=row['source'], generation_id=status['generation_id'],
                               bm25_cost=row['bm25_cost'], native_rank=rank)
                result['candidates'].append(payload)
                used_units += units
                counts[row['source']] = counts.get(row['source'], 0) + 1
                result['trace']['hydrated_passage_bytes'] += row['text_bytes']
                result['trace']['hydrated_payload_bytes'] += len(serialized.encode('utf-8'))
            result['trace']['fts_candidate_count'] = len(rows)
        return result

    def _ensure_passage_schema(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS passage_generations (
                    generation_id TEXT PRIMARY KEY,
                    profile_identity TEXT NOT NULL,
                    passage_count INTEGER NOT NULL,
                    deferred_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retrieval_passages (
                    id INTEGER PRIMARY KEY,
                    generation_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    stable_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(generation_id, stable_id)
                );
                CREATE INDEX IF NOT EXISTS passage_generation_index
                    ON retrieval_passages(generation_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_passages_fts USING fts5(
                    text, content='retrieval_passages', content_rowid='id'
                );
            ''')

    def passage_index_status(self):
        with self._connect() as conn:
            return self._passage_status(conn)

    def _passage_status(self, conn):
        active = self._active_generation_id(conn)
        if self.passage_profile is None or not active:
            return {'ready': False, 'reason': 'preparation_required'}
        row = conn.execute('''SELECT p.*, g.status FROM passage_generations p
            JOIN index_generations g USING(generation_id) WHERE generation_id=?''',
            (active,)).fetchone()
        ready = bool(row and row['status'] == 'active'
                     and row['profile_identity'] == self.passage_profile.identity)
        return {'ready': ready, 'reason': 'active_profile' if ready else 'preparation_required',
                'generation_id': active}

    def list_active_passages(self):
        """Diagnostic inventory, not bounded query/hydration or legacy fallback."""
        with self._connect() as conn:
            status = self._passage_status(conn)
            if not status['ready']:
                raise ValueError('preparation_required')
            rows = conn.execute('''SELECT * FROM retrieval_passages
                WHERE generation_id=? ORDER BY stable_id''', (status['generation_id'],))
            return [{**json.loads(row['payload_json']), 'generation_id': row['generation_id'],
                     'source': row['source']} for row in rows]

    def _build_passage_generation(self, conn, generation_id):
        from dataclasses import asdict
        count, deferred = 0, []
        for source in conn.execute('''SELECT * FROM generation_sources
                WHERE generation_id=? ORDER BY source''', (generation_id,)).fetchall():
            passages, omitted = build_retrieval_passages(
                source['content'], source['source_identity'], snapshot_id=generation_id,
                profile=self.passage_profile)
            metadata = json.loads(source['metadata_json'])
            for passage in passages:
                payload = {**asdict(passage), 'metadata': metadata}
                cursor = conn.execute('''INSERT INTO retrieval_passages
                    (generation_id, source, stable_id, text, payload_json)
                    VALUES (?, ?, ?, ?, ?)''', (generation_id, source['source'],
                    passage.stable_id, passage.text, json.dumps(payload, ensure_ascii=False)))
                conn.execute('INSERT INTO retrieval_passages_fts(rowid, text) VALUES (?, ?)',
                             (cursor.lastrowid, passage.text))
                count += 1
            deferred.extend({'source': source['source'], **asdict(item)} for item in omitted)
        indexed = conn.execute('''SELECT COUNT(*) FROM retrieval_passages p
            JOIN retrieval_passages_fts_docsize f ON f.id=p.id WHERE generation_id=?''',
            (generation_id,)).fetchone()[0]
        if indexed != count:
            raise ValueError('passage FTS parity failed')
        conn.execute("INSERT INTO retrieval_passages_fts(retrieval_passages_fts, rank) VALUES ('integrity-check', 1)")
        conn.execute('''INSERT INTO passage_generations
            (generation_id, profile_identity, passage_count, deferred_json) VALUES (?, ?, ?, ?)''',
            (generation_id, self.passage_profile.identity, count, json.dumps(deferred)))
