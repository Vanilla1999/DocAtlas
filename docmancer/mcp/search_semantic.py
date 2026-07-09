"""Optional semantic backend for MCP Tool Search.

This module is deliberately opt-in: lexical BM25 remains the default path for
`doc-atlas mcp serve`. Hybrid mode loads a local embedding provider only when
explicitly requested by environment.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from docmancer.mcp import paths

INDEX_SCHEMA_VERSION = 1
DEFAULT_INDEX_PATH = "tool-search-index.sqlite"


class SemanticUnavailable(RuntimeError):
    """Raised when hybrid mode was requested but semantic search cannot run."""


class EmbeddingProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class FastEmbedToolEmbeddingProvider:
    model_name: str

    @property
    def provider_id(self) -> str:
        return f"fastembed:{self.model_name}"

    def _model(self):
        try:
            from fastembed import TextEmbedding  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency is optional at runtime
            raise SemanticUnavailable("fastembed is required for DOCMANCER_MCP_SEARCH=hybrid") from exc
        cache_dir = os.environ.get("DOCMANCER_FASTEMBED_CACHE_DIR")
        return TextEmbedding(model_name=self.model_name, cache_dir=cache_dir)

    def embed_query(self, text: str) -> list[float]:
        return [float(x) for x in next(iter(self._model().query_embed(text)))]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [[float(x) for x in vector] for vector in self._model().embed(texts)]


def embedding_provider_from_env(env: Mapping[str, str] | None = None) -> EmbeddingProvider:
    source = env or os.environ
    model = source.get("DOCMANCER_MCP_EMBEDDING_MODEL")
    if not model:
        raise SemanticUnavailable(
            "Semantic search disabled; set DOCMANCER_MCP_SEARCH=hybrid and DOCMANCER_MCP_EMBEDDING_MODEL to a local FastEmbed model."
        )
    return FastEmbedToolEmbeddingProvider(model_name=model)


def index_key(entry: Any, provider_id: str) -> str:
    raw = {
        "name": entry.name,
        "package": entry.package,
        "version": entry.version,
        "operation_id": entry.operation_id,
        "search_text_sha256": hashlib.sha256(entry.search_text.encode("utf-8")).hexdigest(),
        "provider_id": provider_id,
        "index_schema": INDEX_SCHEMA_VERSION,
    }
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()


class EmbeddingCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.mcp_dir() / DEFAULT_INDEX_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tool_embeddings ("
                "cache_key TEXT PRIMARY KEY, "
                "provider_id TEXT NOT NULL, "
                "vector_json TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def get(self, key: str) -> list[float] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT vector_json FROM tool_embeddings WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        if not isinstance(value, list):
            return None
        return [float(x) for x in value]

    def put(self, key: str, provider_id: str, vector: list[float]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tool_embeddings (cache_key, provider_id, vector_json) VALUES (?, ?, ?)",
                (key, provider_id, json.dumps(vector)),
            )

    def get_or_build(self, entries: list[Any], texts: list[str], provider: EmbeddingProvider) -> list[list[float]]:
        keys = [index_key(entry, provider.provider_id) for entry in entries]
        vectors: list[list[float] | None] = [self.get(key) for key in keys]
        missing = [i for i, vector in enumerate(vectors) if vector is None]
        if missing:
            computed = provider.embed_documents([texts[i] for i in missing])
            for idx, vector in zip(missing, computed):
                as_floats = [float(x) for x in vector]
                vectors[idx] = as_floats
                self.put(keys[idx], provider.provider_id, as_floats)
        return [vector for vector in vectors if vector is not None]


class SemanticBackend:
    def __init__(self, provider: EmbeddingProvider, cache: EmbeddingCache | None = None) -> None:
        self.provider = provider
        self.cache = cache or EmbeddingCache()

    def search(self, query: str, candidates: list[Any], *, limit: int):
        from docmancer.mcp.search import SearchHit

        if not query or not candidates:
            return []
        query_vector = self.provider.embed_query(query)
        texts = [entry.search_text for entry in candidates]
        doc_vectors = self.cache.get_or_build(candidates, texts, self.provider)
        hits: list[SearchHit] = []
        for entry, vector in zip(candidates, doc_vectors):
            score = cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            hits.append(SearchHit(entry=entry, score=score, semantic_score=score, rank_reason=["semantic"]))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
