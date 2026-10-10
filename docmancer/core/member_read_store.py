"""Read an already owned, current lexical member store without provisioning.

Only the confirmed member transaction creates or updates this store. Each
connection checks ownership and active-generation metadata in a read transaction;
immutable generation contents are validated once per generation for this reader.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import threading

from docmancer.core._sqlite_store_active_fts import _ACTIVE_FTS_PROJECTION_VERSION
from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.core.structured_chunking import ChunkingConfig
from docmancer.retrieval.contracts import ContextConfig, canonical_hash


class MemberReadStore(SQLiteStore):
    """A separate read connection path, never the writable agent's store."""

    def __init__(self, storage_policy: MemberStoragePolicy, extracted_dir=None):
        if not isinstance(storage_policy, MemberStoragePolicy):
            raise PermissionError("member reads require a host-selected storage policy")
        self.storage_policy = storage_policy
        self.db_path = storage_policy.db_path
        self.extracted_dir = Path(extracted_dir) if extracted_dir else self.db_path.parent / "extracted"
        self._validated_generation = None
        self._read_lock = threading.RLock()
        with closing(self._connect()):
            pass

    def _connect(self) -> sqlite3.Connection:
        if not self.storage_policy.validate(storage_path=str(self.db_path)):
            raise PermissionError("member store has not been explicitly initialized")
        conn = sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=0")
            conn.execute("BEGIN")
            if conn.execute("PRAGMA journal_mode").fetchone()[0] not in {"delete", "persist", "truncate"}:
                raise PermissionError("member storage supports rollback journaling only")
            with self._read_lock:
                self._validate_read_generation(conn)
            return conn
        except BaseException:
            conn.close()
            raise

    def _validate_read_generation(self, conn) -> None:
        try:
            active = self._active_generation_id(conn)
            info = conn.execute(
                "SELECT * FROM index_generations WHERE generation_id = ?", (active,),
            ).fetchone()
            projection = conn.execute(
                "SELECT generation_id, projection_version FROM retrieval_fts_projection_state WHERE singleton = 1",
            ).fetchone()
            config, context = ChunkingConfig(), ContextConfig()
            retrieval_hash = canonical_hash({
                "schema_version": "contextual-retrieval-v1",
                "chunk_config_hash": config.config_hash,
                "context_config_hash": context.config_hash,
            })
            if (
                not isinstance(active, str) or not re.fullmatch(r"gen-[0-9a-f]{32}", active)
                or info is None or info["status"] != "active"
                or info["schema_version"] != config.schema_version
                or info["config_hash"] != config.config_hash
                or info["context_schema_version"] != context.schema_version
                or info["context_config_hash"] != context.config_hash
                or info["retrieval_config_hash"] != retrieval_hash
                or str(info["vector_backend"] or "")
                or json.loads(info["validation_json"] or "{}").get("status") != "PASS"
                or projection is None or projection["generation_id"] != active
                or projection["projection_version"] != _ACTIVE_FTS_PROJECTION_VERSION
            ):
                raise PermissionError("member read requires a current active lexical generation")
            if active != self._validated_generation:
                self._validate_generation(conn, active, config, context)
                self._validated_generation = active
        except (sqlite3.Error, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise PermissionError("member read requires a current active lexical generation") from exc

    def _ensure_schema(self) -> None:
        raise PermissionError("member reads cannot initialize or repair storage")

    def _stage_extraction(self, doc):
        raise PermissionError("member reads cannot stage extraction or ingest documents")
