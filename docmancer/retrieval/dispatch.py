"""Top-level retrieval dispatcher.

Takes a query plus the configured mode (``lexical``, ``dense``, ``sparse``,
``hybrid``) and returns a unified ranked list. For multi-signal modes,
candidate lists are fused with RRF and resolved back to FTS5-flavoured
``RetrievedChunk`` objects so the rest of the agent sees a stable shape.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
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


@dataclass
class DispatchResult:
    chunks: list[Any] = field(default_factory=list)
    contributions: dict[Any, dict[str, int]] = field(default_factory=dict)
    mode_used: str = "lexical"
    candidate_counts: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    query_plan_hash: str = ""
    fusion_config_hash: str = ""


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


class RetrievalDispatcher:
    """Coordinator for lexical / dense / sparse / hybrid retrieval."""

    def __init__(
        self,
        *,
        store: "SQLiteStore",
        config: "DocmancerConfig",
        vector_store: "VectorStore | None" = None,
        provider: "EmbeddingsProvider | None" = None,
        collection: str | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.vector_store = vector_store
        self.provider = provider
        self.collection = collection
        self._auto_hierarchical_cache: bool | None = None

    def run(
        self,
        query: str,
        *,
        mode: str | None = None,
        limit: int | None = None,
        budget: int | None = None,
        expand: str | None = None,
        filters: dict | None = None,
        allow_degraded: bool = False,
    ) -> DispatchResult:
        configured_mode = getattr(getattr(self.config, "retrieval", None), "default_mode", None)
        effective_mode = (
            mode
            or (configured_mode if isinstance(configured_mode, str) else None)
            or "lexical"
        ).lower()
        limit = min(40, limit or self.config.query.default_limit)
        budget = budget or self.config.query.default_budget
        per_source_limit = min(40, max(limit * 3, 20))

        # Query-aware routing: first matching router merges its filters into
        # the dispatcher's filters for this call (e.g. ``status_code=LIVE``,
        # ``international_class=030``).
        merged_filters = self._apply_router(query, filters)
        backend_filters = compile_backend_filters(merged_filters) or None
        requested_lanes = (
            ("lexical", "dense", "sparse")
            if effective_mode == "hybrid"
            else (effective_mode,)
        )
        query_plan = build_query_plan(
            query, filters=merged_filters, requested_lanes=requested_lanes
        )
        # Effective expand: per-call > retrieval.expand > query.default_expand.
        retrieval_expand = (
            expand
            or getattr(self.config.retrieval, "expand", None)
            or self.config.query.default_expand
        )
        fusion_config_hash = canonical_hash({
            "schema_version": "stable-child-rrf-v1",
            "method": self.config.retrieval.fusion.method or "rrf",
            "rrf_k": int(self.config.retrieval.fusion.rrf_k or 60),
            "weights": dict(self.config.retrieval.fusion.weights or {}),
            "candidate_limits": {"per_lane": 40, "fused": 60},
            "post_fusion": {
                "exact_supplement": "api-term-supplement-v2",
                "intent_rerank": "intent-metadata-rerank-v2",
                "expand": retrieval_expand,
                "max_sections_per_source": getattr(
                    self.config.retrieval, "max_sections_per_source", None
                ),
            },
        })

        def finalized(result: DispatchResult) -> DispatchResult:
            result.query_plan_hash = query_plan.plan_hash
            result.fusion_config_hash = fusion_config_hash
            for final_rank, chunk in enumerate(result.chunks, start=1):
                metadata = getattr(chunk, "metadata", None)
                if isinstance(metadata, dict):
                    metadata["query_plan_hash"] = query_plan.plan_hash
                    metadata["fusion_config_hash"] = fusion_config_hash
                    section_id = metadata.get("section_id")
                    metadata["retrieval_trace"] = {
                        "component_ranks": dict(result.contributions.get(section_id, {})),
                        "pre_post_rank": metadata.pop("_pre_post_rank", final_rank),
                        "intent_boost": metadata.pop("_intent_boost", 0.0),
                        "supplemental_rank": metadata.pop("_supplemental_rank", None),
                        "final_rank": final_rank,
                    }
            return result

        missing_capabilities: dict[str, str] = {}
        if effective_mode != "lexical":
            if self.vector_store is None:
                missing_capabilities["vector"] = "vector store is not configured"
            if self.provider is None:
                missing_capabilities["embedding"] = "embedding provider is not configured"
        if missing_capabilities and not allow_degraded:
            raise HybridRetrievalError(missing_capabilities)

        if effective_mode == "lexical" or missing_capabilities:
            query_limit = self._candidate_limit_for_diversity(limit, retrieval_expand)
            chunks = self.store.query(query, limit=query_limit, budget=budget, expand=retrieval_expand, filters=backend_filters)
            chunks = self._filter_chunks(chunks, merged_filters)
            chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=retrieval_expand, backend_filters=backend_filters, verification_filters=merged_filters)
            chunks = self._rerank_intent_matches(query, chunks, expand=retrieval_expand)
            chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
            return finalized(DispatchResult(
                chunks=chunks,
                contributions={c.metadata.get("section_id"): {"lexical": idx + 1} for idx, c in enumerate(chunks) if c.metadata.get("section_id") is not None},
                mode_used=(
                    "lexical"
                    if effective_mode == "lexical"
                    else f"{effective_mode}/lexical_fallback_degraded"
                ),
                candidate_counts={"lexical": len(chunks)},
                failures=missing_capabilities,
            ))

        ready_failure = self._vector_readiness_failure(effective_mode)
        if ready_failure and not allow_degraded:
            raise HybridRetrievalError(ready_failure)
        if ready_failure:
            query_limit = self._candidate_limit_for_diversity(limit, retrieval_expand)
            chunks = self.store.query(query, limit=query_limit, budget=budget, expand=retrieval_expand, filters=backend_filters)
            chunks = self._filter_chunks(chunks, merged_filters)
            chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=retrieval_expand, backend_filters=backend_filters, verification_filters=merged_filters)
            chunks = self._rerank_intent_matches(query, chunks, expand=retrieval_expand)
            chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
            return finalized(DispatchResult(
                chunks=chunks,
                contributions={c.metadata.get("section_id"): {"lexical": idx + 1} for idx, c in enumerate(chunks) if c.metadata.get("section_id") is not None},
                mode_used=f"{effective_mode}/lexical_fallback_degraded",
                candidate_counts={"lexical": len(chunks)},
                failures=ready_failure,
            ))

        hierarchical = getattr(self.config.retrieval, "hierarchical", None)
        if hierarchical is not None and self._hierarchical_active(hierarchical):
            return finalized(self._run_hierarchical(
                query=query,
                mode=effective_mode,
                limit=limit,
                budget=budget,
                filters=merged_filters,
                expand=retrieval_expand,
                allow_degraded=allow_degraded,
            ))

        candidate_lists, raw_counts, failures = self._fan_out(
            query=query,
            mode=effective_mode,
            per_source_limit=per_source_limit,
            filters=backend_filters,
            verification_filters=merged_filters,
        )

        if failures and effective_mode != "lexical" and not allow_degraded:
            raise HybridRetrievalError(failures)

        if not candidate_lists:
            if not failures:
                return finalized(DispatchResult(
                    chunks=[],
                    mode_used=effective_mode,
                    candidate_counts=raw_counts,
                ))
            query_limit = self._candidate_limit_for_diversity(limit, retrieval_expand)
            chunks = self.store.query(query, limit=query_limit, budget=budget, expand=retrieval_expand, filters=backend_filters)
            chunks = self._filter_chunks(chunks, merged_filters)
            chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=retrieval_expand, backend_filters=backend_filters, verification_filters=merged_filters)
            chunks = self._rerank_intent_matches(query, chunks, expand=retrieval_expand)
            chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
            return finalized(DispatchResult(
                chunks=chunks,
                mode_used=f"{effective_mode}/lexical_fallback_degraded",
                candidate_counts=raw_counts,
                failures=failures,
            ))

        ranked = self._rank_candidate_lists(candidate_lists)[:60]
        hydration_by_stable = self._hydration_by_stable(candidate_lists)
        section_ids = self._top_section_ids(
            ranked,
            hydration_by_stable=hydration_by_stable,
            limit=self._candidate_limit_for_diversity(limit, retrieval_expand),
        )
        contributions = {
            hydration_by_stable[stable_id]: dict(component_ranks)
            for stable_id, _score, component_ranks in ranked
            if stable_id in hydration_by_stable
            and hydration_by_stable[stable_id] in section_ids
        }

        # Neighbor expansion in hybrid mode: pull adjacent section ids before
        # hydrate. Lexical mode handles this inside ``SQLiteStore.query``;
        # we replicate the effect here so hybrid hits feel as well-cited.
        if (retrieval_expand or "").lower() in {"adjacent", "page"}:
            section_ids = self._expand_section_ids(
                section_ids,
                mode=retrieval_expand,
                budget_cap=limit * 3,
            )

        chunks = self._hydrate(section_ids, budget=budget)
        chunks = self._filter_chunks(chunks, merged_filters)
        chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=retrieval_expand, backend_filters=backend_filters, verification_filters=merged_filters)
        chunks = self._rerank_intent_matches(query, chunks, expand=retrieval_expand)
        chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
        reported_mode = self._degraded_mode_name(effective_mode, candidate_lists, failures)
        return finalized(DispatchResult(
            chunks=chunks,
            contributions=contributions,
            mode_used=reported_mode,
            candidate_counts=raw_counts,
            failures=failures,
        ))

    def _hierarchical_active(self, hcfg: Any) -> bool:
        """Decide whether to run the two-stage hierarchical pass for this call.

        Explicit ``enabled=True`` always wins. Otherwise, when ``auto`` is
        on, fall back to a corpus-size heuristic: enable when the index
        contains at least ``auto_min_documents`` distinct documents. Below
        that threshold the extra round-trip costs latency without gaining
        recall (you'd select every document anyway).
        """
        if getattr(hcfg, "enabled", False):
            return True
        if not getattr(hcfg, "auto", False):
            return False
        if self._auto_hierarchical_cache is not None:
            return self._auto_hierarchical_cache
        threshold = int(getattr(hcfg, "auto_min_documents", 10))
        try:
            distinct = int(self.store.distinct_document_count())
        except Exception:
            distinct = 0
        active = distinct >= threshold
        self._auto_hierarchical_cache = active
        if active:
            logger.debug(
                "hierarchical retrieval auto-enabled (%d distinct documents >= %d)",
                distinct,
                threshold,
            )
        return active

    def _vector_readiness_failure(self, mode: str) -> dict[str, str]:
        if mode == "lexical" or self.vector_store is None or not self.collection:
            return {}
        generation_info = self.store.generation_info()
        if generation_info and str(generation_info.get("vector_collection") or "") != self.collection:
            return {
                "vector": (
                    "collection identity does not match the active SQLite generation: "
                    f"expected {generation_info.get('vector_collection')!r}, "
                    f"got {self.collection!r}"
                )
            }
        metadata: dict[str, Any] | None = None
        metadata_fn = getattr(self.vector_store, "collection_metadata", None)
        if callable(metadata_fn):
            try:
                metadata = metadata_fn(self.collection)
            except Exception as exc:
                return {"vector": f"collection metadata unavailable: {type(exc).__name__}: {exc}"}
        if not metadata:
            metadata = self._sidecar_collection_metadata()
        if not metadata:
            return {"vector": "collection capability metadata is not verified"}
        expected_provider = str(getattr(self.provider, "name", ""))
        expected_model = str(getattr(self.provider, "model_name", expected_provider))
        expected_dim = int(getattr(self.provider, "dimensions", 0) or 0)
        mismatches = []
        if str(metadata.get("provider") or "") != expected_provider:
            mismatches.append("provider")
        if str(metadata.get("model") or "") != expected_model:
            mismatches.append("model")
        if expected_dim and int(metadata.get("dim") or 0) != expected_dim:
            mismatches.append("dimensions")
        if mode == "sparse" and not metadata.get("sparse_model"):
            mismatches.append("sparse_model")
        if mismatches:
            return {"vector": "collection capability mismatch: " + ", ".join(mismatches)}
        count_fn = getattr(self.vector_store, "count", None)
        if not callable(count_fn):
            return {}
        try:
            points = int(count_fn(self.collection))
        except Exception as exc:
            return {"vector": f"{type(exc).__name__}: {exc}"}
        if points <= 0:
            return {"vector": f"collection {self.collection!r} has no indexed vectors"}
        if generation_info:
            generation_id = str(generation_info.get("generation_id") or "")
            expected = len(self.store.list_sections_for_embedding(generation_id))
            if points != expected:
                return {
                    "vector": (
                        "collection point parity does not match the active SQLite generation: "
                        f"expected {expected}, got {points}"
                    )
                }
        return {}

    def _sidecar_collection_metadata(self) -> dict[str, Any]:
        if not self.collection:
            return {}
        try:
            from docmancer.core import index_meta

            metadata = index_meta.get(self.collection)
        except Exception:
            return {}
        if metadata is None:
            return {}
        return {
            "provider": metadata.provider,
            "model": metadata.model,
            "dim": metadata.dim,
            "sparse_model": metadata.sparse_model,
        }

    # ------------------ hierarchical retrieval ------------------

    def _run_hierarchical(
        self,
        *,
        query: str,
        mode: str,
        limit: int,
        budget: int,
        filters: dict | None,
        expand: str | None,
        allow_degraded: bool = False,
    ) -> DispatchResult:
        """Two-stage retrieval: top documents first, then top sections inside them."""
        hcfg = self.config.retrieval.hierarchical
        candidate_pool = min(40, int(hcfg.candidate_pool))
        backend_filters = compile_backend_filters(filters) or None
        ready_failure = self._vector_readiness_failure(mode)
        if ready_failure and not allow_degraded:
            raise HybridRetrievalError(ready_failure)

        # Stage 1: cast a wide net and aggregate by document_title_hash.
        stage1_candidates, stage1_counts, stage1_failures = self._fan_out(
            query=query,
            mode=mode,
            per_source_limit=candidate_pool,
            filters=backend_filters,
            verification_filters=filters,
        )
        if stage1_failures and mode != "lexical" and not allow_degraded:
            raise HybridRetrievalError(stage1_failures)
        if not stage1_candidates:
            if not stage1_failures:
                return DispatchResult(
                    chunks=[],
                    mode_used=mode,
                    candidate_counts=stage1_counts,
                )
            query_limit = self._candidate_limit_for_diversity(limit, expand)
            chunks = self.store.query(query, limit=query_limit, budget=budget, expand=expand, filters=backend_filters)
            chunks = self._filter_chunks(chunks, filters)
            chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=expand, backend_filters=backend_filters, verification_filters=filters)
            chunks = self._rerank_intent_matches(query, chunks, expand=expand)
            chunks = self._limit_sections_per_source(chunks, limit=limit, expand=expand)
            return DispatchResult(
                chunks=chunks,
                mode_used=f"{mode}/lexical_fallback_degraded",
                candidate_counts=stage1_counts,
                failures=stage1_failures,
            )

        doc_scores: dict[str, float] = {}
        for source, shaped in stage1_candidates.items():
            payload_lookup = self._payload_lookup_for(source, shaped)
            for rank, hit in enumerate(shaped, start=1):
                sid = int(hit["hydration_id"])
                doc_hash = payload_lookup.get(sid, "")
                if not doc_hash:
                    continue
                doc_scores[doc_hash] = doc_scores.get(doc_hash, 0.0) + 1.0 / (60 + rank)

        if not doc_scores:
            # No payloads carry document_title_hash (e.g. mixed corpus where
            # only some loaders set it). Fall through to a flat fusion.
            return self._fuse_and_hydrate(
                stage1_candidates, query=query, limit=limit, budget=budget,
                expand=expand, counts=stage1_counts, mode=mode, filters=filters,
                failures=stage1_failures,
            )

        top_docs = [h for h, _ in sorted(doc_scores.items(), key=lambda kv: kv[1], reverse=True)[: hcfg.documents_limit]]

        # Stage 2: re-retrieve dense + sparse filtered to those documents.
        stage2_filters = dict(filters or {})
        stage2_filters["document_title_hash"] = {"in": top_docs}
        stage2_candidates, stage2_counts, stage2_failures = self._fan_out(
            query=query,
            mode=mode,
            per_source_limit=min(
                40, max(limit * 3, hcfg.sections_per_document * hcfg.documents_limit)
            ),
            filters=compile_backend_filters(stage2_filters),
            verification_filters=stage2_filters,
        )
        if stage2_failures and mode != "lexical" and not allow_degraded:
            raise HybridRetrievalError(stage2_failures)
        combined_failures = {
            **stage1_failures,
            **{f"{key}.stage2": value for key, value in stage2_failures.items()},
        }
        if not stage2_candidates:
            return self._fuse_and_hydrate(
                stage1_candidates, query=query, limit=limit, budget=budget,
                expand=expand, counts=stage1_counts, mode=mode, filters=filters,
                failures=combined_failures,
            )
        return self._fuse_and_hydrate(
            stage2_candidates,
            query=query,
            limit=limit,
            budget=budget,
            expand=expand,
            counts={**stage1_counts, **{f"{k}.stage2": v for k, v in stage2_counts.items()}},
            mode=f"{mode}/hierarchical",
            filters=stage2_filters,
            failures=combined_failures,
        )

    def _fuse_and_hydrate(
        self,
        candidate_lists: dict[str, list[Any]],
        *,
        query: str,
        limit: int,
        budget: int,
        expand: str | None,
        counts: dict[str, int],
        mode: str,
        filters: dict | None,
        failures: dict[str, str] | None = None,
    ) -> DispatchResult:
        failures = dict(failures or {})
        ranked = self._rank_candidate_lists(candidate_lists)[:60]
        hydration_by_stable = self._hydration_by_stable(candidate_lists)
        section_ids = self._top_section_ids(
            ranked,
            hydration_by_stable=hydration_by_stable,
            limit=self._candidate_limit_for_diversity(limit, expand),
        )
        contributions = {
            hydration_by_stable[stable_id]: dict(component_ranks)
            for stable_id, _score, component_ranks in ranked
            if stable_id in hydration_by_stable
            and hydration_by_stable[stable_id] in section_ids
        }
        if (expand or "").lower() in {"adjacent", "page"}:
            section_ids = self._expand_section_ids(
                section_ids, mode=expand, budget_cap=limit * 3
            )
        chunks = self._hydrate(section_ids, budget=budget)
        chunks = self._filter_chunks(chunks, filters)
        chunks = self._append_api_term_matches(
            query, chunks, budget=budget, expand=expand,
            backend_filters=compile_backend_filters(filters),
            verification_filters=filters,
        )
        chunks = self._rerank_intent_matches(query, chunks, expand=expand)
        chunks = self._limit_sections_per_source(chunks, limit=limit, expand=expand)
        return DispatchResult(
            chunks=chunks,
            contributions=contributions,
            mode_used=self._degraded_mode_name(mode, candidate_lists, failures),
            candidate_counts=counts,
            failures=failures,
        )

    # ------------------ helpers ------------------

    def _apply_router(self, query: str, filters: dict | None) -> dict | None:
        """Walk ``retrieval.routers``; merge the first match's filters into ``filters``."""
        import re as _re

        routers = list(getattr(self.config.retrieval, "routers", []) or [])
        if not routers:
            return filters
        for router in routers:
            pattern = getattr(router, "match", "") or ""
            if not pattern:
                continue
            try:
                if _re.search(pattern, query, _re.IGNORECASE):
                    merged = dict(filters or {})
                    for k, v in (router.filters or {}).items():
                        merged.setdefault(k, v)
                    logger.debug("router matched: %s", getattr(router, "description", None) or pattern)
                    return merged
            except _re.error:
                logger.warning("invalid router regex skipped: %r", pattern)
                continue
        return filters

    def _rank_candidate_lists(self, candidate_lists: dict[str, list[Any]]):
        method = self.config.retrieval.fusion.method or "rrf"
        k_rrf = int(self.config.retrieval.fusion.rrf_k or 60)
        weights = dict(self.config.retrieval.fusion.weights or {})
        if method == "weighted_rrf":
            return weighted_rrf(candidate_lists, weights=weights, k_rrf=k_rrf)
        return reciprocal_rank_fusion(candidate_lists, k_rrf=k_rrf)

    @staticmethod
    def _hydration_by_stable(candidate_lists: dict[str, list[Any]]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for hits in candidate_lists.values():
            for hit in hits:
                mapping.setdefault(str(hit["id"]), int(hit["hydration_id"]))
        return mapping

    def _top_section_ids(
        self,
        ranked,
        *,
        hydration_by_stable: dict[str, int],
        limit: int,
    ) -> list[int]:
        section_ids: list[int] = []
        for stable_id, _score, _contrib in ranked:
            hydration_id = hydration_by_stable.get(str(stable_id))
            if hydration_id is None:
                continue
            section_ids.append(hydration_id)
            if len(section_ids) >= limit:
                break
        return section_ids

    def _expand_section_ids(self, section_ids: list[int], *, mode: str, budget_cap: int) -> list[int]:
        """Add adjacent or full-page section ids while preserving order."""
        if not section_ids or not hasattr(self.store, "adjacent_section_ids"):
            return section_ids
        seen: set[int] = set(section_ids)
        out: list[int] = list(section_ids)
        for sid in list(section_ids):
            try:
                neighbors = self.store.adjacent_section_ids(int(sid), mode=mode)
            except Exception:
                continue
            for nid in neighbors:
                if nid in seen:
                    continue
                seen.add(nid)
                out.append(nid)
                if len(out) >= budget_cap:
                    return out
        return out

    def _payload_lookup_for(self, source: str, shaped: list[dict]) -> dict[int, str]:
        """Return ``{section_id: document_title_hash}`` from this round's hits.

        Vector hits carry the hash in their payload; lexical hits don't, so
        we cross-walk the surviving section ids through SQLite for those.
        """
        out: dict[int, str] = {}
        if source == "lexical" and hasattr(self.store, "document_title_hashes_for"):
            try:
                out.update(self.store.document_title_hashes_for([int(h["hydration_id"]) for h in shaped]))
            except Exception:
                pass
            return out
        # For dense/sparse, the dispatcher only stores ``id`` + ``score`` in
        # ``shaped``; the underlying payloads have already been discarded.
        # We re-fetch payloads via SQLite metadata which mirrors the same
        # document_title_hash.
        if hasattr(self.store, "document_title_hashes_for"):
            try:
                out.update(self.store.document_title_hashes_for([int(h["hydration_id"]) for h in shaped]))
            except Exception:
                pass
        return out

    # ------------------ helpers ------------------

    def _fan_out(
        self,
        *,
        query: str,
        mode: str,
        per_source_limit: int,
        filters: dict | None,
        verification_filters: dict | None,
    ) -> tuple[dict[str, list[Any]], dict[str, int], dict[str, str]]:
        from .dense import dense_search
        from .lexical import lexical_search
        from .sparse import sparse_search

        tasks: dict[str, Any] = {}
        # Backends may score a wider internal window, but only the first
        # verified ``per_source_limit`` hits enter the candidate lane. This is
        # required for sqlite-vec, which cannot push metadata predicates down.
        vector_scoring_limit = min(160, max(40, per_source_limit * 4))
        with ThreadPoolExecutor(max_workers=3) as ex:
            if mode in {"hybrid"}:
                tasks["lexical"] = ex.submit(
                    lexical_search,
                    self.store,
                    query,
                    limit=min(40, per_source_limit),
                    budget=10_000,
                    filters=filters,
                )
                tasks["dense"] = ex.submit(
                    dense_search,
                    vector_store=self.vector_store,
                    provider=self.provider,
                    collection=self.collection,
                    query=query,
                    limit=vector_scoring_limit,
                    filters=filters,
                )
                if self._sparse_supported():
                    tasks["sparse"] = ex.submit(
                        sparse_search,
                        vector_store=self.vector_store,
                        provider=self.provider,
                        collection=self.collection,
                        query=query,
                        limit=vector_scoring_limit,
                        filters=filters,
                    )
            elif mode == "dense":
                tasks["dense"] = ex.submit(
                    dense_search,
                    vector_store=self.vector_store,
                        provider=self.provider,
                        collection=self.collection,
                        query=query,
                        limit=vector_scoring_limit,
                        filters=filters,
                )
            elif mode == "sparse":
                tasks["sparse"] = ex.submit(
                    sparse_search,
                    vector_store=self.vector_store,
                    provider=self.provider,
                    collection=self.collection,
                    query=query,
                    limit=vector_scoring_limit,
                    filters=filters,
                )
            else:
                return {}, {}, {}

            candidate_lists: dict[str, list[Any]] = {}
            counts: dict[str, int] = {}
            failures: dict[str, str] = {}
            for source, fut in tasks.items():
                try:
                    hits = fut.result()
                except Exception as exc:
                    logger.warning("retrieval source %s failed: %s", source, exc)
                    failures[source] = f"{type(exc).__name__}: {exc}"
                    hits = []
                if not hits:
                    counts[source] = 0
                    continue
                if source == "lexical":
                    hits = self._filter_chunks(hits, verification_filters)
                else:
                    hits = [
                        hit for hit in hits
                        if metadata_matches_filters(
                            getattr(hit, "payload", {}) or {},
                            verification_filters,
                            source=str((getattr(hit, "payload", {}) or {}).get("source") or ""),
                        )
                    ][:per_source_limit]
                shaped = _shape_for_fusion(source, hits)
                if shaped:
                    candidate_lists[source] = shaped
                    counts[source] = len(shaped)
        return candidate_lists, counts, failures

    def _sparse_supported(self) -> bool:
        if self.vector_store is None or not self.collection:
            return False
        metadata_fn = getattr(self.vector_store, "collection_metadata", None)
        if not callable(metadata_fn):
            return bool(self._sidecar_collection_metadata().get("sparse_model"))
        try:
            metadata = metadata_fn(self.collection)
        except Exception:
            return False
        if metadata is None:
            return bool(self._sidecar_collection_metadata().get("sparse_model"))
        return bool(metadata.get("sparse_model"))

    def _hydrate(self, section_ids: list[int], *, budget: int) -> list:
        if not section_ids:
            return []
        return self.store.fetch_sections_by_id(section_ids, budget=budget)

    def _candidate_limit_for_diversity(self, limit: int, expand: str | None) -> int:
        if (expand or "").lower() in {"adjacent", "page"}:
            return limit
        max_per_source = getattr(self.config.retrieval, "max_sections_per_source", None)
        if not max_per_source:
            return limit
        return max(limit * 3, limit + int(max_per_source) * 3)

    def _limit_sections_per_source(self, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
        if (expand or "").lower() in {"adjacent", "page"}:
            return chunks
        max_per_source = getattr(self.config.retrieval, "max_sections_per_source", None)
        if not max_per_source:
            return chunks[:limit] if limit is not None else chunks
        counts: dict[str, int] = {}
        out: list[Any] = []
        for chunk in chunks:
            metadata = getattr(chunk, "metadata", {}) or {}
            source = str(metadata.get("canonical_url") or getattr(chunk, "source", "") or "")
            count = counts.get(source, 0)
            if count >= int(max_per_source):
                continue
            counts[source] = count + 1
            out.append(chunk)
            if limit is not None and len(out) >= limit:
                break
        return out

    @staticmethod
    def _filter_chunks(chunks: list[Any], filters: dict | None) -> list[Any]:
        if not filters:
            return chunks
        return [
            chunk for chunk in chunks
            if metadata_matches_filters(
                getattr(chunk, "metadata", {}) or {},
                filters,
                source=str(getattr(chunk, "source", "") or ""),
            )
        ]

    def _rerank_intent_matches(self, query: str, chunks: list[Any], *, expand: str | None = None) -> list[Any]:
        if not query or len(chunks) < 2:
            return chunks
        query_lower = query.lower()
        query_terms = _query_api_terms(query)
        intent_terms = _query_intent_terms(query_lower)
        if not query_terms and not intent_terms:
            return chunks

        scored: list[tuple[float, int, Any]] = []
        for index, chunk in enumerate(chunks):
            metadata = getattr(chunk, "metadata", {}) or {}
            source = str(metadata.get("canonical_url") or getattr(chunk, "source", "") or "")
            title = str(metadata.get("title") or metadata.get("section_title") or "")
            document_title = str(metadata.get("document_title") or "")
            anchor = str(metadata.get("anchor") or "")
            haystack = "\n".join([source, title, document_title, anchor]).lower()
            text = str(getattr(chunk, "text", "") or "").lower()

            boost = 0.0
            for term in query_terms:
                term_lower = term.lower()
                compact = term_lower.replace(".", "")
                if term_lower in haystack or compact in haystack:
                    boost += 3.0
                elif term_lower in text[:1200] or compact in text[:1200]:
                    boost += 1.0

            if boost and any(part in source for part in ("/docs/", "/guide/", "/tutorial/", "/reference/", "/concepts/", "/concepts2/")):
                boost += 1.0
            boost += _intent_source_score(query_lower, intent_terms, source, haystack, text)
            boost += _snippet_intent_score(query_lower, intent_terms, query_terms, metadata, text)
            if isinstance(metadata, dict):
                metadata["_pre_post_rank"] = index + 1
                metadata["_intent_boost"] = boost
            scored.append((boost, index, chunk))

        if not any(boost for boost, _index, _chunk in scored):
            return chunks
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [chunk for _boost, _index, chunk in scored]

    def _append_api_term_matches(
        self,
        query: str,
        chunks: list[Any],
        *,
        budget: int,
        expand: str | None = None,
        backend_filters: dict | None = None,
        verification_filters: dict | None = None,
    ) -> list[Any]:
        query_terms = _query_api_terms(query)
        if not query_terms:
            return chunks
        try:
            supplemental = self.store.query(
                " ".join(sorted(query_terms)), limit=10, budget=budget,
                expand=expand, filters=backend_filters,
            )
        except Exception:
            return chunks
        supplemental = self._filter_chunks(supplemental, verification_filters)
        for rank, chunk in enumerate(supplemental, start=1):
            metadata = getattr(chunk, "metadata", None)
            if isinstance(metadata, dict):
                metadata["_supplemental_rank"] = rank
        seen: set[Any] = set()
        out: list[Any] = []
        for chunk in [*chunks, *supplemental]:
            metadata = getattr(chunk, "metadata", {}) or {}
            key = metadata.get("section_id") or (getattr(chunk, "source", ""), getattr(chunk, "chunk_index", None))
            if key in seen:
                continue
            seen.add(key)
            out.append(chunk)
        return out

    def _degraded_mode_name(self, mode: str, candidate_lists: dict[str, list[Any]], failures: dict[str, str]) -> str:
        if not failures:
            return mode
        if not candidate_lists:
            return f"{mode}/lexical_fallback_degraded"
        signals = "_".join(sorted(candidate_lists.keys()))
        return f"{mode}/{signals}_degraded"


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
