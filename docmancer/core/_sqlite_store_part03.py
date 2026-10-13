"""SQLiteStore implementation shard 3."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStorePart03:
    def set_generation_vector_collection(
        self, generation_id: str, collection: str
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", collection):
            raise ValueError(f"invalid generation vector collection: {collection!r}")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status, vector_backend FROM index_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            mutable_candidate = bool(
                row is not None
                and (
                    row["status"] in {"ready", "building"}
                    or (row["status"] == "active" and not str(row["vector_backend"] or ""))
                )
            )
            if not mutable_candidate:
                raise ValueError("only a candidate generation collection can be changed")
            conn.execute(
                "UPDATE index_generations SET vector_collection = ? WHERE generation_id = ?",
                (collection, generation_id),
            )

    def set_generation_vector_backend(
        self, generation_id: str, backend: str, backend_identity: str = ""
    ) -> None:
        """Bind a generation to the backend that actually received its vectors."""
        normalized = str(backend or "").strip().lower()
        if normalized not in {"qdrant", "sqlite-vec"}:
            raise ValueError(f"invalid generation vector backend: {backend!r}")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM index_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            if row is None or row["status"] not in {"building", "ready", "active"}:
                raise ValueError("vector backend can only be bound to a usable generation")
            conn.execute(
                "UPDATE index_generations SET vector_backend = ?, vector_backend_identity = ? WHERE generation_id = ?",
                (normalized, str(backend_identity or ""), generation_id),
            )

    @staticmethod
    def _chunking_config_from_generation(row: sqlite3.Row) -> ChunkingConfig:
        try:
            payload = json.loads(row["config_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        return ChunkingConfig(
            target_tokens=int(payload.get("target_tokens") or 160),
            hard_max_tokens=int(payload.get("hard_max_tokens") or 512),
            overlap_tokens=int(payload.get("overlap_tokens") or 0),
            schema_version=str(row["schema_version"]),
            estimator_version=str(payload.get("estimator_version") or "utf8-bytes-div4-v1"),
        )

    def _build_generation_without_sources(
        self,
        conn: sqlite3.Connection,
        excluded_sources: set[str],
    ) -> str | None:
        """Clone the active immutable generation minus deleted sources."""
        active = self._active_generation_id(conn)
        if not active or not excluded_sources:
            return None
        placeholders = ",".join("?" for _ in excluded_sources)
        present = int(conn.execute(
            f"""
            SELECT COUNT(*) AS count FROM generation_sources
            WHERE generation_id = ? AND source IN ({placeholders})
            """,
            (active, *sorted(excluded_sources)),
        ).fetchone()["count"])
        if not present:
            return None
        previous = conn.execute(
            "SELECT * FROM index_generations WHERE generation_id = ?", (active,)
        ).fetchone()
        if previous is None:
            raise ValueError(f"active generation {active!r} is missing")
        if not str(previous["context_config_hash"] or "") or not str(
            previous["retrieval_config_hash"] or ""
        ):
            raise ValueError("active generation does not satisfy the current context schema")
        generation_id = "gen-" + uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO index_generations
                (generation_id, schema_version, config_hash, config_json,
                 context_schema_version, context_config_hash,
                 retrieval_config_hash, status, vector_collection,
                  vector_backend, vector_backend_identity,
                  vector_parity_schema, vector_parity_digest,
                  vector_parity_verified_at, vector_parity_count,
                  vector_parity_backend_identity, vector_parity_collection,
                  validation_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'building', ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)
            """,
            (
                generation_id, previous["schema_version"], previous["config_hash"],
                previous["config_json"], previous["context_schema_version"],
                previous["context_config_hash"], previous["retrieval_config_hash"],
                previous["vector_collection"], previous["vector_backend"],
                previous["vector_backend_identity"], previous["vector_parity_schema"],
                previous["vector_parity_digest"], previous["vector_parity_verified_at"],
                previous["vector_parity_count"], previous["vector_parity_backend_identity"],
                previous["vector_parity_collection"], now,
            ),
        )
        exclusion = f"AND source NOT IN ({placeholders})"
        params: tuple[Any, ...] = (
            generation_id, active, *sorted(excluded_sources)
        )
        conn.execute(
            f"""
            INSERT INTO generation_sources
                (generation_id, source, source_identity, content, content_hash,
                 metadata_json, raw_tokens)
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
        rows = conn.execute(
            f"""
            SELECT * FROM retrieval_children
            WHERE generation_id = ? {exclusion}
            ORDER BY id
            """,
            (active, *sorted(excluded_sources)),
        ).fetchall()
        for row in rows:
            child_id = self._insert_retrieval_child_copy(conn, generation_id, row)
            conn.execute(
                """
                INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source)
                VALUES (?, ?, ?, ?)
                """,
                (child_id, row["title"], row["retrieval_text"], row["source"]),
            )
        config = self._chunking_config_from_generation(previous)
        validation = self._validate_generation(
            conn, generation_id, config, ContextConfig()
        )
        conn.execute(
            """
            UPDATE index_generations
            SET status = 'ready', validation_json = ?
            WHERE generation_id = ?
            """,
            (json.dumps(validation, sort_keys=True), generation_id),
        )
        self._activate_generation(conn, generation_id)
        return generation_id

    def query(
        self,
        text: str,
        *,
        limit: int,
        budget: int,
        expand: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        return self._query_bm25_candidates(text, limit=limit, budget=budget, filters=filters)

    def _query_bm25_candidates(
        self, text: str, *, limit: int, budget: int,
        filters: dict[str, Any] | None,
    ) -> list[RetrievedChunk]:
        """Acquire bounded native children independently of the delivery budget."""
        from docmancer.retrieval.experimental_acquisition import (
            ACQUISITION_CANDIDATES, ACQUISITION_ESTIMATED_TOKENS,
            ACQUISITION_METHOD, ACQUISITION_TEXT_BYTES,
        )

        rows = self._search_rows(text, ACQUISITION_CANDIDATES, filters=filters)
        selected: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        token_total = byte_total = skipped = 0
        for raw_rank, row in enumerate(rows, start=1):
            row_id = int(row["id"])
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            tokens = max(0, int(row["token_estimate"]))
            text_bytes = len(str(row["text"]).encode("utf-8"))
            if (
                token_total + tokens > ACQUISITION_ESTIMATED_TOKENS
                or byte_total + text_bytes > ACQUISITION_TEXT_BYTES
            ):
                skipped += 1
                continue
            selected.append({**row, "_bm25_rank": raw_rank})
            token_total += tokens
            byte_total += text_bytes

        raw_tokens = self._raw_token_total([row["source"] for row in selected])
        savings = 0.0 if raw_tokens <= 0 else max(0.0, 100.0 * (1 - token_total / raw_tokens))
        runway = 1.0 if token_total <= 0 else raw_tokens / token_total
        acquisition = {
            "method": ACQUISITION_METHOD,
            "sql_rows": len(rows),
            "candidate_ceiling": ACQUISITION_CANDIDATES,
            "estimated_token_ceiling": ACQUISITION_ESTIMATED_TOKENS,
            "text_byte_ceiling": ACQUISITION_TEXT_BYTES,
            "admitted_rows": len(selected),
            "admitted_estimated_tokens": token_total,
            "admitted_text_bytes": byte_total,
            "resource_skipped_rows": skipped,
            "delivery_limit_not_applied": limit,
            "delivery_budget_not_applied": budget,
        }
        results: list[RetrievedChunk] = []
        for row in selected:
            cost = float(row["rank"])
            rank = int(row["_bm25_rank"])
            metadata = json.loads(row["metadata_json"] or "{}")
            metadata.update({
                "title": row["title"], "section_id": int(row["id"]),
                "token_estimate": int(row["token_estimate"]),
                "docmancer_tokens": token_total, "raw_tokens": raw_tokens,
                "savings_percent": round(savings, 1),
                "runway_multiplier": round(runway, 2),
                "acquisition": dict(acquisition),
                "ranking": {
                    "stable_id": self._lexical_row_identity(row),
                    "section_id": int(row["id"]),
                    "score_direction": "higher_is_better",
                    "raw_component_ranks": {"fts5_bm25_cost": cost},
                    "base_utility": -cost, "feature_contributions": {},
                    "final_utility": -cost, "raw_rank": rank,
                    "final_rank": rank, "rank_delta": 0,
                    "candidate_pool_size": len(rows), "method": ACQUISITION_METHOD,
                },
                "lexical_match": self._lexical_match_trace(
                    text, title=str(row["title"]), body=str(row["text"]),
                    retrieval_text=str(row.get("retrieval_text") or ""),
                    mode="or", bm25_cost=cost,
                ),
            })
            results.append(RetrievedChunk(
                source=row["source"], chunk_index=int(row["chunk_index"]),
                text=row["text"], score=-cost, metadata=metadata,
            ))
        return results

    @classmethod
    def _lexical_match_trace(
        cls, query: str, *, title: str, body: str, retrieval_text: str = "",
        mode: str, bm25_cost: float,
    ) -> dict[str, Any]:
        raw_terms = tuple(
            token for token in re.findall(r"\w+", cls._strip_stopwords(query))
            if token
        )
        terms = tuple(dict.fromkeys(token.casefold() for token in raw_terms))
        exact_terms = tuple(dict.fromkeys(
            token.casefold()
            for token in re.findall(r"[\w~./:+-]+", query)
            if is_exact_technical_token(token)
        ))
        fields = {
            "title": title.casefold(),
            "body": body.casefold(),
            "retrieval_text": retrieval_text.casefold(),
        }
        haystack = (retrieval_text or f"{title}\n{body}").casefold()
        matched = tuple(term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack))
        missing_exact = tuple(
            term for term in exact_terms
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack) is None
        )
        ratio = len(matched) / len(terms) if terms else 0.0
        field_matches = {
            field: [
                term for term in terms
                if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", value)
            ]
            for field, value in fields.items()
        }
        return {
            "mode": mode,
            "query_terms": list(terms),
            "matched_terms": list(matched),
            "exact_terms": list(exact_terms),
            "missing_exact_terms": list(missing_exact),
            "query_term_count": len(terms),
            "matched_term_count": len(matched),
            "match_ratio": round(ratio, 4),
            "bm25_cost": bm25_cost,
            "lexical_score": -bm25_cost,
            "field_matches": field_matches,
        }

    @classmethod
    def _ranking_candidate(
        cls,
        row: dict[str, Any],
        query: str,
        content_terms: set[str],
    ) -> RankingCandidate:
        bm25_cost = float(row["rank"])
        title_words = set(re.findall(r"\w+", str(row["title"]).lower()))
        body_lower = str(row["text"]).lower()
        contributions: list[tuple[str, float]] = []

        tokens = int(row["token_estimate"])
        if tokens > 600:
            contributions.append(("long_section_penalty", -0.3 * (tokens - 600) / 600))

        title_term_overlap = title_words & content_terms
        if title_term_overlap:
            contributions.append(("title_term_boost", 1.5 * len(title_term_overlap)))

        stripped_query = cls._strip_stopwords(query).lower()
        # Preserve the complete relation (including negation) across inline
        # Markdown emphasis. Matching is source-local and cannot cross sentence
        # or paragraph boundaries; no text or qualification flags are rewritten.
        phrase_tokens = query.casefold().split()
        inline_phrase = r"(?<!\w)" + r"[ \t*_`~]+".join(
            re.escape(token) for token in phrase_tokens
        ) + r"(?!\w)"
        if (stripped_query and stripped_query in body_lower[:500]) or (
            len(phrase_tokens) > 1 and re.search(inline_phrase, body_lower[:500])
        ):
            contributions.append(("leading_exact_phrase_boost", 2.0))

        metadata = json.loads(str(row.get("metadata_json") or "{}"))
        authority = str(metadata.get("authority") or "").casefold()
        if authority in {"generated", "mirror", "stale"}:
            contributions.append((f"{authority}_authority_penalty", -3.0))
        elif authority == "external_generic":
            contributions.append(("external_generic_authority_penalty", -1.5))
        source = str(row["source"])
        chunk_index = int(row["chunk_index"])
        content_hash = str(row.get("content_hash") or _chunk_hash(str(row["text"])))
        stable_id = str(row.get("stable_chunk_id") or "") or "lex-" + hashlib.sha256(
            f"{source}\0{chunk_index}\0{content_hash}".encode("utf-8")
        ).hexdigest()[:20]
        base_utility = -bm25_cost
        return RankingCandidate(
            stable_id=stable_id,
            section_id=int(row["id"]),
            raw_component_ranks=(("fts5_bm25_cost", bm25_cost),),
            base_utility=base_utility,
            feature_contributions=tuple(contributions),
            final_utility=base_utility + sum(value for _, value in contributions),
        )

    def fetch_sections_by_id(
        self,
        section_ids: list[int],
        *,
        budget: int = 2400,
    ) -> list[RetrievedChunk]:
        """Hydrate ``RetrievedChunk`` objects from raw section ids, preserving order."""
        if not section_ids:
            return []
        placeholders = ",".join("?" * len(section_ids))
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if not active_generation:
                return []
            query = f"""
                SELECT c.hydration_id AS id, c.source, c.chunk_index, c.title,
                       c.display_text AS text,
                       c.display_token_estimate AS token_estimate,
                       c.metadata_json
                FROM retrieval_children c
                WHERE c.generation_id = ? AND c.hydration_id IN ({placeholders})
            """
            values: tuple[Any, ...] = (active_generation, *section_ids)
            rows = {
                int(row["id"]): row
                for row in conn.execute(query, values)
            }
        selected_rows: list[tuple[int, sqlite3.Row]] = []
        used_tokens = 0
        for rank, sid in enumerate(section_ids):
            row = rows.get(int(sid))
            if row is None:
                continue
            tok = int(row["token_estimate"] or 0)
            if used_tokens and used_tokens + tok > budget:
                break
            used_tokens += tok
            selected_rows.append((rank, row))

        # Compute pack-level token metrics so the hybrid dispatcher returns
        # the same shape as the lexical path. Without these, the CLI prints
        # "~0 tokens" / "~0 raw tokens" because nothing else sets them.
        raw_tokens = self._raw_token_total([row["source"] for _, row in selected_rows])
        token_total = used_tokens
        savings = 0.0 if raw_tokens <= 0 else max(0.0, 100.0 * (1 - (token_total / raw_tokens)))
        runway = 1.0 if token_total <= 0 else raw_tokens / token_total

        results: list[RetrievedChunk] = []
        for rank, row in selected_rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            metadata.setdefault("title", row["title"])
            metadata.setdefault("section_id", int(row["id"]))
            metadata["token_estimate"] = int(row["token_estimate"] or 0)
            metadata["docmancer_tokens"] = token_total
            metadata["raw_tokens"] = raw_tokens
            metadata["savings_percent"] = round(savings, 1)
            metadata["runway_multiplier"] = round(runway, 2)
            score = max(0.0, 1.0 - (rank * 0.05))
            results.append(
                RetrievedChunk(
                    source=row["source"],
                    chunk_index=int(row["chunk_index"]),
                    text=row["text"],
                    score=score,
                    metadata=metadata,
                )
            )
        return results

    @staticmethod
    def _strip_stopwords(query: str) -> str:
        """Tokenize FTS input without a natural-language omission dictionary."""
        return " ".join(re.findall(r"\w+", query)) or query

    def _search_rows(
        self,
        query: str,
        limit: int,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cleaned = self._strip_stopwords(query)
        terms = [token for token in re.findall(r"\w+", cleaned) if token]
        # These are literal query words, never an FTS expression. Quote every
        # token so uppercase AND/OR/NOT remain data in both backend lanes.
        literal_terms = [f'"{token}"' for token in terms]
        filter_sql, filter_params = self._metadata_filter_sql(filters, promoted=True)
        from docmancer.retrieval.experimental_acquisition import (
            ACQUISITION_CANDIDATES,
        )

        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if not active_generation:
                return []
            if not literal_terms:
                return []
            rows = list(conn.execute(
                f"""
                SELECT sections.hydration_id AS id, sections.*,
                       sections.display_text AS text,
                       sections.display_token_estimate AS token_estimate,
                       sections.display_content_hash AS content_hash,
                       bm25(retrieval_children_fts) AS rank
                FROM retrieval_children_fts
                JOIN retrieval_children AS sections
                  ON sections.id = retrieval_children_fts.rowid
                WHERE retrieval_children_fts MATCH ?
                  AND sections.generation_id = ?
                {filter_sql}
                ORDER BY rank, sections.source, sections.chunk_index,
                         sections.stable_chunk_id
                LIMIT ?
                """,
                (" OR ".join(literal_terms), active_generation, *filter_params,
                 min(limit, ACQUISITION_CANDIDATES)),
            ))
            return self._mark_lexical_mode(rows, "or")

    @staticmethod
    def _mark_lexical_mode(rows: list[Any], mode: str) -> list[dict[str, Any]]:
        return [{**dict(row), "_lexical_query_mode": mode} for row in rows]

    @staticmethod
    def _lexical_row_identity(row: dict[str, Any]) -> str:
        stable_id = str(row.get("stable_chunk_id") or "")
        if stable_id:
            return stable_id
        return "lex-" + hashlib.sha256(
            f"{row['source']}\0{row['chunk_index']}\0{row.get('content_hash') or _chunk_hash(str(row['text']))}".encode(
                "utf-8"
            )
        ).hexdigest()[:20]

    @staticmethod
    def _metadata_filter_sql(
        filters: dict[str, Any] | None,
        *,
        promoted: bool = False,
    ) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if value is None:
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
                raise ValueError(f"Unsupported metadata filter key: {key!r}")
            json_path = f"$.{key}"
            column = str(key) if promoted and key in {
                "library_id", "resolved_version", "version_family", "project_identity",
                "project_path", "module_id", "doc_scope", "source_class", "authority",
                "lifecycle_status", "temporal_relevance", "index_freshness",
                "docs_snapshot_exact", "source", "source_identity",
            } else None
            expression = f"sections.{column}" if column else "json_extract(sections.metadata_json, ?)"
            if not column:
                params.append(json_path)
            if isinstance(value, bool):
                clauses.append(f"{expression} = ?")
                params.append(1 if value else 0)
            elif isinstance(value, dict) and "in" in value:
                values = list(value["in"])
                if not values:
                    clauses.append("0")
                    continue
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"{expression} IN ({placeholders})")
                params.extend(values)
            elif isinstance(value, (list, tuple, set, frozenset)):
                values = list(value)
                if not values:
                    clauses.append("0")
                    continue
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"{expression} IN ({placeholders})")
                params.extend(values)
            else:
                clauses.append(f"{expression} = ?")
                params.append(value)
        if not clauses:
            return "", []
        return "AND " + " AND ".join(f"({clause})" for clause in clauses), params
