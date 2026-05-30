from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from docmancer.docs.resolver import canonical_library_id, legacy_library_id, normalize_library_name, normalize_lookup_key, normalize_version


@dataclass(frozen=True)
class LibraryRecord:
    library_id: str
    name: str
    normalized_name: str
    ecosystem: str | None
    version: str | None
    source_type: str | None
    docs_url: str | None
    docs_url_template: str | None
    aliases: list[str]
    status: str | None
    added_at: str
    last_checked_at: str | None
    last_refreshed_at: str | None
    last_error: str | None
    target_spec: dict | None = None


class LibraryRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doc_libraries (
                    library_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    ecosystem TEXT,
                    version TEXT,
                    source_type TEXT,
                    docs_url TEXT,
                    docs_url_template TEXT,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT,
                    added_at TEXT NOT NULL,
                    last_checked_at TEXT,
                    last_refreshed_at TEXT,
                    last_error TEXT,
                    target_spec_json TEXT
                )
                """
            )
            self._ensure_column(conn, "doc_libraries", "version", "TEXT")
            self._ensure_column(conn, "doc_libraries", "source_type", "TEXT")
            self._ensure_column(conn, "doc_libraries", "docs_url_template", "TEXT")
            self._ensure_column(conn, "doc_libraries", "target_spec_json", "TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_doc_libraries_normalized "
                "ON doc_libraries(normalized_name, ecosystem, version, source_type)"
            )

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> LibraryRecord:
        return LibraryRecord(
            library_id=row["library_id"],
            name=row["name"],
            normalized_name=row["normalized_name"],
            ecosystem=row["ecosystem"],
            version=row["version"],
            source_type=row["source_type"] or "api",
            docs_url=row["docs_url"],
            docs_url_template=row["docs_url_template"],
            aliases=json.loads(row["aliases_json"] or "[]"),
            status=row["status"],
            added_at=row["added_at"],
            last_checked_at=row["last_checked_at"],
            last_refreshed_at=row["last_refreshed_at"],
            last_error=row["last_error"],
            target_spec=json.loads(row["target_spec_json"] or "null"),
        )

    def get(
        self,
        library: str,
        ecosystem: str | None = None,
        version: str | None = None,
        source_type: str | None = None,
    ) -> LibraryRecord | None:
        normalized = normalize_library_name(library)
        lookup_key = normalize_lookup_key(library)
        normalized_version = normalize_version(version)
        normalized_source_type = normalize_library_name(source_type or "api")
        library_id = canonical_library_id(library, ecosystem, normalized_version, normalized_source_type)
        legacy_id = legacy_library_id(library, normalized_version)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM doc_libraries WHERE library_id = ?",
                (library,),
            ).fetchone()
            if row:
                return self._row_to_record(row)
            row = conn.execute(
                "SELECT * FROM doc_libraries WHERE library_id = ?",
                (library_id,),
            ).fetchone()
            if row:
                return self._row_to_record(row)
            row = conn.execute(
                "SELECT * FROM doc_libraries WHERE library_id = ?",
                (legacy_id,),
            ).fetchone()
            if row:
                return self._row_to_record(row)

            if normalized_version:
                if ecosystem:
                    row = conn.execute(
                        """
                        SELECT * FROM doc_libraries
                        WHERE normalized_name = ? AND ecosystem = ? AND version = ? AND COALESCE(source_type, 'api') = ?
                        """,
                        (normalized, ecosystem, normalized_version, normalized_source_type),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM doc_libraries WHERE normalized_name = ? AND version = ? AND COALESCE(source_type, 'api') = ?",
                        (normalized, normalized_version, normalized_source_type),
                    ).fetchone()
                if row:
                    return self._row_to_record(row)
                for row in conn.execute(
                    "SELECT * FROM doc_libraries WHERE version = ? AND COALESCE(source_type, 'api') = ?",
                    (normalized_version, normalized_source_type),
                ):
                    if normalize_lookup_key(row["normalized_name"]) == lookup_key:
                        return self._row_to_record(row)
                return None

            if ecosystem:
                row = conn.execute(
                    """
                    SELECT * FROM doc_libraries
                    WHERE normalized_name = ? AND ecosystem = ? AND version IS NULL AND COALESCE(source_type, 'api') = ?
                    """,
                    (normalized, ecosystem, normalized_source_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM doc_libraries WHERE normalized_name = ? AND version IS NULL AND COALESCE(source_type, 'api') = ?",
                    (normalized, normalized_source_type),
                ).fetchone()
            if row:
                return self._row_to_record(row)

            row = conn.execute(
                """
                SELECT * FROM doc_libraries
                WHERE normalized_name = ? AND version = 'latest' AND COALESCE(source_type, 'api') = ?
                ORDER BY ecosystem IS NULL
                LIMIT 1
                """,
                (normalized, normalized_source_type),
            ).fetchone()
            if row:
                return self._row_to_record(row)

            for row in conn.execute("SELECT * FROM doc_libraries"):
                if row["version"] is None and normalize_lookup_key(row["normalized_name"]) == lookup_key:
                    return self._row_to_record(row)
                aliases = json.loads(row["aliases_json"] or "[]")
                if lookup_key in {normalize_lookup_key(alias) for alias in aliases}:
                    return self._row_to_record(row)
        return None

    def upsert(
        self,
        *,
        library: str,
        ecosystem: str | None,
        docs_url: str | None,
        now: str,
        version: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        last_refreshed_at: str | None = None,
        last_error: str | None = None,
        target_spec: dict | None = None,
    ) -> LibraryRecord:
        normalized_version = normalize_version(version)
        normalized_source_type = normalize_library_name(source_type or "api")
        existing = self.get(library, ecosystem, normalized_version, normalized_source_type)
        canonical_id = canonical_library_id(library, ecosystem, normalized_version, normalized_source_type)
        if existing and existing.library_id != canonical_id and existing.ecosystem == ecosystem:
            existing = self.migrate_library_id(existing.library_id, canonical_id)
        library_id = existing.library_id if existing else canonical_id
        normalized = existing.normalized_name if existing else normalize_library_name(library)
        name = existing.name if existing else library
        final_docs_url = docs_url if docs_url is not None else (existing.docs_url if existing else None)
        final_template = (
            docs_url_template
            if docs_url_template is not None
            else (existing.docs_url_template if existing else None)
        )
        final_source_type = normalized_source_type if not existing else (existing.source_type or normalized_source_type)
        final_status = status if status is not None else (existing.status if existing else None)
        final_refreshed = (
            last_refreshed_at if last_refreshed_at is not None else (existing.last_refreshed_at if existing else None)
        )
        final_error = last_error if last_error is not None else (existing.last_error if existing else None)
        final_target_spec = target_spec if target_spec is not None else (existing.target_spec if existing else None)
        aliases = existing.aliases if existing else []
        added_at = existing.added_at if existing else now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO doc_libraries (
                    library_id, name, normalized_name, ecosystem, version, source_type, docs_url, docs_url_template, aliases_json,
                    status, added_at, last_checked_at, last_refreshed_at, last_error, target_spec_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_id) DO UPDATE SET
                    name = excluded.name,
                    normalized_name = excluded.normalized_name,
                    ecosystem = excluded.ecosystem,
                    version = excluded.version,
                    source_type = excluded.source_type,
                    docs_url = excluded.docs_url,
                    docs_url_template = excluded.docs_url_template,
                    aliases_json = excluded.aliases_json,
                    status = excluded.status,
                    last_checked_at = excluded.last_checked_at,
                    last_refreshed_at = excluded.last_refreshed_at,
                    last_error = excluded.last_error,
                    target_spec_json = excluded.target_spec_json
                """,
                (
                    library_id,
                    name,
                    normalized,
                    ecosystem,
                    normalized_version,
                    final_source_type,
                    final_docs_url,
                    final_template,
                    json.dumps(aliases),
                    final_status,
                    added_at,
                    now,
                    final_refreshed,
                    final_error,
                    json.dumps(final_target_spec) if final_target_spec is not None else None,
                ),
            )
        record = self.get(library_id, None)
        if record is None:
            raise RuntimeError("failed to store library metadata")
        return record



    def migrate_library_id(self, old_library_id: str, new_library_id: str) -> LibraryRecord | None:
        if old_library_id == new_library_id:
            return self.get(old_library_id)
        with self._connect() as conn:
            existing_new = conn.execute(
                "SELECT * FROM doc_libraries WHERE library_id = ?",
                (new_library_id,),
            ).fetchone()
            if existing_new:
                conn.execute("DELETE FROM doc_libraries WHERE library_id = ?", (old_library_id,))
                return self._row_to_record(existing_new)
            conn.execute(
                "UPDATE doc_libraries SET library_id = ? WHERE library_id = ?",
                (new_library_id, old_library_id),
            )
        return self.get(new_library_id)

    def delete(self, library_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM doc_libraries WHERE library_id = ?", (library_id,))
            return cursor.rowcount > 0

    def list(self, limit: int | None = None) -> list[LibraryRecord]:
        sql = "SELECT * FROM doc_libraries ORDER BY name"
        args: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        with self._connect() as conn:
            return [self._row_to_record(row) for row in conn.execute(sql, args)]
