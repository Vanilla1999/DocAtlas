from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any

from docmancer.core.config import DocmancerConfig
from docmancer.docs.section_metadata import (
    SECTION_METADATA_SCHEMA_VERSION,
    SECTION_PARSE_REASON_CODES,
    SECTION_PARSE_STATUSES,
)


_MAX_INDEXED_DOCS = 500
_MAX_HASH_BYTES = 16 * 1024 * 1024
_MAX_SECTIONS = 256
_MAX_REFERENCES = 64
_MAX_METADATA_JSON_BYTES = 2 * 1024 * 1024
_MAX_SOURCE_PATH_CHARACTERS = 4096
_MAX_HEADING_CHARACTERS = 512
_MAX_REFERENCE_CHARACTERS = 4096
_MAX_SYMBOL_CHARACTERS = 512


class ProjectSectionIndexReader:
    """Read stored project section metadata without invoking retrieval/vector layers."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DocmancerConfig().index.db_path).expanduser()

    def read(self, project_path: str | Path) -> dict[str, dict[str, Any]]:
        root = Path(project_path).expanduser().resolve()
        if not self.db_path.is_file():
            return {}
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT metadata_json, ingested_at
                FROM sources
                WHERE json_extract(metadata_json, '$.project_path') = ?
                  AND json_extract(metadata_json, '$.source_class') = 'project_file'
                  AND json_extract(metadata_json, '$.project_docs') = 1
                  AND length(CAST(metadata_json AS BLOB)) <= ?
                ORDER BY source
                LIMIT ?
                """,
                (str(root), _MAX_METADATA_JSON_BYTES, _MAX_INDEXED_DOCS),
            ).fetchall()
        except (sqlite3.DatabaseError, OSError):
            return {}
        finally:
            if "conn" in locals():
                conn.close()

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(metadata, dict):
                continue
            relative = str(metadata.get("project_doc_path") or "").replace("\\", "/").strip("/")
            current_path = _safe_project_file(root, relative)
            if current_path is None:
                continue
            indexed_hash = str(metadata.get("project_doc_content_hash") or "")
            current_hash = _file_hash(current_path)
            schema = metadata.get("project_doc_sections_schema")
            sections = _validated_sections(metadata.get("project_doc_sections"), source_document_path=relative)
            parse_status = metadata.get("project_doc_sections_status")
            parse_reason = metadata.get("project_doc_sections_reason")
            schema_current = schema == SECTION_METADATA_SCHEMA_VERSION
            hash_current = bool(indexed_hash and current_hash and indexed_hash == current_hash)
            sections_current = (
                sections is not None
                and parse_status in SECTION_PARSE_STATUSES
                and parse_reason == SECTION_PARSE_REASON_CODES[parse_status]
            )
            result[relative] = {
                "path": relative,
                "status": "current" if schema_current and hash_current and sections_current else "stale",
                "indexed_content_hash": indexed_hash or None,
                "current_content_hash": current_hash,
                "schema_version": schema,
                "expected_schema_version": SECTION_METADATA_SCHEMA_VERSION,
                "sections": sections or [],
                "parse_status": parse_status if parse_status in SECTION_PARSE_STATUSES else None,
                "parse_reason": parse_reason if isinstance(parse_reason, str) else None,
                "ingested_at": row["ingested_at"],
                "reason_code": (
                    "indexed_section_metadata_current"
                    if schema_current and hash_current and sections_current
                    else "indexed_section_schema_stale" if not schema_current
                    else "indexed_document_hash_stale" if not hash_current
                    else "indexed_sections_invalid"
                ),
            }
        return result


def _safe_project_file(root: Path, relative: str) -> Path | None:
    if not relative:
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or (pure.parts and pure.parts[0].endswith(":")):
        return None
    try:
        resolved = (root / Path(*pure.parts)).resolve()
        resolved.relative_to(root)
        stat = resolved.stat()
    except (OSError, ValueError):
        return None
    if not resolved.is_file() or stat.st_size > _MAX_HASH_BYTES:
        return None
    return resolved


def _validated_sections(value: object, *, source_document_path: str) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) > _MAX_SECTIONS:
        return None
    validated: list[dict[str, Any]] = []
    for section in value:
        if not isinstance(section, dict):
            return None
        heading = section.get("heading_path")
        paths = section.get("mentioned_paths")
        symbols = section.get("mentioned_symbols")
        content_hash = section.get("content_hash")
        source = section.get("source_document_path")
        paths_truncated = section.get("paths_truncated")
        symbols_truncated = section.get("symbols_truncated")
        fields_truncated = section.get("fields_truncated")
        document_sections_truncated = section.get("document_sections_truncated")
        if (
            source != source_document_path
            or len(source_document_path) > _MAX_SOURCE_PATH_CHARACTERS
            or not isinstance(heading, list)
            or len(heading) > 6
            or not all(isinstance(item, str) for item in heading)
            or any(len(item) > _MAX_HEADING_CHARACTERS for item in heading)
            or not isinstance(paths, list)
            or len(paths) > _MAX_REFERENCES
            or not all(isinstance(item, str) for item in paths)
            or any(len(item) > _MAX_REFERENCE_CHARACTERS for item in paths)
            or not isinstance(symbols, list)
            or len(symbols) > _MAX_REFERENCES
            or not all(isinstance(item, str) for item in symbols)
            or any(len(item) > _MAX_SYMBOL_CHARACTERS for item in symbols)
            or not isinstance(paths_truncated, bool)
            or not isinstance(symbols_truncated, bool)
            or not isinstance(fields_truncated, bool)
            or not isinstance(document_sections_truncated, bool)
            or not isinstance(content_hash, str)
            or len(content_hash) != 71
            or not content_hash.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in content_hash[7:].lower())
        ):
            return None
        validated.append({
            "source_document_path": source,
            "heading_path": heading,
            "mentioned_paths": paths,
            "mentioned_symbols": symbols,
            "paths_truncated": paths_truncated,
            "symbols_truncated": symbols_truncated,
            "fields_truncated": fields_truncated,
            "document_sections_truncated": document_sections_truncated,
            "content_hash": content_hash,
        })
    return validated


def _file_hash(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return f"sha256:{digest.hexdigest()}"
