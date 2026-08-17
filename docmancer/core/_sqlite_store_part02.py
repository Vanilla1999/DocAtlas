"""SQLiteStore implementation shard 2."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStorePart02:
    def _build_candidate_generation(
        self,
        conn: sqlite3.Connection,
        documents: list[Document],
        *,
        recreate: bool,
    ) -> str:
        configs = {
            ChunkingConfig(
                target_tokens=int((doc.metadata or {}).get("child_target_tokens") or 160),
                hard_max_tokens=int((doc.metadata or {}).get("child_hard_max_tokens") or 512),
                overlap_tokens=0,
            )
            for doc in documents
        }
        if len(configs) != 1:
            raise ValueError("one index generation cannot mix chunking configurations")
        config = next(iter(configs))
        context_config = ContextConfig()
        retrieval_config_hash = canonical_hash({
            "schema_version": "contextual-retrieval-v1",
            "chunk_config_hash": config.config_hash,
            "context_config_hash": context_config.config_hash,
        })
        generation_id = "gen-" + uuid.uuid4().hex
        active = self._active_generation_id(conn)
        vector_collection = f"docmancer_ctx_{retrieval_config_hash[:16]}"
        active_same_config = False
        if active:
            active_info = conn.execute(
                """
                SELECT config_hash, retrieval_config_hash, vector_collection
                FROM index_generations
                WHERE generation_id = ?
                """,
                (active,),
            ).fetchone()
            active_same_config = bool(
                active_info
                and str(active_info["config_hash"]) == config.config_hash
                and str(active_info["retrieval_config_hash"] or "") == retrieval_config_hash
            )
            if active_same_config:
                vector_collection = str(active_info["vector_collection"])
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO index_generations
                (generation_id, schema_version, config_hash, config_json,
                 context_schema_version, context_config_hash,
                 retrieval_config_hash, status, vector_collection,
                 validation_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'building', ?, '{}', ?)
            """,
            (
                generation_id,
                config.schema_version,
                config.config_hash,
                json.dumps({
                    "target_tokens": config.target_tokens,
                    "hard_max_tokens": config.hard_max_tokens,
                    "overlap_tokens": config.overlap_tokens,
                    "estimator_version": config.estimator_version,
                    "context": {
                        "schema_version": context_config.schema_version,
                        "max_prefix_bytes": context_config.max_prefix_bytes,
                        "max_prefix_tokens": context_config.max_prefix_tokens,
                        "allowed_fields": list(context_config.allowed_fields),
                        "symbol_extractor_version": context_config.symbol_extractor_version,
                    },
                }, sort_keys=True),
                context_config.schema_version,
                context_config.config_hash,
                retrieval_config_hash,
                vector_collection,
                now,
            ),
        )
        input_sources = {doc.source for doc in documents}
        if active and not recreate and not active_same_config:
            rebuilt: list[Document] = []
            for row in conn.execute(
                """
                SELECT source, content, metadata_json FROM generation_sources
                WHERE generation_id = ? ORDER BY source
                """,
                (active,),
            ):
                if str(row["source"]) in input_sources:
                    continue
                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                metadata.update({
                    "chunking_schema": config.schema_version,
                    "child_target_tokens": config.target_tokens,
                    "child_hard_max_tokens": config.hard_max_tokens,
                })
                rebuilt.append(Document(
                    source=str(row["source"]),
                    content=str(row["content"]),
                    metadata=metadata,
                ))
            documents = [*rebuilt, *documents]
        changed_sources = {doc.source for doc in documents}
        if active and not recreate and active_same_config:
            placeholders = ",".join("?" for _ in changed_sources)
            exclusion = f"AND source NOT IN ({placeholders})" if changed_sources else ""
            params: tuple[Any, ...] = (generation_id, active, *sorted(changed_sources))
            conn.execute(
                f"""
                INSERT INTO generation_sources
                    (generation_id, source, source_identity, content,
                     content_hash, metadata_json, raw_tokens)
                SELECT ?, source, source_identity, content, content_hash,
                       metadata_json, raw_tokens
                FROM generation_sources
                WHERE generation_id = ? {exclusion}
                """,
                params,
            )
            conn.execute(
                f"""
                INSERT INTO retrieval_parents
                    (generation_id, logical_id, revision_id, source_id, source,
                     source_identity, title, level, heading_path_json,
                     heading_levels_json, occurrence, char_start, char_end,
                     byte_start, byte_end, line_start, line_end, display_text,
                     source_content_hash)
                SELECT ?, logical_id, revision_id, source_id, source,
                       source_identity, title, level, heading_path_json,
                       heading_levels_json, occurrence, char_start, char_end,
                       byte_start, byte_end, line_start, line_end, display_text,
                       source_content_hash
                FROM retrieval_parents
                WHERE generation_id = ? {exclusion}
                """,
                params,
            )
            child_rows = conn.execute(
                f"""
                SELECT * FROM retrieval_children
                WHERE generation_id = ? {exclusion}
                ORDER BY id
                """,
                (active, *sorted(changed_sources)),
            ).fetchall()
            for row in child_rows:
                child_id = self._insert_retrieval_child_copy(conn, generation_id, row)
                conn.execute(
                    """
                    INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (child_id, row["title"], row["retrieval_text"], row["source"]),
                )

        for doc in documents:
            source_row = conn.execute(
                "SELECT id FROM sources WHERE source = ?", (doc.source,)
            ).fetchone()
            if source_row is None:
                raise ValueError(f"source row missing during generation build: {doc.source}")
            source_id = int(source_row["id"])
            source_identity = _stable_source_identity(doc)
            metadata = dict(doc.metadata or {})
            source_content_hash = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO generation_sources
                    (generation_id, source, source_identity, content,
                     content_hash, metadata_json, raw_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id, doc.source, source_identity, doc.content,
                    source_content_hash,
                    json.dumps(metadata, ensure_ascii=False),
                    estimate_tokens(doc.content),
                ),
            )
            parents, children = chunk_markdown_parent_child(
                doc.content, source_identity, config
            )
            parent_by_id = {parent.logical_id: parent for parent in parents}
            for parent in parents:
                conn.execute(
                    """
                    INSERT INTO retrieval_parents
                        (generation_id, logical_id, revision_id, source_id, source,
                         source_identity, title, level, heading_path_json,
                         heading_levels_json, occurrence, char_start, char_end,
                         byte_start, byte_end, line_start, line_end, display_text,
                         source_content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generation_id, parent.logical_id, parent.revision_id,
                        source_id, doc.source, source_identity, parent.title,
                        parent.level, json.dumps(parent.heading_path, ensure_ascii=False),
                        json.dumps(parent.heading_levels), parent.occurrence,
                        parent.char_start, parent.char_end, parent.byte_start,
                        parent.byte_end, parent.line_start, parent.line_end,
                        parent.display_text, parent.source_content_hash,
                    ),
                )
            source_path = str(metadata.get("source_path") or doc.source)
            document_title = str(metadata.get("title") or Path(doc.source).stem or "Document")
            format_name = str(metadata.get("format") or "markdown")
            for global_index, child in enumerate(children):
                parent = parent_by_id[child.parent_logical_id]
                anchor = " > ".join(parent.heading_path) or parent.title
                display_hash = _chunk_hash(child.display_text)
                context_prefix = build_context_prefix(
                    {
                        **metadata,
                        "document_title": document_title,
                        "source_path": metadata.get("source_path") or source_path,
                    },
                    heading_path=parent.heading_path,
                    display_text=child.display_text,
                    config=context_config,
                    available_tokens=max(
                        0, config.hard_max_tokens - child.token_estimate - 2
                    ),
                )
                retrieval_text = embedding_input(context_prefix, child.display_text)
                retrieval_hash = _chunk_hash(retrieval_text)
                filter_metadata = normalized_filter_metadata({
                    **metadata,
                    "source_path": metadata.get("source_path") or source_path,
                })
                context_manifest = context_prefix.manifest()
                child_metadata = {
                    **metadata,
                    **filter_metadata,
                    "section_title": parent.title,
                    "section_level": parent.level,
                    "source_path": source_path,
                    "document_title": document_title,
                    "document_title_hash": hashlib.sha1(
                        document_title.encode("utf-8")
                    ).hexdigest()[:16],
                    "format": format_name,
                    "anchor": anchor,
                    "content_hash": display_hash,
                    "retrieval_content_hash": retrieval_hash,
                    "context_schema_version": context_prefix.schema_version,
                    "context_config_hash": context_prefix.config_hash,
                    "context_content_hash": context_prefix.content_hash,
                    "context_manifest": context_manifest,
                    "embedding_input_hash": retrieval_hash,
                    "stable_chunk_id": child.stable_id,
                    "vector_id": child.vector_id,
                    "parent_logical_id": child.parent_logical_id,
                    "atom_type": child.atom_type,
                    "atom_id": child.atom_id,
                    "source_identity": source_identity,
                    "source_content_hash": child.source_content_hash,
                    "heading_path": list(parent.heading_path),
                    "heading_levels": list(parent.heading_levels),
                    "char_span": [child.char_start, child.char_end],
                    "byte_span": [child.byte_start, child.byte_end],
                    "line_span": [child.line_start, child.line_end],
                    "chunk_schema_version": config.schema_version,
                    "chunk_config_hash": config.config_hash,
                    "token_estimator_version": child.estimator_version,
                    "display_token_estimate": child.token_estimate,
                    "retrieval_token_estimate": estimate_utf8_tokens(retrieval_text),
                    "generation_id": generation_id,
                }
                snippets = _code_snippets(child.display_text)
                if snippets:
                    child_metadata["code_snippets"] = snippets
                    child_metadata["has_code_snippet"] = True
                child_id = conn.execute(
                    """
                    INSERT INTO retrieval_children
                        (generation_id, hydration_id, stable_chunk_id, vector_id,
                         parent_logical_id, source_id, source, source_identity,
                         chunk_index, parent_ordinal, title, level, atom_type,
                         atom_id, display_text, retrieval_text,
                         display_content_hash, retrieval_content_hash,
                         display_token_estimate, retrieval_token_estimate,
                         context_prefix, context_manifest_json,
                         context_schema_version, context_config_hash,
                         context_content_hash, embedding_input_hash,
                         char_start, char_end, byte_start, byte_end, line_start,
                         line_end, source_path, document_title, format, anchor,
                         library_id, resolved_version, version_family,
                         project_identity, project_path, module_id, doc_scope,
                         source_class, authority, lifecycle_status, temporal_relevance,
                         index_freshness, docs_snapshot_exact, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generation_id, child.sqlite_id, child.stable_id, child.vector_id,
                        child.parent_logical_id, source_id, doc.source,
                        source_identity, global_index, child.ordinal,
                        parent.title, parent.level, child.atom_type,
                        child.atom_id, child.display_text, retrieval_text,
                        display_hash, retrieval_hash, child.token_estimate,
                        estimate_utf8_tokens(retrieval_text), context_prefix.text,
                        json.dumps(context_manifest, ensure_ascii=False, sort_keys=True),
                        context_prefix.schema_version, context_prefix.config_hash,
                        context_prefix.content_hash, retrieval_hash, child.char_start,
                        child.char_end, child.byte_start, child.byte_end,
                        child.line_start, child.line_end, source_path,
                        document_title, format_name, anchor,
                        filter_metadata["library_id"],
                        filter_metadata["resolved_version"],
                        filter_metadata["version_family"],
                        filter_metadata["project_identity"],
                        filter_metadata["project_path"],
                        filter_metadata["module_id"], filter_metadata["doc_scope"],
                        filter_metadata["source_class"], filter_metadata["authority"],
                        filter_metadata["lifecycle_status"],
                        filter_metadata["temporal_relevance"],
                        filter_metadata["index_freshness"],
                        filter_metadata["docs_snapshot_exact"],
                        json.dumps(child_metadata, ensure_ascii=False),
                    ),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (int(child_id), parent.title, retrieval_text, doc.source),
                )

        validation = self._validate_generation(
            conn, generation_id, config, context_config
        )
        conn.execute(
            """
            UPDATE index_generations
            SET status = 'ready', validation_json = ?
            WHERE generation_id = ?
            """,
            (json.dumps(validation, sort_keys=True), generation_id),
        )
        return generation_id

    @staticmethod
    def _insert_retrieval_child_copy(
        conn: sqlite3.Connection,
        generation_id: str,
        row: sqlite3.Row,
    ) -> int:
        columns = (
            "hydration_id", "stable_chunk_id", "vector_id", "parent_logical_id", "source_id",
            "source", "source_identity", "chunk_index", "parent_ordinal",
            "title", "level", "atom_type", "atom_id", "display_text",
            "retrieval_text", "display_content_hash", "retrieval_content_hash",
            "display_token_estimate", "retrieval_token_estimate", "char_start",
            "context_prefix", "context_manifest_json", "context_schema_version",
            "context_config_hash", "context_content_hash", "embedding_input_hash",
            "char_end", "byte_start", "byte_end", "line_start", "line_end",
            "source_path", "document_title", "format", "anchor", "metadata_json",
            "library_id", "resolved_version", "version_family", "project_identity",
            "project_path", "module_id", "doc_scope", "source_class", "authority",
            "lifecycle_status", "temporal_relevance", "index_freshness",
            "docs_snapshot_exact",
        )
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        values = []
        for column in columns:
            if column != "metadata_json":
                values.append(row[column])
                continue
            metadata = json.loads(str(row[column] or "{}"))
            metadata.update({
                name: row[name]
                for name in normalized_filter_metadata(metadata)
            })
            values.append(json.dumps(metadata, ensure_ascii=False))
        cursor = conn.execute(
            f"INSERT INTO retrieval_children (generation_id, {', '.join(columns)}) "
            f"VALUES ({placeholders})",
            (generation_id, *values),
        )
        return int(cursor.lastrowid)

    def _validate_generation(
        self,
        conn: sqlite3.Connection,
        generation_id: str,
        config: ChunkingConfig,
        context_config: ContextConfig,
    ) -> dict[str, Any]:
        child_count = int(conn.execute(
            "SELECT COUNT(*) AS count FROM retrieval_children WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()["count"])
        fts_count = int(conn.execute(
            """
            SELECT COUNT(*) AS count FROM retrieval_children_fts f
            JOIN retrieval_children c ON c.id = f.rowid
            WHERE c.generation_id = ?
            """,
            (generation_id,),
        ).fetchone()["count"])
        if child_count != fts_count:
            raise ValueError(
                f"generation FTS parity failed: children={child_count}, fts={fts_count}"
            )
        missing_parents = int(conn.execute(
            """
            SELECT COUNT(*) AS count FROM retrieval_children c
            LEFT JOIN retrieval_parents p
              ON p.generation_id = c.generation_id
             AND p.logical_id = c.parent_logical_id
            WHERE c.generation_id = ? AND p.logical_id IS NULL
            """,
            (generation_id,),
        ).fetchone()["count"])
        if missing_parents:
            raise ValueError(f"generation has {missing_parents} child rows without parents")
        missing_source_snapshots = int(conn.execute(
            """
            SELECT COUNT(*) AS count FROM retrieval_children c
            LEFT JOIN generation_sources gs
              ON gs.generation_id = c.generation_id
             AND gs.source = c.source
            WHERE c.generation_id = ? AND gs.source IS NULL
            """,
            (generation_id,),
        ).fetchone()["count"])
        if missing_source_snapshots:
            raise ValueError(
                f"generation has {missing_source_snapshots} child rows without source snapshots"
            )
        snapshot_hash_errors = 0
        for source_row in conn.execute(
            """
            SELECT content, content_hash FROM generation_sources
            WHERE generation_id = ?
            """,
            (generation_id,),
        ):
            actual_hash = hashlib.sha256(
                str(source_row["content"]).encode("utf-8")
            ).hexdigest()
            snapshot_hash_errors += int(actual_hash != str(source_row["content_hash"]))
        parent_snapshot_errors = int(conn.execute(
            """
            SELECT COUNT(*) AS count FROM retrieval_parents p
            JOIN generation_sources gs
              ON gs.generation_id = p.generation_id
             AND gs.source = p.source
            WHERE p.generation_id = ?
              AND p.source_content_hash != gs.content_hash
            """,
            (generation_id,),
        ).fetchone()["count"])
        if snapshot_hash_errors or parent_snapshot_errors:
            raise ValueError(
                "generation snapshot binding failed: "
                f"source_hash_errors={snapshot_hash_errors}, "
                f"parent_hash_errors={parent_snapshot_errors}"
            )
        span_errors = 0
        token_errors = 0
        context_errors = 0
        rows = conn.execute(
            """
            SELECT c.*, gs.content AS source_content
            FROM retrieval_children c
            JOIN generation_sources gs
              ON gs.generation_id = c.generation_id
             AND gs.source = c.source
            WHERE c.generation_id = ?
            """,
            (generation_id,),
        ).fetchall()
        for row in rows:
            source_content = str(row["source_content"])
            start = int(row["char_start"])
            end = int(row["char_end"])
            display = str(row["display_text"])
            if source_content[start:end] != display:
                span_errors += 1
                continue
            encoded = source_content.encode("utf-8")
            byte_slice = encoded[int(row["byte_start"]):int(row["byte_end"])]
            if byte_slice != display.encode("utf-8"):
                span_errors += 1
            if int(row["retrieval_token_estimate"]) > config.hard_max_tokens:
                token_errors += 1
            try:
                manifest = json.loads(str(row["context_manifest_json"] or "{}"))
                fields = manifest.get("fields", [])
                expected_context_hash = canonical_hash(fields)
                expected_retrieval = (
                    f"{row['context_prefix']}\n\n{display}"
                    if row["context_prefix"] else display
                )
                metadata = json.loads(str(row["metadata_json"] or "{}"))
                promoted = normalized_filter_metadata(metadata)
                promoted_matches = all(
                    row[name] == value
                    for name, value in promoted.items()
                )
                context_errors += int(
                    str(row["context_schema_version"]) != context_config.schema_version
                    or str(row["context_config_hash"]) != context_config.config_hash
                    or str(row["context_content_hash"]) != expected_context_hash
                    or manifest.get("schema_version") != context_config.schema_version
                    or manifest.get("config_hash") != context_config.config_hash
                    or manifest.get("content_hash") != expected_context_hash
                    or str(row["embedding_input_hash"]) != _chunk_hash(expected_retrieval)
                    or str(row["retrieval_text"]) != expected_retrieval
                    or len(str(row["context_prefix"]).encode("utf-8"))
                    > context_config.max_prefix_bytes
                    or estimate_utf8_tokens(str(row["context_prefix"]))
                    > context_config.max_prefix_tokens
                    or not promoted_matches
                )
            except (TypeError, json.JSONDecodeError):
                context_errors += 1
        if span_errors or token_errors or context_errors:
            raise ValueError(
                f"generation validation failed: span_errors={span_errors}, "
                f"retrieval_token_errors={token_errors}, "
                f"context_errors={context_errors}"
            )
        accepted_config = ChunkingConfig()
        accepted_profile_status = (
            "MATCH" if config.config_hash == accepted_config.config_hash else "UNVALIDATED"
        )
        return {
            "status": "PASS",
            "children": child_count,
            "fts_rows": fts_count,
            "span_errors": 0,
            "duplicate_id_errors": 0,
            "retrieval_token_errors": 0,
            "context_errors": 0,
            "context_schema_version": context_config.schema_version,
            "context_config_hash": context_config.config_hash,
            "source_snapshot_hash_errors": 0,
            "parent_snapshot_hash_errors": 0,
            "accepted_profile": {
                "status": accepted_profile_status,
                "config_hash": accepted_config.config_hash,
                "evidence_revision": "task40-parent-child-grid-v1",
            },
        }

    @staticmethod
    def _active_generation_id(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT active_generation_id FROM index_state WHERE singleton = 1"
        ).fetchone()
        return str(row["active_generation_id"]) if row and row["active_generation_id"] else None

    @staticmethod
    def _deactivate_active_generation(conn: sqlite3.Connection) -> None:
        active = SQLiteStore._active_generation_id(conn)
        if active:
            conn.execute(
                """
                UPDATE index_generations SET status = 'superseded'
                WHERE generation_id = ? AND status = 'active'
                """,
                (active,),
            )
        conn.execute(
            "UPDATE index_state SET active_generation_id = NULL WHERE singleton = 1"
        )

    def active_generation_id(self) -> str | None:
        with self._connect() as conn:
            return self._active_generation_id(conn)

    def _activate_generation(self, conn: sqlite3.Connection, generation_id: str) -> None:
        row = conn.execute(
            "SELECT status, validation_json FROM index_generations WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()
        if row is None or row["status"] != "ready":
            raise ValueError(f"generation {generation_id!r} is not ready")
        validation = json.loads(row["validation_json"] or "{}")
        if validation.get("status") != "PASS":
            raise ValueError(f"generation {generation_id!r} has not passed validation")
        conn.execute(
            "UPDATE index_generations SET status = 'superseded' WHERE status = 'active'"
        )
        conn.execute(
            """
            UPDATE index_generations SET status = 'active', activated_at = ?
            WHERE generation_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), generation_id),
        )
        conn.execute(
            "UPDATE index_state SET active_generation_id = ? WHERE singleton = 1",
            (generation_id,),
        )

    def activate_generation(
        self, generation_id: str, *, require_vector_witness: bool = False
    ) -> None:
        with self._connect() as conn:
            if require_vector_witness:
                row = conn.execute(
                    """SELECT vector_backend, vector_backend_identity,
                              vector_collection, vector_parity_schema,
                              vector_parity_digest, vector_parity_verified_at,
                              vector_parity_count, vector_parity_backend_identity,
                              vector_parity_collection
                       FROM index_generations WHERE generation_id = ?""",
                    (generation_id,),
                ).fetchone()
                if row is None or not self._has_verified_vector_witness(row):
                    raise ValueError(
                        f"generation {generation_id!r} has no verified vector parity witness"
                    )
            self._activate_generation(conn, generation_id)

    @staticmethod
    def _has_verified_vector_witness(row: Any) -> bool:
        return bool(
            str(row["vector_backend"] or "")
            and str(row["vector_backend_identity"] or "")
            and str(row["vector_parity_schema"] or "") == "vector-parity-v1"
            and str(row["vector_parity_digest"] or "")
            and str(row["vector_parity_verified_at"] or "")
            and row["vector_parity_count"] is not None
            and int(row["vector_parity_count"]) >= 0
            and str(row["vector_parity_backend_identity"] or "")
            == str(row["vector_backend_identity"] or "")
            and str(row["vector_parity_collection"] or "")
            == str(row["vector_collection"] or "")
        )

    def record_vector_parity_witness(
        self, generation_id: str, *, digest: str, count: int,
        backend: str, backend_identity: str, collection: str,
    ) -> None:
        if not digest or count < 0 or not backend_identity or not collection:
            raise ValueError("a complete vector parity witness is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status, vector_collection FROM index_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            if row is None or row["status"] not in {"building", "ready"}:
                raise ValueError("vector parity can only be recorded for a candidate")
            if str(row["vector_collection"] or "") != collection:
                raise ValueError("vector parity collection does not match candidate")
            conn.execute(
                """UPDATE index_generations
                   SET vector_backend = ?, vector_backend_identity = ?,
                       vector_parity_schema = 'vector-parity-v1',
                       vector_parity_digest = ?, vector_parity_verified_at = ?,
                       vector_parity_count = ?, vector_parity_backend_identity = ?,
                       vector_parity_collection = ?
                   WHERE generation_id = ?""",
                (backend, backend_identity, digest,
                 datetime.now(timezone.utc).isoformat(timespec="seconds"), count,
                 backend_identity, collection, generation_id),
            )

    def generation_info(self, generation_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            target = generation_id or self._active_generation_id(conn)
            if not target:
                return None
            row = conn.execute(
                "SELECT * FROM index_generations WHERE generation_id = ?", (target,)
            ).fetchone()
            return dict(row) if row else None

    def superseded_generation_candidates(self, *, retain: int = 1) -> list[dict[str, Any]]:
        """List old immutable generations eligible for bounded retention cleanup."""
        if retain < 0:
            raise ValueError("retain must be non-negative")
        with self._connect() as conn:
            rows = list(conn.execute(
                """
                SELECT generation_id, vector_collection, vector_backend,
                       vector_backend_identity, activated_at, created_at
                FROM index_generations
                WHERE status = 'superseded'
                ORDER BY COALESCE(activated_at, created_at) DESC, generation_id DESC
                """
            ))
        return [dict(row) for row in rows[retain:]]

    def delete_superseded_generations(self, generation_ids: Iterable[str]) -> int:
        """Delete only generations that remain superseded at cleanup time."""
        requested = tuple(dict.fromkeys(str(value) for value in generation_ids if str(value)))
        if not requested:
            return 0
        deleted = 0
        with self._connect() as conn:
            for generation_id in requested:
                row = conn.execute(
                    "SELECT status FROM index_generations WHERE generation_id = ?",
                    (generation_id,),
                ).fetchone()
                if row is None or str(row["status"]) != "superseded":
                    continue
                child_ids = [
                    int(item["id"])
                    for item in conn.execute(
                        "SELECT id FROM retrieval_children WHERE generation_id = ?",
                        (generation_id,),
                    )
                ]
                for child_id in child_ids:
                    conn.execute(
                        "DELETE FROM retrieval_children_fts WHERE rowid = ?", (child_id,)
                    )
                conn.execute(
                    "DELETE FROM generation_vector_upserts WHERE generation_id = ?",
                    (generation_id,),
                )
                conn.execute(
                    "DELETE FROM retrieval_children WHERE generation_id = ?",
                    (generation_id,),
                )
                conn.execute(
                    "DELETE FROM retrieval_parents WHERE generation_id = ?",
                    (generation_id,),
                )
                conn.execute(
                    "DELETE FROM generation_sources WHERE generation_id = ?",
                    (generation_id,),
                )
                deleted += conn.execute(
                    "DELETE FROM index_generations WHERE generation_id = ? AND status = 'superseded'",
                    (generation_id,),
                ).rowcount
        return deleted

    def discard_candidate_generation(self, generation_id: str) -> bool:
        """Remove an unpublished candidate after its external collection is cleaned."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM index_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            if row is None or row["status"] not in {"building", "ready"}:
                return False
            child_ids = [int(row["id"]) for row in conn.execute(
                "SELECT id FROM retrieval_children WHERE generation_id = ?", (generation_id,)
            )]
            for child_id in child_ids:
                conn.execute("DELETE FROM retrieval_children_fts WHERE rowid = ?", (child_id,))
            for table in (
                "generation_vector_upserts", "retrieval_children",
                "retrieval_parents", "generation_sources",
            ):
                conn.execute(f"DELETE FROM {table} WHERE generation_id = ?", (generation_id,))
            return bool(conn.execute(
                "DELETE FROM index_generations WHERE generation_id = ?", (generation_id,)
            ).rowcount)
