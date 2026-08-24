#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

FORBIDDEN_ROOTS = {".git", ".product-truth"}


def run_git(repository: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe archive member: {name}")
    return path


def forbidden(path: PurePosixPath) -> bool:
    return bool(path.parts and path.parts[0] in FORBIDDEN_ROOTS)


def safe_link_target(path: PurePosixPath, target: str) -> None:
    link = PurePosixPath(target)
    if link.is_absolute():
        raise ValueError(f"absolute symlink is not allowed in model snapshot: {path} -> {target}")
    depth = len(path.parent.parts)
    for part in link.parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                raise ValueError(f"escaping symlink is not allowed in model snapshot: {path} -> {target}")
        elif part not in {".", ""}:
            depth += 1


def extract_snapshot(archive: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:") as handle:
        for member in handle.getmembers():
            path = safe_member_path(member.name)
            if forbidden(path):
                continue
            target = output.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                safe_link_target(path, member.linkname)
                os.symlink(member.linkname, target)
                continue
            if member.islnk():
                raise ValueError(f"hard links are not allowed in model snapshot: {path}")
            if not member.isfile():
                raise ValueError(f"unsupported archive entry in model snapshot: {path}")
            source = handle.extractfile(member)
            if source is None:
                raise ValueError(f"cannot read archive entry: {path}")
            target.write_bytes(source.read())
            target.chmod(member.mode & 0o777)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            kind = "L"
            payload = os.readlink(path).encode("utf-8")
        elif path.is_file():
            kind = "F"
            payload = path.read_bytes()
        elif path.is_dir():
            kind = "D"
            payload = b""
        else:
            raise ValueError(f"unsupported filesystem object: {rel}")
        digest.update(kind.encode("ascii") + b"\0" + rel.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


def validate_workspace(workspace: Path) -> dict[str, Any]:
    if not workspace.is_dir():
        raise ValueError("model workspace does not exist")
    forbidden_found: list[str] = []
    unsafe_links: list[str] = []
    for path in workspace.rglob("*"):
        rel = path.relative_to(workspace)
        if rel.parts and rel.parts[0] in FORBIDDEN_ROOTS:
            forbidden_found.append(rel.as_posix())
        if path.is_symlink():
            try:
                safe_link_target(PurePosixPath(rel.as_posix()), os.readlink(path))
            except ValueError:
                unsafe_links.append(rel.as_posix())
    if forbidden_found:
        raise ValueError(f"forbidden evaluator data in model workspace: {forbidden_found[:10]}")
    if unsafe_links:
        raise ValueError(f"unsafe model-workspace symlinks: {unsafe_links[:10]}")
    return {
        "git_metadata_absent": not (workspace / ".git").exists(),
        "benchmark_metadata_absent": not (workspace / ".product-truth").exists(),
        "unsafe_links": 0,
        "tree_sha256": tree_digest(workspace),
    }


def materialize(repository: Path, base: str, output: Path, attestation: Path) -> dict[str, Any]:
    repository = repository.resolve()
    output = output.resolve()
    attestation = attestation.resolve()
    if output.exists():
        raise ValueError("model workspace output must not already exist")
    commit = run_git(repository, "rev-parse", f"{base}^{{commit}}").decode().strip()
    tree = run_git(repository, "rev-parse", f"{base}^{{tree}}").decode().strip()
    with tempfile.TemporaryDirectory(prefix="product-truth-model-snapshot-") as raw:
        archive = Path(raw) / "source.tar"
        result = subprocess.run(
            ["git", "archive", "--format=tar", f"--output={archive}", commit],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(result.stderr.decode("utf-8", errors="replace")[-1000:])
        try:
            extract_snapshot(archive, output)
        except Exception:
            shutil.rmtree(output, ignore_errors=True)
            raise
    checks = validate_workspace(output)
    payload = {
        "schema_version": 1,
        "protocol": "product-truth-hermetic-source-snapshot-v1",
        "base_commit": commit,
        "base_tree": tree,
        **checks,
        "claim_boundary": {
            "filesystem_isolated": True,
            "network_isolated": False,
            "evaluator_separated": True,
            "real_model_oracle_authorized": False,
        },
    }
    attestation.parent.mkdir(parents=True, exist_ok=True)
    if output == attestation or output in attestation.parents:
        shutil.rmtree(output, ignore_errors=True)
        raise ValueError("attestation must be stored outside the model workspace")
    attestation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    args = parser.parse_args()
    payload = materialize(args.repository, args.base, args.output, args.attestation)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
