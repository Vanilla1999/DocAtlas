"""Filesystem layout for the local MCP runtime."""
from __future__ import annotations

import os
from pathlib import Path

from docmancer.core.product_identity import (
    docatlas_home,
    ensure_owned_home,
    resolve_home,
)


def mcp_dir() -> Path:
    return docatlas_home() / "mcp"


def manifest_path() -> Path:
    return mcp_dir() / "manifest.json"


def config_path() -> Path:
    return mcp_dir() / "config.json"


def calls_log_path() -> Path:
    return mcp_dir() / "calls.jsonl"


def idempotency_db_path() -> Path:
    return mcp_dir() / "idempotency.db"


def servers_dir() -> Path:
    return docatlas_home() / "servers"


def registry_dir() -> Path:
    """Default local registry root under the DocAtlas machine-state home."""
    override = os.environ.get("DOCATLAS_REGISTRY_DIR")
    if override:
        return Path(override).expanduser()
    return docatlas_home() / "registry"


def _validate_pack_component(value: str, *, kind: str) -> str:
    """Reject pack/version components that could escape the storage root.

    Path-traversal segments (`..`), backslashes, NULs, and absolute paths would let
    `package_dir()` resolve outside the managed servers root, which a later
    `uninstall_package()` would remove recursively. Forward slashes are allowed for
    npm-style scoped names (`@scope/pkg`); the resolve+containment check below
    catches anything that still escapes.
    """
    if not value or value.strip() != value:
        raise ValueError(f"invalid pack {kind}: empty or whitespace-padded")
    if "\x00" in value or "\\" in value:
        raise ValueError(f"invalid pack {kind}: forbidden character in {value!r}")
    if value.startswith("/"):
        raise ValueError(f"invalid pack {kind}: absolute path in {value!r}")
    parts = value.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"invalid pack {kind}: path traversal in {value!r}")
    if kind == "version" and value.startswith("@"):
        raise ValueError(f"invalid pack {kind}: leading @ in {value!r}")
    return value


def package_dir(package: str, version: str) -> Path:
    _validate_pack_component(package, kind="package")
    _validate_pack_component(version, kind="version")
    root = servers_dir().resolve()
    candidate = (root / f"{package}@{version}").resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(
            f"resolved pack path {candidate} escapes servers root {root}"
        )
    return candidate


def secrets_dir() -> Path:
    return docatlas_home() / "secrets"


def secrets_env_file(package: str) -> Path:
    _validate_pack_component(package, kind="package")
    root = secrets_dir().resolve()
    candidate = (root / f"{package}.env").resolve()
    if root not in candidate.parents:
        raise ValueError(
            f"resolved secrets path {candidate} escapes secrets root {root}"
        )
    return candidate


def ensure_dirs() -> None:
    resolution = resolve_home()
    root = ensure_owned_home(resolution.path)
    (root / "mcp").mkdir(parents=True, exist_ok=True)
    (root / "servers").mkdir(parents=True, exist_ok=True)
    registry_override = os.environ.get("DOCATLAS_REGISTRY_DIR")
    registry = Path(registry_override).expanduser() if registry_override else root / "registry"
    registry.mkdir(parents=True, exist_ok=True)
