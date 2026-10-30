"""Host-bound finite membership, with discovery only in confirmed preparation.

The context is a request-local catalog locator, not an authority token. Query
readers never enumerate directories or provision storage. Host manifests live
in the selected private SQLite store and publish with their member upserts.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Iterator

from docmancer.core.member_storage_policy import MemberCommitUnknown, MemberStoragePolicy
from docmancer.docs.project_docs_catalog import (
    CATALOG_FILENAME, MAX_CATALOG_BYTES, MAX_CATALOG_DOCUMENTS,
    ProjectDocCatalogEntry, _literal_path, parse_project_docs_catalog,
)


@dataclass
class _CatalogContext:
    root: Path
    policy: MemberStoragePolicy
    cached: dict[str, bytes | None] = field(default_factory=dict)
    pending: bytes | None = None
    previous_sha256: str | None = None


_CURRENT_CATALOG: ContextVar[_CatalogContext | None] = ContextVar("docatlas_host_project_catalog", default=None)


@contextmanager
def catalog_scope(root: Path, storage_policy: MemberStoragePolicy) -> Iterator[None]:
    root = Path(root)
    if not isinstance(storage_policy, MemberStoragePolicy):
        raise PermissionError("host catalog requires the host-selected member store")
    if not root.is_absolute() or ".." in root.parts or root.resolve() != root:
        raise PermissionError("host catalog requires the exact bound absolute project root")
    storage_policy.validate(root)
    token = _CURRENT_CATALOG.set(_CatalogContext(root, storage_policy))
    try:
        yield
    finally:
        _CURRENT_CATALOG.reset(token)


def _selected_context(root: Path, policy: MemberStoragePolicy | None = None) -> _CatalogContext | None:
    selected = _CURRENT_CATALOG.get()
    if selected is None or Path(root) != selected.root:
        return None
    if policy is not None and selected.policy != policy:
        return None
    return selected


def host_catalog_bytes(root: Path) -> bytes | None:
    """Read one immutable per-request catalog; absent legacy table is not DDL."""
    selected = _selected_context(root)
    if selected is None:
        return None
    if selected.pending is not None:
        return selected.pending
    if "raw" in selected.cached:
        return selected.cached["raw"]
    raw = None
    if selected.policy.validate(root):
        conn = sqlite3.connect(selected.policy.db_path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=0")
            conn.execute("BEGIN")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='project_doc_manifests'").fetchone():
                header = conn.execute(
                    "SELECT length(catalog_bytes), catalog_sha256 FROM project_doc_manifests WHERE project_path=?",
                    (str(root),),
                ).fetchone()
                if header is not None:
                    if not isinstance(header[0], int) or not 0 < header[0] <= MAX_CATALOG_BYTES:
                        raise PermissionError("host project catalog exceeds its bounded representation")
                    raw = conn.execute("SELECT catalog_bytes FROM project_doc_manifests WHERE project_path=?", (str(root),)).fetchone()[0]
                    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != header[1]:
                        raise PermissionError("host project catalog hash precondition failed")
        finally:
            conn.close()
    selected.cached["raw"] = raw
    return raw


@contextmanager
def _pending_catalog(root: Path, policy: MemberStoragePolicy, raw: bytes) -> Iterator[None]:
    selected = _selected_context(root, policy)
    if selected is None or selected.pending is not None:
        raise PermissionError("pending catalog requires the bound host preparation scope")
    prior = host_catalog_bytes(root)
    pending = _CatalogContext(root, policy, pending=raw,
                              previous_sha256=hashlib.sha256(prior).hexdigest() if prior is not None else None)
    token = _CURRENT_CATALOG.set(pending)
    try:
        yield
    finally:
        _CURRENT_CATALOG.reset(token)


def host_catalog_transaction(root: Path, policy: MemberStoragePolicy, raw: bytes) -> tuple[bytes | None, str | None]:
    """Internal publication/CAS data; never accepted from public tool arguments."""
    selected = _selected_context(root, policy)
    if selected is None or host_catalog_bytes(root) != raw:
        raise PermissionError("member transaction is not bound to the host catalog snapshot")
    if selected.pending is not None:
        return raw, selected.previous_sha256
    return None, hashlib.sha256(raw).hexdigest()


class _DiscoveryBudgetExceeded(ValueError):
    reason_code = "project_discovery_budget_exceeded"


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise _DiscoveryBudgetExceeded("project discovery deadline exhausted")


def _discover_paths(root: Path, pinned, boundary, deadline: float, receipt: dict) -> list[str]:
    from docmancer.docs.domain.source_boundary import _excluded_directory, _generated_path, finite_local_path
    from docmancer.docs.project import DOC_FILE_EXTENSIONS

    selected: list[str] = []

    def excluded(reason: str, count: int = 1) -> None:
        receipt["excluded_entries"] += count
        reasons = receipt["exclusions"]
        reasons[reason] = reasons.get(reason, 0) + count

    def visit(directory: int, prefix: str, depth: int) -> None:
        _check_deadline(deadline)
        children = []
        with os.scandir(directory) as entries:
            for entry in entries:
                _check_deadline(deadline)
                receipt["scanned_entries"] += 1
                if receipt["scanned_entries"] > boundary.max_scanned_files:
                    raise _DiscoveryBudgetExceeded("project discovery inventory limit exhausted")
                children.append((entry.name, entry.stat(follow_symlinks=False)))
        # Existing boundaries implement root .gitignore, not the complete Git
        # ignore language. Never read through an unhandled nested ignore file.
        if prefix and boundary.respect_gitignore and any(name == ".gitignore" for name, _ in children):
            excluded("nested_gitignore_subtree", len(children))
            return
        for name, info in sorted(children, key=lambda item: item[0]):
            _check_deadline(deadline)
            relative = f"{prefix}/{name}" if prefix else name
            try:
                relative.encode("utf-8")
            except UnicodeError:
                excluded("unsupported_path_encoding")
                continue
            if not _literal_path(relative) or stat.S_ISLNK(info.st_mode):
                excluded("nonliteral_or_symlink")
                continue
            if stat.S_ISDIR(info.st_mode):
                if _excluded_directory(relative, name, boundary) or _generated_path(relative + "/member.md", boundary):
                    excluded("excluded_directory")
                    continue
                if depth >= boundary.max_directory_depth:
                    raise _DiscoveryBudgetExceeded("project discovery directory depth limit exhausted")
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    opened = os.fstat(fd)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        raise PermissionError("discovery directory was replaced")
                    visit(fd, relative, depth + 1)
                finally:
                    os.close(fd)
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                excluded("nonregular_or_hardlinked")
                continue
            if Path(name).suffix.lower() not in DOC_FILE_EXTENSIONS:
                excluded("unsupported_format")
                continue
            if info.st_size > boundary.max_file_bytes:
                excluded("max_file_bytes")
                continue
            if finite_local_path(root, relative, boundary=boundary,
                                 supported_extensions=frozenset(DOC_FILE_EXTENSIONS),
                                 use_configured_extensions=False) is None:
                excluded("source_boundary")
                continue
            selected.append(relative)
            if len(selected) > MAX_CATALOG_DOCUMENTS:
                raise _DiscoveryBudgetExceeded("project discovery catalog member limit exhausted")

    visit(pinned.root_fd, "", 0)
    return sorted(selected)


def discover_project_docs(root: Path, storage_policy: MemberStoragePolicy, *, confirm: bool = False) -> dict:
    """Confirmed bounded discovery + finite lexical upsert, never repository writes.

    This is its own explicit lifecycle grant: confirmation covers discovery and
    indexing of the resulting snapshot, not an invented external member grant.
    """
    root = Path(root)
    if confirm is not True or _selected_context(root, storage_policy) is None:
        raise PermissionError("explicit confirmed discovery of the host-bound project required")
    from docmancer.docs.application.project_docs_member_transaction import (
        MemberReadBudgetExceeded, MemberTransaction, PinnedProject, _execute_pinned, catalog_entry_hash,
        project_member_boundary,
    )
    from docmancer.docs.domain.source_boundary import SourceBoundary, finite_local_path
    from docmancer.docs.project import DOC_FILE_EXTENSIONS

    started = time.monotonic()
    exists = storage_policy.validate(root)
    active = storage_policy.generation() if exists else None
    receipt = {"mode": "bounded_discovery", "complete": False, "scanned_entries": 0,
               "selected_documents": 0, "source_bytes": 0, "excluded_entries": 0,
               "exclusions": {}, "coverage": "within_declared_boundaries"}
    try:
        with PinnedProject(root, capture_reads=True) as pinned:
            configured = project_member_boundary(root, pinned, storage_policy.db_path)
            ceilings = SourceBoundary()
            boundary = replace(configured, **{
                key: min(getattr(configured, key), getattr(ceilings, key))
                for key in ("max_scanned_files", "max_scanned_bytes", "max_file_bytes",
                            "scan_deadline_seconds", "max_directory_depth")
            })
            deadline = started + boundary.scan_deadline_seconds
            receipt["limits"] = {key: getattr(boundary, key) for key in (
                "max_scanned_files", "max_scanned_bytes", "max_file_bytes",
                "scan_deadline_seconds", "max_directory_depth",
            )}
            receipt["limits"]["max_catalog_documents"] = MAX_CATALOG_DOCUMENTS
            repository_catalog = os.path.lexists(root / CATALOG_FILENAME)
            if repository_catalog:
                receipt["mode"] = "explicit_catalog"
                raw = pinned.read(CATALOG_FILENAME, MAX_CATALOG_BYTES, deadline=deadline)
                catalog = parse_project_docs_catalog(root, raw, docs_only=True)
                if not catalog.valid or catalog.code_files:
                    raise PermissionError("explicit catalog must be valid finite docs-only membership; discovery does not replace it")
                entries = list(catalog.entries)
            else:
                paths = _discover_paths(root, pinned, boundary, deadline, receipt)
                entries = [ProjectDocCatalogEntry(
                    path=path, role="other", scope="project",
                    description="Documentation selected by explicit bounded project preparation.",
                    authority="supporting", status="active", impact="search_only",
                ) for path in paths]
                raw = json.dumps({"schema_version": 1, "documents": [asdict(entry) for entry in entries],
                                  "code_files": []}, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")
            if len(raw) > MAX_CATALOG_BYTES or len(entries) > min(MAX_CATALOG_DOCUMENTS, boundary.max_scanned_files):
                raise _DiscoveryBudgetExceeded("project discovery catalog budget exhausted")
            receipt["selected_documents"] = len(entries)
            if not entries:
                receipt["complete"] = True
                return {"tool": "prepare_docs", "action": "discover_project_docs", "status": "blocked",
                        "reason_code": "no_project_document_members", "project_path": str(root),
                        "mutation_performed": False, "candidate_count": 0, "discovery": receipt}
            documents = []
            for entry in entries:
                _check_deadline(deadline)
                if finite_local_path(root, entry.path, boundary=boundary,
                                     supported_extensions=frozenset(DOC_FILE_EXTENSIONS),
                                     use_configured_extensions=False) is None:
                    raise PermissionError("selected project document violates its source boundary")
                info = os.fstat(pinned.bind(entry.path))
                if receipt["source_bytes"] + info.st_size > boundary.max_scanned_bytes:
                    raise _DiscoveryBudgetExceeded("project discovery source byte budget exhausted")
                data = pinned.read(entry.path, min(boundary.max_file_bytes,
                                   boundary.max_scanned_bytes - receipt["source_bytes"]), deadline=deadline)
                receipt["source_bytes"] += len(data)
                data.decode("utf-8")
                documents.append({"path": entry.path, "content_sha256": hashlib.sha256(data).hexdigest(),
                                  "catalog_entry_hash": catalog_entry_hash(entry)})
            pinned.recheck()
            _check_deadline(deadline)
            request = MemberTransaction.parse({
                "operation": "sync_project_docs", "confirm": True,
                "storage_path": str(storage_policy.db_path),
                "catalog_sha256": hashlib.sha256(raw).hexdigest(),
                "expected_generation_id": active, "documents": documents,
            }, operation="sync_project_docs")
            if repository_catalog:
                _, outcome = _execute_pinned(root, pinned, request, started, storage_policy,
                                             reuse_pinned_reads=True, read_deadline=deadline)
            else:
                with _pending_catalog(root, storage_policy, raw):
                    _, outcome = _execute_pinned(root, pinned, request, started, storage_policy,
                                                 reuse_pinned_reads=True, read_deadline=deadline)
            receipt.update(complete=True, selected_documents=len(documents))
            return {"tool": "prepare_docs", "action": "discover_project_docs", "status": "success",
                    "project_path": str(root), "candidate_count": len(documents), "metrics": outcome,
                    "catalog_sha256": request.catalog_sha256,
                    "manifest_origin": "repository" if repository_catalog else "host",
                    "mutation_performed": True, "discovery": receipt,
                    "vector_sync": {"status": "not_requested"}}
    except (_DiscoveryBudgetExceeded, MemberReadBudgetExceeded) as exc:
        return {"tool": "prepare_docs", "action": "discover_project_docs", "status": "blocked",
                "reason_code": "project_discovery_budget_exceeded", "message": str(exc), "project_path": str(root),
                "mutation_performed": False, "discovery": receipt}
    except MemberCommitUnknown:
        return {"tool": "prepare_docs", "action": "discover_project_docs", "status": "blocked",
                "reason_code": "member_commit_outcome_unknown", "mutation_performed": None,
                "retryable": False, "message": "Commit outcome is unknown; inspect the trusted store before retrying."}
