"""Explicit local member upserts; caller intent is not issuer authentication."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any

from docmancer.core.models import Document
from docmancer.core.config import DocmancerConfig
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.domain.project_path_validation import validate_project_path
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


def _read_member(root: Path, relative: str, limit: int) -> bytes:
    """Open every component without following symlinks, with a bounded read."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = Path(relative).parts
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ValueError("member is not a bounded regular file")
            data = handle.read(limit + 1)
            after = os.fstat(handle.fileno())
            if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns,
            ):
                raise ValueError("member changed during bounded read")
            return data
    finally:
        os.close(fd)


def execute_member_transaction(project_path: str, mutation: Any, *, operation: str) -> tuple[ProjectMetadata, dict[str, Any]]:
    request = MemberTransaction.parse(mutation, operation=operation)
    started = time.monotonic()
    if not isinstance(project_path, str) or not Path(project_path).is_absolute():
        raise ValueError("project_path must be absolute")
    raw_root = Path(project_path)
    if any(path.is_symlink() for path in (raw_root, *raw_root.parents)):
        raise ValueError("project_path must not contain symlinks")
    root = validate_project_path(project_path).path
    storage = root / ".docatlas" / "docatlas.db"
    if request.storage_path != str(storage):
        raise PermissionError("storage_path must be project_path/.docatlas/docatlas.db")
    # No constructor/schema/config/agent dispatch. Existing initialized local DB only.
    for path in (storage.parent, storage, *(Path(str(storage) + suffix) for suffix in
                                           ("-journal", "-wal", "-shm"))):
        if path.is_symlink():
            raise PermissionError("storage paths must not be symlinks")
        if path.exists() and path.is_file() and path.stat().st_nlink != 1:
            raise PermissionError("storage files must not be hardlinked")
    if not storage.is_file():
        raise ValueError("explicit project-local storage must already be initialized")
    catalog_bytes = _read_member(root, CATALOG_FILENAME, MAX_CATALOG_BYTES)
    if hashlib.sha256(catalog_bytes).hexdigest() != request.catalog_sha256:
        raise ValueError("catalog hash precondition failed")
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
    config = DocmancerConfig()
    if (root / "docatlas.yaml").exists() or (root / "docatlas.yaml").is_symlink():
        config = DocmancerConfig(**(yaml.load(
            _read_member(root, "docatlas.yaml", MAX_CATALOG_BYTES).decode("utf-8"),
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
        lines = _read_member(root, ".gitignore", MAX_CATALOG_BYTES).decode("utf-8").splitlines()
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
        path = finite_local_path(root, member.path, boundary=boundary,
                                 supported_extensions=frozenset(DOC_FILE_EXTENSIONS),
                                 use_configured_extensions=False)
        if path is None or time.monotonic() >= deadline:
            raise PermissionError("member rejected by current source boundary")
        selected.append((member, entry, path))
    for member, entry, path in selected:
        data = _read_member(root, member.path, boundary.max_file_bytes)
        spent += len(data)
        if spent > boundary.max_scanned_bytes or time.monotonic() >= deadline:
            raise ValueError("member transaction exceeds configured read budget")
        if hashlib.sha256(data).hexdigest() != member.content_sha256:
            raise ValueError("document hash precondition failed")
        text = data.decode("utf-8")
        metadata = {
            "project_path": str(root), "source_class": "project_file", "project_docs": True,
            "project_doc_path": member.path, "source_path": member.path, "format": path.suffix[1:],
            "project_doc_content_hash": "sha256:" + member.content_sha256,
            "project_doc_catalog_entry_hash": member.catalog_entry_hash,
            "project_doc_reason": entry.role, "doc_scope": entry.scope,
            "module_path": entry.module_path, "project_doc_description": entry.description,
            "project_doc_authority": entry.authority, "project_doc_lifecycle_status": entry.status,
            "lifecycle_status": entry.status, "project_doc_impact_policy": entry.impact,
            "index_freshness": "synchronized",
        }
        documents.append(Document(source=str(root / member.path), content=text, metadata=metadata))
    store = SQLiteStore.__new__(SQLiteStore)
    store.db_path = storage
    store.extracted_dir = storage.parent / "extracted"
    outcome = store.upsert_project_members(
        documents, project_path=str(root), expected_generation_id=request.expected_generation_id,
    )
    return ProjectMetadata(project_path=str(root), docs_catalog_present=True,
                           docs_catalog_valid=True), outcome
