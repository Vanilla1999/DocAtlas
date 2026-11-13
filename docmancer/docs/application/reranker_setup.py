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
import stat
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


def _empty_destination_identity(out: Path) -> tuple[int, int] | None:
    """Accept an absent path or a real empty directory, never a symlink."""
    try:
        current = out.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(current.st_mode):
        raise ValueError("reranker_prepare_symlink_destination")
    if not stat.S_ISDIR(current.st_mode) or any(out.iterdir()):
        raise ValueError("reranker_prepare_requires_empty_directory")
    return current.st_dev, current.st_ino


def prepare_assets(out: Path, *, timeout: float = 600.0) -> dict:
    """Verify assets in private staging, then atomically publish the directory.

    `out` must be absent or an empty real directory. No downloaded file is
    written there before verification. Failure/cancellation cleans only our
    staging directory, never the destination or files another process added.
    The parent directory must be trusted: this is not a sandbox against a
    malicious process running as the same user and changing ancestor paths.
    """
    out = Path(out).expanduser()
    if not out.is_absolute():
        raise ValueError("reranker_prepare_requires_absolute_out")
    _empty_destination_identity(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Bind an existing parent symlink once; do not resolve the final component,
    # since that would silently accept a symlink destination.
    out = out.parent.resolve(strict=True) / out.name
    destination_identity = _empty_destination_identity(out)
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.prepare-", dir=out.parent))
    stage_stat = stage.lstat()
    stage_identity = stage_stat.st_dev, stage_stat.st_ino
    published = False
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
            target = stage / f"{name}.partial"
            digest = hashlib.sha256()
            size = 0
            try:
                with _open(url, timeout=timeout) as response, target.open("xb") as stream:
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > entry["size"]:
                            raise ValueError(f"reranker_prepare_hash_mismatch:{name}")
                        stream.write(block)
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
                target.replace(stage / name)
            finally:
                target.unlink(missing_ok=True)
            manifest["files"][name] = {
                "sha256": actual,
                "bytes": size,
                "url": url,
                "remote_lfs_sha256": entry.get("lfs", {}).get("oid"),
                "remote_git_blob_sha1": entry.get("oid"),
            }
        with (stage / "provenance.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
        scorer.verify_assets(str(stage))  # The scorer's exact per-call gate.
        try:
            current_identity = _empty_destination_identity(out)
        except ValueError as exc:
            raise ValueError("reranker_prepare_destination_changed") from exc
        if current_identity != destination_identity:
            raise ValueError("reranker_prepare_destination_changed")
        # Same-filesystem directory rename publishes all verified files at once.
        # On POSIX it can replace an empty directory, but never a file, symlink
        # or nonempty directory. Files arriving after the check therefore make
        # publication fail instead of being overwritten or recursively deleted.
        stage.rename(out)
        published = True
        return manifest
    finally:
        if not published:
            try:
                current = stage.lstat()
            except FileNotFoundError:
                pass
            else:
                if (current.st_dev, current.st_ino) != stage_identity or not stat.S_ISDIR(current.st_mode):
                    raise ValueError("reranker_prepare_staging_directory_changed")
                shutil.rmtree(stage)


def _runtime_snapshot() -> dict:
    snapshot: dict = {}
    try:
        import torch

        snapshot["torch"] = torch.__version__
        snapshot["cuda"] = torch.version.cuda
        snapshot["cuda_available"] = torch.cuda.is_available()
        if snapshot["cuda_available"]:
            snapshot["capability"] = list(torch.cuda.get_device_capability(0))
            snapshot["gpu"] = torch.cuda.get_device_name(0)
        else:
            snapshot["capability"] = None
            snapshot["gpu"] = None
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


def _profile_report() -> dict:
    try:
        from .experimental_qwen_profile import configured_profile

        return {"valid": True, "error": None, **configured_profile()}
    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "error": str(exc), "native_budget": None,
                "request_binding": "not_checked"}


def _readiness_issues(assets: dict, configured_assets: dict | None, snapshot: dict,
                      diff: dict, profile: dict) -> list[dict]:
    issues = []

    def issue(code: str, component: str, message: str, action: str) -> None:
        issues.append({"code": code, "component": component, "message": message, "action": action})

    for label, item in (("checked assets", assets), ("enabled process assets", configured_assets)):
        if item is None or item["ok"] or (label == "enabled process assets" and item == assets):
            continue
        if not item["path"]:
            issue("RERANKER_ASSET_PATH_NOT_SET", "assets", f"{label}: {item['error']}",
                  "Prepare an absolute model directory with `doc-atlas reranker prepare DIR`; "
                  "set DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH in the MCP server environment.")
        else:
            issue("RERANKER_ASSETS_INVALID", "assets", f"{label}: {item['error']}",
                  "Inspect this directory and the reported integrity error; prepare a new absolute "
                  "directory if necessary. Do not delete existing assets or reinstall torch to repair model files.")
    capability = snapshot.get("capability")
    if capability is not None and capability != scorer.RUNTIME["capability"]:
        issue("RERANKER_GPU_UNSUPPORTED", "hardware",
              f"CUDA device 0 capability {capability} does not match {scorer.RUNTIME['capability']}.",
              "Select a supported CUDA device in the server environment or disable the Qwen profile. "
              "Installing a different torch package cannot change GPU capability.")
    elif snapshot.get("cuda_available") is False:
        issue("RERANKER_CUDA_UNAVAILABLE", "hardware", "CUDA is unavailable to this process.",
              "Check GPU visibility and drivers on a supported CUDA machine; otherwise use the lexical default.")
    dependencies = [key for key in ("torch", "cuda", *RUNTIME_PACKAGES) if not diff[key]["matches"]]
    if dependencies:
        issue("RERANKER_RUNTIME_MISMATCH", "runtime_dependencies",
              "Pinned package/build mismatches: " + ", ".join(dependencies),
              "Install the exact pinned GPU dependencies into the same environment that runs doc-atlas; "
              "see the pinned installation recipe in wiki/Reranker.md.")
    if snapshot.get("error"):
        issue("RERANKER_RUNTIME_CHECK_FAILED", "runtime", snapshot["error"],
              "Resolve the import or device error in this process's tool environment, then rerun the check.")
    if not profile["valid"]:
        issue("RERANKER_PROFILE_INVALID", "profile", profile["error"],
              "Correct the reported shared selector guard in the MCP server environment. "
              "Use one documented profile, rerun this check with that same environment, and restart the server.")
    return issues


def check_ready(model_path: str | None = None) -> dict:
    """Preflight this process, not a client config, model load or inference.

    A disabled, compatible installation can pass before opt-in. An enabled
    profile must also have valid assets at its actual configured model path,
    even when MODEL_PATH explicitly asks to inspect a different directory.
    """
    enabled = os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_QWEN") == "1"
    configured_path = os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", "")
    model_path = model_path or configured_path
    assets = check_assets(model_path) if model_path else {
        "path": "", "ok": False, "error": "evidence_model_path_not_set"}
    configured_assets = None
    if enabled:
        configured_assets = assets if configured_path == model_path else (
            check_assets(configured_path) if configured_path else {
                "path": "", "ok": False, "error": "evidence_model_path_not_set"})
    snapshot = _runtime_snapshot()
    diff = {key: {"expected": want, "actual": got, "matches": ok}
            for key, (want, got, ok) in runtime_diff(snapshot).items()}
    profile = _profile_report()
    env = {name: os.environ.get(name) for name in (
        "DOCATLAS_EXPERIMENT_PAIRED_QWEN", "DOCATLAS_EXPERIMENT_QWEN_STUDY",
        "DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE", "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT",
        "DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", "DOCATLAS_EXPERIMENT_PAIRED_CACHE",
        "DOCATLAS_EXPERIMENT_QWEN_STUDY_PRUNING", "DOCATLAS_EXPERIMENT_QWEN_STUDY_UNITS",
        "DOCATLAS_EXPERIMENT_QWEN_STUDY_UNIT_GUARD", "DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS",
        "DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS", "DOCATLAS_EXPERIMENT_POOL_PRUNE",
        "DOCATLAS_EXPERIMENT_JOINT_TERMS", "DOCATLAS_EXPERIMENT_JOINT_PRIORITY",
        "DOCATLAS_EXPERIMENT_JOINT_FUSION", "DOCATLAS_EXPERIMENT_JOINT_CUT",
        "DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "DOCATLAS_CONTEXT_COMPRESSION",
        "DOCATLAS_MINILM_MODEL_DIR", "CUDA_VISIBLE_DEVICES",
    )}
    assets_ready = bool(assets["ok"] and (configured_assets is None or configured_assets["ok"]))
    runtime_compatible = bool(not snapshot.get("error") and all(row["matches"] for row in diff.values()))
    return {
        "schema_version": 2,
        "model_id": scorer.MODEL_ID,
        "revision": scorer.REVISION,
        "contract_sha256": scorer.CONTRACT_SHA256,
        "assets": assets,
        "configured_assets": configured_assets,
        "assets_ready": assets_ready,
        "runtime": snapshot,
        "runtime_diff": diff,
        "runtime_compatible": runtime_compatible,
        "profile": profile,
        "profile_valid": profile["valid"],
        "enabled": enabled,
        "inference_checked": False,
        "environment_scope": "current_process",
        "environment": env,
        "check_scope": "Asset integrity, pinned package/GPU compatibility and shared selector configuration only; "
                       "no model load, forward, future request binding or client-config inspection.",
        "issues": _readiness_issues(assets, configured_assets, snapshot, diff, profile),
        "ready": bool(assets_ready and runtime_compatible and profile["valid"]),
    }
