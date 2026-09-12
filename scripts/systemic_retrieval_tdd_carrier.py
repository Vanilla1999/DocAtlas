from __future__ import annotations

import sys
from pathlib import Path


ACTIVE_FTS_TESTS = r'''from __future__ import annotations

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
'''


SUBJECT_TESTS = r'''from __future__ import annotations

import pytest

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


@pytest.mark.parametrize("lead", ["Since", "From"])
def test_version_capability_binds_subject_from_grammar_not_sentence_lead(lead: str):
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
    assert lead.casefold() not in {item.subject.casefold() for item in contract.proof_obligations}


def test_explicit_technical_version_subject_keeps_strong_identity():
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


ACTIVE_FTS_MODULE = r'''"""Active-generation-only FTS projection for deterministic lexical scoring.

Retrieval generations remain immutable and retained for rollback/audit, while
FTS5 BM25 statistics are projected from exactly the active generation. The
projection and active-generation pointer are changed in the same SQLite
transaction so readers observe either the previous snapshot or the next one.
"""
from __future__ import annotations

import sqlite3
from typing import Any


_ACTIVE_FTS_PROJECTION_VERSION = "active-generation-v1"


class _SQLiteStoreActiveFTS:
    """Keep lexical postings/statistics independent of inactive history."""

    @staticmethod
    def _ensure_fts_projection_state(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_fts_projection_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                generation_id TEXT,
                projection_version TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO retrieval_fts_projection_state(
                singleton, generation_id, projection_version
            ) VALUES (1, NULL, '')
            """
        )

    @classmethod
    def _replace_fts_projection(
        cls,
        conn: sqlite3.Connection,
        generation_id: str | None,
    ) -> None:
        cls._ensure_fts_projection_state(conn)
        conn.execute("DELETE FROM retrieval_children_fts")
        if generation_id:
            conn.execute(
                """
                INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source)
                SELECT id, title, retrieval_text, source
                FROM retrieval_children
                WHERE generation_id = ?
                ORDER BY id
                """,
                (generation_id,),
            )
        conn.execute(
            """
            UPDATE retrieval_fts_projection_state
            SET generation_id = ?, projection_version = ?
            WHERE singleton = 1
            """,
            (generation_id, _ACTIVE_FTS_PROJECTION_VERSION),
        )

    def _ensure_schema(self) -> None:
        super()._ensure_schema()
        # Existing databases have no projection-state table. Repair them once
        # on open without deleting immutable generation rows themselves.
        with self._connect() as conn:
            self._ensure_fts_projection_state(conn)
            active = self._active_generation_id(conn)
            state = conn.execute(
                """
                SELECT generation_id, projection_version
                FROM retrieval_fts_projection_state WHERE singleton = 1
                """
            ).fetchone()
            recorded = str(state["generation_id"]) if state and state["generation_id"] else None
            version = str(state["projection_version"] or "") if state else ""
            if recorded != active or version != _ACTIVE_FTS_PROJECTION_VERSION:
                self._replace_fts_projection(conn, active)

    def _build_candidate_generation(
        self,
        conn: sqlite3.Connection,
        documents: list[Any],
        *,
        recreate: bool,
    ) -> str:
        generation_id = super()._build_candidate_generation(
            conn, documents, recreate=recreate
        )
        # Candidate construction temporarily writes postings so the existing
        # generation validator can inspect them. Before commit, restore the
        # active projection. Activation below then switches it atomically.
        self._replace_fts_projection(conn, self._active_generation_id(conn))
        return generation_id

    def _activate_generation(self, conn: sqlite3.Connection, generation_id: str) -> None:
        super()._activate_generation(conn, generation_id)
        self._replace_fts_projection(conn, generation_id)

    def _deactivate_active_generation(self, conn: sqlite3.Connection) -> None:
        super()._deactivate_active_generation(conn)
        self._replace_fts_projection(conn, None)
'''


SUBJECT_HELPER = r'''
_VERSION_CAPABILITY_SUBJECT_RE = re.compile(
    r"^\s*(?:since|from)\s+which\s+version\s+can\s+(?:the\s+)?"
    r"(?P<subject>`[^`\n]{2,120}`|[A-Za-z_][A-Za-z0-9_.:-]*)\s+be\b",
    re.I,
)


def _version_capability_subject(
    question: str,
    technical_terms: tuple[TechnicalTerm, ...],
) -> tuple[str, dict[str, Any]] | None:
    """Bind a version subject from syntax instead of sentence-initial title case.

    A query span proves where text came from, not that a title-cased discourse
    word is the entity being constrained. This narrow grammar covers the
    auditable ``Since/From which version can X be ...`` form. Explicit
    technical identifiers retain their stronger typed identity.
    """

    match = _VERSION_CAPABILITY_SUBJECT_RE.match(question)
    if match is None:
        return None
    raw_subject = _clean_phrase(match.group("subject").strip("`"))
    if not raw_subject:
        return None
    term = _technical_term_for_value(raw_subject, technical_terms)
    subject = term.raw if term is not None else raw_subject
    return subject, _subject_fields(subject, term)

'''


OLD_VERSION_BLOCK = '''    if _VERSION_QUESTION_RE.search(raw_question):
        subject = _best_subject(
            raw_question,
            [value for value in subjects if value.casefold() not in {"python", "version"}],
            fallback="project",
        )
        attribute = "python_version" if re.search(r"\\bpython\\b", raw_question, re.I) else "version"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute=attribute, value_kind="version_range",
            lifecycle_intent=lifecycle, span_value=_VERSION_QUESTION_RE.search(raw_question).group(0),
        ))
'''


NEW_VERSION_BLOCK = '''    version_question = _VERSION_QUESTION_RE.search(raw_question)
    if version_question:
        bound_version_subject = _version_capability_subject(raw_question, technical_terms)
        subject_fields: dict[str, Any] = {}
        if bound_version_subject is not None:
            subject, subject_fields = bound_version_subject
        else:
            subject = _best_subject(
                raw_question,
                [value for value in subjects if value.casefold() not in {"python", "version"}],
                fallback="project",
            )
        attribute = "python_version" if re.search(r"\\bpython\\b", raw_question, re.I) else "version"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute=attribute, value_kind="version_range",
            lifecycle_intent=lifecycle, span_value=version_question.group(0),
            **subject_fields,
        ))
'''


def write_tests() -> None:
    Path("tests/test_active_fts_projection.py").write_text(ACTIVE_FTS_TESTS, encoding="utf-8")
    Path("tests/docs/test_subject_binding_strength.py").write_text(SUBJECT_TESTS, encoding="utf-8")


def apply_fix() -> None:
    Path("docmancer/core/_sqlite_store_active_fts.py").write_text(
        ACTIVE_FTS_MODULE, encoding="utf-8"
    )

    sqlite_store = Path("docmancer/core/sqlite_store.py")
    text = sqlite_store.read_text(encoding="utf-8")
    old = "from ._sqlite_store_shared import *  # noqa: F401,F403\n\nfrom ._sqlite_store_part01 import _SQLiteStorePart01"
    new = "from ._sqlite_store_shared import *  # noqa: F401,F403\n\nfrom ._sqlite_store_active_fts import _SQLiteStoreActiveFTS\nfrom ._sqlite_store_part01 import _SQLiteStorePart01"
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
    old = "class SQLiteStore(_SQLiteStorePart01, _SQLiteStorePart02, _SQLiteStorePart03, _SQLiteStorePart04, _SQLiteStorePart05):"
    new = "class SQLiteStore(_SQLiteStoreActiveFTS, _SQLiteStorePart01, _SQLiteStorePart02, _SQLiteStorePart03, _SQLiteStorePart04, _SQLiteStorePart05):"
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
    old = "install_class_shard_bridge(__name__, SQLiteStore, ['docmancer.core._sqlite_store_shared', 'docmancer.core._sqlite_store_part01', 'docmancer.core._sqlite_store_part02', 'docmancer.core._sqlite_store_part03', 'docmancer.core._sqlite_store_part04', 'docmancer.core._sqlite_store_part05'])"
    new = "install_class_shard_bridge(__name__, SQLiteStore, ['docmancer.core._sqlite_store_shared', 'docmancer.core._sqlite_store_active_fts', 'docmancer.core._sqlite_store_part01', 'docmancer.core._sqlite_store_part02', 'docmancer.core._sqlite_store_part03', 'docmancer.core._sqlite_store_part04', 'docmancer.core._sqlite_store_part05'])"
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
    sqlite_store.write_text(text, encoding="utf-8")

    contract = Path("docmancer/docs/domain/_project_answer_contract_part02.py")
    text = contract.read_text(encoding="utf-8")
    marker = "\ndef build_project_answer_contract(question: str) -> ProjectAnswerContract:\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        "\n" + SUBJECT_HELPER + "def build_project_answer_contract(question: str) -> ProjectAnswerContract:\n",
        1,
    )
    assert text.count(OLD_VERSION_BLOCK) == 1, text.count(OLD_VERSION_BLOCK)
    text = text.replace(OLD_VERSION_BLOCK, NEW_VERSION_BLOCK, 1)
    contract.write_text(text, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"write-tests", "apply-fix"}:
        raise SystemExit("usage: systemic_retrieval_tdd_carrier.py write-tests|apply-fix")
    if sys.argv[1] == "write-tests":
        write_tests()
    else:
        apply_fix()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
