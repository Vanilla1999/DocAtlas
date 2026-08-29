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
            # A pre-contextual Task 40 generation has additive columns filled
            # with empty defaults. Cloning it would validate those legacy rows
            # against the Task 41 context contract and fail delete-only updates.
            config = self._chunking_config_from_generation(previous)
            remaining: list[Document] = []
            for row in conn.execute(
                f"""
                SELECT source, content, metadata_json
                FROM generation_sources
                WHERE generation_id = ? AND source NOT IN ({placeholders})
                ORDER BY source
                """,
                (active, *sorted(excluded_sources)),
            ):
                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                metadata.update({
                    "chunking_schema": config.schema_version,
                    "child_target_tokens": config.target_tokens,
                    "child_hard_max_tokens": config.hard_max_tokens,
                })
                remaining.append(Document(
                    source=str(row["source"]),
                    content=str(row["content"]),
                    metadata=metadata,
                ))
            if remaining:
                generation_id = self._build_candidate_generation(
                    conn, remaining, recreate=True
                )
                self._activate_generation(conn, generation_id)
                return generation_id
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
        expand_mode = expand or "none"
        # The FTS scoring window is internal; the returned candidate lane is
        # still capped by the dispatcher. Keeping the wider scoring window is
        # required for authority/diversity reranking to displace contamination.
        rows = [dict(r) for r in self._search_rows(text, max(limit * 4, limit), filters=filters)]
        content_terms = set(re.findall(r"\w+", self._strip_stopwords(text).lower()))
        ranked = [(self._ranking_candidate(row, text, content_terms), row) for row in rows]
        raw_order = {
            candidate.stable_id: index
            for index, (candidate, _) in enumerate(
                sorted(
                    ranked,
                    key=lambda item: (
                        dict(item[0].raw_component_ranks)["fts5_bm25_cost"],
                        item[0].stable_id,
                    ),
                ),
                start=1,
            )
        }
        ranked.sort(key=lambda item: (-item[0].final_utility, item[0].stable_id))
        for final_rank, (candidate, row) in enumerate(ranked, start=1):
            trace = candidate.trace()
            trace.update(
                {
                    "raw_rank": raw_order[candidate.stable_id],
                    "final_rank": final_rank,
                    "rank_delta": raw_order[candidate.stable_id] - final_rank,
                    "candidate_pool_size": len(ranked),
                }
            )
            row["_ranking_trace"] = trace
        rows = [row for _, row in ranked]
        selected: list[dict] = []
        used_ids: set[int] = set()
        seen_content: set[str] = set()
        token_total = 0

        for row in rows:
            expanded = self._expand_row(row, expand_mode)
            for raw_candidate in expanded:
                candidate = dict(raw_candidate)
                candidate.setdefault("rank", row["rank"])
                candidate.setdefault("_lexical_query_mode", row.get("_lexical_query_mode", "and"))
                candidate.setdefault("_ranking_trace", row.get("_ranking_trace"))
                row_id = int(candidate["id"])
                if row_id in used_ids:
                    continue
                # Dedupe sections with identical content (common in
                # aggregated sources like llms-full.txt where the same
                # heading/text can appear in multiple pages).
                content_key = hashlib.sha1(
                    (candidate["title"] + "\n" + candidate["text"]).encode()
                ).hexdigest()
                if content_key in seen_content:
                    used_ids.add(row_id)
                    continue
                tokens = int(candidate["token_estimate"])
                if selected and token_total + tokens > budget:
                    continue
                selected.append(candidate)
                used_ids.add(row_id)
                seen_content.add(content_key)
                token_total += tokens
                if len(selected) >= limit:
                    break
            if len(selected) >= limit or token_total >= budget:
                break

        raw_tokens = self._raw_token_total([row["source"] for row in selected])
        savings = 0.0 if raw_tokens <= 0 else max(0.0, 100.0 * (1 - (token_total / raw_tokens)))
        runway = 1.0 if token_total <= 0 else raw_tokens / token_total
        results: list[RetrievedChunk] = []
        for index, row in enumerate(selected):
            metadata = json.loads(row["metadata_json"] or "{}")
            metadata.update(
                {
                    "title": row["title"],
                    "section_id": int(row["id"]),
                    "token_estimate": int(row["token_estimate"]),
                    "docmancer_tokens": token_total,
                    "raw_tokens": raw_tokens,
                    "savings_percent": round(savings, 1),
                    "runway_multiplier": round(runway, 2),
                }
            )
            if isinstance(row, dict) and isinstance(row.get("_ranking_trace"), dict):
                metadata["ranking"] = dict(row["_ranking_trace"])
            metadata["lexical_match"] = self._lexical_match_trace(
                text,
                title=str(row["title"]),
                body=str(row["text"]),
                mode=str(row.get("_lexical_query_mode") or "and"),
                bm25_cost=float(row["rank"]),
            )
            # FTS5 bm25 is lower-is-better. Present a positive rank-like score.
            score = max(0.0, 1.0 - (index * 0.05))
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

    @classmethod
    def _lexical_match_trace(
        cls, query: str, *, title: str, body: str, mode: str, bm25_cost: float,
    ) -> dict[str, Any]:
        raw_terms = tuple(
            token for token in re.findall(r"[\w./:+-]+", cls._strip_stopwords(query))
            if token
        )
        terms = tuple(dict.fromkeys(token.casefold() for token in raw_terms))
        exact_terms = tuple(dict.fromkeys(
            token.casefold()
            for token in raw_terms
            if token.casefold() not in _GENERIC_QUERY_TERMS
            and (
                any(char in token for char in "._/:+-")
                or any(char.isupper() for char in token[1:])
                or (token[:1].isupper() and len(token) > 2)
            )
        ))
        haystack = f"{title}\n{body}".casefold()
        matched = tuple(term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack))
        missing_exact = tuple(term for term in exact_terms if term not in matched)
        ratio = len(matched) / len(terms) if terms else 0.0
        required_ratio = 1.0 if len(terms) == 1 else 0.5
        qualified = bool(matched) and (
            mode == "and"
            or (ratio >= required_ratio and not missing_exact)
        )
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
            "qualified": qualified,
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

        boilerplate_overlap = title_words & _BOILERPLATE_KEYWORDS
        if boilerplate_overlap:
            contributions.append(
                ("boilerplate_title_penalty", -3.0 * len(boilerplate_overlap))
            )

        title_term_overlap = title_words & content_terms
        if title_term_overlap:
            contributions.append(("title_term_boost", 1.5 * len(title_term_overlap)))

        stripped_query = cls._strip_stopwords(query).lower()
        if stripped_query and stripped_query in body_lower[:500]:
            contributions.append(("leading_exact_phrase_boost", 2.0))

        task_signals = {
            "how", "create", "setup", "set", "configure", "install", "add",
            "build", "deploy", "start", "connect", "enable", "generate", "register",
        }
        action_verbs = {
            "create", "set", "setup", "configure", "install", "add", "build",
            "deploy", "start", "connect", "enable", "initialize", "register",
            "sign", "generate", "getting", "started",
        }
        if content_terms & task_signals and title_words & action_verbs:
            contributions.append(("task_action_title_boost", 1.5))

        metadata = json.loads(str(row.get("metadata_json") or "{}"))
        authority = str(metadata.get("authority") or "").casefold()
        legal_intent = bool(content_terms & _BOILERPLATE_KEYWORDS)
        if authority == "legal" and not legal_intent:
            contributions.append(("non_legal_query_legal_source_penalty", -4.0))
        elif authority in {"generated", "mirror", "stale"}:
            contributions.append((f"{authority}_authority_penalty", -3.0))
        elif authority == "external_generic":
            contributions.append(("external_generic_authority_penalty", -1.5))
        project_signals = {"project", "repository", "repo", "docatlas", "rule", "policy"}
        if authority == "project_rule" and content_terms & project_signals:
            contributions.append(("project_rule_authority_boost", 2.0))

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
            if active_generation:
                query = f"""
                    SELECT s.id, s.source, s.chunk_index, s.title, s.text,
                           s.token_estimate, s.metadata_json
                    FROM sections s
                    WHERE s.id IN ({placeholders})
                      AND s.source NOT IN (
                          SELECT source FROM generation_sources
                          WHERE generation_id = ?
                      )
                    UNION ALL
                    SELECT c.hydration_id AS id, c.source, c.chunk_index, c.title,
                           c.display_text AS text,
                           c.display_token_estimate AS token_estimate,
                           c.metadata_json
                    FROM retrieval_children c
                    WHERE c.generation_id = ? AND c.hydration_id IN ({placeholders})
                """
                values: tuple[Any, ...] = (
                    *section_ids, active_generation, active_generation, *section_ids
                )
            else:
                query = f"""
                    SELECT s.id, s.source, s.chunk_index, s.title, s.text,
                           s.token_estimate, s.metadata_json
                    FROM sections s
                    WHERE s.id IN ({placeholders})
                """
                values = tuple(section_ids)
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
        """Remove common stopwords to reduce noise in BM25 scoring."""
        tokens = re.findall(r"\w+", query)
        answer_format_request = any(token.casefold() in {"ответь", "укажи"} for token in tokens)
        filtered = [
            token for token in tokens
            if token.casefold() not in _QUERY_STOPWORDS
            and not (answer_format_request and token.casefold() in {"evidence", "id", "ids"})
        ]
        return " ".join(filtered) if filtered else query

    def _search_rows(
        self,
        query: str,
        limit: int,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cleaned = self._strip_stopwords(query)
        terms = [token for token in re.findall(r"\w+", cleaned) if token]
        filter_sql, filter_params = self._metadata_filter_sql(filters, promoted=True)
        legacy_filter_sql, legacy_filter_params = self._metadata_filter_sql(filters)
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if active_generation:
                try:
                    rows = list(
                        conn.execute(
                            f"""
                            SELECT sections.hydration_id AS id, sections.*,
                                   sections.display_text AS text,
                                   sections.display_token_estimate AS token_estimate,
                                   sections.display_content_hash AS content_hash,
                                   bm25(retrieval_children_fts, 6.0, 2.0, 0.5) AS rank
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
                            (cleaned, active_generation, *filter_params, limit),
                        )
                    )
                    legacy_rows = list(
                        conn.execute(
                            f"""
                            SELECT sections.*, bm25(sections_fts) AS rank
                            FROM sections_fts
                            JOIN sections ON sections.id = sections_fts.rowid
                            WHERE sections_fts MATCH ?
                              AND sections.source NOT IN (
                                  SELECT source FROM retrieval_children
                                  WHERE generation_id = ?
                              )
                            {legacy_filter_sql}
                            ORDER BY rank, sections.source, sections.chunk_index
                            LIMIT ?
                            """,
                            (cleaned, active_generation, *legacy_filter_params, limit),
                        )
                    )
                    combined = sorted(
                        [*rows, *legacy_rows],
                        key=lambda item: (
                            float(item["rank"]), str(item["source"]),
                            int(item["chunk_index"]),
                        ),
                    )[:limit]
                    if combined or len(terms) <= 1:
                        return self._mark_lexical_mode(combined, "and")
                except sqlite3.OperationalError:
                    pass
                fallback_query = " OR ".join(terms)
                if not fallback_query:
                    return []
                child_fallback = list(
                    conn.execute(
                        f"""
                        SELECT sections.hydration_id AS id, sections.*,
                               sections.display_text AS text,
                               sections.display_token_estimate AS token_estimate,
                               sections.display_content_hash AS content_hash,
                               bm25(retrieval_children_fts, 6.0, 2.0, 0.5) AS rank
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
                        (fallback_query, active_generation, *filter_params, limit),
                    )
                )
                legacy_fallback = list(
                    conn.execute(
                        f"""
                        SELECT sections.*, bm25(sections_fts) AS rank
                        FROM sections_fts
                        JOIN sections ON sections.id = sections_fts.rowid
                        WHERE sections_fts MATCH ?
                          AND sections.source NOT IN (
                              SELECT source FROM retrieval_children
                              WHERE generation_id = ?
                          )
                        {legacy_filter_sql}
                        ORDER BY rank, sections.source, sections.chunk_index
                        LIMIT ?
                        """,
                        (fallback_query, active_generation, *legacy_filter_params, limit),
                    )
                )
                return self._mark_lexical_mode(sorted(
                    [*child_fallback, *legacy_fallback],
                    key=lambda item: (
                        float(item["rank"]), str(item["source"]),
                        int(item["chunk_index"]),
                    ),
                )[:limit], "or_fallback")
            try:
                rows = list(
                    conn.execute(
                        f"""
                        SELECT sections.*, bm25(sections_fts) AS rank
                        FROM sections_fts
                        JOIN sections ON sections.id = sections_fts.rowid
                        WHERE sections_fts MATCH ?
                        {legacy_filter_sql}
                        ORDER BY rank, sections.source, sections.chunk_index, sections.content_hash
                        LIMIT ?
                        """,
                        (cleaned, *legacy_filter_params, limit),
                    )
                )
                if rows or len(terms) <= 1:
                    return self._mark_lexical_mode(rows, "and")
            except sqlite3.OperationalError:
                pass

            fallback_query = " OR ".join(terms)
            if not fallback_query:
                return []
            return self._mark_lexical_mode(list(
                conn.execute(
                    f"""
                    SELECT sections.*, bm25(sections_fts) AS rank
                    FROM sections_fts
                    JOIN sections ON sections.id = sections_fts.rowid
                    WHERE sections_fts MATCH ?
                    {legacy_filter_sql}
                    ORDER BY rank, sections.source, sections.chunk_index, sections.content_hash
                    LIMIT ?
                    """,
                    (fallback_query, *legacy_filter_params, limit),
                )
            ), "or_fallback")

    @staticmethod
    def _mark_lexical_mode(rows: list[Any], mode: str) -> list[dict[str, Any]]:
        return [{**dict(row), "_lexical_query_mode": mode} for row in rows]

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
