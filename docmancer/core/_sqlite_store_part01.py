"""SQLiteStore implementation shard 1."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStorePart01:
    def __init__(self, db_path: str | Path, extracted_dir: str | Path | None = None):
        self.db_path = Path(db_path).expanduser()
        self.extracted_dir = Path(extracted_dir).expanduser() if extracted_dir else self.db_path.parent / "extracted"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts5_check USING fts5(value)")
                conn.execute("DROP TABLE IF EXISTS fts5_check")
            except sqlite3.OperationalError as exc:
                raise RuntimeError(
                    "SQLite FTS5 is required but is not available in this Python build. "
                    "Install a Python distribution compiled with SQLite FTS5."
                ) from exc

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL UNIQUE,
                    docset_root TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    markdown_path TEXT NOT NULL DEFAULT '',
                    json_path TEXT NOT NULL DEFAULT '',
                    raw_tokens INTEGER NOT NULL DEFAULT 0,
                    ingested_at TEXT NOT NULL,
                    content_hash TEXT,
                    index_schema_version TEXT
                );

                CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    source_path TEXT,
                    document_title TEXT,
                    format TEXT,
                    anchor TEXT,
                    content_hash TEXT,
                    stable_chunk_id TEXT,
                    parent_logical_id TEXT,
                    retrieval_text TEXT,
                    retrieval_content_hash TEXT,
                    char_start INTEGER,
                    char_end INTEGER,
                    byte_start INTEGER,
                    byte_end INTEGER,
                    line_start INTEGER,
                    line_end INTEGER,
                    chunk_schema_version TEXT,
                    chunk_config_hash TEXT,
                    token_estimator_version TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS parent_sections (
                    logical_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    heading_path_json TEXT NOT NULL,
                    heading_levels_json TEXT NOT NULL,
                    occurrence INTEGER NOT NULL,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    byte_start INTEGER NOT NULL,
                    byte_end INTEGER NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    display_text TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    config_hash TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
                    title,
                    text,
                    source,
                    content='sections',
                    content_rowid='id'
                );

                CREATE TABLE IF NOT EXISTS index_generations (
                    generation_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    context_schema_version TEXT NOT NULL DEFAULT '',
                    context_config_hash TEXT NOT NULL DEFAULT '',
                    retrieval_config_hash TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    vector_collection TEXT NOT NULL,
                    vector_backend TEXT NOT NULL DEFAULT '',
                    vector_backend_identity TEXT NOT NULL DEFAULT '',
                    vector_parity_schema TEXT NOT NULL DEFAULT '',
                    vector_parity_digest TEXT NOT NULL DEFAULT '',
                    vector_parity_verified_at TEXT,
                    vector_parity_count INTEGER,
                    vector_parity_backend_identity TEXT NOT NULL DEFAULT '',
                    vector_parity_collection TEXT NOT NULL DEFAULT '',
                    validation_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS index_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    active_generation_id TEXT
                );
                INSERT OR IGNORE INTO index_state(singleton, active_generation_id)
                VALUES (1, NULL);

                CREATE TABLE IF NOT EXISTS generation_sources (
                    generation_id TEXT NOT NULL REFERENCES index_generations(generation_id),
                    source TEXT NOT NULL,
                    source_identity TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    raw_tokens INTEGER NOT NULL,
                    PRIMARY KEY (generation_id, source)
                );

                CREATE TABLE IF NOT EXISTS retrieval_parents (
                    generation_id TEXT NOT NULL REFERENCES index_generations(generation_id),
                    logical_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_identity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    heading_path_json TEXT NOT NULL,
                    heading_levels_json TEXT NOT NULL,
                    occurrence INTEGER NOT NULL,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    byte_start INTEGER NOT NULL,
                    byte_end INTEGER NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    display_text TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL,
                    PRIMARY KEY (generation_id, logical_id)
                );

                CREATE TABLE IF NOT EXISTS retrieval_children (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hydration_id INTEGER NOT NULL,
                    generation_id TEXT NOT NULL REFERENCES index_generations(generation_id),
                    stable_chunk_id TEXT NOT NULL,
                    vector_id TEXT NOT NULL,
                    parent_logical_id TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_identity TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    parent_ordinal INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    atom_type TEXT NOT NULL,
                    atom_id TEXT NOT NULL,
                    display_text TEXT NOT NULL,
                    retrieval_text TEXT NOT NULL,
                    display_content_hash TEXT NOT NULL,
                    retrieval_content_hash TEXT NOT NULL,
                    display_token_estimate INTEGER NOT NULL,
                    retrieval_token_estimate INTEGER NOT NULL,
                    context_prefix TEXT NOT NULL DEFAULT '',
                    context_manifest_json TEXT NOT NULL DEFAULT '{}',
                    context_schema_version TEXT NOT NULL DEFAULT '',
                    context_config_hash TEXT NOT NULL DEFAULT '',
                    context_content_hash TEXT NOT NULL DEFAULT '',
                    embedding_input_hash TEXT NOT NULL DEFAULT '',
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    byte_start INTEGER NOT NULL,
                    byte_end INTEGER NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    source_path TEXT,
                    document_title TEXT,
                    format TEXT,
                    anchor TEXT,
                    library_id TEXT,
                    resolved_version TEXT,
                    version_family TEXT,
                    project_identity TEXT,
                    project_path TEXT,
                    module_id TEXT,
                    doc_scope TEXT,
                    source_class TEXT,
                    authority TEXT,
                    lifecycle_status TEXT,
                    temporal_relevance TEXT,
                    index_freshness TEXT,
                    docs_snapshot_exact INTEGER,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (generation_id, stable_chunk_id),
                    UNIQUE (generation_id, vector_id),
                    UNIQUE (generation_id, hydration_id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_children_fts USING fts5(
                    title,
                    retrieval_text,
                    source,
                    content='retrieval_children',
                    content_rowid='id'
                );

                """
            )
            conn.executescript(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_stable_chunk_id
                    ON sections(stable_chunk_id) WHERE stable_chunk_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_sections_parent_logical_id
                    ON sections(parent_logical_id, chunk_index);
                CREATE INDEX IF NOT EXISTS idx_parent_sections_source_id
                    ON parent_sections(source_id);
                CREATE INDEX IF NOT EXISTS idx_retrieval_parents_source
                    ON retrieval_parents(generation_id, source_id);
                CREATE INDEX IF NOT EXISTS idx_generation_sources_identity
                    ON generation_sources(generation_id, source_identity);
                CREATE INDEX IF NOT EXISTS idx_retrieval_children_parent
                    ON retrieval_children(generation_id, parent_logical_id, chunk_index);
                CREATE INDEX IF NOT EXISTS idx_retrieval_children_source
                    ON retrieval_children(generation_id, source_id, chunk_index);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_children_hydration
                    ON retrieval_children(generation_id, hydration_id);
                CREATE INDEX IF NOT EXISTS idx_retrieval_children_filters
                    ON retrieval_children(
                        generation_id, project_identity, library_id,
                        resolved_version, version_family, source_class, authority,
                        lifecycle_status, temporal_relevance, index_freshness
                    );
                CREATE INDEX IF NOT EXISTS idx_retrieval_children_project_scope
                    ON retrieval_children(generation_id, module_id, doc_scope);
                """
            )
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS embedding_upserts (
                    chunk_id INTEGER NOT NULL,
                    qdrant_collection TEXT NOT NULL,
                    content_hash TEXT,
                    embedding_hash TEXT,
                    upserted_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ok',
                    stable_chunk_id TEXT,
                    PRIMARY KEY (chunk_id, qdrant_collection)
                );
                CREATE INDEX IF NOT EXISTS idx_embedding_upserts_collection
                    ON embedding_upserts(qdrant_collection);
                CREATE TABLE IF NOT EXISTS generation_vector_upserts (
                    stable_chunk_id TEXT NOT NULL,
                    qdrant_collection TEXT NOT NULL,
                    vector_id TEXT NOT NULL,
                    retrieval_content_hash TEXT NOT NULL,
                    embedding_hash TEXT NOT NULL,
                    generation_id TEXT NOT NULL,
                    upserted_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ok',
                    PRIMARY KEY (stable_chunk_id, qdrant_collection)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_vector_id
                    ON generation_vector_upserts(qdrant_collection, vector_id);
                """
            )

    def add_documents(
        self,
        documents: Iterable[Document],
        recreate: bool = False,
        *,
        activate_generation: bool = True,
    ) -> IndexResult:
        normalized = [self._current_schema_document(doc) for doc in documents]
        docs_by_source: dict[str, Document] = {}
        for doc in normalized:
            existing = docs_by_source.get(doc.source)
            if existing is None:
                docs_by_source[doc.source] = doc
                continue
            docs_by_source[doc.source] = Document(
                source=doc.source,
                content=f"{existing.content.rstrip()}\n\n{doc.content.lstrip()}",
                metadata={**existing.metadata, **doc.metadata},
            )
        docs = list(docs_by_source.values())
        staged: list[_StagedExtraction] = []
        try:
            for doc in docs:
                staged.append(self._stage_extraction(doc))
        except Exception:
            self._discard_staged_extractions(staged)
            raise
        conn = self._connect()
        try:
            if recreate:
                conn.execute("DELETE FROM sections_fts")
                conn.execute("DELETE FROM sections")
                conn.execute("DELETE FROM parent_sections")
                conn.execute("DELETE FROM sources")

            section_count = 0
            for doc in docs:
                section_count += self._add_document(conn, doc)
            generation_id = None
            if docs:
                generation_id = self._build_candidate_generation(
                    conn,
                    docs,
                    recreate=recreate,
                )
                if activate_generation:
                    self._activate_generation(conn, generation_id)
            elif recreate:
                self._deactivate_active_generation(conn)
            result = IndexResult(
                sources=len(docs),
                sections=section_count,
                generation_id=generation_id,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            self._discard_staged_extractions(staged)
            raise
        finally:
            conn.close()
        self._publish_staged_extractions(staged)
        return result

    @staticmethod
    def _current_schema_document(doc: Document) -> Document:
        metadata = dict(doc.metadata or {})
        schema = str(metadata.get("chunking_schema") or PARENT_CHILD_SCHEMA_VERSION)
        if schema != PARENT_CHILD_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported chunking schema {schema!r}; "
                f"expected {PARENT_CHILD_SCHEMA_VERSION!r}"
            )
        metadata["chunking_schema"] = PARENT_CHILD_SCHEMA_VERSION
        metadata.setdefault("child_target_tokens", 160)
        metadata.setdefault("child_hard_max_tokens", 512)
        return Document(source=doc.source, content=doc.content, metadata=metadata)

    def add_documents_stream(
        self,
        documents: Iterable[Document],
        *,
        recreate: bool = False,
        batch_size: int = 1000,
        progress_callback=None,
    ) -> IndexResult:
        """Stream-ingest an iterable of documents, committing in batches.

        Use this for atomic-record corpora (USPTO case files, court filings,
        product catalogs) where the iterator would yield millions of records
        and ``list(documents)`` would OOM. Commits every ``batch_size`` rows
        so a killed process loses at most one batch.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        section_count = 0
        source_count = 0
        generation_id = None
        batch: list[Document] = []
        first_batch = True
        for doc in documents:
            batch.append(doc)
            if len(batch) < batch_size:
                continue
            result = self.add_documents(batch, recreate=recreate and first_batch)
            first_batch = False
            source_count += result.sources
            section_count += result.sections
            generation_id = result.generation_id
            batch = []
            if progress_callback is not None:
                progress_callback(source_count, section_count)
        if batch:
            result = self.add_documents(batch, recreate=recreate and first_batch)
            source_count += result.sources
            section_count += result.sections
            generation_id = result.generation_id
        elif first_batch and recreate:
            self.delete_all()
        if progress_callback is not None:
            progress_callback(source_count, section_count)
        return IndexResult(
            sources=source_count,
            sections=section_count,
            generation_id=generation_id,
        )

    def _stage_extraction(self, doc: Document) -> _StagedExtraction:
        metadata = dict(doc.metadata or {})
        source_slug = _slug(doc.source)
        markdown_path = self.extracted_dir / f"{source_slug}.md"
        json_path = self.extracted_dir / f"{source_slug}.json"
        nonce = uuid.uuid4().hex
        markdown_temp = self.extracted_dir / f".{source_slug}.{nonce}.md.tmp"
        json_temp = self.extracted_dir / f".{source_slug}.{nonce}.json.tmp"
        try:
            markdown_temp.write_text(doc.content, encoding="utf-8")
            json_temp.write_text(
                json.dumps(
                    {"source": doc.source, "metadata": metadata, "content": doc.content},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            markdown_temp.unlink(missing_ok=True)
            json_temp.unlink(missing_ok=True)
            raise
        return _StagedExtraction(
            markdown_temp=markdown_temp,
            json_temp=json_temp,
            markdown_path=markdown_path,
            json_path=json_path,
        )

    @staticmethod
    def _discard_staged_extractions(staged: Iterable[_StagedExtraction]) -> None:
        for extraction in staged:
            extraction.markdown_temp.unlink(missing_ok=True)
            extraction.json_temp.unlink(missing_ok=True)

    @staticmethod
    def _publish_staged_extractions(staged: Iterable[_StagedExtraction]) -> None:
        for extraction in staged:
            extraction.markdown_temp.replace(extraction.markdown_path)
            extraction.json_temp.replace(extraction.json_path)

    def _add_document(self, conn: sqlite3.Connection, doc: Document) -> int:
        metadata = dict(doc.metadata or {})
        docset_root = str(metadata.get("docset_root") or "")
        ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        source_slug = _slug(doc.source)
        markdown_path = self.extracted_dir / f"{source_slug}.md"
        json_path = self.extracted_dir / f"{source_slug}.json"
        existing = conn.execute("SELECT id FROM sources WHERE source = ?", (doc.source,)).fetchone()
        if existing:
            source_id = int(existing["id"])
            row_ids = [row["id"] for row in conn.execute("SELECT id FROM sections WHERE source_id = ?", (source_id,))]
            for row_id in row_ids:
                conn.execute("DELETE FROM sections_fts WHERE rowid = ?", (row_id,))
            conn.execute("DELETE FROM sections WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM parent_sections WHERE source_id = ?", (source_id,))
            conn.execute(
                """
                UPDATE sources
                SET docset_root = ?, content = ?, metadata_json = ?, markdown_path = ?,
                    json_path = ?, raw_tokens = ?, ingested_at = ?, content_hash = ?,
                    index_schema_version = ?
                WHERE id = ?
                """,
                (
                    docset_root,
                    doc.content,
                    json.dumps(metadata, ensure_ascii=False),
                    str(markdown_path),
                    str(json_path),
                    estimate_tokens(doc.content),
                    ingested_at,
                    _chunk_hash(doc.content),
                    str(metadata.get("chunking_schema") or INDEX_SCHEMA_VERSION),
                    source_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO sources
                    (source, docset_root, content, metadata_json, markdown_path, json_path, raw_tokens,
                     ingested_at, content_hash, index_schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.source,
                    docset_root,
                    doc.content,
                    json.dumps(metadata, ensure_ascii=False),
                    str(markdown_path),
                    str(json_path),
                    estimate_tokens(doc.content),
                    ingested_at,
                    _chunk_hash(doc.content),
                    str(metadata.get("chunking_schema") or INDEX_SCHEMA_VERSION),
                ),
            )
            source_id = int(cursor.lastrowid)

        section_count = 0
        source_path = str(metadata.get("source_path") or doc.source)
        document_title = str(metadata.get("title") or Path(doc.source).stem or "Document")
        format_name = str(metadata.get("format") or "")
        for chunk_index, (title, level, text, chunk_meta) in enumerate(_sections_for_document(doc)):
            anchor = str(chunk_meta.get("anchor") or title)
            content_hash = _chunk_hash(text)
            section_meta = {
                **metadata,
                "section_title": title,
                "section_level": level,
                "source_path": source_path,
                "document_title": document_title,
                "document_title_hash": hashlib.sha1(
                    (document_title or "").encode("utf-8")
                ).hexdigest()[:16],
                "format": format_name,
                "anchor": anchor,
                "content_hash": content_hash,
            }
            snippets = _code_snippets(text)
            if snippets:
                section_meta["code_snippets"] = snippets
                section_meta["has_code_snippet"] = True
            cursor = conn.execute(
                """
                INSERT INTO sections
                    (source_id, source, chunk_index, title, level, text, token_estimate,
                     source_path, document_title, format, anchor, content_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    doc.source,
                    chunk_index,
                    title,
                    level,
                    text,
                    estimate_tokens(text),
                    source_path,
                    document_title,
                    format_name,
                    anchor,
                    content_hash,
                    json.dumps(section_meta, ensure_ascii=False),
                ),
            )
            row_id = int(cursor.lastrowid)
            search_text = text
            project_doc_description = metadata.get("project_doc_description")
            if isinstance(project_doc_description, str) and project_doc_description.strip():
                # Catalog descriptions are routing metadata only: searchable
                # in FTS, but never injected into the cited section body.
                search_text = f"{text}\n{project_doc_description.strip()}"
            conn.execute(
                "INSERT INTO sections_fts(rowid, title, text, source) VALUES (?, ?, ?, ?)",
                (row_id, title, search_text, doc.source),
            )
            section_count += 1
        return section_count
