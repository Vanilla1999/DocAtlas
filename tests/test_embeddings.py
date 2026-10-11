from __future__ import annotations

import pytest

from docmancer.embeddings.base import (
    EmbeddingsCache,
    EmbeddingsProvider,
    content_cache_key,
    embed_with_cache,
)


class StubProvider(EmbeddingsProvider):
    name = "stub"
    dimensions = 4
    max_batch_size = 16

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[float(len(t)), 1.0, 2.0, 3.0] for t in texts]

    def embed_query(self, query):
        return self.embed([query])[0]





