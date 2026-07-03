"""Sidecar metadata for the local vector index.

Records which embedder built each Qdrant collection so docmancer can refuse
ingest / query against an index built with a different model. Without this
sidecar, a default-model bump (or a stale collection from a previous install)
silently produces dimension mismatches that fail silently inside Qdrant and
surface as empty / nonsense search results.

Schema (``~/.docmancer/index-meta.json``)::

    {
      "version": 1,
      "collections": {
        "<collection_name>": {
          "provider": "fastembed",
          "model": "BAAI/bge-small-en-v1.5",
          "dim": 384,
          "sparse_model": "prithivida/Splade_PP_en_v1",
          "created_at": "2026-05-16T20:11:00+00:00"
        }
      }
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CollectionMeta:
    provider: str
    model: str
    dim: int
    sparse_model: str | None
    created_at: str


class IndexMismatchError(RuntimeError):
    """Raised when the configured embedder does not match the persisted one."""

    def __init__(self, collection: str, want: CollectionMeta, have: CollectionMeta) -> None:
        self.collection = collection
        self.want = want
        self.have = have
        super().__init__(self._format(collection, want, have))

    @staticmethod
    def _format(collection: str, want: CollectionMeta, have: CollectionMeta) -> str:
        diffs: list[str] = []
        if want.provider != have.provider:
            diffs.append(f"provider {have.provider!r} -> {want.provider!r}")
        if want.model != have.model:
            diffs.append(f"model {have.model!r} -> {want.model!r}")
        if want.dim != have.dim:
            diffs.append(f"dim {have.dim} -> {want.dim}")
        if (want.sparse_model or None) != (have.sparse_model or None):
            diffs.append(f"sparse_model {have.sparse_model!r} -> {want.sparse_model!r}")
        change = "; ".join(diffs) or "embedder configuration"
        return (
            f"Index {collection!r} was built with a different embedder ({change}). "
            f"Rebuild it before running queries:\n"
            f"  doc-atlas ingest <path> --recreate\n"
            f"or, to start fresh, drop docmancer state and re-ingest:\n"
            f"  doc-atlas clear --keep-config --keep-models && doc-atlas ingest <path>"
        )


def _meta_path() -> Path:
    home = os.environ.get("DOCMANCER_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".docmancer"
    return base / "index-meta.json"


def _load_raw() -> dict:
    path = _meta_path()
    if not path.exists():
        return {"version": SCHEMA_VERSION, "collections": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {"version": SCHEMA_VERSION, "collections": {}}
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("collections", {})
    return data


def _save_raw(data: dict) -> None:
    path = _meta_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
    tmp.replace(path)


def get(collection: str) -> CollectionMeta | None:
    data = _load_raw()
    entry = data.get("collections", {}).get(collection)
    if not isinstance(entry, dict):
        return None
    try:
        return CollectionMeta(
            provider=str(entry["provider"]),
            model=str(entry["model"]),
            dim=int(entry["dim"]),
            sparse_model=(str(entry["sparse_model"]) if entry.get("sparse_model") else None),
            created_at=str(entry.get("created_at") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def put(collection: str, meta: CollectionMeta) -> None:
    data = _load_raw()
    data["version"] = SCHEMA_VERSION
    collections = data.setdefault("collections", {})
    collections[collection] = asdict(meta)
    _save_raw(data)


def drop(collection: str) -> bool:
    data = _load_raw()
    collections = data.get("collections", {})
    if collection in collections:
        collections.pop(collection, None)
        _save_raw(data)
        return True
    return False


def assert_match(collection: str, want: CollectionMeta) -> CollectionMeta:
    """Read the persisted meta for ``collection``; raise if it differs.

    If no meta is persisted yet, write ``want`` and return it (first run).
    """
    have = get(collection)
    if have is None:
        put(collection, want)
        return want
    if (
        have.provider == want.provider
        and have.model == want.model
        and int(have.dim) == int(want.dim)
        and (have.sparse_model or None) == (want.sparse_model or None)
    ):
        return have
    raise IndexMismatchError(collection, want, have)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CollectionMeta",
    "IndexMismatchError",
    "assert_match",
    "drop",
    "get",
    "now_iso",
    "put",
]
