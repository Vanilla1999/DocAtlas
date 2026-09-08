from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


PROOF_RUNTIME_PATHS = (
    "docmancer/docs/application/_evidence_selection_part01.py",
    "docmancer/docs/application/_evidence_selection_part02.py",
    "docmancer/docs/application/_evidence_selection_part03.py",
    "docmancer/docs/application/_evidence_selection_part04.py",
    "docmancer/docs/application/_evidence_selection_shared.py",
    "docmancer/docs/application/evidence_candidates.py",
    "docmancer/docs/application/evidence_models.py",
    "docmancer/docs/application/evidence_requirements.py",
    "docmancer/docs/application/evidence_selection.py",
    "docmancer/docs/application/proofability.py",
    "docmancer/docs/domain/_answer_units_part01.py",
    "docmancer/docs/domain/_answer_units_part02.py",
    "docmancer/docs/domain/_answer_units_shared.py",
    "docmancer/docs/domain/_project_answer_contract_part01.py",
    "docmancer/docs/domain/_project_answer_contract_part02.py",
    "docmancer/docs/domain/_project_answer_contract_shared.py",
    "docmancer/docs/domain/answer_units.py",
    "docmancer/docs/domain/project_answer_contract.py",
)


def _git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def proof_runtime_manifest_digest(files: list[Mapping[str, str]]) -> str:
    payload = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_proof_runtime_manifest(repo_root: Path) -> dict[str, Any]:
    files = []
    for relative in PROOF_RUNTIME_PATHS:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"proof-runtime source is missing: {relative}")
        files.append({"path": relative, "git_blob_sha1": _git_blob_sha1(path)})
    return {
        "algorithm": "ordered-git-blob-sha1-manifest-v1",
        "files": files,
        "sha256": proof_runtime_manifest_digest(files),
    }


def verify_proof_runtime_manifest(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"algorithm", "files", "sha256"}:
        raise ValueError("proof-runtime manifest shape is invalid")
    if value.get("algorithm") != "ordered-git-blob-sha1-manifest-v1":
        raise ValueError("proof-runtime manifest algorithm is invalid")
    files = value.get("files")
    if not isinstance(files, list) or len(files) != len(PROOF_RUNTIME_PATHS):
        raise ValueError("proof-runtime manifest file inventory is incomplete")
    paths = tuple(
        str(row.get("path") or "") if isinstance(row, dict) else ""
        for row in files
    )
    if paths != PROOF_RUNTIME_PATHS:
        raise ValueError("proof-runtime manifest paths are incomplete or unordered")
    if any(
        not isinstance(row, dict)
        or set(row) != {"path", "git_blob_sha1"}
        or re.fullmatch(r"[0-9a-f]{40}", str(row.get("git_blob_sha1") or "")) is None
        for row in files
    ):
        raise ValueError("proof-runtime manifest contains an invalid file identity")
    if value.get("sha256") != proof_runtime_manifest_digest(files):
        raise ValueError("proof-runtime manifest digest does not match its files")
