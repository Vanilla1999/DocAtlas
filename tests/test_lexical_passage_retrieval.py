import pytest
import sqlite3

from docmancer.core.models import Document
from docmancer.core.retrieval_passages import PassageProfile
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.core.config import DocmancerConfig
from docmancer.retrieval.dispatch import RetrievalDispatcher


def indexed(tmp_path, documents):
    db = SQLiteStore(tmp_path / 'index.db', passage_profile=PassageProfile())
    db.add_documents(documents)
    return db


def doc(source, text, **metadata):
    return Document(source=source, content=text, metadata={
        'project_identity': 'p', 'source_class': 'project_doc', **metadata})


def query(db, text='retention storage', **kwargs):
    return db.query_passages(text, filters={'project_identity': 'p'}, **kwargs)


def test_order_matches_independent_sql_bm25_and_stable_ties(tmp_path):
    db = indexed(tmp_path, [doc('c.md', 'storage retention'),
                            doc('b.md', 'storage retention storage'),
                            doc('a.md', 'storage retention')])
    result = query(db)
    assert len(result['candidates']) == 3
    with db._connect() as conn:
        expected = conn.execute('''SELECT p.stable_id, bm25(retrieval_passages_fts) AS cost
            FROM retrieval_passages_fts JOIN retrieval_passages p
            ON p.id=retrieval_passages_fts.rowid WHERE retrieval_passages_fts MATCH ?
            AND p.generation_id=? ORDER BY cost, p.stable_id''',
            ('"retention" OR "storage"', db.active_generation_id())).fetchall()
    assert [(p['stable_id'], p['bm25_cost']) for p in result['candidates']] == [tuple(r) for r in expected]
    assert all('qualified' not in p and 'score' not in p for p in result['candidates'])
    with db._connect() as conn:
        rows = conn.execute('SELECT id, text FROM retrieval_passages ORDER BY id DESC').fetchall()
        conn.execute("INSERT INTO retrieval_passages_fts(retrieval_passages_fts) VALUES ('delete-all')")
        for row in rows:
            conn.execute('INSERT INTO retrieval_passages_fts(rowid,text) VALUES (?,?)', tuple(row))
    assert query(db)['candidates'] == result['candidates']


def test_source_filters_precede_top_k_and_hydration(tmp_path):
    db = indexed(tmp_path, [doc('wrong.md', 'retention storage '*10, project_identity='other'),
        doc('unsafe.md', 'retention storage '*10, risk_flags=['injection']),
        doc('stale.md', 'retention storage '*10, freshness='stale'),
        doc('valid.md', 'retention storage')])
    result = query(db, limit=1)
    assert [p['source'] for p in result['candidates']] == ['valid.md']
    assert result['trace']['hydrated_passage_bytes'] == len(b'retention storage')
    with pytest.raises(ValueError):
        db.query_passages('storage', filters={})
    scoped = indexed(tmp_path / 'scope', [
        doc('old.md', 'storage retention', resolved_version='1', doc_scope='project'),
        doc('current.md', 'storage retention', resolved_version='2', doc_scope='module', module_id='m'),
    ])
    selected = scoped.query_passages('storage', filters={
        'project_identity': 'p', 'resolved_version': '2', 'doc_scope': 'module', 'module_id': 'm'}, limit=1)
    assert [p['source'] for p in selected['candidates']] == ['current.md']
    selected = scoped.query_passages('storage', filters={'project_identity': 'p', 'source': 'old.md'})
    assert [p['source'] for p in selected['candidates']] == ['old.md']
    with scoped._connect() as conn:
        conn.execute("UPDATE generation_sources SET metadata_json='broken' WHERE source='current.md'")
    with pytest.raises(sqlite3.OperationalError, match='user-defined function|malformed JSON'):
        query(scoped)


def test_limits_empty_unicode_and_quoted_question(tmp_path):
    db = indexed(tmp_path, [doc('large.md', 'storage '*250), doc('small.md', 'storage')])
    result = query(db, 'storage', budget=2)
    assert [p['source'] for p in result['candidates']] == ['small.md']
    assert result['trace']['hydrated_passage_bytes'] <= 8
    assert query(db, ' !!! ')['candidates'] == []
    assert query(db, '"storage" OR *')['question'] == '"storage" OR *'
    assert len(query(db, 'storage', limit=100)['candidates']) <= 20
    unicode_db = indexed(tmp_path / 'unicode', [doc('ru.md', 'Хранение данных.')])
    assert query(unicode_db, 'Хранение')['candidates']
    capped = indexed(tmp_path / 'caps', [doc('one.md', '# A\n\nstorage\n\n# B\n\nstorage\n\n# C\n\nstorage')])
    assert len(query(capped, 'storage')['candidates']) == 2


def test_dispatch_entry_does_not_call_legacy_reranking(tmp_path, monkeypatch):
    db = indexed(tmp_path, [doc('guide.md', 'storage retention')])
    dispatcher = RetrievalDispatcher(store=db, config=DocmancerConfig())
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy retrieval called')
    monkeypatch.setattr(db, 'query', forbidden)
    monkeypatch.setattr(dispatcher, '_rerank_intent_matches', forbidden)
    result = dispatcher.run_project_passages('retention storage', project_identity='p')
    assert result['candidates']
    dispatcher.config.retrieval.budget = 1
    assert not dispatcher.run_project_passages('retention storage', project_identity='p')['candidates']
    from eval.evidence_quality_v2.run import load_protocol, documents_for
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'mkdocs-05')
    documents = documents_for('mkdocs', manifest)
    frozen = indexed(tmp_path / 'frozen', [doc(path, text) for path, text in documents.items()])
    candidates = query(frozen, case['question'])['candidates']
    # Gold is used only after native retrieval, never supplied to index or query.
    witness = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    assert any(witness in row['text'] for row in candidates)
