"""Cohere embeddings provider stub."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from .base import EmbeddingsProvider

if TYPE_CHECKING:
    from docmancer.core.config import EmbeddingsConfig


class CohereProvider(EmbeddingsProvider):
    name = "cohere"

    def __init__(self, config: "EmbeddingsConfig") -> None:
        try:
            import cohere  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "cohere embeddings require the 'embeddings-cohere' extra; "
                "install with `pip install docmancer[embeddings-cohere]`."
            ) from exc
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY environment variable is not set")
        self._client: Any = cohere.Client(api_key=api_key)
        self.model_name = config.model or "embed-english-v3.0"
        self.dimensions = int(config.dimensions or 1024)
        self.max_batch_size = 96

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embed(texts=texts, model=self.model_name, input_type="search_document")
        return [list(map(float, v)) for v in resp.embeddings]

    def embed_query(self, query: str) -> list[float]:
        resp = self._client.embed(texts=[query], model=self.model_name, input_type="search_query")
        return [float(x) for x in resp.embeddings[0]]
