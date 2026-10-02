import pytest

from docmancer.core.models import Document
from docmancer.core.retrieval_passages import PassageProfile
from docmancer.core.sqlite_store import SQLiteStore


def doc(body='Current rule.', **metadata):
    return Document(source='docs/guide.md', content='# Guide\n\n' + body + '\n',
                    metadata={'project_identity': 'project-a', **metadata})


def store(tmp_path):
    return SQLiteStore(tmp_path / 'index.db', passage_profile=PassageProfile())


def test_passages_are_visible_only_after_generation_activation(tmp_path):
    db = store(tmp_path)
    first = db.add_documents([doc()])
    assert db.passage_index_status()['ready']
    assert db.list_active_passages()[0]['generation_id'] == first.generation_id
    next_generation = db.add_documents([doc('New rule.')], activate_generation=False)
    assert 'Current rule.' in db.list_active_passages()[0]['text']
    with db._connect() as conn:
        hits = conn.execute('''SELECT p.text FROM retrieval_passages_fts f
            JOIN retrieval_passages p ON p.id=f.rowid
            JOIN index_state s ON s.active_generation_id=p.generation_id
            WHERE retrieval_passages_fts MATCH 'rule' ''').fetchall()
        assert len(hits) == 1 and 'Current rule.' in hits[0]['text']
    db.activate_generation(next_generation.generation_id)
    assert 'New rule.' in db.list_active_passages()[0]['text']


def test_failed_passage_build_rolls_back_generation_and_extraction(tmp_path, monkeypatch):
    db = store(tmp_path)
    db.add_documents([doc()])
    active = db.active_generation_id()
    before = {str(p): p.read_bytes() for p in db.extracted_dir.rglob('*') if p.is_file()}
    original = db._build_passage_generation
    def fail(*args):
        original(*args)
        raise ValueError('passage build failed')
    monkeypatch.setattr(db, '_build_passage_generation', fail)
    with pytest.raises(ValueError, match='passage build failed'):
        db.add_documents([doc('Broken candidate.')], recreate=True)
    assert db.active_generation_id() == active
    assert 'Current rule.' in db.list_active_passages()[0]['text']
    assert before == {str(p): p.read_bytes() for p in db.extracted_dir.rglob('*') if p.is_file()}
    with db._connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM passage_generations').fetchone()[0] == 1


def test_metadata_update_and_recreate_do_not_keep_old_active_hits(tmp_path):
    db = store(tmp_path)
    db.add_documents([doc(authority='old')])
    old = db.list_active_passages()[0]
    db.add_documents([doc(authority='canonical')])
    new = db.list_active_passages()[0]
    assert new['metadata']['authority'] == 'canonical'
    assert new['source_content_hash'] == old['source_content_hash']
    assert new['stable_id'] != old['stable_id']  # snapshot is part of passage ID
    db.add_documents([Document(source='docs/new.md', content='Replacement.')], recreate=True)
    assert {p['source'] for p in db.list_active_passages()} == {'docs/new.md'}
    db.add_documents([doc('Edited rule.')])
    assert all('Current rule.' not in p['text'] for p in db.list_active_passages())
    assert db.delete_source('docs/guide.md')
    assert {p['source'] for p in db.list_active_passages()} == {'docs/new.md'}


def test_missing_or_incompatible_profile_requires_preparation(tmp_path):
    plain = SQLiteStore(tmp_path / 'index.db')
    plain.add_documents([doc()])
    db = store(tmp_path)
    assert not db.passage_index_status()['ready']
    with pytest.raises(ValueError, match='preparation_required'):
        db.list_active_passages()
    db.add_documents([doc()])
    other = SQLiteStore(tmp_path / 'index.db', passage_profile=PassageProfile(256, 512))
    assert not other.passage_index_status()['ready']
    with pytest.raises(ValueError, match='preparation_required'):
        other.list_active_passages()
    # Read-only readiness never changes generation or silently builds passages.
    assert db.active_generation_id() == other.active_generation_id()
    db.add_documents([
        Document(source='project-a/guide.md', content='Identical text.', metadata={'project_identity': 'a'}),
        Document(source='project-b/guide.md', content='Identical text.', metadata={'project_identity': 'b'}),
    ], recreate=True)
    passages = db.list_active_passages()
    assert len(passages) == 2 and len({p['stable_id'] for p in passages}) == 2
    assert {p['metadata']['project_identity'] for p in passages} == {'a', 'b'}
