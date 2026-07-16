from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from docmancer.core.chunking import chunk_paragraphs
from docmancer.core.models import Document, RetrievedChunk
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


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _slug(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:72] or "source"
    return f"{stem}-{digest}"


def _normalize_source_like(value: str | Path) -> str:
    return str(value).replace("\\", "/").rstrip("/")


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

                CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
                    title,
                    text,
                    source,
                    content='sections',
                    content_rowid='id'
                );

                """
            )
            self._ensure_nullable_column(conn, "sections", "source_path", "TEXT")
            self._ensure_nullable_column(conn, "sections", "document_title", "TEXT")
            self._ensure_nullable_column(conn, "sections", "format", "TEXT")
            self._ensure_nullable_column(conn, "sections", "anchor", "TEXT")
            self._ensure_nullable_column(conn, "sections", "content_hash", "TEXT")
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
                """
            )

    @staticmethod
    def _ensure_nullable_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def add_documents(self, documents: Iterable[Document], recreate: bool = False) -> IndexResult:
        docs = list(documents)
        with self._connect() as conn:
            if recreate:
                conn.execute("DELETE FROM sections_fts")
                conn.execute("DELETE FROM sections")
                conn.execute("DELETE FROM sources")

            section_count = 0
            for doc in docs:
                section_count += self._add_document(conn, doc)
            return IndexResult(sources=len(docs), sections=section_count)

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
        try:
            if recreate:
                conn.execute("DELETE FROM sections_fts")
                conn.execute("DELETE FROM sections")
                conn.execute("DELETE FROM sources")
                conn.commit()
            for doc in documents:
                section_count += self._add_document(conn, doc)
                source_count += 1
                if source_count % batch_size == 0:
                    conn.commit()
                    if progress_callback is not None:
                        progress_callback(source_count, section_count)
            conn.commit()
        finally:
            conn.close()
        if progress_callback is not None:
            progress_callback(source_count, section_count)
        return IndexResult(sources=source_count, sections=section_count)

    def _add_document(self, conn: sqlite3.Connection, doc: Document) -> int:
        metadata = dict(doc.metadata or {})
        docset_root = str(metadata.get("docset_root") or "")
        ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        source_slug = _slug(doc.source)
        markdown_path = self.extracted_dir / f"{source_slug}.md"
        json_path = self.extracted_dir / f"{source_slug}.json"
        markdown_path.write_text(doc.content, encoding="utf-8")
        json_path.write_text(
            json.dumps(
                {"source": doc.source, "metadata": metadata, "content": doc.content},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        existing = conn.execute("SELECT id FROM sources WHERE source = ?", (doc.source,)).fetchone()
        if existing:
            source_id = int(existing["id"])
            row_ids = [row["id"] for row in conn.execute("SELECT id FROM sections WHERE source_id = ?", (source_id,))]
            for row_id in row_ids:
                conn.execute("DELETE FROM sections_fts WHERE rowid = ?", (row_id,))
            conn.execute("DELETE FROM sections WHERE source_id = ?", (source_id,))
            conn.execute(
                """
                UPDATE sources
                SET docset_root = ?, content = ?, metadata_json = ?, markdown_path = ?,
                    json_path = ?, raw_tokens = ?, ingested_at = ?
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
                    source_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO sources
                    (source, docset_root, content, metadata_json, markdown_path, json_path, raw_tokens, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        stable_id = "lex-" + hashlib.sha256(
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
            rows = {
                int(row["id"]): row
                for row in conn.execute(
                    f"""
                    SELECT s.id, s.source, s.chunk_index, s.title, s.text,
                           s.token_estimate, s.metadata_json
                    FROM sections s
                    WHERE s.id IN ({placeholders})
                    """,
                    section_ids,
                )
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
            row = conn.execute(
                f"SELECT COALESCE(SUM(raw_tokens), 0) AS total FROM sources WHERE source IN ({placeholders})",
                unique_sources,
            ).fetchone()
            return int(row["total"] or 0)

    def collection_stats(self) -> dict:
        with self._connect() as conn:
            sources = conn.execute("SELECT COUNT(*) AS count FROM sources").fetchone()["count"]
            sections = conn.execute("SELECT COUNT(*) AS count FROM sections").fetchone()["count"]
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
            "sources_by_format": {str(row["format"]): int(row["count"]) for row in source_format_rows},
            "sections_by_format": {str(row["format"]): int(row["count"]) for row in format_rows},
            "db_path": str(self.db_path),
            "extracted_dir": str(self.extracted_dir),
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
                SELECT chunk_id, content_hash, embedding_hash, upserted_at, status
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
                }
                for row in rows
            }

    def section_ids_for_source(self, source: str) -> list[int]:
        """Return stable chunk ids before a source is removed."""
        with self._connect() as conn:
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
                    (chunk_id, qdrant_collection, content_hash, embedding_hash, upserted_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, qdrant_collection) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    embedding_hash = excluded.embedding_hash,
                    upserted_at = excluded.upserted_at,
                    status = excluded.status
                """,
                [
                    (
                        int(r["chunk_id"]),
                        collection,
                        r.get("content_hash") or "",
                        r.get("embedding_hash") or "",
                        now,
                        r.get("status") or "ok",
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
            row = conn.execute(
                "SELECT source, chunk_index FROM sections WHERE id = ?",
                (int(section_id),),
            ).fetchone()
            if not row:
                return []
            source = row["source"]
            chunk_index = int(row["chunk_index"])
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
            for row in conn.execute(
                f"SELECT id, metadata_json FROM sections WHERE id IN ({placeholders})",
                section_ids,
            ):
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

    def list_sections_for_embedding(self) -> list[dict]:
        """Return canonical section chunks for embedding-based consumers.

        Emits the same chunks the FTS index stores, so future embedding
        features can reuse identical section boundaries. Each row has:
        section_id (int), source, chunk_index, title, level, text, and
        token_estimate.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source, chunk_index, title, level, text, token_estimate,
                       source_path, document_title, format, anchor, content_hash
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
                    "text": str(row["text"] or ""),
                    "token_estimate": int(row["token_estimate"] or 0),
                    "source_path": str(row["source_path"] or ""),
                    "document_title": str(row["document_title"] or ""),
                    "format": str(row["format"] or ""),
                    "anchor": str(row["anchor"] or ""),
                    "content_hash": str(row["content_hash"] or ""),
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
            row_ids = [r["id"] for r in conn.execute("SELECT id FROM sections WHERE source_id = ?", (source_id,))]
            for row_id in row_ids:
                conn.execute("DELETE FROM sections_fts WHERE rowid = ?", (row_id,))
            conn.execute("DELETE FROM sections WHERE source_id = ?", (source_id,))
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
        return stats["sources_count"] > 0 or stats["sections_count"] > 0
