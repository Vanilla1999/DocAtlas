from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from docmancer.core.chunking import chunk_paragraphs
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.structured_chunking import (
    SCHEMA_VERSION as PARENT_CHILD_SCHEMA_VERSION,
    ChunkingConfig,
    chunk_markdown_parent_child,
)
from docmancer.docs.domain.quality import looks_like_code_or_command


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)\n(.*?)^ {0,3}\1\s*$", re.MULTILINE | re.DOTALL)

# Keywords that indicate boilerplate/legal content.  Matched against
# normalized title words so numbered headings like "12. Miscellaneous"
# and subsections like "Privacy Policy" are caught.
_BOILERPLATE_KEYWORDS = frozenset({
    "terms", "conditions", "privacy", "policy", "legal", "disclaimer",
    "eula", "license", "agreement", "dmca", "copyright", "sla",
    "miscellaneous", "modifications", "indemnification", "severability",
    "arbitration", "jurisdiction", "governing", "waiver", "warranties",
    "limitation", "liability",
})

# Query stopwords that inflate BM25 scores for legal text without
# carrying search intent.
_QUERY_STOPWORDS = frozenset({
    "how", "do", "i", "a", "an", "the", "to", "is", "it", "in", "on",
    "of", "for", "my", "can", "what", "where", "when", "why", "does",
    "should", "would", "could", "with", "this", "that", "are", "was",
    "be", "have", "has", "will", "we", "you", "your", "me",
})

INDEX_SCHEMA_VERSION = "sqlite-sections-v1"


@dataclass(frozen=True, slots=True)
class RankingCandidate:
    """Auditable lexical candidate with one explicit score direction.

    SQLite FTS5 exposes BM25 as a lower-is-better cost.  DocAtlas converts
    that cost to a higher-is-better utility before applying named features;
    callers never have to infer whether adding a value is a boost or penalty.
    """

    stable_id: str
    section_id: int
    raw_component_ranks: tuple[tuple[str, float], ...]
    base_utility: float
    feature_contributions: tuple[tuple[str, float], ...]
    final_utility: float

    def trace(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "section_id": self.section_id,
            "score_direction": "higher_is_better",
            "raw_component_ranks": {
                name: round(value, 12) for name, value in self.raw_component_ranks
            },
            "base_utility": round(self.base_utility, 12),
            "feature_contributions": {
                name: round(value, 12) for name, value in self.feature_contributions
            },
            "final_utility": round(self.final_utility, 12),
        }


@dataclass(slots=True)
class IndexResult:
    sources: int
    sections: int
    generation_id: str | None = None


@dataclass(frozen=True, slots=True)
class _StagedExtraction:
    markdown_temp: Path
    json_temp: Path
    markdown_path: Path
    json_path: Path


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _slug(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:72] or "source"
    return f"{stem}-{digest}"


def _normalize_source_like(value: str | Path) -> str:
    return str(value).replace("\\", "/").rstrip("/")


def _stable_source_identity(doc: Document) -> str:
    metadata = dict(doc.metadata or {})
    explicit = str(metadata.get("source_identity") or "").strip()
    if explicit:
        return _normalize_source_like(explicit)
    canonical = str(metadata.get("canonical_url") or metadata.get("source_url") or "").strip()
    if canonical:
        return _normalize_source_like(canonical)
    relative = str(
        metadata.get("project_doc_path")
        or metadata.get("source_path")
        or ""
    ).strip()
    namespace = str(
        metadata.get("source_identity_namespace")
        or metadata.get("library_id")
        or metadata.get("source_class")
        or "document"
    ).strip()
    project_identity = str(
        metadata.get("repository_identity")
        or metadata.get("canonical_project_id")
        or metadata.get("project_id")
        or metadata.get("repository_url")
        or ""
    ).strip()
    if project_identity and not metadata.get("source_identity_namespace"):
        namespace = f"{namespace}:{_normalize_source_like(project_identity)}"
    if relative:
        return f"{namespace}:{_normalize_source_like(relative).lstrip('/')}"
    # Direct callers may not have loader metadata. Keep their logical source,
    # but never inject a machine-specific resolved path into the stable ID.
    return _normalize_source_like(doc.source)


def _split_sections(content: str) -> list[tuple[str, int, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        return [("Document", 1, content.strip())] if content.strip() else []

    sections: list[tuple[str, int, str]] = []
    if matches[0].start() > 0:
        intro = content[: matches[0].start()].strip()
        if intro:
            sections.append(("Introduction", 1, intro))

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        level = len(match.group(1))
        title = match.group(2).strip()
        text = content[start:end].strip()
        if text:
            sections.append((title, level, text))
    return sections


def _split_sections_with_anchors(content: str) -> list[tuple[str, int, str, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        stripped = content.strip()
        return [("Document", 1, stripped, "Document")] if stripped else []

    sections: list[tuple[str, int, str, str]] = []
    if matches[0].start() > 0:
        intro = content[: matches[0].start()].strip()
        if intro:
            sections.append(("Introduction", 1, intro, "Introduction"))

    heading_stack: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, title))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        text = content[start:end].strip()
        if text:
            sections.append((title, level, text, " > ".join(item for _, item in heading_stack)))
    return sections


def _sections_for_document(doc: Document) -> list[tuple[str, int, str, dict[str, str]]]:
    metadata = dict(doc.metadata or {})
    strategy = str(metadata.get("chunking_strategy") or "heading")
    chunk_size = int(metadata.get("chunk_size") or 800)
    chunk_overlap = int(metadata.get("chunk_overlap") or 100)

    if strategy == "paragraph":
        title = str(metadata.get("title") or Path(doc.source).stem or "Document")
        chunks = chunk_paragraphs(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        sections: list[tuple[str, int, str, dict[str, str]]] = []
        for index, text in enumerate(chunks):
            page_match = re.search(r"##\s+Page\s+(\d+)", text)
            anchor = f"Page {page_match.group(1)}" if page_match else f"{title} chunk {index + 1}"
            sections.append((title, 1, text, {"anchor": anchor}))
        return sections

    if strategy == "single":
        # Atomic-record sources (e.g. USPTO case files): the whole document is one
        # section. We do not split on headings — heading-aware splitting would
        # otherwise carve each record into two or three sub-sections, which is
        # the wrong shape for "match the mark against every case file".
        title = str(metadata.get("title") or Path(doc.source).stem or "Document")
        anchor = str(metadata.get("anchor") or title)
        text = doc.content.strip()
        if not text:
            return []
        return [(title, 1, text, {"anchor": anchor})]

    return [
        (title, level, text, {"anchor": anchor})
        for title, level, text, anchor in _split_sections_with_anchors(doc.content)
    ]


def document_section_count(doc: Document) -> int:
    """Return the exact number of SQLite sections that ingest will create."""
    return len(_sections_for_document(doc))


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _code_snippets(text: str, *, limit: int = 3, max_chars: int = 1200) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    for match in FENCED_CODE_RE.finditer(text):
        language = match.group(2).strip().split()[0] if match.group(2).strip() else ""
        code = match.group(3).strip()
        if not code:
            continue
        snippets.append({"language": language, "code": code[:max_chars]})
        if len(snippets) >= limit:
            break
    return snippets or _code_like_snippets(text, max_chars=max_chars)


def _code_like_snippets(text: str, *, max_chars: int = 1200) -> list[dict[str, str]]:
    if not looks_like_code_or_command(text):
        return []
    lines = [line.strip() for line in text.splitlines()]
    code_lines: list[str] = []
    for line in lines:
        stripped = line.strip("`").strip()
        if not stripped:
            if code_lines and code_lines[-1] != "":
                code_lines.append("")
            continue
        if _looks_like_code_line(stripped):
            code_lines.append(stripped)
        elif code_lines and code_lines[-1] != "":
            code_lines.append("")

    while code_lines and code_lines[-1] == "":
        code_lines.pop()
    compact = "\n".join(code_lines).strip()
    meaningful = [line for line in code_lines if line]
    if len(meaningful) < 3 or len(compact) < 40:
        return []
    return [{"language": "", "code": compact[:max_chars]}]


def _looks_like_code_line(line: str) -> bool:
    code_tokens = (
        "=>", "{", "}", ";", "(", ")", "=", "<", ">", "//",
        "final ", "class ", "Future", "Provider", "ref.", "return ", "await ", "async",
    )
    if line.startswith(("#", "- ", "* ", "|")):
        return False
    return any(token in line for token in code_tokens)


class SQLiteStore:
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
                    ingested_at TEXT NOT NULL
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
                    status TEXT NOT NULL,
                    vector_collection TEXT NOT NULL,
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
            self._ensure_nullable_column(conn, "sections", "source_path", "TEXT")
            self._ensure_nullable_column(conn, "sections", "document_title", "TEXT")
            self._ensure_nullable_column(conn, "sections", "format", "TEXT")
            self._ensure_nullable_column(conn, "sections", "anchor", "TEXT")
            self._ensure_nullable_column(conn, "sections", "content_hash", "TEXT")
            self._ensure_nullable_column(conn, "sections", "stable_chunk_id", "TEXT")
            self._ensure_nullable_column(conn, "sections", "parent_logical_id", "TEXT")
            self._ensure_nullable_column(conn, "sections", "retrieval_text", "TEXT")
            self._ensure_nullable_column(conn, "sections", "retrieval_content_hash", "TEXT")
            self._ensure_nullable_column(conn, "sections", "char_start", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "char_end", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "byte_start", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "byte_end", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "line_start", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "line_end", "INTEGER")
            self._ensure_nullable_column(conn, "sections", "chunk_schema_version", "TEXT")
            self._ensure_nullable_column(conn, "sections", "chunk_config_hash", "TEXT")
            self._ensure_nullable_column(conn, "sections", "token_estimator_version", "TEXT")
            self._ensure_nullable_column(conn, "sources", "content_hash", "TEXT")
            self._ensure_nullable_column(conn, "sources", "index_schema_version", "TEXT")
            self._ensure_nullable_column(conn, "index_generations", "config_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_nullable_column(conn, "retrieval_children", "hydration_id", "INTEGER")
            conn.execute(
                "UPDATE retrieval_children SET hydration_id = id WHERE hydration_id IS NULL"
            )
            # One-time additive backfill for databases created by early v2
            # builds. New generations always write immutable snapshots before
            # any child row is validated.
            conn.execute(
                """
                INSERT OR IGNORE INTO generation_sources
                    (generation_id, source, source_identity, content,
                     content_hash, metadata_json, raw_tokens)
                SELECT DISTINCT c.generation_id, c.source, c.source_identity,
                       s.content, COALESCE(s.content_hash, ''),
                       s.metadata_json, s.raw_tokens
                FROM retrieval_children c
                JOIN sources s ON s.id = c.source_id
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
            self._ensure_nullable_column(conn, "embedding_upserts", "stable_chunk_id", "TEXT")

    @staticmethod
    def _ensure_nullable_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def add_documents(
        self,
        documents: Iterable[Document],
        recreate: bool = False,
        *,
        activate_generation: bool = True,
    ) -> IndexResult:
        docs = list(documents)
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
            v2_docs = [
                doc for doc in docs
                if str((doc.metadata or {}).get("chunking_schema") or "")
                    == PARENT_CHILD_SCHEMA_VERSION
            ]
            if v2_docs:
                generation_id = self._build_candidate_generation(
                    conn,
                    v2_docs,
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
        section_count = 0
        source_count = 0
        conn = self._connect()
        pending_extractions: list[_StagedExtraction] = []
        try:
            if recreate:
                conn.execute("DELETE FROM sections_fts")
                conn.execute("DELETE FROM sections")
                conn.execute("DELETE FROM parent_sections")
                conn.execute("DELETE FROM sources")
                self._deactivate_active_generation(conn)
            for doc in documents:
                pending_extractions.append(self._stage_extraction(doc))
                section_count += self._add_document(conn, doc)
                source_count += 1
                if source_count % batch_size == 0:
                    conn.commit()
                    self._publish_staged_extractions(pending_extractions)
                    pending_extractions = []
                    if progress_callback is not None:
                        progress_callback(source_count, section_count)
            conn.commit()
            self._publish_staged_extractions(pending_extractions)
            pending_extractions = []
        except Exception:
            conn.rollback()
            self._discard_staged_extractions(pending_extractions)
            raise
        finally:
            conn.close()
        if progress_callback is not None:
            progress_callback(source_count, section_count)
        return IndexResult(sources=source_count, sections=section_count)

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
        generation_id = "gen-" + uuid.uuid4().hex
        active = self._active_generation_id(conn)
        vector_collection = f"docmancer_pc_{config.config_hash[:16]}"
        active_same_config = False
        if active:
            active_info = conn.execute(
                """
                SELECT config_hash, vector_collection FROM index_generations
                WHERE generation_id = ?
                """,
                (active,),
            ).fetchone()
            active_same_config = bool(
                active_info and str(active_info["config_hash"]) == config.config_hash
            )
            if active_same_config:
                vector_collection = str(active_info["vector_collection"])
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO index_generations
                (generation_id, schema_version, config_hash, config_json, status,
                 vector_collection, validation_json, created_at)
            VALUES (?, ?, ?, ?, 'building', ?, '{}', ?)
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
                }, sort_keys=True),
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
                retrieval_hash = _chunk_hash(child.retrieval_text)
                child_metadata = {
                    **metadata,
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
                    "retrieval_token_estimate": child.retrieval_token_estimate,
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
                         char_start, char_end, byte_start, byte_end, line_start,
                         line_end, source_path, document_title, format, anchor,
                         metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generation_id, child.sqlite_id, child.stable_id, child.vector_id,
                        child.parent_logical_id, source_id, doc.source,
                        source_identity, global_index, child.ordinal,
                        parent.title, parent.level, child.atom_type,
                        child.atom_id, child.display_text, child.retrieval_text,
                        display_hash, retrieval_hash, child.token_estimate,
                        child.retrieval_token_estimate, child.char_start,
                        child.char_end, child.byte_start, child.byte_end,
                        child.line_start, child.line_end, source_path,
                        document_title, format_name, anchor,
                        json.dumps(child_metadata, ensure_ascii=False),
                    ),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO retrieval_children_fts(rowid, title, retrieval_text, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (int(child_id), parent.title, child.retrieval_text, doc.source),
                )

        validation = self._validate_generation(conn, generation_id, config)
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
            "char_end", "byte_start", "byte_end", "line_start", "line_end",
            "source_path", "document_title", "format", "anchor", "metadata_json",
        )
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        cursor = conn.execute(
            f"INSERT INTO retrieval_children (generation_id, {', '.join(columns)}) "
            f"VALUES ({placeholders})",
            (generation_id, *(row[column] for column in columns)),
        )
        return int(cursor.lastrowid)

    def _validate_generation(
        self,
        conn: sqlite3.Connection,
        generation_id: str,
        config: ChunkingConfig,
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
        if span_errors or token_errors:
            raise ValueError(
                f"generation validation failed: span_errors={span_errors}, "
                f"retrieval_token_errors={token_errors}"
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

    def activate_generation(self, generation_id: str) -> None:
        with self._connect() as conn:
            self._activate_generation(conn, generation_id)

    def generation_info(self, generation_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            target = generation_id or self._active_generation_id(conn)
            if not target:
                return None
            row = conn.execute(
                "SELECT * FROM index_generations WHERE generation_id = ?", (target,)
            ).fetchone()
            return dict(row) if row else None

    def set_generation_vector_collection(
        self, generation_id: str, collection: str
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", collection):
            raise ValueError(f"invalid generation vector collection: {collection!r}")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM index_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            if row is None or row["status"] not in {"ready", "building"}:
                raise ValueError("only a candidate generation collection can be changed")
            conn.execute(
                "UPDATE index_generations SET vector_collection = ? WHERE generation_id = ?",
                (collection, generation_id),
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
        generation_id = "gen-" + uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO index_generations
                (generation_id, schema_version, config_hash, config_json,
                 status, vector_collection, validation_json, created_at)
            VALUES (?, ?, ?, ?, 'building', ?, '{}', ?)
            """,
            (
                generation_id, previous["schema_version"], previous["config_hash"],
                previous["config_json"], previous["vector_collection"], now,
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
        validation = self._validate_generation(conn, generation_id, config)
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
            for candidate in expanded:
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
        filtered = [t for t in tokens if t.lower() not in _QUERY_STOPWORDS]
        return " ".join(filtered) if filtered else query

    def _search_rows(
        self,
        query: str,
        limit: int,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[sqlite3.Row]:
        cleaned = self._strip_stopwords(query)
        terms = [token for token in re.findall(r"\w+", cleaned) if token]
        filter_sql, filter_params = self._metadata_filter_sql(filters)
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
                            {filter_sql}
                            ORDER BY rank, sections.source, sections.chunk_index
                            LIMIT ?
                            """,
                            (cleaned, active_generation, *filter_params, limit),
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
                        return combined
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
                        {filter_sql}
                        ORDER BY rank, sections.source, sections.chunk_index
                        LIMIT ?
                        """,
                        (fallback_query, active_generation, *filter_params, limit),
                    )
                )
                return sorted(
                    [*child_fallback, *legacy_fallback],
                    key=lambda item: (
                        float(item["rank"]), str(item["source"]),
                        int(item["chunk_index"]),
                    ),
                )[:limit]
            try:
                rows = list(
                    conn.execute(
                        f"""
                        SELECT sections.*, bm25(sections_fts) AS rank
                        FROM sections_fts
                        JOIN sections ON sections.id = sections_fts.rowid
                        WHERE sections_fts MATCH ?
                        {filter_sql}
                        ORDER BY rank, sections.source, sections.chunk_index, sections.content_hash
                        LIMIT ?
                        """,
                        (cleaned, *filter_params, limit),
                    )
                )
                if rows or len(terms) <= 1:
                    return rows
            except sqlite3.OperationalError:
                pass

            fallback_query = " OR ".join(terms)
            if not fallback_query:
                return []
            return list(
                conn.execute(
                    f"""
                    SELECT sections.*, bm25(sections_fts) AS rank
                    FROM sections_fts
                    JOIN sections ON sections.id = sections_fts.rowid
                    WHERE sections_fts MATCH ?
                    {filter_sql}
                    ORDER BY rank, sections.source, sections.chunk_index, sections.content_hash
                    LIMIT ?
                    """,
                    (fallback_query, *filter_params, limit),
                )
            )

    @staticmethod
    def _metadata_filter_sql(filters: dict[str, Any] | None) -> tuple[str, list[Any]]:
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
            if isinstance(value, bool):
                clauses.append("json_extract(sections.metadata_json, ?) = ?")
                params.extend([json_path, 1 if value else 0])
            elif isinstance(value, (list, tuple, set, frozenset)):
                values = list(value)
                if not values:
                    clauses.append("0")
                    continue
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"json_extract(sections.metadata_json, ?) IN ({placeholders})")
                params.append(json_path)
                params.extend(values)
            else:
                clauses.append("json_extract(sections.metadata_json, ?) = ?")
                params.extend([json_path, value])
        if not clauses:
            return "", []
        return "AND " + " AND ".join(f"({clause})" for clause in clauses), params

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
            parent_logical_id = row["parent_logical_id"] if "parent_logical_id" in row.keys() else None
            if parent_logical_id:
                if expand == "page":
                    rows = list(
                        conn.execute(
                            """
                            SELECT * FROM sections
                            WHERE parent_logical_id = ?
                            ORDER BY chunk_index
                            LIMIT 21
                            """,
                            (parent_logical_id,),
                        )
                    )
                    return [item for item in rows if int(item["id"]) == int(row["id"])] + [
                        item for item in rows if int(item["id"]) != int(row["id"])
                    ]
                if expand == "adjacent":
                    siblings = list(
                        conn.execute(
                            """
                            SELECT * FROM sections
                            WHERE parent_logical_id = ? AND chunk_index BETWEEN ? AND ?
                            ORDER BY chunk_index
                            """,
                            (
                                parent_logical_id,
                                max(0, int(row["chunk_index"]) - 1),
                                int(row["chunk_index"]) + 1,
                            ),
                        )
                    )
                    return [item for item in siblings if int(item["id"]) == int(row["id"])] + [
                        item for item in siblings if int(item["id"]) != int(row["id"])
                    ]
            if expand == "page":
                # Find sections that belong to the same logical page as the
                # matching row.  For multi-page docsets the page boundary is
                # the nearest preceding level-1 heading.  For single-page
                # sources (e.g. llms-full.txt) this avoids returning the
                # entire document from chunk_index 0 and instead anchors on
                # the matched section's page neighbourhood.
                anchor_idx = int(row["chunk_index"])
                source_id = row["source_id"]

                # Walk backwards to find the nearest level-1 heading.
                prev_h1 = conn.execute(
                    """
                    SELECT chunk_index FROM sections
                    WHERE source_id = ? AND chunk_index <= ? AND level = 1
                    ORDER BY chunk_index DESC LIMIT 1
                    """,
                    (source_id, anchor_idx),
                ).fetchone()
                page_start = int(prev_h1["chunk_index"]) if prev_h1 else anchor_idx

                # Walk forward to find the next level-1 heading (exclusive).
                next_h1 = conn.execute(
                    """
                    SELECT chunk_index FROM sections
                    WHERE source_id = ? AND chunk_index > ? AND level = 1
                    ORDER BY chunk_index ASC LIMIT 1
                    """,
                    (source_id, anchor_idx),
                ).fetchone()
                page_end = int(next_h1["chunk_index"]) - 1 if next_h1 else anchor_idx + 20

                # Return sections within this page, anchored section first.
                rows = list(
                    conn.execute(
                        """
                        SELECT * FROM sections
                        WHERE source_id = ? AND chunk_index BETWEEN ? AND ?
                        ORDER BY chunk_index
                        """,
                        (source_id, page_start, page_end),
                    )
                )
                # Reorder so the matching section comes first (budget
                # packing keeps early items, so this ensures the actual
                # match is always included).
                anchor_rows = [r for r in rows if int(r["chunk_index"]) == anchor_idx]
                other_rows = [r for r in rows if int(r["chunk_index"]) != anchor_idx]
                return anchor_rows + other_rows

            if expand == "adjacent":
                return list(
                    conn.execute(
                        """
                        SELECT * FROM sections
                        WHERE source_id = ? AND chunk_index BETWEEN ? AND ?
                        ORDER BY chunk_index
                        """,
                        (row["source_id"], max(0, int(row["chunk_index"]) - 1), int(row["chunk_index"]) + 1),
                    )
                )
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

    def collection_stats(self) -> dict:
        with self._connect() as conn:
            sources = conn.execute("SELECT COUNT(*) AS count FROM sources").fetchone()["count"]
            legacy_sections = int(conn.execute(
                "SELECT COUNT(*) AS count FROM sections"
            ).fetchone()["count"])
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
                compatibility = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM sections
                    WHERE source NOT IN (
                        SELECT source FROM retrieval_children WHERE generation_id = ?
                    )
                    """,
                    (active_generation,),
                ).fetchone()["count"])
                sections = children + compatibility
            else:
                children = 0
                parents = 0
                sections = legacy_sections
            format_rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(format, ''), 'unknown') AS format, COUNT(*) AS count
                FROM sections
                GROUP BY COALESCE(NULLIF(format, ''), 'unknown')
                ORDER BY format
                """
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
            "legacy_sections_count": int(legacy_sections),
            "active_generation_id": active_generation,
            "sources_by_format": {str(row["format"]): int(row["count"]) for row in source_format_rows},
            "sections_by_format": {str(row["format"]): int(row["count"]) for row in format_rows},
            "db_path": str(self.db_path),
            "extracted_dir": str(self.extracted_dir),
        }

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
                legacy_count = int(conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM sections
                    WHERE source NOT IN (
                        SELECT source FROM retrieval_children WHERE generation_id = ?
                    )
                    """,
                    (active,),
                ).fetchone()["count"])
                if legacy_count:
                    schemas[INDEX_SCHEMA_VERSION] = legacy_count
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
            else:
                legacy_count = int(conn.execute(
                    "SELECT COUNT(*) AS count FROM sections"
                ).fetchone()["count"])
                if legacy_count:
                    schemas[INDEX_SCHEMA_VERSION] = legacy_count
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
                    for row in conn.execute(
                        """
                        SELECT source, chunk_index, text, retrieval_text,
                               content_hash, retrieval_content_hash
                        FROM sections
                        WHERE source NOT IN (
                            SELECT source FROM generation_sources
                            WHERE generation_id = ?
                        )
                        """,
                        (active,),
                    ):
                        retrieval_text = str(row["retrieval_text"] or row["text"] or "")
                        retrieval_hash = str(
                            row["retrieval_content_hash"]
                            or hashlib.sha256(retrieval_text.encode("utf-8")).hexdigest()
                        )
                        current_stable_ids.add(
                            "legacy-" + hashlib.sha256(
                                f"{row['source']}\0{row['chunk_index']}\0{retrieval_hash}".encode("utf-8")
                            ).hexdigest()[:40]
                        )
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
            if active:
                rows = list(conn.execute(
                    """
                    SELECT hydration_id AS id FROM retrieval_children
                    WHERE generation_id = ? AND source = ?
                    ORDER BY chunk_index
                    """,
                    (active, source),
                ))
                if rows:
                    return [int(row["id"]) for row in rows]
            return [
                int(row["id"])
                for row in conn.execute(
                    "SELECT id FROM sections WHERE source = ? ORDER BY id",
                    (source,),
                )
            ]

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
                           byte_start, byte_end, metadata_json
                    FROM retrieval_children
                    WHERE generation_id = ?
                    ORDER BY source, chunk_index
                    """,
                    (target_generation,),
                )
                info = conn.execute(
                    "SELECT schema_version, config_hash FROM index_generations WHERE generation_id = ?",
                    (target_generation,),
                ).fetchone()
                embedded = [
                    {
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
                    }
                    for row in rows
                ]
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

    def delete_source(self, source: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM sources WHERE source = ?", (source,)).fetchone()
            if not row:
                return False
            source_id = int(row["id"])
            # Active retrieval generations are immutable. Publish a validated
            # clone without this source before removing compatibility rows.
            self._build_generation_without_sources(conn, {source})
            row_ids = [r["id"] for r in conn.execute("SELECT id FROM sections WHERE source_id = ?", (source_id,))]
            for row_id in row_ids:
                conn.execute("DELETE FROM sections_fts WHERE rowid = ?", (row_id,))
            conn.execute("DELETE FROM sections WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM parent_sections WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
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
        artifact_paths: set[Path] = set()
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
            for path_value in (row["markdown_path"], row["json_path"]):
                if path_value:
                    artifact_paths.add(Path(str(path_value)))

        deleted = 0
        for source in sources_to_delete:
            if self.delete_source(source):
                deleted += 1

        for artifact_path in artifact_paths:
            try:
                artifact_path.unlink(missing_ok=True)
            except TypeError:
                if artifact_path.exists():
                    artifact_path.unlink()

        return deleted

    def delete_all(self) -> bool:
        stats = self.collection_stats()
        with self._connect() as conn:
            conn.execute("DELETE FROM sections_fts")
            conn.execute("DELETE FROM sections")
            conn.execute("DELETE FROM sources")
            self._deactivate_active_generation(conn)
        return stats["sources_count"] > 0 or stats["sections_count"] > 0
