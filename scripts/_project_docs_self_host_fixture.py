"""A tracked-file self-host mirror with explicit, isolated member preparation.

The mirror preserves physical unselected files. Only the existing literal catalog
selects indexed documents; neither questions nor evaluator expectations enter here.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any
from unittest.mock import patch

import yaml

from docmancer.docs._impact_part01 import _run_process_bounded
from docmancer.docs.application.project_docs_member_transaction import (
    PinnedProject, catalog_entry_hash, local_project_identity,
)
from docmancer.docs.project_docs_catalog import (
    CATALOG_FILENAME, _UniqueKeySafeLoader, _literal_path, read_project_docs_catalog,
)
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
from eval.evidence_quality_v2.runtime import _ENV_LOCK, isolated_service


# Copy work only. Production catalog/source/retrieval limits are unchanged.
MAX_FILES = 10_000
MAX_INVENTORY_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
COPY_SECONDS = 60.0
GIT_SECONDS = 10.0


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_digest(value: Any) -> str:
    return _digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode())


def _import_origins(mirror: Path) -> dict:
    code_root = Path(__file__).resolve().parents[1]
    origins = {}
    for name in (
        "docmancer.mcp._docs_server_part01", "docmancer.docs.project",
        "docmancer.docs.application.project_docs_member_transaction",
        "eval.evidence_quality_v2.runtime", "scripts._project_docs_self_host_fixture",
    ):
        path = Path(sys.modules[name].__file__).resolve()
        if not path.is_relative_to(code_root) or path.is_relative_to(mirror):
            raise ValueError("self-host production import is outside the executing checkout")
        origins[name] = {"path": str(path), "sha256": _digest(path.read_bytes())}
    return {"executing_checkout": str(code_root), "modules": origins,
            "claim_boundary": "in_process_checkout_imports_not_installed_client"}


def _git(root: Path, args: list[str], commands: list[list[str]], *, deadline: float | None = None) -> bytes:
    timeout = GIT_SECONDS if deadline is None else min(GIT_SECONDS, deadline - time.monotonic())
    if timeout <= 0:
        raise ValueError("self-host Git inventory exceeded copy deadline")
    argv = ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
            "-C", str(root), *args]
    commands.append(argv)
    stdout, stderr, code, truncated, timed_out = _run_process_bounded(
        argv, max_stdout_bytes=MAX_INVENTORY_BYTES, timeout_seconds=timeout,
    )
    if code or stderr or truncated or timed_out:
        raise ValueError("self-host Git inventory failed or exceeded its work bounds")
    return stdout


def _inventory(root: Path, commands: list[list[str]], *, deadline: float | None = None) -> tuple[dict, list[dict]]:
    def git(args):
        return _git(root, args, commands, deadline=deadline)

    top = git(["rev-parse", "--show-toplevel"]).decode().strip()
    if top != str(root):
        raise ValueError("self-host origin must be the exact checkout root")
    head = git(["rev-parse", "--verify", "HEAD"]).decode().strip()
    tree = git(["rev-parse", "--verify", "HEAD^{tree}"]).decode().strip()
    algorithm = git(["rev-parse", "--show-object-format"]).decode().strip()
    if algorithm not in {"sha1", "sha256"} or any(
        len(value) != (40 if algorithm == "sha1" else 64)
        or any(char not in "0123456789abcdef" for char in value) for value in (head, tree)
    ):
        raise ValueError("self-host origin has an unsupported Git identity")
    # The report's HEAD/tree must describe the indexed paths, not staged edits.
    git(["diff", "--cached", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--"])
    raw = git(["ls-files", "--stage", "-z", "--cached"])
    if not raw or not raw.endswith(b"\0"):
        raise ValueError("self-host requires a complete nonempty tracked inventory")
    records = raw[:-1].split(b"\0")
    if len(records) > MAX_FILES:
        raise ValueError("self-host tracked file count exceeds copy work bound")
    rows, seen = [], set()
    for record in records:
        metadata, raw_path = record.split(b"\t", 1)
        mode, blob, stage = metadata.decode("ascii").split(" ")
        relative = raw_path.decode("utf-8")
        if (stage != "0" or mode not in {"100644", "100755"}
                or not _literal_path(relative) or ".git" in Path(relative).parts
                or relative in seen or len(blob) != len(head)
                or any(char not in "0123456789abcdef" for char in blob)):
            raise ValueError("self-host tracked member is unsafe, nonregular or unmerged")
        seen.add(relative)
        rows.append({"path": relative, "git_mode": mode, "git_blob": blob})
    return {"head_sha": head, "tree_sha": tree, "object_format": algorithm,
            "inventory_sha256": _digest(raw)}, sorted(rows, key=lambda row: row["path"])


def _version(path: Path) -> tuple[int, ...]:
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError("self-host source has a symlinked ancestor")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("self-host source must remain a non-hardlinked regular file")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def _read(root: Path, relative: str, deadline: float) -> bytes:
    # A context per member bounds retained descriptors independently of file count.
    with PinnedProject(root) as pinned:
        return pinned.read(relative, MAX_FILE_BYTES, deadline=deadline)


def _mirror(origin: Path, root: Path, commands: list[list[str]]) -> tuple[dict, dict]:
    deadline = time.monotonic() + COPY_SECONDS
    source, entries = _inventory(origin, commands, deadline=deadline)
    versions, total, rows = {}, 0, []
    root.mkdir()
    for entry in entries:
        relative = entry["path"]
        before = _version(origin / relative)
        if before[3] > MAX_FILE_BYTES or total + before[3] > MAX_TOTAL_BYTES:
            raise ValueError("self-host tracked bytes exceed copy work bound")
        data = _read(origin, relative, deadline)
        if _version(origin / relative) != before:
            raise ValueError("self-host source changed while copying")
        blob = hashlib.new(source["object_format"],
                           b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != entry["git_blob"]:
            raise ValueError("self-host tracked checkout bytes do not match the Git index")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
        copied = _read(root, relative, deadline)
        if copied != data:
            raise ValueError("self-host mirror differs from its source")
        versions[relative] = before
        total += len(data)
        rows.append({**entry, "bytes": len(data), "original_sha256": _digest(data),
                     "copied_sha256": _digest(copied)})
    _verify_origin(origin, source, entries, versions, commands, deadline=deadline)
    if time.monotonic() >= deadline:
        raise ValueError("self-host mirror exceeded copy deadline")
    return {"origin_root": str(origin), "origin": source, "mirror_root": str(root),
            "mirror_identity": local_project_identity(root), "files": rows,
            "file_count": len(rows), "total_source_bytes": total,
            "source_manifest_sha256": _json_digest([
                {key: row[key] for key in ("path", "git_mode", "git_blob", "bytes", "original_sha256")}
                for row in rows
            ]), "git_witness": "not_git",
            "claim_boundary": "tracked_repository_mirror_not_original_storage_or_git_impact",
            "copy_work_bounds": {"files": MAX_FILES, "inventory_bytes": MAX_INVENTORY_BYTES,
                                 "file_bytes": MAX_FILE_BYTES, "total_bytes": MAX_TOTAL_BYTES,
                                 "seconds": COPY_SECONDS, "git_seconds": GIT_SECONDS}}, versions


def _verify_origin(origin: Path, source: dict, entries: list[dict], versions: dict,
                   commands: list[list[str]], *, deadline: float | None = None) -> None:
    current, current_entries = _inventory(origin, commands, deadline=deadline)
    expected = [{key: row[key] for key in ("path", "git_mode", "git_blob")} for row in entries]
    if current != source or current_entries != expected:
        raise ValueError("self-host origin inventory changed")
    for relative, before in versions.items():
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("self-host source recheck exceeded copy deadline")
        if _version(origin / relative) != before:
            raise ValueError("self-host origin file changed")


def _bind_config(root: Path, storage_path: str, provenance: dict) -> None:
    path = root / "docatlas.yaml"
    original = path.read_bytes()
    before = yaml.load(original.decode("utf-8"), Loader=_UniqueKeySafeLoader)
    if not isinstance(before, dict) or not isinstance(before.get("index"), dict):
        raise ValueError("self-host requires its tracked project configuration")
    if "db_path" not in before["index"]:
        raise ValueError("self-host configuration must declare its original storage binding")
    after = deepcopy(before)
    after["index"]["db_path"] = storage_path
    encoded = yaml.safe_dump(after, sort_keys=False, allow_unicode=True).encode("utf-8")
    restored = yaml.load(encoded.decode("utf-8"), Loader=_UniqueKeySafeLoader)
    restored["index"]["db_path"] = before["index"]["db_path"]
    if restored != before:
        raise ValueError("self-host config relocation changed non-storage values")
    path.write_bytes(encoded)
    provenance["config_delta"] = {
        "path": "docatlas.yaml", "field": "index.db_path",
        "before": before["index"]["db_path"], "after": storage_path,
        "original_sha256": _digest(original), "relocated_sha256": _digest(encoded),
        "all_other_values_preserved": True,
    }
    for row in provenance["files"]:
        row["mirror_sha256"] = _digest(encoded) if row["path"] == "docatlas.yaml" else row["copied_sha256"]
    provenance["mirror_manifest_sha256"] = _json_digest(provenance["files"])


def _permissions(root: Path, files: list[dict], *, readonly: bool) -> None:
    directories = {root}
    for row in files:
        target = root / row["path"]
        target.chmod((0o555 if row["git_mode"] == "100755" else 0o444) if readonly else 0o600)
        directories.update(parent for parent in target.parents if parent == root or root in parent.parents)
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=readonly):
        directory.chmod(0o555 if readonly else 0o700)


@dataclass
class SelfHostFixture:
    root: Path
    service: Any
    config: Any
    provenance: dict
    mutation: dict
    cold_read_verified: bool = False

    def verify_cold_read(self, payload: Any) -> bool:
        cold = self.service._cold
        policy = cold.member_storage_policy
        error = payload.get("error") if isinstance(payload, Mapping) else None
        self.cold_read_verified = bool(
            isinstance(error, Mapping) and payload.get("status") == "failed"
            and error.get("reason_code") == "permission_denied"
            and error.get("exception_type") == "PermissionError"
            and error.get("retryable") is False
            and error.get("where") == {"tool": "get_docs_context", "handler": None, "phase": "execution"}
            and not payload.get("sources")
            and payload.get("kind") is None
            and all(payload.get(key) is None or payload.get(key) is False for key in (
                "answer_supported", "answer_available", "edit_ready", "mutation_ready", "context_available",
            ))
            and cold._service is None and not policy.db_path.exists() and not policy.marker.exists()
        )
        self.provenance["cold_read_verified"] = self.cold_read_verified
        return self.cold_read_verified

    def prepare(self) -> None:
        if not self.cold_read_verified:
            raise ValueError("self-host pre-sync cold read guard has not passed")
        cold = self.service._cold
        policy = cold.member_storage_policy
        if cold._service is not None or policy.validate(self.root, self.config.index.db_path):
            raise ValueError("self-host preparation requires the original cold store")
        result = call_docs_tool_payload("prepare_docs", {
            "action": "sync_project_docs", "project_path": str(self.root),
            "mutation": deepcopy(self.mutation),
        }, cold)
        if result.get("status") != "success":
            raise RuntimeError(f"self-host explicit member preparation failed: {result!r}")
        generation = result["metrics"]["generation_id"]
        if not generation or policy.generation() != generation or cold._service is not None:
            raise RuntimeError("self-host preparation did not preserve its cold store/generation binding")
        with closing(policy.connect()) as db:
            stored = [dict(row) for row in db.execute("SELECT source, content, metadata_json FROM sources")]
            indexed = sorted({row[0] for row in db.execute(
                "SELECT source_path FROM retrieval_children WHERE generation_id = ?", (generation,))})
        members = {row["path"]: row for row in self.mutation["documents"]}
        if len(stored) != len(members) or indexed != sorted(members):
            raise RuntimeError("self-host preparation omitted or added member sources")
        for row in stored:
            metadata = json.loads(row["metadata_json"])
            relative = metadata.get("project_doc_path")
            member = members.get(relative)
            if (member is None or row["source"] != str(self.root / relative)
                    or metadata.get("project_path") != str(self.root)
                    or metadata.get("project_identity") != self.provenance["mirror_identity"]
                    or metadata.get("project_doc_catalog_entry_hash") != member["catalog_entry_hash"]
                    or _digest(row["content"].encode("utf-8")) != member["content_sha256"]):
                raise RuntimeError("self-host indexed source lost its original byte/catalog/root binding")
        self.provenance["preparation"] = {
            "storage_path": str(policy.db_path), "generation_id": generation,
            "mutation": deepcopy(self.mutation), "indexed_paths": indexed,
            "transaction_metrics": result["metrics"],
        }


@contextmanager
def self_host_fixture(origin: Path):
    """Keep mirror, sanitized environment and actual service alive for all reads."""
    origin = Path(origin)
    if not origin.is_absolute() or origin.resolve() != origin:
        raise ValueError("self-host origin must be an absolute non-symlinked checkout")
    with _ENV_LOCK, TemporaryDirectory(prefix="docatlas-self-host-", dir="/tmp") as raw_tmp:
        temporary = Path(raw_tmp).resolve()
        root = temporary / "project"
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_OPTIONAL_LOCKS="0", GIT_CEILING_DIRECTORIES=str(temporary))
        with patch.dict(os.environ, env, clear=True):
            commands: list[list[str]] = []
            provenance, versions = _mirror(origin, root, commands)
            provenance["git_commands"] = commands
            provenance["import_origins"] = _import_origins(root)
            with isolated_service(temporary / "state") as (service, config):
                policy = service._cold.member_storage_policy
                if policy.validate(root, config.index.db_path) or service._cold._service is not None:
                    raise ValueError("self-host requires fresh host-selected storage")
                _bind_config(root, str(policy.db_path), provenance)
                catalog = read_project_docs_catalog(root)
                if not catalog.present or not catalog.valid or catalog.roots or catalog.code_files or not catalog.entries:
                    raise ValueError("self-host requires the original finite docs-only catalog")
                files = {row["path"]: row for row in provenance["files"]}
                if CATALOG_FILENAME not in files or any(entry.path not in files for entry in catalog.entries):
                    raise ValueError("self-host catalog members must be tracked source files")
                mutation = {
                    "operation": "sync_project_docs", "confirm": True,
                    "storage_path": str(policy.db_path), "expected_generation_id": None,
                    "catalog_sha256": files[CATALOG_FILENAME]["original_sha256"],
                    "documents": [{"path": entry.path,
                                   "content_sha256": files[entry.path]["original_sha256"],
                                   "catalog_entry_hash": catalog_entry_hash(entry)} for entry in catalog.entries],
                }
                _permissions(root, provenance["files"], readonly=True)
                try:
                    yield SelfHostFixture(root, service, config, provenance, mutation)
                    _verify_origin(origin, provenance["origin"], provenance["files"], versions, commands,
                                   deadline=time.monotonic() + COPY_SECONDS)
                    provenance["origin_unchanged_after_calls"] = True
                finally:
                    _permissions(root, provenance["files"], readonly=False)
