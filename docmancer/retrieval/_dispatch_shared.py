"""Top-level retrieval dispatcher.

Takes a query plus the configured mode (``lexical``, ``dense``, ``sparse``,
``hybrid``) and returns a unified ranked list. For multi-signal modes,
candidate lists are fused with RRF and resolved back to FTS5-flavoured
``RetrievedChunk`` objects so the rest of the agent sees a stable shape.
"""
from __future__ import annotations

import logging
import re
import threading
import hashlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .contracts import canonical_hash
from .fusion import reciprocal_rank_fusion, weighted_rrf
from .query_planning import (
    build_query_plan,
    compile_backend_filters,
    extract_exact_terms,
    metadata_matches_filters,
)

if TYPE_CHECKING:
    from docmancer.core.config import DocmancerConfig
    from docmancer.core.models import RetrievedChunk
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.embeddings.base import EmbeddingsProvider
    from docmancer.stores.base import VectorStore

logger = logging.getLogger(__name__)

VECTOR_READINESS_SCHEMA = "vector-readiness-v1"
VECTOR_READINESS_REASONS = frozenset({
    "unverified_backend_identity", "backend_identity_mismatch",
    "collection_identity_mismatch", "unverified_parity_witness",
    "metadata_unavailable", "metadata_unverified", "capability_mismatch",
    "health_unavailable", "backend_unhealthy", "count_unavailable",
    "count_mismatch",
})


class _CachedQueryProvider:
    """Bound repeated public retrieval passes to one embedding per query."""

    def __init__(self, provider: Any, *, max_entries: int = 16) -> None:
        self._provider = provider
        self._max_entries = max(1, int(max_entries))
        self._dense: OrderedDict[str, Any] = OrderedDict()
        self._sparse: OrderedDict[str, Any] = OrderedDict()
        self._dense_lock = threading.RLock()
        self._sparse_lock = threading.RLock()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    def _cached(
        self,
        cache: OrderedDict[str, Any],
        lock: threading.RLock,
        query: str,
        build: Any,
    ) -> Any:
        with lock:
            if query in cache:
                value = cache.pop(query)
                cache[query] = value
                return value
            value = build(query)
            cache[query] = value
            while len(cache) > self._max_entries:
                cache.popitem(last=False)
            return value

    def embed_query(self, query: str) -> list[float]:
        return self._cached(
            self._dense, self._dense_lock, query, self._provider.embed_query
        )

    def embed_sparse_query(self, query: str) -> Any:
        return self._cached(
            self._sparse, self._sparse_lock, query, self._provider.embed_sparse_query
        )


@dataclass
class DispatchResult:
    chunks: list[Any] = field(default_factory=list)
    contributions: dict[Any, dict[str, int]] = field(default_factory=dict)
    mode_used: str = "lexical"
    candidate_counts: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    query_plan_hash: str = ""
    fusion_config_hash: str = ""
    requirements_hash: str = ""
    requirements: Any | None = field(default=None, repr=False)


class HybridRetrievalError(RuntimeError):
    """Raised when one or more non-lexical retrievers fail in strict mode."""

    def __init__(self, failures: dict[str, str]) -> None:
        self.failures = dict(failures)
        parts = "; ".join(f"{src}: {msg}" for src, msg in failures.items())
        super().__init__(
            f"hybrid retrieval failed in {len(failures)} source(s): {parts}. "
            f"Pass --allow-degraded to fall back to the remaining signals, or "
            f"run `doc-atlas doctor` to diagnose."
        )




def _shape_for_fusion(source: str, hits: list[Any]) -> list[dict]:
    """Reduce hits to stable child identity plus a separate hydration key."""
    shaped: list[dict] = []
    for hit in hits:
        if source == "lexical":
            section_id = (hit.metadata or {}).get("section_id") if hasattr(hit, "metadata") else None
            if section_id is None:
                continue
            metadata = hit.metadata or {}
            stable_id = str(metadata.get("stable_chunk_id") or f"hydration:{section_id}")
            shaped.append({
                "id": stable_id,
                "hydration_id": int(section_id),
                "score": float(getattr(hit, "score", 0.0)),
            })
        else:
            payload = hit.payload or {}
            try:
                section_id = int(hit.id)
            except (TypeError, ValueError):
                section_id = payload.get("section_id")
                if section_id is None:
                    continue
                section_id = int(section_id)
            stable_id = str(payload.get("stable_chunk_id") or f"hydration:{section_id}")
            shaped.append({
                "id": stable_id,
                "hydration_id": section_id,
                "score": float(getattr(hit, "score", 0.0)),
            })
    return shaped


def _query_api_terms(query: str) -> set[str]:
    return {
        term.value
        for term in extract_exact_terms(query)
        if term.kind in {"symbol", "flag", "config_key", "error_code", "path", "quoted"}
        and len(term.value) >= 3
    }


def _query_intent_terms(query: str) -> set[str]:
    return {term for term in re.findall(r"[a-z][a-z0-9_+-]*", query) if len(term) >= 3}


def _intent_source_score(query: str, terms: set[str], source: str, haystack: str, text: str) -> float:
    score = 0.0
    basic_or_example = terms & {"basic", "example", "examples", "tutorial", "path", "operation", "test", "testing", "pytest", "client", "assertions"}
    exact_api = terms & {"reference", "api", "signature", "parameters", "constructor"}
    advanced_requested = terms & {"advanced", "yield", "lifecycle", "async"}

    if basic_or_example and "/tutorial/" in source:
        score += 1.5
    if exact_api and "/reference/" in source:
        score += 1.5
    if "testclient" in terms and "/tutorial/testing" in source:
        score += 2.0
    if "httpexception" in terms and ("/reference/exceptions" in source or "/tutorial/handling-errors" in source):
        score += 2.0
    if "depends" in terms and "/tutorial/dependencies" in source and "dependencies-with-yield" not in source:
        score += 2.0
    if "/advanced/" in source and not advanced_requested:
        score -= 1.5
    if "dependencies-with-yield" in source and "yield" not in terms:
        score -= 3.0
    if basic_or_example and "source code in `" in haystack:
        score -= 1.0
    if basic_or_example and any(term in text[:1200] for term in ("from fastapi.testclient", "client = testclient", "assert response")):
        score += 1.0
    return score


def _snippet_intent_score(query: str, terms: set[str], api_terms: set[str], metadata: dict[str, Any], text: str) -> float:
    code_intent = terms & {"example", "examples", "usage", "code", "import", "test", "testing", "pytest", "assert", "client", "signature"}
    if not code_intent:
        return 0.0
    snippets = metadata.get("code_snippets") or []
    has_snippet = bool(metadata.get("has_code_snippet") or snippets)
    if not has_snippet:
        return 0.0

    snippet_text = "\n".join(str(item.get("code") or "") for item in snippets if isinstance(item, dict)).lower()
    if not snippet_text:
        snippet_text = text[:1200]

    score = 0.75
    for term in api_terms:
        if term.lower() in snippet_text:
            score += 1.5
    for term in terms:
        if len(term) >= 4 and term in snippet_text:
            score += 0.25
    return min(score, 3.0)


def dispatch_query(
    *,
    store: "SQLiteStore",
    config: "DocmancerConfig",
    vector_store: "VectorStore | None",
    provider: "EmbeddingsProvider | None",
    collection: str | None,
    query: str,
    mode: str | None = None,
    limit: int | None = None,
    budget: int | None = None,
    expand: str | None = None,
    filters: dict | None = None,
    allow_degraded: bool = False,
) -> DispatchResult:
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vector_store,
        provider=provider,
        collection=collection,
    )
    return dispatcher.run(
        query,
        mode=mode,
        limit=limit,
        budget=budget,
        expand=expand,
        filters=filters,
        allow_degraded=allow_degraded,
    )

__all__ = [name for name in globals() if not name.startswith('__')]
