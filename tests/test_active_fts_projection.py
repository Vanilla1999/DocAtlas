from __future__ import annotations

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore


def _doc(source: str, content: str) -> Document:
    return Document(
        source=source,
        content=content,
        metadata={
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 32,
            "child_hard_max_tokens": 64,
        },
    )


def _search_signature(store: SQLiteStore) -> tuple[tuple[str, float], ...]:
    rows = store._search_rows("projectiontoken rareterm", 20)
    return tuple(
        (str(row["stable_chunk_id"]), float(row["rank"]))
        for row in rows
    )


def _projection_ids(store: SQLiteStore) -> tuple[set[int], set[int]]:
    with store._connect() as conn:
        active = store._active_generation_id(conn)
        expected = {
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM retrieval_children WHERE generation_id = ?",
                (active,),
            )
        } if active else set()
        actual = {
            int(row["rowid"])
            for row in conn.execute(
                "SELECT rowid FROM retrieval_children_fts "
                "WHERE retrieval_children_fts MATCH 'projectiontoken'"
            )
        }
    return expected, actual


def test_ready_candidate_cannot_change_active_fts_scoring_or_postings(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    docs = [
        _doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha alpha\n"),
        _doc("docs/b.md", "# B\n\nprojectiontoken common beta beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    active_before = store.active_generation_id()
    signature_before = _search_signature(store)
    expected_before, actual_before = _projection_ids(store)
    assert actual_before == expected_before

    candidate = store.add_documents([docs[0]], activate_generation=False)

    assert candidate.generation_id != active_before
    assert store.active_generation_id() == active_before
    assert _search_signature(store) == signature_before
    expected_after, actual_after = _projection_ids(store)
    assert actual_after == expected_after == expected_before


def test_superseded_history_is_absent_from_active_fts_projection(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    docs = [
        _doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha\n"),
        _doc("docs/b.md", "# B\n\nprojectiontoken common beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    first_generation = store.active_generation_id()
    store.add_documents([docs[0]])
    assert store.active_generation_id() != first_generation

    expected, actual = _projection_ids(store)
    assert actual == expected
    with store._connect() as conn:
        assert int(conn.execute(
            "SELECT COUNT(*) FROM retrieval_children WHERE generation_id = ?",
            (first_generation,),
        ).fetchone()[0]) > 0


def test_open_repairs_pre_projection_state_database(tmp_path):
    db = tmp_path / "index.db"
    store = SQLiteStore(db)
    docs = [
        _doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha\n"),
        _doc("docs/b.md", "# B\n\nprojectiontoken common beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    old_generation = store.active_generation_id()
    store.add_documents([docs[0]])
    active = store.active_generation_id()
    assert active != old_generation

    # Simulate a database produced by the old runtime: immutable historical
    # rows remain and an inactive posting leaks into the global FTS table, while
    # the new projection-state metadata has never existed.
    with store._connect() as conn:
        conn.execute("DROP TABLE IF EXISTS retrieval_fts_projection_state")
        stale = conn.execute(
            "SELECT id, title, retrieval_text, source FROM retrieval_children "
            "WHERE generation_id = ? ORDER BY id LIMIT 1",
            (old_generation,),
        ).fetchone()
        assert stale is not None
        already = conn.execute(
            "SELECT 1 FROM retrieval_children_fts "
            "WHERE rowid = ? AND retrieval_children_fts MATCH 'projectiontoken'",
            (stale["id"],),
        ).fetchone()
        if already is None:
            conn.execute(
                "INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source) "
                "VALUES (?, ?, ?, ?)",
                (stale["id"], stale["title"], stale["retrieval_text"], stale["source"]),
            )

    reopened = SQLiteStore(db)
    assert reopened.active_generation_id() == active
    expected, actual = _projection_ids(reopened)
    assert actual == expected
