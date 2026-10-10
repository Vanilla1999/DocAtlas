"""Finite local MCP storage policy; the OS and current-UID processes are trusted.

Project inputs never select this policy. Private app storage, including recovery
files, must be outside the project. Checks reject accidental/foreign adoption;
they are not a sandbox against a malicious process with equivalent credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import stat

from docmancer.core.product_identity import PRODUCT_ID


class MemberCommitUnknown(RuntimeError):
    reason_code = "member_commit_outcome_unknown"


def _literal_absolute(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != str(value):
        raise PermissionError("trusted storage requires a literal absolute path")
    return path


@dataclass(frozen=True)
class MemberStoragePolicy:
    app_home: Path
    db_path: Path
    config_path: Path | None = None

    def __post_init__(self) -> None:
        home = _literal_absolute(self.app_home)
        database = _literal_absolute(self.db_path)
        if not database.is_relative_to(home) or database.parent == home:
            raise PermissionError("member storage requires a private app-data subdirectory")
        if database.suffix != ".db":
            raise PermissionError("member storage target must be an exact .db file")

    @property
    def marker(self) -> Path:
        return self.db_path.with_name(self.db_path.name + ".member-owner.json")

    def _directories(self) -> None:
        for directory in reversed(self.db_path.parent.parents):
            self._directory(directory, private=False)
        self._directory(self.db_path.parent, private=True)

    def _directory(self, path: Path, *, private: bool) -> None:
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISDIR(info.st_mode):
            raise PermissionError("storage ancestors must be plain directories")
        # A sticky system temporary directory is permitted, but an ordinary
        # writable ancestor would let another principal replace private state.
        if (info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            raise PermissionError("storage ancestors must not permit foreign namespace replacement")
        if path == self.app_home or path.is_relative_to(self.app_home):
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise PermissionError("app storage must be owned and not writable by others")
            if private and info.st_mode & 0o077:
                raise PermissionError("member storage directory must be private")

    @staticmethod
    def _file(path: Path) -> os.stat_result | None:
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise PermissionError("storage files must be private owned non-hardlinked regular files")
        return info

    def validate(self, project: Path | None = None, storage_path: str | None = None) -> bool:
        if os.name != "posix":
            raise PermissionError("unsupported_trusted_storage_platform")
        if storage_path is not None and storage_path != str(self.db_path):
            raise PermissionError("storage_path does not match the host-selected member store")
        if project is not None:
            root = _literal_absolute(project)
            if self.app_home.is_relative_to(root) or self.db_path.is_relative_to(root):
                raise PermissionError("member storage must be outside the project")
            if self.config_path is not None and self.config_path.is_relative_to(root):
                raise PermissionError("project configuration cannot select member storage")
        self._directories()
        database = self._file(self.db_path)
        marker = self._file(self.marker)
        journal = self._file(Path(str(self.db_path) + "-journal"))
        for suffix in ("-wal", "-shm"):
            if os.path.lexists(str(self.db_path) + suffix):
                raise PermissionError("member storage supports rollback journaling only")
        if database is None:
            if marker is not None or journal is not None:
                raise PermissionError("orphaned storage ownership or recovery files")
            return False
        if marker is None or marker.st_size > 4096:
            raise PermissionError("unexpected existing member database; adoption is forbidden")
        expected = self._ownership(database)
        try:
            actual = json.loads(self.marker.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise PermissionError("invalid member storage ownership marker") from exc
        if actual != expected:
            raise PermissionError("member storage ownership identity mismatch")
        return True

    def _ownership(self, info: os.stat_result) -> dict:
        return {"product_id": PRODUCT_ID, "schema": "mcp-member-storage-v1",
                "database": str(self.db_path), "device": info.st_dev, "inode": info.st_ino}

    def connect(self) -> sqlite3.Connection:
        if not self.validate():
            raise PermissionError("member store has not been explicitly initialized")
        conn = sqlite3.connect(self.db_path.as_uri() + "?mode=rw", uri=True, timeout=0.2)
        try:
            conn.row_factory = sqlite3.Row
            if conn.execute("PRAGMA journal_mode").fetchone()[0] not in {"delete", "persist", "truncate"}:
                raise PermissionError("member storage supports rollback journaling only")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=0")
            return conn
        except BaseException:
            conn.close()
            raise

    def generation(self) -> str | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT active_generation_id FROM index_state WHERE singleton=1").fetchone()
            if row is None:
                raise PermissionError("member storage schema is incomplete")
            return row[0]
        finally:
            conn.close()

    def initialize(self) -> None:
        """Called only after complete confirmed member/source validation.

        O_EXCL refuses concurrent/foreign adoption. An interrupted initializer
        leaves an unowned file which fails closed; it is never silently replaced.
        """
        if self.validate():
            return
        missing = []
        directory = self.db_path.parent
        while not directory.exists():
            missing.append(directory)
            directory = directory.parent
        for directory in reversed(missing):
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                pass
        self._directories()
        fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        from docmancer.core.sqlite_store import SQLiteStore
        store = SQLiteStore.__new__(SQLiteStore)
        store.db_path = self.db_path
        store.extracted_dir = self.db_path.parent / "extracted"
        store._ensure_schema()
        info = self._file(self.db_path)
        with self.marker.open("x", encoding="utf-8") as marker:
            os.fchmod(marker.fileno(), 0o600)
            json.dump(self._ownership(info), marker, sort_keys=True)
            marker.flush()
            os.fsync(marker.fileno())
        fd = os.open(self.db_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
