"""SQLiteStore implementation shard 4."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStorePart04:
    def _expand_row(self, row: sqlite3.Row, expand: str) -> list[sqlite3.Row]:
        if expand == "none":
            return [row]
        with self._connect() as conn:
            generation_id = row["generation_id"] if "generation_id" in row.keys() else None
            if generation_id:
                parent_logical_id = row["parent_logical_id"]
                anchor_index = int(row["chunk_index"])
                clauses = [
                    "(chunk_index BETWEEN ? AND ?)",
                ]
                params: list[Any] = [anchor_index - 1, anchor_index + 1]
                if expand == "page" and row["atom_type"] in {"code", "table"}:
                    clauses.append("atom_id = ?")
                    params.append(row["atom_id"])
                rows = list(
                    conn.execute(
                        f"""
                        SELECT c.hydration_id AS id, c.*, c.display_text AS text,
                               c.display_token_estimate AS token_estimate,
                               c.display_content_hash AS content_hash
                        FROM retrieval_children c
                        WHERE c.generation_id = ? AND c.parent_logical_id = ?
                          AND ({' OR '.join(clauses)})
                        ORDER BY c.chunk_index
                        LIMIT 8
                        """,
                        (generation_id, parent_logical_id, *params),
                    )
                )
                return [item for item in rows if int(item["id"]) == int(row["id"])] + [
                    item for item in rows if int(item["id"]) != int(row["id"])
                ]
        return [row]

    def _raw_token_total(self, sources: list[str]) -> int:
        if not sources:
            return 0
        unique_sources = sorted(set(sources))
        placeholders = ",".join("?" for _ in unique_sources)
        with self._connect() as conn:
            active = self._active_generation_id(conn)
            if active:
                row = conn.execute(
                    f"""
                    SELECT
                        COALESCE((
                            SELECT SUM(raw_tokens) FROM generation_sources
                            WHERE generation_id = ?
                              AND source IN ({placeholders})
                        ), 0)
                        + COALESCE((
                            SELECT SUM(s.raw_tokens) FROM sources s
                            WHERE s.source IN ({placeholders})
                              AND NOT EXISTS (
                                  SELECT 1 FROM generation_sources gs
                                  WHERE gs.generation_id = ?
                                    AND gs.source = s.source
                              )
                        ), 0) AS total
                    """,
                    (active, *unique_sources, *unique_sources, active),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT COALESCE(SUM(raw_tokens), 0) AS total FROM sources WHERE source IN ({placeholders})",
                    unique_sources,
                ).fetchone()
            return int(row["total"] or 0)

    def project_scope_stats(
        self,
        *,
        project_path: str | None = None,
        project_identity: str | None = None,
    ) -> dict[str, Any]:
        """Return counts owned by one project without conflating shared rows."""

        normalized_path = str(project_path or "").strip()
        normalized_identity = str(project_identity or "").strip()
        if not normalized_path and not normalized_identity:
            return {
                "sources_count": 0,
                "sections_count": 0,
                "active_generation_id": None,
                "ownership": "unscoped",
            }
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            clauses: list[str] = []
            params: list[Any] = []
            if normalized_path:
                clauses.append("project_path = ?")
                params.append(normalized_path)
            if normalized_identity:
                clauses.append("project_identity = ?")
                params.append(normalized_identity)
            ownership_sql = "(" + " OR ".join(clauses) + ")"
            child_sources: set[str] = set()
            child_sections = 0
            if active_generation:
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT source
                    FROM retrieval_children
                    WHERE generation_id = ? AND {ownership_sql}
                    """,
                    (active_generation, *params),
                ).fetchall()
                child_sources = {str(row["source"]) for row in rows}
                child_sections = int(conn.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM retrieval_children
                    WHERE generation_id = ? AND {ownership_sql}
                    """,
                    (active_generation, *params),
                ).fetchone()["count"] or 0)

        sources = child_sources
        return {
            "sources_count": len(sources),
            "sections_count": child_sections,
            "active_generation_id": active_generation,
            "ownership": "project_owned" if sources else "no_project_rows",
        }

    def collection_stats(self) -> dict:
        with self._connect() as conn:
            sources = conn.execute("SELECT COUNT(*) AS count FROM sources").fetchone()["count"]
            active_generation = self._active_generation_id(conn)
            if active_generation:
                children = int(conn.execute(
                    "SELECT COUNT(*) AS count FROM retrieval_children WHERE generation_id = ?",
                    (active_generation,),
                ).fetchone()["count"])
                parents = int(conn.execute(
                    "SELECT COUNT(*) AS count FROM retrieval_parents WHERE generation_id = ?",
                    (active_generation,),
                ).fetchone()["count"])
                sections = children
            else:
                children = 0
                parents = 0
                sections = 0
            format_rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(format, ''), 'unknown') AS format, COUNT(*) AS count
                FROM retrieval_children
                WHERE generation_id = ?
                GROUP BY COALESCE(NULLIF(format, ''), 'unknown')
                ORDER BY format
                """,
                (active_generation or "",),
            ).fetchall()
            source_format_rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(json_extract(metadata_json, '$.format'), ''), 'unknown') AS format,
                       COUNT(*) AS count
                FROM sources
                GROUP BY COALESCE(NULLIF(json_extract(metadata_json, '$.format'), ''), 'unknown')
                ORDER BY format
                """
            ).fetchall()
        return {
            "collection_exists": self.db_path.exists(),
            "sources_count": int(sources),
            "points_count": int(sections),
            "sections_count": int(sections),
            "parent_sections_count": int(parents),
            "retrieval_children_count": int(children),
            "active_generation_id": active_generation,
            "sources_by_format": {str(row["format"]): int(row["count"]) for row in source_format_rows},
            "sections_by_format": {str(row["format"]): int(row["count"]) for row in format_rows},
            "db_path": str(self.db_path),
            "extracted_dir": str(self.extracted_dir),
        }

    def orphaned_extraction_artifacts(self) -> list[str]:
        """Report generated extraction files that no source row references."""
        with self._connect() as conn:
            referenced = {
                Path(str(path_value)).resolve()
                for row in conn.execute("SELECT markdown_path, json_path FROM sources")
                for path_value in (row["markdown_path"], row["json_path"])
                if path_value
            }

        regular_artifacts = {
            path.name: path
            for path in self.extracted_dir.iterdir()
            if path.suffix in {".json", ".md"}
            and not path.is_symlink()
            and path.is_file()
        }
        orphaned: list[Path] = []
        stems = sorted({Path(name).stem for name in regular_artifacts})
        for stem in stems:
            json_artifact = regular_artifacts.get(f"{stem}.json")
            markdown_artifact = regular_artifacts.get(f"{stem}.md")
            if json_artifact is None or markdown_artifact is None:
                continue
            pair = (json_artifact, markdown_artifact)
            if all(path.resolve() not in referenced for path in pair):
                orphaned.extend(pair)
        return [str(path) for path in orphaned]

    def index_health(self, collection: str | None = None) -> dict[str, Any]:
        """Audit the active generation, exact spans, FTS parity and vector drift."""
        with self._connect() as conn:
            active = self._active_generation_id(conn)
            schemas: dict[str, int] = {}
            missing_parents = missing_source_snapshots = 0
            source_snapshot_hash_errors = parent_snapshot_hash_errors = 0
            invalid_spans = duplicate_stable_ids = fts_drift = 0
            active_status = None
            if active:
                generation = conn.execute(
                    "SELECT schema_version, status FROM index_generations WHERE generation_id = ?",
                    (active,),
                ).fetchone()
                active_status = str(generation["status"]) if generation else "missing"
                child_count = int(conn.execute(
                    "SELECT COUNT(*) AS count FROM retrieval_children WHERE generation_id = ?",
                    (active,),
                ).fetchone()["count"])
                schemas[str(generation["schema_version"])] = child_count
                missing_parents = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM retrieval_children c
                    LEFT JOIN retrieval_parents p
                      ON p.generation_id = c.generation_id
                     AND p.logical_id = c.parent_logical_id
                    WHERE c.generation_id = ? AND p.logical_id IS NULL
                    """,
                    (active,),
                ).fetchone()["count"])
                missing_source_snapshots = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM retrieval_children c
                    LEFT JOIN generation_sources gs
                      ON gs.generation_id = c.generation_id
                     AND gs.source = c.source
                    WHERE c.generation_id = ? AND gs.source IS NULL
                    """,
                    (active,),
                ).fetchone()["count"])
                for source_row in conn.execute(
                    """
                    SELECT content, content_hash FROM generation_sources
                    WHERE generation_id = ?
                    """,
                    (active,),
                ):
                    actual_hash = hashlib.sha256(
                        str(source_row["content"]).encode("utf-8")
                    ).hexdigest()
                    source_snapshot_hash_errors += int(
                        actual_hash != str(source_row["content_hash"])
                    )
                parent_snapshot_hash_errors = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM retrieval_parents p
                    JOIN generation_sources gs
                      ON gs.generation_id = p.generation_id
                     AND gs.source = p.source
                    WHERE p.generation_id = ?
                      AND p.source_content_hash != gs.content_hash
                    """,
                    (active,),
                ).fetchone()["count"])
                duplicate_stable_ids = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM (
                        SELECT stable_chunk_id FROM retrieval_children
                        WHERE generation_id = ? GROUP BY stable_chunk_id
                        HAVING COUNT(*) > 1
                    )
                    """,
                    (active,),
                ).fetchone()["count"])
                fts_count = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM retrieval_children_fts f
                    JOIN retrieval_children c ON c.id = f.rowid
                    WHERE c.generation_id = ?
                    """,
                    (active,),
                ).fetchone()["count"])
                fts_drift = abs(child_count - fts_count)
                for row in conn.execute(
                    """
                    SELECT c.char_start, c.char_end, c.byte_start, c.byte_end,
                           c.display_text, gs.content
                    FROM retrieval_children c
                    JOIN generation_sources gs
                      ON gs.generation_id = c.generation_id
                     AND gs.source = c.source
                    WHERE c.generation_id = ?
                    """,
                    (active,),
                ):
                    content = str(row["content"])
                    display = str(row["display_text"])
                    if content[int(row["char_start"]):int(row["char_end"])] != display:
                        invalid_spans += 1
                        continue
                    if content.encode("utf-8")[int(row["byte_start"]):int(row["byte_end"])] != display.encode("utf-8"):
                        invalid_spans += 1
            vector_drift = 0
            vector_collection_mismatch = False
            if collection:
                if active:
                    generation = conn.execute(
                        """
                        SELECT vector_collection FROM index_generations
                        WHERE generation_id = ?
                        """,
                        (active,),
                    ).fetchone()
                    vector_collection_mismatch = bool(
                        generation and str(generation["vector_collection"]) != collection
                    )
                    current_stable_ids = {
                        str(row["stable_chunk_id"])
                        for row in conn.execute(
                            """
                            SELECT stable_chunk_id FROM retrieval_children
                            WHERE generation_id = ?
                            """,
                            (active,),
                        )
                    }
                    recorded = {
                        str(row["stable_chunk_id"]): str(row["generation_id"])
                        for row in conn.execute(
                            """
                            SELECT stable_chunk_id, generation_id
                            FROM generation_vector_upserts
                            WHERE qdrant_collection = ?
                            """,
                            (collection,),
                        )
                    }
                    vector_drift = len(current_stable_ids.symmetric_difference(recorded))
                    vector_drift += sum(
                        1 for stable_id in current_stable_ids & recorded.keys()
                        if recorded[stable_id] != active
                    )
                else:
                    vector_drift = int(
                        conn.execute(
                            """
                            SELECT COUNT(*) AS count FROM embedding_upserts e
                            LEFT JOIN sections s ON s.id = e.chunk_id
                            WHERE e.qdrant_collection = ? AND s.id IS NULL
                            """,
                            (collection,),
                        ).fetchone()["count"]
                    )
        issues = {
            "mixed_schema_versions": len(schemas) > 1,
            "active_generation_invalid": bool(active and active_status != "active"),
            "missing_parents": missing_parents,
            "missing_source_snapshots": missing_source_snapshots,
            "source_snapshot_hash_errors": source_snapshot_hash_errors,
            "parent_snapshot_hash_errors": parent_snapshot_hash_errors,
            "invalid_spans": invalid_spans,
            "duplicate_stable_ids": duplicate_stable_ids,
            "fts_drift": fts_drift,
            "vector_drift": vector_drift,
            "vector_collection_mismatch": vector_collection_mismatch,
        }
        return {
            "ok": not any(bool(value) for value in issues.values()),
            "schema_versions": schemas,
            "active_generation_id": active,
            "active_generation_status": active_status,
            "issues": issues,
        }

    def list_sources_with_dates(self) -> list[dict]:
        with self._connect() as conn:
            return [
                {"source": row["source"], "ingested_at": row["ingested_at"]}
                for row in conn.execute("SELECT source, ingested_at FROM sources ORDER BY ingested_at DESC, source")
            ]

    def list_grouped_sources_with_dates(self) -> list[dict]:
        with self._connect() as conn:
            return [
                {"source": row["source"], "ingested_at": row["ingested_at"]}
                for row in conn.execute(
                    """
                    SELECT COALESCE(NULLIF(docset_root, ''), source) AS source, MAX(ingested_at) AS ingested_at
                    FROM sources
                    GROUP BY COALESCE(NULLIF(docset_root, ''), source)
                    ORDER BY ingested_at DESC, source
                    """
                )
            ]

    def list_sources(self) -> list[str]:
        return [entry["source"] for entry in self.list_sources_with_dates()]

    def list_embedding_upserts(self, collection: str) -> dict[int, dict]:
        """Return ``{chunk_id: {content_hash, embedding_hash, status}}`` for a collection."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, content_hash, embedding_hash, upserted_at, status,
                       stable_chunk_id
                FROM embedding_upserts
                WHERE qdrant_collection = ?
                """,
                (collection,),
            )
            return {
                int(row["chunk_id"]): {
                    "content_hash": row["content_hash"] or "",
                    "embedding_hash": row["embedding_hash"] or "",
                    "upserted_at": row["upserted_at"] or "",
                    "status": row["status"] or "",
                    "stable_chunk_id": row["stable_chunk_id"] or "",
                }
                for row in rows
            }

    def list_generation_vector_upserts(self, collection: str) -> dict[str, dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT stable_chunk_id, vector_id, retrieval_content_hash,
                       embedding_hash, generation_id, status
                FROM generation_vector_upserts
                WHERE qdrant_collection = ?
                """,
                (collection,),
            )
            return {
                str(row["stable_chunk_id"]): {
                    "vector_id": str(row["vector_id"]),
                    "content_hash": str(row["retrieval_content_hash"]),
                    "embedding_hash": str(row["embedding_hash"]),
                    "generation_id": str(row["generation_id"]),
                    "status": str(row["status"]),
                }
                for row in rows
            }

    def record_generation_vector_upserts(
        self,
        collection: str,
        generation_id: str,
        records: list[dict[str, Any]],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO generation_vector_upserts
                    (stable_chunk_id, qdrant_collection, vector_id,
                     retrieval_content_hash, embedding_hash, generation_id,
                     upserted_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stable_chunk_id, qdrant_collection) DO UPDATE SET
                    vector_id = excluded.vector_id,
                    retrieval_content_hash = excluded.retrieval_content_hash,
                    embedding_hash = excluded.embedding_hash,
                    generation_id = excluded.generation_id,
                    upserted_at = excluded.upserted_at,
                    status = excluded.status
                """,
                [
                    (
                        str(row["stable_chunk_id"]), collection,
                        str(row["vector_id"]), str(row["content_hash"]),
                        str(row["embedding_hash"]), generation_id, now,
                        str(row.get("status") or "ok"),
                    )
                    for row in records
                ],
            )

    def delete_generation_vector_upserts(
        self,
        collection: str,
        stable_chunk_ids: list[str],
    ) -> int:
        if not stable_chunk_ids:
            return 0
        placeholders = ",".join("?" for _ in stable_chunk_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                DELETE FROM generation_vector_upserts
                WHERE qdrant_collection = ?
                  AND stable_chunk_id IN ({placeholders})
                """,
                (collection, *stable_chunk_ids),
            )
            return int(cursor.rowcount or 0)

    def section_ids_for_source(self, source: str) -> list[int]:
        """Return stable chunk ids before a source is removed."""
        with self._connect() as conn:
            active = self._active_generation_id(conn)
            if not active:
                return []
            rows = conn.execute(
                """
                SELECT hydration_id AS id FROM retrieval_children
                WHERE generation_id = ? AND source = ?
                ORDER BY chunk_index
                """,
                (active, source),
            )
            return [int(row["id"]) for row in rows]

    def record_embedding_upserts(
        self,
        collection: str,
        records: list[dict],
    ) -> None:
        """Insert/replace rows in ``embedding_upserts``.

        Each record needs ``chunk_id``, ``content_hash``, ``embedding_hash``,
        and optionally ``status`` (defaults to "ok").
        """
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO embedding_upserts
                    (chunk_id, qdrant_collection, content_hash, embedding_hash, upserted_at, status,
                     stable_chunk_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, qdrant_collection) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    embedding_hash = excluded.embedding_hash,
                    upserted_at = excluded.upserted_at,
                    status = excluded.status,
                    stable_chunk_id = excluded.stable_chunk_id
                """,
                [
                    (
                        int(r["chunk_id"]),
                        collection,
                        r.get("content_hash") or "",
                        r.get("embedding_hash") or "",
                        now,
                        r.get("status") or "ok",
                        r.get("stable_chunk_id") or "",
                    )
                    for r in records
                ],
            )

    def delete_embedding_upserts(self, collection: str, chunk_ids: list[int]) -> int:
        if not chunk_ids:
            return 0
        placeholders = ",".join("?" * len(chunk_ids))
        with self._connect() as conn:
            cur = conn.execute(
                f"DELETE FROM embedding_upserts "
                f"WHERE qdrant_collection = ? AND chunk_id IN ({placeholders})",
                (collection, *chunk_ids),
            )
            return cur.rowcount or 0
