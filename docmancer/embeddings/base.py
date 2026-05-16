from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from docmancer.core.config import EmbeddingsConfig

logger = logging.getLogger(__name__)


@dataclass
class SparseEmbeddings:
    """Sparse vector in Qdrant-friendly shape: maps index -> weight."""

    indices: list[int]
    values: list[float]

    def as_dict(self) -> dict[int, float]:
        return dict(zip(self.indices, self.values))


class EmbeddingsProvider(ABC):
    """Abstract base for dense (and optionally sparse) embedding providers."""

    name: str = "abstract"
    dimensions: int = 0
    max_batch_size: int = 32

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""

    def embed_sparse(self, texts: list[str]) -> list[SparseEmbeddings]:  # pragma: no cover - default
        raise NotImplementedError("sparse embeddings not supported by this provider")

    def embed_sparse_query(self, query: str) -> SparseEmbeddings:  # pragma: no cover - default
        raise NotImplementedError("sparse embeddings not supported by this provider")

    def health_check(self) -> bool:
        return True


def content_cache_key(provider: str, model: str, text: str) -> str:
    h = hashlib.sha256()
    h.update(provider.encode("utf-8"))
    h.update(b"\0")
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class EmbeddingsCache:
    """Content-hash-keyed on-disk cache for dense embeddings.

    Each entry is one binary file ``<key>.f32`` containing little-endian
    float32s; tiny metadata sidecar tracks the model name. Re-ingesting
    unchanged content is a no-op cache hit. Sparse vectors are not cached
    here: SPLADE outputs are small enough that recomputing on rare queries
    is cheaper than the bookkeeping.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        env_override = os.environ.get("DOCMANCER_FASTEMBED_CACHE_DIR")
        # The fastembed cache dir is the model cache for FastEmbed; here we
        # use it only as a hint for where embeddings cache should live when
        # the caller passed no explicit path. The embeddings cache is keyed
        # separately to keep model files and per-chunk vectors apart.
        base = Path(env_override).expanduser() / "embeddings" if env_override else Path(cache_dir).expanduser()
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base / f"{key[:2]}/{key}.f32"

    def get(self, key: str) -> list[float] | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = p.read_bytes()
        except OSError:
            return None
        if len(data) % 4 != 0:
            return None
        n = len(data) // 4
        return list(struct.unpack(f"<{n}f", data))

    def put(self, key: str, vector: list[float]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".f32.tmp")
        tmp.write_bytes(struct.pack(f"<{len(vector)}f", *vector))
        tmp.replace(p)


def embed_with_cache(
    provider: EmbeddingsProvider,
    texts: list[str],
    *,
    cache: EmbeddingsCache | None,
    model: str | None = None,
    progress_callback=None,
) -> list[list[float]]:
    """Embed ``texts``, satisfying cache hits and only calling the provider for misses."""
    if cache is None:
        return provider.embed(texts)
    model_name = model or provider.name
    keys = [content_cache_key(provider.name, model_name, t) for t in texts]
    vectors: list[list[float] | None] = [cache.get(k) for k in keys]
    miss_idx = [i for i, v in enumerate(vectors) if v is None]
    if miss_idx:
        miss_texts = [texts[i] for i in miss_idx]
        computed: list[list[float]] = []
        bs = max(1, provider.max_batch_size)
        for start in range(0, len(miss_texts), bs):
            computed.extend(provider.embed(miss_texts[start : start + bs]))
            if progress_callback is not None:
                progress_callback(min(start + bs, len(miss_texts)), len(miss_texts))
        for i, vec in zip(miss_idx, computed):
            vectors[i] = vec
            cache.put(keys[i], vec)
    return [v for v in vectors if v is not None]


__all__ = [
    "EmbeddingsProvider",
    "SparseEmbeddings",
    "EmbeddingsCache",
    "content_cache_key",
    "embed_with_cache",
]
