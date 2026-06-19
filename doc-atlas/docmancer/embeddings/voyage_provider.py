"""Voyage AI embeddings provider stub.

Implementation is intentionally minimal: it wires the config and surfaces a
clear error when the optional ``voyageai`` package is missing. Filling in the
batch calls is a small mechanical step against ``voyageai.Client.embed``.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from .base import EmbeddingsProvider

if TYPE_CHECKING:
    from docmancer.core.config import EmbeddingsConfig


class VoyageProvider(EmbeddingsProvider):
    name = "voyage"

    def __init__(self, config: "EmbeddingsConfig") -> None:
        try:
            import voyageai  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "voyage embeddings require the 'embeddings-voyage' extra; "
                "install with `pip install docmancer[embeddings-voyage]`."
            ) from exc
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY environment variable is not set")
        import voyageai  # type: ignore

        self._client: Any = voyageai.Client(api_key=api_key)
        self.model_name = config.model or "voyage-3"
        self.dimensions = int(config.dimensions or 1024)
        self.max_batch_size = 128

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self.model_name, input_type="document")
        return [list(map(float, v)) for v in result.embeddings]

    def embed_query(self, query: str) -> list[float]:
        result = self._client.embed([query], model=self.model_name, input_type="query")
        return [float(x) for x in result.embeddings[0]]
