"""Explicit local member upserts; caller intent is not issuer authentication."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sqlite3
import time
from typing import Any

from docmancer.core.models import Document
from docmancer.core.config import DocmancerConfig
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.domain.source_boundary import SourceBoundary, finite_local_path
from docmancer.docs.models import ProjectMetadata
from docmancer.docs.project import DOC_FILE_EXTENSIONS
from docmancer.docs.project_docs_catalog import (
    CATALOG_FILENAME, MAX_CATALOG_BYTES, MAX_CATALOG_DOCUMENTS,
    TOP_LEVEL_FIELDS, _UniqueKeySafeLoader, _literal_path, _validated_entry,
)
import yaml


@dataclass(frozen=True, slots=True)
class MemberDocument:
    path: str
    content_sha256: str
    catalog_entry_hash: str


@dataclass(frozen=True, slots=True)
class MemberTransaction:
    operation: str
    storage_path: str
    catalog_sha256: str
    expected_generation_id: str | None
    documents: tuple[MemberDocument, ...]

    @classmethod
    def parse(cls, value: Any, *, operation: str) -> MemberTransaction:
        fields = {"operation", "confirm", "storage_path", "catalog_sha256",
                  "expected_generation_id", "documents"}
        if not isinstance(value, dict) or set(value) != fields:
            raise PermissionError("Explicit complete member mutation object required")
        if value["confirm"] is not True or value["operation"] != operation:
            raise PermissionError("Explicit confirmation and matching operation required")
        storage = value["storage_path"]
        if not isinstance(storage, str) or not Path(storage).is_absolute():
            raise ValueError("storage_path must be an absolute project-local path")
        digest = value["catalog_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("catalog_sha256 must be a lowercase SHA256 digest")
        generation = value["expected_generation_id"]
        if generation is not None and (
            not isinstance(generation, str)
            or not re.fullmatch(r"gen-[0-9a-f]{32}", generation)
        ):
            raise ValueError("expected_generation_id must be null or an exact generation ID")
        raw_docs = value["documents"]
        if not isinstance(raw_docs, list) or not 1 <= len(raw_docs) <= 500:
            raise ValueError("documents must contain 1 to 500 exact members")
        docs = []
        seen = set()
        for raw in raw_docs:
            if not isinstance(raw, dict) or set(raw) != {
                "path", "content_sha256", "catalog_entry_hash",
            }:
                raise ValueError("invalid member document fields")
            path = raw["path"]
            if not isinstance(path, str) or not _literal_path(path) or path in seen:
                raise ValueError("documents require unique literal relative paths")
            for key, pattern in (("content_sha256", r"[0-9a-f]{64}"),
                                 ("catalog_entry_hash", r"sha256:[0-9a-f]{64}")):
                if not isinstance(raw[key], str) or not re.fullmatch(pattern, raw[key]):
                    raise ValueError(f"invalid {key}")
            seen.add(path)
            docs.append(MemberDocument(**raw))
        return cls(operation, storage, digest, generation, tuple(docs))


def catalog_entry_hash(entry: Any) -> str:
    """Same literal entry binding used by ProjectMetadataReader."""
    return "sha256:" + hashlib.sha256(json.dumps(
        asdict(entry), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def local_project_identity(root: Path) -> str:
    """Pure identity for an already root-bound absolute path; no filesystem IO."""
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("project identity requires an absolute literal root")
    return "local:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()


def member_document(root: Path, member: MemberDocument, entry: Any, data: bytes) -> Document:
    """Persist the exact same root identity consumed by filtered lexical reads."""
    identity = local_project_identity(root)
    if hashlib.sha256(data).hexdigest() != member.content_sha256:
        raise ValueError("document hash precondition failed")
    if entry.path != member.path or catalog_entry_hash(entry) != member.catalog_entry_hash:
        raise ValueError("catalog entry precondition failed")
    return Document(source=str(root / member.path), content=data.decode("utf-8"), metadata={
        "project_path": str(root), "project_identity": identity, "repository_identity": identity,
        "source_class": "project_file", "project_docs": True,
        "project_doc_path": member.path, "source_path": member.path,
        "format": Path(member.path).suffix[1:],
        "project_doc_content_hash": "sha256:" + member.content_sha256,
        "project_doc_catalog_entry_hash": member.catalog_entry_hash,
        "project_doc_reason": entry.role, "doc_scope": entry.scope,
        "module_path": entry.module_path, "module_id": entry.module_path,
        "project_doc_description": entry.description,
        "project_doc_authority": entry.authority, "project_doc_lifecycle_status": entry.status,
        "lifecycle_status": entry.status, "project_doc_impact_policy": entry.impact,
        "index_freshness": "synchronized",
    })


class UnsafeSQLitePathMutation(PermissionError):
    """No stdlib SQLite API binds the database and sidecars to selected FDs."""


_DESCRIPTOR_READ_SUPPORTED = (
    os.name == "posix" and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY") and os.open in os.supports_dir_fd
)
_DIR_FD_OPEN = os.open


def reject_pathname_sqlite_mutation() -> None:
    raise UnsafeSQLitePathMutation(
        "unsafe_sqlite_path_mutation: descriptor-bound SQLite database and sidecar "
        "opens are unavailable in this route; pathname checks do not authorize writes"
    )


class PinnedProject:
    """POSIX no-follow directory walk and retained member descriptors.

    Rechecks detect replacements; read confinement comes from retained FDs, not
    from a check followed by reopening a pathname. No persistence API is exposed.
    """

    def __init__(self, root: Path):
        if (not _DESCRIPTOR_READ_SUPPORTED or os.name != "posix"
            or not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_DIRECTORY", 0)
            or _DIR_FD_OPEN not in getattr(os, "supports_dir_fd", ())):
            raise PermissionError("unsupported_descriptor_read_platform")
        if not root.is_absolute() or str(root) != root.as_posix() or ".." in root.parts:
            raise ValueError("project_path must be an absolute literal path")
        self.fds: list[int] = []
        self.edges: list[tuple[int, str, int, tuple[int, ...]]] = []
        self.members: dict[str, int] = {}
        self.versions: dict[int, tuple[int, ...]] = {}
        try:
            fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.fds.append(fd)
            for part in root.parts[1:]:
                fd = self._open(fd, part, directory=True)
            self.root_fd = fd
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _identity(fd: int) -> tuple[int, ...]:
        info = os.fstat(fd)
        return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))

    @staticmethod
    def _version(fd: int) -> tuple[int, ...]:
        info = os.fstat(fd)
        return (info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def _open(self, parent: int, name: str, *, directory: bool) -> int:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        fd = os.open(name, flags, dir_fd=parent)
        self.fds.append(fd)
        info = os.fstat(fd)
        if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise PermissionError("member must be a non-hardlinked regular file")
        if not directory:
            self.versions[fd] = self._version(fd)
        self.edges.append((parent, name, fd, self._identity(fd)))
        return fd

    def bind(self, relative: str) -> int:
        if not _literal_path(relative):
            raise ValueError("descriptor members require literal relative paths")
        if relative not in self.members:
            parent = self.root_fd
            for part in Path(relative).parts[:-1]:
                parent = self._open(parent, part, directory=True)
            self.members[relative] = self._open(parent, Path(relative).name, directory=False)
        self.recheck()
        return self.members[relative]

    def recheck(self) -> None:
        for parent, name, original, identity in self.edges:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if identity[2] == stat.S_IFDIR:
                flags |= os.O_DIRECTORY
            current = os.open(name, flags, dir_fd=parent)
            try:
                if self._identity(current) != identity or self._identity(original) != identity:
                    raise PermissionError("selected descriptor path was replaced")
                if identity[2] == stat.S_IFREG and (
                    os.fstat(original).st_nlink != 1 or os.fstat(current).st_nlink != 1
                ):
                    raise PermissionError("selected descriptor file was hardlinked")
                if original in self.versions and self._version(original) != self.versions[original]:
                    raise PermissionError("selected descriptor content was replaced")
            finally:
                os.close(current)

    def read(self, relative: str, limit: int, *, deadline: float | None = None) -> bytes:
        if limit < 0 or (deadline is not None and time.monotonic() >= deadline):
            raise ValueError("member read budget exhausted before IO")
        fd = self.bind(relative)
        before = os.fstat(fd)
        if before.st_size > limit:
            raise ValueError("member exceeds bounded read limit")
        os.lseek(fd, 0, os.SEEK_SET)
        data = bytearray()
        while len(data) < limit:
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError("member deadline exhausted before chunk read")
            chunk = os.read(fd, min(65536, limit - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        self.recheck()
        if (len(data) != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise PermissionError("selected descriptor content changed during read")
        return bytes(data)

    def close(self) -> None:
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()

    def __enter__(self) -> PinnedProject:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _read_member(root: PinnedProject, relative: str, limit: int,
                 *, deadline: float | None = None) -> bytes:
    return root.read(relative, limit, deadline=deadline)


def execute_member_transaction(project_path: str, mutation: Any, *, operation: str) -> tuple[ProjectMetadata, dict[str, Any]]:
    request = MemberTransaction.parse(mutation, operation=operation)
    started = time.monotonic()
    if not isinstance(project_path, str) or not Path(project_path).is_absolute():
        raise ValueError("project_path must be absolute")
    raw_root = Path(project_path)
    with PinnedProject(raw_root) as pinned:
        return _execute_pinned(raw_root, pinned, request, started)


def _execute_pinned(root: Path, pinned: PinnedProject, request: MemberTransaction,
                    started: float) -> tuple[ProjectMetadata, dict[str, Any]]:
    storage = root / ".docatlas" / "docatlas.db"
    if request.storage_path != str(storage):
        raise PermissionError("storage_path must be project_path/.docatlas/docatlas.db")
    catalog_bytes = _read_member(pinned, CATALOG_FILENAME, MAX_CATALOG_BYTES)
    if hashlib.sha256(catalog_bytes).hexdigest() != request.catalog_sha256:
        raise ValueError("catalog hash precondition failed")
    # Read the initialized DB only through its retained no-follow descriptor.
    # Reject sidecars: an independent WAL/hot-journal snapshot cannot be safely
    # reconstructed by this bounded read-only preflight.
    pinned.bind(".docatlas/docatlas.db")
    for suffix in ("-journal", "-wal", "-shm"):
        try:
            pinned.bind(".docatlas/docatlas.db" + suffix)
        except FileNotFoundError:
            continue
        raise PermissionError("unsupported_sqlite_sidecar_snapshot")
    snapshot = _read_member(pinned, ".docatlas/docatlas.db", 32 * 1024 * 1024)
    if not hasattr(sqlite3.Connection, "deserialize"):
        raise PermissionError("unsupported_sqlite_descriptor_snapshot_platform")
    memory = sqlite3.connect(":memory:")
    try:
        memory.execute("PRAGMA temp_store=MEMORY")
        memory.deserialize(snapshot)
        memory.execute("PRAGMA query_only=ON")
        row = memory.execute("SELECT active_generation_id FROM index_state WHERE singleton=1").fetchone()
        if row is None or row[0] != request.expected_generation_id:
            raise ValueError("active generation precondition failed")
    finally:
        memory.close()
    raw_catalog = yaml.load(catalog_bytes.decode("utf-8"), Loader=_UniqueKeySafeLoader)
    # This docs-only lane must not inspect code/dependency membership.
    if not isinstance(raw_catalog, dict) or raw_catalog.get("code_files", []) != []:
        raise ValueError("member transaction requires empty code_files")
    if (set(raw_catalog) - set(TOP_LEVEL_FIELDS)
        or type(raw_catalog.get("schema_version")) is not int
        or raw_catalog["schema_version"] != 1 or raw_catalog.get("roots", []) != []
        or not isinstance(raw_catalog.get("documents"), list)
        or len(raw_catalog["documents"]) > MAX_CATALOG_DOCUMENTS):
        raise ValueError("valid explicit finite documentation catalog required")
    entries = {}
    for raw_entry in raw_catalog["documents"]:
        entry, error = _validated_entry(root, raw_entry)
        if error or entry is None or entry.path in entries:
            raise ValueError("invalid or duplicate catalog document")
        entries[entry.path] = entry
    pinned.recheck()
    config = DocmancerConfig()
    if (root / "docatlas.yaml").exists() or (root / "docatlas.yaml").is_symlink():
        config = DocmancerConfig(**(yaml.load(
            _read_member(pinned, "docatlas.yaml", MAX_CATALOG_BYTES).decode("utf-8"),
            Loader=_UniqueKeySafeLoader,
        ) or {}))
        configured_db = Path(config.index.db_path)
        if not configured_db.is_absolute():
            configured_db = root / configured_db
        if configured_db != storage:
            raise PermissionError("project config storage is not the explicit local target")
    if config.index.provider != "sqlite" or str(config.retrieval.default_mode).lower() != "lexical":
        raise PermissionError("member transaction requires lexical project configuration")
    configured = config.project.source_boundary()
    patterns = ()
    if configured.respect_gitignore and ((root / ".gitignore").exists() or (root / ".gitignore").is_symlink()):
        lines = _read_member(pinned, ".gitignore", MAX_CATALOG_BYTES).decode("utf-8").splitlines()
        patterns = tuple(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))
    boundary = SourceBoundary.from_config(configured.model_copy(update={"respect_gitignore": False}), root=root)
    boundary = replace(boundary, respect_gitignore=configured.respect_gitignore, gitignore_patterns=patterns)
    if not boundary.enabled or len(request.documents) > boundary.max_scanned_files:
        raise ValueError("source boundary rejects member transaction")
    deadline = started + boundary.scan_deadline_seconds
    documents = []
    spent = 0
    selected = []
    for member in request.documents:
        entry = entries.get(member.path)
        if entry is None or catalog_entry_hash(entry) != member.catalog_entry_hash:
            raise PermissionError("member is not bound to the current catalog entry")
        pinned.bind(member.path)
        path = finite_local_path(root, member.path, boundary=boundary,
                                 supported_extensions=frozenset(DOC_FILE_EXTENSIONS),
                                 use_configured_extensions=False)
        if path is None or time.monotonic() >= deadline:
            raise PermissionError("member rejected by current source boundary")
        selected.append((member, entry, path))
    pinned.recheck()
    for member, entry, path in selected:
        if time.monotonic() >= deadline:
            raise ValueError("member transaction deadline exhausted before member read")
        remaining = boundary.max_scanned_bytes - spent
        data = _read_member(pinned, member.path, min(boundary.max_file_bytes, remaining),
                            deadline=deadline)
        spent += len(data)
        if spent > boundary.max_scanned_bytes or time.monotonic() >= deadline:
            raise ValueError("member transaction exceeds configured read budget")
        documents.append(member_document(root, member, entry, data))
    store = SQLiteStore.__new__(SQLiteStore)
    store.db_path = storage
    store.extracted_dir = storage.parent / "extracted"
    pinned.recheck()
    outcome = store.upsert_project_members(
        documents, project_path=str(root), expected_generation_id=request.expected_generation_id,
    )
    return ProjectMetadata(project_path=str(root), docs_catalog_present=True,
                           docs_catalog_valid=True), outcome
