"""Active-generation-only FTS projection for deterministic lexical scoring.

Retrieval generations remain immutable and retained for rollback/audit, while
FTS5 BM25 statistics are projected from exactly the active generation. The
projection and active-generation pointer are changed in the same SQLite
transaction so readers observe either the previous snapshot or the next one.
"""
from __future__ import annotations

import json
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
        conn.execute(
            "INSERT INTO retrieval_children_fts(retrieval_children_fts) "
            "VALUES (\'delete-all\')"
        )
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

    def fetch_section_filter_metadata(self, section_ids: list[int]) -> list[dict[str, Any]]:
        """Read only policy metadata for candidate ids before text hydration."""
        ordered = list(dict.fromkeys(int(value) for value in section_ids))
        if not ordered:
            return []
        placeholders = ",".join("?" for _ in ordered)
        with self._connect() as conn:
            generation_id = self._active_generation_id(conn)
            if not generation_id:
                return []
            rows = conn.execute(
                f"""
                SELECT hydration_id AS section_id, source, source_path,
                       source_identity, library_id, project_identity, project_path,
                       module_id, doc_scope, source_class, authority, lifecycle_status,
                       temporal_relevance, index_freshness, docs_snapshot_exact, metadata_json
                FROM retrieval_children
                WHERE generation_id = ? AND hydration_id IN ({placeholders})
                """,
                (generation_id, *ordered),
            )
            result: dict[int, dict[str, Any]] = {}
            for row in rows:
                try:
                    metadata = json.loads(str(row["metadata_json"] or "{}"))
                except (TypeError, json.JSONDecodeError):
                    metadata = {}
                metadata.update({
                    "section_id": int(row["section_id"]),
                    "source": str(row["source"] or ""),
                    "source_path": str(row["source_path"] or ""),
                    "source_identity": str(row["source_identity"] or ""),
                    "library_id": str(row["library_id"] or ""),
                    "project_identity": str(row["project_identity"] or ""),
                    "project_path": str(row["project_path"] or ""),
                    "module_id": str(row["module_id"] or ""),
                    "doc_scope": str(row["doc_scope"] or ""),
                    "source_class": str(row["source_class"] or ""),
                    "authority": str(row["authority"] or "unknown"),
                    "lifecycle_status": str(row["lifecycle_status"] or "active"),
                    "temporal_relevance": str(row["temporal_relevance"] or "current"),
                    "index_freshness": str(row["index_freshness"] or "synchronized"),
                })
                if row["docs_snapshot_exact"] is not None:
                    metadata["docs_snapshot_exact"] = bool(row["docs_snapshot_exact"])
                result[int(row["section_id"])] = metadata
        return [result[value] for value in ordered if value in result]

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
