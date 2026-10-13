"""RetrievalDispatcher implementation shard 1."""
from __future__ import annotations

from ._dispatch_shared import *  # noqa: F401,F403


class _RetrievalDispatcherPart01:
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
        self.provider = _CachedQueryProvider(provider) if provider is not None else None
        self.collection = collection

    def vector_readiness(self, mode: str | None = None) -> dict[str, Any]:
        """Return the versioned bounded public readiness contract."""
        effective_mode = str(mode or self.config.retrieval.default_mode or "lexical").lower()
        if effective_mode == "lexical":
            return {"schema_version": VECTOR_READINESS_SCHEMA,
                    "status": "not_required", "mode": "lexical"}
        failure = self._vector_readiness_failure(effective_mode)
        if not failure:
            return {
                "schema_version": VECTOR_READINESS_SCHEMA,
                "status": "ready", "mode": effective_mode,
                "collection_id": self._public_collection_id(),
            }
        reason = next(iter(failure.values())).split(":", 1)[0]
        return {
            "schema_version": VECTOR_READINESS_SCHEMA,
            "status": "not_ready",
            "mode": effective_mode,
            "reason_code": reason if reason in VECTOR_READINESS_REASONS else "metadata_unavailable",
            "collection_id": self._public_collection_id(),
        }

    def _public_collection_id(self) -> str:
        if not self.collection:
            return ""
        return "sha256:" + hashlib.sha256(self.collection.encode("utf-8")).hexdigest()[:16]

    def _bounded_vector_probe(self, operation: Any) -> Any:
        if not getattr(self.vector_store, "supports_concurrent_queries", True):
            return operation()
        options = getattr(getattr(self.config, "vector_store", None), "options", {}) or {}
        timeout = max(0.01, min(float(options.get("readiness_timeout_seconds", 0.25)), 2.0))
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vector-readiness")
        future = executor.submit(operation)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError("vector readiness deadline exceeded") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def run(
        self,
        query: str,
        *,
        mode: str | None = None,
        limit: int | None = None,
        budget: int | None = None,
        expand: str | None = None,
        filters: dict | None = None,
        requirements: Any | None = None,
        allow_degraded: bool = False,
    ) -> DispatchResult:
        configured_mode = getattr(getattr(self.config, "retrieval", None), "default_mode", None)
        effective_mode = (
            mode
            or (configured_mode if isinstance(configured_mode, str) else None)
            or "lexical"
        ).lower()
        from .experimental_acquisition import (
            ACQUISITION_CANDIDATES, ACQUISITION_ESTIMATED_TOKENS,
            ACQUISITION_METHOD, ACQUISITION_TEXT_BYTES,
        )

        q_active = effective_mode == "lexical"
        limit = min(40, limit or self.config.query.default_limit)
        budget = budget or self.config.query.default_budget
        per_source_limit = min(40, max(limit * 3, 20))

        # Only explicit filters choose scope; legacy query routers are inert.
        merged_filters = self._apply_router(query, filters)
        backend_filters = compile_backend_filters(merged_filters) or None
        requested_lanes = (
            ("lexical", "dense", "sparse")
            if effective_mode == "hybrid"
            else (effective_mode,)
        )
        query_plan = build_query_plan(
            query, filters=merged_filters, requested_lanes=requested_lanes, requirements=requirements,
        )
        # The dispatcher only expands when this retrieval call or retrieval
        # configuration requests it. Agent callers apply query.default_expand
        # explicitly; treating it as implicit here disables compact source caps.
        retrieval_expand = (
            expand
            or getattr(self.config.retrieval, "expand", None)
        )
        fusion_config_hash = canonical_hash({
            "schema_version": "stable-child-rrf-v1",
            "method": self.config.retrieval.fusion.method or "rrf",
            "rrf_k": int(self.config.retrieval.fusion.rrf_k or 60),
            "weights": dict(self.config.retrieval.fusion.weights or {}),
            "candidate_limits": {"per_lane": 40, "fused": 60},
            "post_fusion": {
                "exact_supplement": "explicit-query-only-v1",
                "intent_rerank": "retriever-order-preserved-v2",
                "expand": retrieval_expand,
                "max_sections_per_source": None,
            },
        })
        if q_active:
            fusion_config_hash = canonical_hash({
                "schema_version": ACQUISITION_METHOD,
                "candidate_ceiling": ACQUISITION_CANDIDATES,
                "estimated_token_ceiling": ACQUISITION_ESTIMATED_TOKENS,
                "text_byte_ceiling": ACQUISITION_TEXT_BYTES,
                "expansion": "none", "source_quota": None,
            })

        def finalized(result: DispatchResult) -> DispatchResult:
            result.query_plan_hash = query_plan.plan_hash
            result.fusion_config_hash = fusion_config_hash
            result.requirements_hash = query_plan.requirements_hash
            result.requirements = query_plan.requirements
            for final_rank, chunk in enumerate(result.chunks, start=1):
                metadata = getattr(chunk, "metadata", None)
                if isinstance(metadata, dict):
                    metadata["query_plan_hash"] = query_plan.plan_hash
                    metadata["fusion_config_hash"] = fusion_config_hash
                    section_id = metadata.get("section_id")
                    metadata["retrieval_trace"] = {
                        "requested_mode": effective_mode,
                        "mode_used": result.mode_used,
                        "component_ranks": dict(result.contributions.get(section_id, {})),
                        "pre_post_rank": metadata.pop("_pre_post_rank", final_rank),
                        "intent_boost": metadata.pop("_intent_boost", 0.0),
                        "supplemental_rank": metadata.pop("_supplemental_rank", None),
                        "final_rank": final_rank,
                    }
            return result

        if q_active:
            chunks = self.store.query(
                query, limit=ACQUISITION_CANDIDATES,
                budget=ACQUISITION_ESTIMATED_TOKENS, expand="none",
                filters=backend_filters,
            )
            acquired_count = len(chunks)
            chunks = self._filter_chunks(chunks, merged_filters)
            for chunk in chunks:
                chunk.metadata.setdefault("acquisition", {}).update({
                    "dispatcher_post_policy_rows": len(chunks),
                    "delivery_limit_not_applied": limit,
                    "delivery_budget_not_applied": budget,
                })
            return finalized(DispatchResult(
                chunks=chunks,
                contributions={
                    c.metadata.get("section_id"): {"lexical": idx + 1}
                    for idx, c in enumerate(chunks)
                    if c.metadata.get("section_id") is not None
                },
                mode_used="lexical", candidate_counts={"lexical": acquired_count},
            ))

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
            chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
            return finalized(DispatchResult(
                chunks=chunks,
                contributions={c.metadata.get("section_id"): {"lexical": idx + 1} for idx, c in enumerate(chunks) if c.metadata.get("section_id") is not None},
                mode_used=f"{effective_mode}/lexical_fallback_degraded",
                candidate_counts={"lexical": len(chunks)},
                failures=ready_failure,
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

        chunks = self._hydrate_policy_filtered(
            section_ids, budget=budget, filters=merged_filters,
        )
        scores_by_section = {
            hydration_by_stable[stable_id]: score
            for stable_id, score, _ in ranked if stable_id in hydration_by_stable
        }
        for chunk in chunks:
            chunk.score = scores_by_section.get(chunk.metadata.get("section_id"), 0.0)
        chunks = self._filter_chunks(chunks, merged_filters)
        chunks = self._append_api_term_matches(query, chunks, budget=budget, expand=retrieval_expand, backend_filters=backend_filters, verification_filters=merged_filters)
        chunks = self._limit_sections_per_source(chunks, limit=limit, expand=retrieval_expand)
        reported_mode = self._degraded_mode_name(effective_mode, candidate_lists, failures)
        return finalized(DispatchResult(
            chunks=chunks,
            contributions=contributions,
            mode_used=reported_mode,
            candidate_counts=raw_counts,
            failures=failures,
        ))

    def _vector_readiness_failure(self, mode: str) -> dict[str, str]:
        if mode == "lexical" or self.vector_store is None or not self.collection:
            return {}
        generation_info = self.store.generation_info()
        if generation_info and str(generation_info.get("vector_collection") or "") != self.collection:
            return {
                "vector": (
                    "collection_identity_mismatch"
                )
            }
        if generation_info:
            backend_identity = str(generation_info.get("vector_backend_identity") or "")
            if not backend_identity:
                return {"vector": "unverified_backend_identity"}
            try:
                current_identity = self.vector_store.backend_identity()
            except Exception:
                return {"vector": "unverified_backend_identity"}
            if current_identity != backend_identity:
                return {"vector": "backend_identity_mismatch"}
            if not (
                str(generation_info.get("vector_parity_schema") or "") == "vector-parity-v1"
                and str(generation_info.get("vector_parity_digest") or "")
                and str(generation_info.get("vector_parity_verified_at") or "")
                and generation_info.get("vector_parity_count") is not None
                and str(generation_info.get("vector_parity_backend_identity") or "") == backend_identity
                and str(generation_info.get("vector_parity_collection") or "") == self.collection
            ):
                return {"vector": "unverified_parity_witness"}
        metadata: dict[str, Any] | None = None
        metadata_fn = getattr(self.vector_store, "collection_metadata", None)
        if callable(metadata_fn):
            try:
                metadata = self._bounded_vector_probe(
                    lambda: metadata_fn(self.collection)
                )
            except Exception as exc:
                return {"vector": f"metadata_unavailable:{type(exc).__name__}"}
        if not metadata:
            metadata = self._sidecar_collection_metadata()
        if not metadata:
            return {"vector": "metadata_unverified"}
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
        if mode in {"sparse", "hybrid"} and not metadata.get("sparse_model"):
            mismatches.append("sparse_model")
        if mismatches:
            return {"vector": "capability_mismatch:" + ",".join(mismatches)}
        health_fn = getattr(self.vector_store, "health_check", None)
        if not callable(health_fn):
            return {"vector": "health_unavailable"}
        try:
            if not self._bounded_vector_probe(health_fn):
                return {"vector": "backend_unhealthy"}
        except Exception as exc:
            return {"vector": f"health_unavailable:{type(exc).__name__}"}
        count_fn = getattr(self.vector_store, "count", None)
        if not callable(count_fn):
            return {"vector": "count_unavailable"}
        try:
            points = int(self._bounded_vector_probe(lambda: count_fn(self.collection)))
        except Exception as exc:
            return {"vector": f"count_unavailable:{type(exc).__name__}"}
        if generation_info:
            expected = int(generation_info["vector_parity_count"])
            if points != expected:
                return {"vector": f"count_mismatch:expected={expected},actual={points}"}
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

    def _apply_router(self, query: str, filters: dict | None) -> dict | None:
        """Compatibility hook: only explicit filters select retrieval scope."""
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
