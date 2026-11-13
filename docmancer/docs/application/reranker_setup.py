"""Public reranker setup: pinned model assets and runtime compatibility check.

The Qwen evidence scorer runs one pinned opt-in model contract
(context_evidence_scoring). These helpers make that contract installable:
`prepare` downloads the pinned revision with SHA-256 verification and writes
the provenance manifest the scorer requires on every call; `check` reports
assets and runtime compatibility without raising.

No inference happens here and no CUDA is required to prepare assets.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

from . import context_evidence_scoring as scorer

HF_API = "https://huggingface.co/api/models/{model}/tree/{revision}"
HF_RESOLVE = "https://huggingface.co/{model}/resolve/{revision}/{name}"

RUNTIME_PACKAGES = ("transformers", "tokenizers", "safetensors")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _open(url: str, *, timeout: float):
    """Open a URL with a few retries for transient TLS/network failures."""
    import time

    last: Exception | None = None
    for attempt in range(3):
        try:
            return urllib.request.urlopen(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last  # type: ignore[misc]


def prepare_assets(out: Path, *, timeout: float = 600.0) -> dict:
    """Download the pinned revision into `out` and verify every pinned hash.

    `out` must not exist or must be empty. Fails loudly on any hash mismatch
    with the pinned contract; partial files are removed before returning.
    Returns the written provenance manifest.
    """
    out = Path(out).expanduser()
    if not out.is_absolute():
        raise ValueError("reranker_prepare_requires_absolute_out")
    if out.exists() and any(out.iterdir()):
        raise ValueError("reranker_prepare_requires_empty_directory")
    out.mkdir(parents=True, exist_ok=True)
    model, revision = scorer.MODEL_ID, scorer.REVISION
    manifest: dict = {
        "model": model,
        "revision": revision,
        "official_origin": f"https://huggingface.co/{model}",
        "files": {},
    }
    try:
        with _open(HF_API.format(model=model, revision=revision), timeout=60) as response:
            tree = {item["path"]: item for item in json.load(response)}
        for name, expected in scorer.ASSETS.items():
            if name not in tree:
                raise ValueError(f"reranker_prepare_missing_remote_file:{name}")
            entry = tree[name]
            url = HF_RESOLVE.format(model=model, revision=revision, name=name)
            target = out / f"{name}.partial"
            digest = hashlib.sha256()
            size = 0
            try:
                with _open(url, timeout=timeout) as response, target.open("xb") as stream:
                    while block := response.read(1024 * 1024):
                        stream.write(block)
                        size += len(block)
                        digest.update(block)
                actual = digest.hexdigest()
                if size != entry["size"] or actual != expected:
                    raise ValueError(f"reranker_prepare_hash_mismatch:{name}")
                # Origin integrity: LFS objects carry the content SHA-256 as the
                # LFS oid; regular files carry a Git blob SHA-1 of the content.
                if "lfs" in entry:
                    if entry["lfs"]["oid"] != expected:
                        raise ValueError(f"reranker_prepare_remote_lfs_mismatch:{name}")
                else:
                    blob = hashlib.sha1(f"blob {size}\0".encode())
                    with target.open("rb") as stream:
                        while block := stream.read(1024 * 1024):
                            blob.update(block)
                    if blob.hexdigest() != entry["oid"]:
                        raise ValueError(f"reranker_prepare_remote_blob_mismatch:{name}")
                target.replace(out / name)
            finally:
                target.unlink(missing_ok=True)
            manifest["files"][name] = {
                "sha256": actual,
                "bytes": size,
                "url": url,
                "remote_lfs_sha256": entry.get("lfs", {}).get("oid"),
                "remote_git_blob_sha1": entry.get("oid"),
            }
        (out / "provenance.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        scorer.verify_assets(str(out))  # The exact gate the scorer runs per call.
        return manifest
    except Exception:
        shutil.rmtree(out, ignore_errors=True)
        raise


def _runtime_snapshot() -> dict:
    snapshot: dict = {}
    try:
        import torch

        snapshot["torch"] = torch.__version__
        snapshot["cuda"] = torch.version.cuda
        if torch.cuda.is_available():
            snapshot["capability"] = list(torch.cuda.get_device_capability(0))
            snapshot["gpu"] = torch.cuda.get_device_name(0)
        else:
            snapshot["capability"] = None
            snapshot["gpu"] = None
            snapshot["cuda_available"] = False
    except ImportError:
        snapshot["torch"] = None
        snapshot["error"] = "reranker_deps_missing"
    except Exception as exc:  # noqa: BLE001
        snapshot["error"] = f"{type(exc).__name__}: {exc}"
    for name in RUNTIME_PACKAGES:
        try:
            import importlib.metadata

            snapshot[name] = importlib.metadata.version(name)
        except Exception:  # noqa: BLE001
            snapshot[name] = None
    return snapshot


def runtime_diff(snapshot: dict) -> dict[str, tuple]:
    """Expected vs actual for every pinned runtime dimension."""
    expected = {"torch": scorer.RUNTIME["torch"], "cuda": scorer.RUNTIME["cuda"],
                "capability": scorer.RUNTIME["capability"], **{
                    name: scorer.RUNTIME[name] for name in RUNTIME_PACKAGES}}
    diff = {}
    for key, want in expected.items():
        got = snapshot.get(key)
        diff[key] = (want, got, got == want)
    return diff


def check_assets(model_path: str) -> dict:
    """Verify the prepared directory exactly like the per-call scorer gate."""
    try:
        scorer.verify_assets(model_path)
        return {"path": model_path, "ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"path": model_path, "ok": False, "error": str(exc)}


def check_ready(model_path: str | None = None) -> dict:
    """Full readiness report: assets, runtime and enabling environment."""
    model_path = model_path or os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", "")
    assets = check_assets(model_path) if model_path else {
        "path": "", "ok": False, "error": "evidence_model_path_not_set"}
    snapshot = _runtime_snapshot()
    diff = {key: {"expected": want, "actual": got, "matches": ok}
            for key, (want, got, ok) in runtime_diff(snapshot).items()}
    env = {
        "DOCATLAS_EXPERIMENT_PAIRED_QWEN": os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_QWEN", ""),
        "DOCATLAS_EXPERIMENT_QWEN_STUDY": os.environ.get("DOCATLAS_EXPERIMENT_QWEN_STUDY", ""),
        "DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE": os.environ.get("DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE", ""),
        "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": os.environ.get("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", ""),
    }
    return {
        "model_id": scorer.MODEL_ID,
        "revision": scorer.REVISION,
        "contract_sha256": scorer.CONTRACT_SHA256,
        "assets": assets,
        "runtime": snapshot,
        "runtime_diff": diff,
        "environment": env,
        "ready": bool(assets["ok"] and all(row["matches"] for row in diff.values())),
    }
