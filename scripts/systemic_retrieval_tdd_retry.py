from __future__ import annotations

import sys
from pathlib import Path

from systemic_retrieval_tdd_carrier import apply_fix


FTS_MARKER = "# systemic-retrieval-active-fts-regressions"
SUBJECT_MARKER = "# systemic-retrieval-subject-binding-regressions"

FTS_APPEND = r'''

# systemic-retrieval-active-fts-regressions

def _systemic_doc(source: str, content: str) -> Document:
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


def _systemic_search_signature(store: SQLiteStore) -> tuple[tuple[str, float], ...]:
    rows = store._search_rows("projectiontoken rareterm", 20)
    return tuple(
        (str(row["stable_chunk_id"]), float(row["rank"]))
        for row in rows
    )


def _systemic_projection_ids(store: SQLiteStore) -> tuple[set[int], set[int]]:
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
        _systemic_doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha alpha\n"),
        _systemic_doc("docs/b.md", "# B\n\nprojectiontoken common beta beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    active_before = store.active_generation_id()
    signature_before = _systemic_search_signature(store)
    expected_before, actual_before = _systemic_projection_ids(store)
    assert actual_before == expected_before

    candidate = store.add_documents([docs[0]], activate_generation=False)

    assert candidate.generation_id != active_before
    assert store.active_generation_id() == active_before
    assert _systemic_search_signature(store) == signature_before
    expected_after, actual_after = _systemic_projection_ids(store)
    assert actual_after == expected_after == expected_before


def test_superseded_history_is_absent_from_active_fts_projection(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    docs = [
        _systemic_doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha\n"),
        _systemic_doc("docs/b.md", "# B\n\nprojectiontoken common beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    first_generation = store.active_generation_id()
    store.add_documents([docs[0]])
    assert store.active_generation_id() != first_generation

    expected, actual = _systemic_projection_ids(store)
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
        _systemic_doc("docs/a.md", "# A\n\nprojectiontoken rareterm alpha\n"),
        _systemic_doc("docs/b.md", "# B\n\nprojectiontoken common beta\n"),
    ]
    store.add_documents(docs, recreate=True)
    old_generation = store.active_generation_id()
    store.add_documents([docs[0]])
    active = store.active_generation_id()
    assert active != old_generation

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
    expected, actual = _systemic_projection_ids(reopened)
    assert actual == expected
'''

SUBJECT_APPEND = r'''

# systemic-retrieval-subject-binding-regressions

def test_v3_version_capability_binds_subject_from_grammar_not_sentence_lead():
    for lead in ("Since", "From"):
        question = (
            f"{lead} which version can preview be configured separately "
            "for linting and formatting?"
        )
        contract = build_project_answer_contract(question)
        version = [
            item for item in contract.proof_obligations
            if item.kind == "attribute" and item.attribute == "version"
        ]
        assert len(version) == 1
        assert version[0].subject.casefold() == "preview"
        assert version[0].query_span_text is not None
        assert lead.casefold() not in {
            item.subject.casefold() for item in contract.proof_obligations
        }


def test_v3_explicit_technical_version_subject_keeps_strong_identity():
    question = "Since which version can `lint.preview` be configured separately?"
    contract = build_project_answer_contract(question)
    version = [
        item for item in contract.proof_obligations
        if item.kind == "attribute" and item.attribute == "version"
    ]
    assert len(version) == 1
    assert version[0].subject == "lint.preview"
    assert version[0].subject_kind == "config_key"
'''


def _append_once(path: str, marker: str, payload: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    assert marker not in text
    target.write_text(text.rstrip() + payload + "\n", encoding="utf-8")


def write_tests() -> None:
    _append_once("tests/test_parent_child_index.py", FTS_MARKER, FTS_APPEND)
    _append_once(
        "tests/docs/test_project_answer_contract_v3.py",
        SUBJECT_MARKER,
        SUBJECT_APPEND,
    )


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"write-tests", "apply-fix"}:
        raise SystemExit("usage: systemic_retrieval_tdd_retry.py write-tests|apply-fix")
    if sys.argv[1] == "write-tests":
        write_tests()
    else:
        apply_fix()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
