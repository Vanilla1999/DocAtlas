"""FastEmbed-backed local embeddings provider (dense + optional sparse)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import EmbeddingsCache, EmbeddingsProvider, SparseEmbeddings

if TYPE_CHECKING:
    from docmancer.core.config import EmbeddingsConfig

logger = logging.getLogger(__name__)


def _fastembed_cache_dir() -> str | None:
    override = os.environ.get("DOCMANCER_FASTEMBED_CACHE_DIR")
    if override:
        return str(Path(override).expanduser())
    return str(Path.home() / ".docmancer" / "models")


class FastEmbedProvider(EmbeddingsProvider):
    """Local dense embeddings via FastEmbed.

    Sparse SPLADE is loaded lazily on first ``embed_sparse`` call so the
    dense-only path stays cheap.
    """

    name = "fastembed"

    def __init__(self, config: "EmbeddingsConfig") -> None:
        self._config = config
        self.model_name = config.model
        self.dimensions = int(config.dimensions or 768)
        self.max_batch_size = int(getattr(config, "batch_size", 64) or 64)
        self._dense: Any | None = None
        self._sparse: Any | None = None
        self.cache = EmbeddingsCache(config.cache)

    def _ensure_dense(self) -> Any:
        if self._dense is None:
            try:
                from fastembed import TextEmbedding  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "fastembed is required for the FastEmbed provider; "
                    "reinstall docmancer; this dependency ships in core."
                ) from exc
            self._dense = TextEmbedding(model_name=self.model_name, cache_dir=_fastembed_cache_dir())
        return self._dense

    def _ensure_sparse(self) -> Any:
        if self._sparse is None:
            try:
                from fastembed import SparseTextEmbedding  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "fastembed[sparse] / SparseTextEmbedding is required for sparse embeddings"
                ) from exc
            model = self._config.sparse_model or "prithivida/Splade_PP_en_v1"
            self._sparse = SparseTextEmbedding(model_name=model, cache_dir=_fastembed_cache_dir())
        return self._sparse

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_dense()
        # FastEmbed's TextEmbedding.embed returns a generator of numpy arrays.
        return [list(map(float, v)) for v in model.embed(texts, batch_size=self.max_batch_size)]

    def embed_query(self, query: str) -> list[float]:
        model = self._ensure_dense()
        # Some FastEmbed models have a dedicated query_embed for prefix tokens.
        if hasattr(model, "query_embed"):
            for vec in model.query_embed([query]):
                return [float(x) for x in vec]
        return self.embed([query])[0]

    def embed_sparse(self, texts: list[str]) -> list[SparseEmbeddings]:
        if not texts:
            return []
        model = self._ensure_sparse()
        out: list[SparseEmbeddings] = []
        for raw in model.embed(texts, batch_size=self.max_batch_size):
            indices = [int(i) for i in getattr(raw, "indices", [])]
            values = [float(v) for v in getattr(raw, "values", [])]
            out.append(SparseEmbeddings(indices=indices, values=values))
        return out

    def embed_sparse_query(self, query: str) -> SparseEmbeddings:
        model = self._ensure_sparse()
        emb_iter = (
            model.query_embed([query]) if hasattr(model, "query_embed") else model.embed([query])
        )
        for raw in emb_iter:
            return SparseEmbeddings(
                indices=[int(i) for i in getattr(raw, "indices", [])],
                values=[float(v) for v in getattr(raw, "values", [])],
            )
        return SparseEmbeddings(indices=[], values=[])

    def health_check(self) -> bool:
        try:
            self._ensure_dense()
            return True
        except Exception:
            return False
