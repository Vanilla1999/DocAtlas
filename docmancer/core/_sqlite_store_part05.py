"""SQLiteStore implementation shard 5."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStorePart05:
    def adjacent_section_ids(self, section_id: int, *, mode: str = "adjacent") -> list[int]:
        """Return neighboring section ids for hybrid-mode neighbor expansion.

        ``mode="adjacent"`` returns the prev + next sections within the same
        source. ``mode="page"`` returns every section belonging to the same
        source as the target.
        """
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if active_generation:
                row = conn.execute(
                    """
                    SELECT chunk_index, parent_logical_id, atom_type, atom_id
                    FROM retrieval_children
                    WHERE generation_id = ? AND hydration_id = ?
                    """,
                    (active_generation, int(section_id)),
                ).fetchone()
                if not row:
                    legacy = conn.execute(
                        """
                        SELECT source, chunk_index, parent_logical_id
                        FROM sections
                        WHERE id = ? AND source NOT IN (
                            SELECT source FROM generation_sources
                            WHERE generation_id = ?
                        )
                        """,
                        (int(section_id), active_generation),
                    ).fetchone()
                    if not legacy:
                        return []
                    source = legacy["source"]
                    chunk_index = int(legacy["chunk_index"])
                    parent_logical_id = legacy["parent_logical_id"]
                    if parent_logical_id:
                        if mode == "page":
                            rows = conn.execute(
                                """
                                SELECT id FROM sections
                                WHERE parent_logical_id = ? AND id != ?
                                ORDER BY chunk_index LIMIT 20
                                """,
                                (parent_logical_id, int(section_id)),
                            )
                        else:
                            rows = conn.execute(
                                """
                                SELECT id FROM sections
                                WHERE parent_logical_id = ?
                                  AND chunk_index IN (?, ?)
                                ORDER BY chunk_index
                                """,
                                (parent_logical_id, chunk_index - 1, chunk_index + 1),
                            )
                    elif mode == "page":
                        rows = conn.execute(
                            """
                            SELECT id FROM sections
                            WHERE source = ? AND id != ? ORDER BY chunk_index
                            """,
                            (source, int(section_id)),
                        )
                    else:
                        rows = conn.execute(
                            """
                            SELECT id FROM sections
                            WHERE source = ? AND chunk_index IN (?, ?)
                            ORDER BY chunk_index
                            """,
                            (source, chunk_index - 1, chunk_index + 1),
                        )
                    return [int(item["id"]) for item in rows]
                conditions = ["chunk_index IN (?, ?)"]
                params: list[Any] = [
                    int(row["chunk_index"]) - 1,
                    int(row["chunk_index"]) + 1,
                ]
                if mode == "page" and row["atom_type"] in {"code", "table"}:
                    conditions.append("atom_id = ?")
                    params.append(row["atom_id"])
                neighbors = conn.execute(
                    f"""
                    SELECT hydration_id AS id FROM retrieval_children
                    WHERE generation_id = ? AND parent_logical_id = ? AND hydration_id != ?
                      AND ({' OR '.join(conditions)})
                    ORDER BY chunk_index LIMIT 7
                    """,
                    (
                        active_generation,
                        row["parent_logical_id"],
                        int(section_id),
                        *params,
                    ),
                )
                return [int(item["id"]) for item in neighbors]
            row = conn.execute(
                "SELECT source, chunk_index, parent_logical_id FROM sections WHERE id = ?",
                (int(section_id),),
            ).fetchone()
            if not row:
                return []
            source = row["source"]
            chunk_index = int(row["chunk_index"])
            parent_logical_id = row["parent_logical_id"]
            if parent_logical_id:
                if mode == "page":
                    rows = conn.execute(
                        """
                        SELECT id, chunk_index FROM sections
                        WHERE parent_logical_id = ? AND id != ?
                        ORDER BY chunk_index
                        LIMIT 20
                        """,
                        (parent_logical_id, int(section_id)),
                    )
                    return [int(r["id"]) for r in rows]
                rows = conn.execute(
                    """
                    SELECT id, chunk_index FROM sections
                    WHERE parent_logical_id = ? AND chunk_index IN (?, ?)
                    ORDER BY chunk_index
                    """,
                    (parent_logical_id, chunk_index - 1, chunk_index + 1),
                )
                return [int(r["id"]) for r in rows]
            if mode == "page":
                rows = conn.execute(
                    """
                    SELECT id, chunk_index FROM sections
                    WHERE source = ? AND id != ?
                    ORDER BY chunk_index
                    """,
                    (source, int(section_id)),
                )
                return [int(r["id"]) for r in rows]
            # default: adjacent (prev + next)
            rows = conn.execute(
                """
                SELECT id, chunk_index FROM sections
                WHERE source = ? AND chunk_index IN (?, ?)
                ORDER BY chunk_index
                """,
                (source, chunk_index - 1, chunk_index + 1),
            )
            return [int(r["id"]) for r in rows]

    def document_title_hashes_for(self, section_ids: list[int]) -> dict[int, str]:
        """Return ``{section_id: document_title_hash}`` for hierarchical retrieval.

        Pulled from ``metadata_json`` because the field is loader-set and
        not promoted to a top-level column. Empty hash means the loader
        did not record one (USPTO atomic records, etc.) and the section
        should not participate in document-level grouping.
        """
        if not section_ids:
            return {}
        placeholders = ",".join("?" * len(section_ids))
        out: dict[int, str] = {}
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if active_generation:
                query = f"""
                    SELECT id, metadata_json FROM sections
                    WHERE id IN ({placeholders})
                      AND source NOT IN (
                          SELECT source FROM generation_sources
                          WHERE generation_id = ?
                      )
                    UNION ALL
                    SELECT hydration_id AS id, metadata_json
                    FROM retrieval_children
                    WHERE generation_id = ?
                      AND hydration_id IN ({placeholders})
                """
                params: tuple[Any, ...] = (
                    *section_ids, active_generation,
                    active_generation, *section_ids,
                )
            else:
                query = (
                    f"SELECT id, metadata_json FROM sections "
                    f"WHERE id IN ({placeholders})"
                )
                params = tuple(section_ids)
            for row in conn.execute(query, params):
                try:
                    md = json.loads(row["metadata_json"] or "{}")
                except json.JSONDecodeError:
                    md = {}
                doc_hash = md.get("document_title_hash") or md.get("docset_root") or ""
                if doc_hash:
                    out[int(row["id"])] = str(doc_hash)
        return out

    def distinct_document_count(self) -> int:
        """Return the number of distinct documents in the index.

        Mirrors what ``document_title_hash`` would group by: the hash is
        derived from ``document_title``, so counting distinct
        non-empty ``document_title`` values is equivalent and avoids a
        scan through ``metadata_json``.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT document_title) AS n "
                "FROM sections WHERE document_title IS NOT NULL AND document_title <> ''"
            ).fetchone()
            return int(row["n"]) if row else 0

    def section_count_grouped_by_format(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(format, ''), 'unknown') AS fmt, COUNT(*) AS n
                FROM sections
                GROUP BY fmt
                """
            )
            return {row["fmt"]: int(row["n"]) for row in rows}

    def list_sections_for_embedding(self, generation_id: str | None = None) -> list[dict]:
        """Return canonical section chunks for embedding-based consumers.

        Emits the same chunks the FTS index stores, so future embedding
        features can reuse identical section boundaries. Each row has:
        section_id (int), source, chunk_index, title, level, text, and
        token_estimate.
        """
        with self._connect() as conn:
            target_generation = generation_id or self._active_generation_id(conn)
            if target_generation:
                rows = conn.execute(
                    """
                    SELECT hydration_id AS id, source, chunk_index, title, level, display_text,
                           retrieval_text, display_token_estimate,
                           retrieval_token_estimate, source_path, document_title,
                           format, anchor, display_content_hash,
                           retrieval_content_hash, stable_chunk_id, vector_id,
                           parent_logical_id, generation_id, char_start, char_end,
                           byte_start, byte_end, metadata_json,
                           context_schema_version, context_config_hash,
                           context_content_hash, embedding_input_hash,
                           source_identity, library_id, resolved_version,
                           version_family, project_identity, project_path,
                           module_id, doc_scope, source_class, authority,
                           lifecycle_status, temporal_relevance, index_freshness,
                           docs_snapshot_exact
                    FROM retrieval_children
                    WHERE generation_id = ?
                    ORDER BY source, chunk_index
                    """,
                    (target_generation,),
                )
                info = conn.execute(
                    """SELECT schema_version, config_hash, retrieval_config_hash
                       FROM index_generations WHERE generation_id = ?""",
                    (target_generation,),
                ).fetchone()
                embedded = []
                for row in rows:
                    try:
                        source_metadata = json.loads(str(row["metadata_json"] or "{}"))
                    except (TypeError, json.JSONDecodeError):
                        source_metadata = {}
                    item = {
                        "section_id": int(row["id"]),
                        "vector_id": str(row["vector_id"]),
                        "source": str(row["source"]),
                        "chunk_index": int(row["chunk_index"]),
                        "title": str(row["title"] or ""),
                        "level": int(row["level"] or 0),
                        "text": str(row["retrieval_text"]),
                        "display_text": str(row["display_text"]),
                        "token_estimate": int(row["display_token_estimate"]),
                        "retrieval_token_estimate": int(row["retrieval_token_estimate"]),
                        "source_path": str(row["source_path"] or ""),
                        "document_title": str(row["document_title"] or ""),
                        "format": str(row["format"] or ""),
                        "anchor": str(row["anchor"] or ""),
                        "content_hash": str(row["retrieval_content_hash"]),
                        "display_content_hash": str(row["display_content_hash"]),
                        "stable_chunk_id": str(row["stable_chunk_id"]),
                        "parent_logical_id": str(row["parent_logical_id"]),
                        "generation_id": str(row["generation_id"]),
                        "char_start": int(row["char_start"]),
                        "char_end": int(row["char_end"]),
                        "byte_start": int(row["byte_start"]),
                        "byte_end": int(row["byte_end"]),
                        "chunk_schema_version": str(info["schema_version"]),
                        "chunk_config_hash": str(info["config_hash"]),
                        "context_schema_version": str(row["context_schema_version"]),
                        "context_config_hash": str(row["context_config_hash"]),
                        "context_content_hash": str(row["context_content_hash"]),
                        "embedding_input_hash": str(row["embedding_input_hash"]),
                        "retrieval_config_hash": str(info["retrieval_config_hash"] or ""),
                        "source_identity": str(row["source_identity"] or ""),
                        "library_id": str(row["library_id"] or ""),
                        "resolved_version": str(row["resolved_version"] or ""),
                        "version_family": str(row["version_family"] or ""),
                        "project_identity": str(row["project_identity"] or ""),
                        "project_path": str(row["project_path"] or ""),
                        "module_id": str(row["module_id"] or ""),
                        "doc_scope": str(row["doc_scope"] or ""),
                        "source_class": str(row["source_class"] or ""),
                        "authority": str(row["authority"] or "unknown"),
                        "lifecycle_status": str(row["lifecycle_status"] or "active"),
                        "temporal_relevance": str(row["temporal_relevance"] or "current"),
                        "index_freshness": str(row["index_freshness"] or "synchronized"),
                        "docs_snapshot_exact": (
                            bool(row["docs_snapshot_exact"])
                            if row["docs_snapshot_exact"] is not None else None
                        ),
                        "canonical_url": str(source_metadata.get("canonical_url") or ""),
                        "source_url": str(source_metadata.get("source_url") or ""),
                    }
                    embedded.append(item)
                legacy_rows = conn.execute(
                    """
                    SELECT id, source, chunk_index, title, level, text,
                           retrieval_text, token_estimate, source_path,
                           document_title, format, anchor, content_hash,
                           retrieval_content_hash, parent_logical_id
                    FROM sections
                    WHERE source NOT IN (
                        SELECT source FROM generation_sources
                        WHERE generation_id = ?
                    )
                    ORDER BY source, chunk_index
                    """,
                    (target_generation,),
                )
                for row in legacy_rows:
                    retrieval_text = str(row["retrieval_text"] or row["text"] or "")
                    retrieval_hash = str(
                        row["retrieval_content_hash"]
                        or hashlib.sha256(retrieval_text.encode("utf-8")).hexdigest()
                    )
                    stable_id = "legacy-" + hashlib.sha256(
                        (
                            f"{row['source']}\0{row['chunk_index']}\0{retrieval_hash}"
                        ).encode("utf-8")
                    ).hexdigest()[:40]
                    embedded.append({
                        "section_id": int(row["id"]),
                        "vector_id": str(uuid.uuid5(
                            uuid.NAMESPACE_URL, f"docatlas:legacy:{stable_id}"
                        )),
                        "source": str(row["source"]),
                        "chunk_index": int(row["chunk_index"]),
                        "title": str(row["title"] or ""),
                        "level": int(row["level"] or 0),
                        "text": retrieval_text,
                        "display_text": str(row["text"] or ""),
                        "token_estimate": int(row["token_estimate"] or 0),
                        "retrieval_token_estimate": estimate_tokens(retrieval_text),
                        "source_path": str(row["source_path"] or ""),
                        "document_title": str(row["document_title"] or ""),
                        "format": str(row["format"] or ""),
                        "anchor": str(row["anchor"] or ""),
                        "content_hash": retrieval_hash,
                        "display_content_hash": str(row["content_hash"] or ""),
                        "stable_chunk_id": stable_id,
                        "parent_logical_id": str(row["parent_logical_id"] or ""),
                        "generation_id": str(target_generation),
                        "chunk_schema_version": INDEX_SCHEMA_VERSION,
                        "chunk_config_hash": "legacy-compatibility-v1",
                        "context_schema_version": "",
                        "context_config_hash": "",
                        "context_content_hash": "",
                        "embedding_input_hash": retrieval_hash,
                        "retrieval_config_hash": "legacy-compatibility-v1",
                    })
                return embedded
            rows = conn.execute(
                """
                SELECT id, source, chunk_index, title, level, text, retrieval_text,
                       token_estimate, source_path, document_title, format, anchor,
                       content_hash, retrieval_content_hash, stable_chunk_id, parent_logical_id,
                       chunk_schema_version, chunk_config_hash
                FROM sections
                ORDER BY source, chunk_index
                """
            )
            return [
                {
                    "section_id": int(row["id"]),
                    "source": str(row["source"]),
                    "chunk_index": int(row["chunk_index"]),
                    "title": str(row["title"] or ""),
                    "level": int(row["level"] or 0),
                    "text": str(row["retrieval_text"] or row["text"] or ""),
                    "display_text": str(row["text"] or ""),
                    "token_estimate": int(row["token_estimate"] or 0),
                    "source_path": str(row["source_path"] or ""),
                    "document_title": str(row["document_title"] or ""),
                    "format": str(row["format"] or ""),
                    "anchor": str(row["anchor"] or ""),
                    "content_hash": str(row["retrieval_content_hash"] or row["content_hash"] or ""),
                    "display_content_hash": str(row["content_hash"] or ""),
                    "stable_chunk_id": str(row["stable_chunk_id"] or ""),
                    "parent_logical_id": str(row["parent_logical_id"] or ""),
                    "chunk_schema_version": str(row["chunk_schema_version"] or INDEX_SCHEMA_VERSION),
                    "chunk_config_hash": str(row["chunk_config_hash"] or ""),
                }
                for row in rows
            ]

    def get_document_content(self, source: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT content FROM sources WHERE source = ?", (source,)).fetchone()
            return str(row["content"]) if row else None

    def source_metadata(self, source: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT metadata_json FROM sources WHERE source = ?", (source,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            return None

    def has_source_content_hash(self, source: str, content_hash: str) -> bool:
        if not content_hash:
            return False
        metadata = self.source_metadata(source)
        if metadata is None:
            return False
        return metadata.get("content_hash") == content_hash

    def delete_docset(self, docset_root: str) -> bool:
        with self._connect() as conn:
            sources = [
                row["source"]
                for row in conn.execute("SELECT source FROM sources WHERE docset_root = ?", (docset_root,))
            ]
        deleted = False
        for source in sources:
            deleted = self.delete_source(source) or deleted
        return deleted

    def delete_docset_sources_except(
        self, docset_root: str, retained_sources: Iterable[str]
    ) -> int:
        """Remove sources no longer present in one successfully fetched docset."""

        retained = {str(source) for source in retained_sources}
        with self._connect() as conn:
            stale = [
                str(row["source"])
                for row in conn.execute(
                    "SELECT source FROM sources WHERE docset_root = ? ORDER BY source",
                    (docset_root,),
                )
                if str(row["source"]) not in retained
            ]
        return sum(1 for source in stale if self.delete_source(source))

    def delete_source(self, source: str) -> bool:
        artifact_paths: set[Path] = set()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, markdown_path, json_path FROM sources WHERE source = ?",
                (source,),
            ).fetchone()
            if not row:
                return False
            source_id = int(row["id"])
            artifact_paths = {
                Path(str(path_value))
                for path_value in (row["markdown_path"], row["json_path"])
                if path_value
            }
            # Active retrieval generations are immutable. Publish a validated
            # clone without this source before removing compatibility rows.
            self._build_generation_without_sources(conn, {source})
            row_ids = [r["id"] for r in conn.execute("SELECT id FROM sections WHERE source_id = ?", (source_id,))]
            for row_id in row_ids:
                conn.execute("DELETE FROM sections_fts WHERE rowid = ?", (row_id,))
            conn.execute("DELETE FROM sections WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM parent_sections WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            artifact_values = tuple(str(path) for path in artifact_paths)
            referenced_paths: set[Path] = set()
            if artifact_values:
                placeholders = ", ".join("?" for _ in artifact_values)
                remaining_rows = conn.execute(
                    f"SELECT markdown_path, json_path FROM sources "
                    f"WHERE markdown_path IN ({placeholders}) OR json_path IN ({placeholders})",
                    (*artifact_values, *artifact_values),
                )
                referenced_paths = {
                    Path(str(path_value))
                    for remaining in remaining_rows
                    for path_value in (remaining["markdown_path"], remaining["json_path"])
                    if path_value
                }

        extracted_root = self.extracted_dir.resolve()
        for artifact_path in artifact_paths - referenced_paths:
            # Extraction artifacts are direct children generated by _stage_extraction.
            # Never trust a persisted path enough to unlink outside that directory.
            if artifact_path.parent.resolve() == extracted_root:
                artifact_path.unlink(missing_ok=True)
        return True

    def delete_sources_under_roots(self, roots: Iterable[str | Path]) -> int:
        """Delete sources whose source/docset_root live under any local root."""
        normalized_roots = [
            _normalize_source_like(root)
            for root in roots
            if str(root).strip()
        ]
        if not normalized_roots:
            return 0

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source, docset_root, markdown_path, json_path FROM sources"
            ).fetchall()

        sources_to_delete: list[str] = []
        for row in rows:
            source = str(row["source"] or "")
            docset_root = str(row["docset_root"] or "")
            source_norm = _normalize_source_like(source)
            docset_norm = _normalize_source_like(docset_root)

            matched = False
            for root in normalized_roots:
                prefix = root + "/"
                if source_norm == root or source_norm.startswith(prefix):
                    matched = True
                    break
                if docset_norm == root or docset_norm.startswith(prefix):
                    matched = True
                    break

            if not matched:
                continue

            sources_to_delete.append(source)

        deleted = 0
        for source in sources_to_delete:
            if self.delete_source(source):
                deleted += 1

        return deleted

    def delete_all(self) -> bool:
        stats = self.collection_stats()
        with self._connect() as conn:
            conn.execute("DELETE FROM sections_fts")
            conn.execute("DELETE FROM sections")
            conn.execute("DELETE FROM sources")
            self._deactivate_active_generation(conn)
        return stats["sources_count"] > 0 or stats["sections_count"] > 0
