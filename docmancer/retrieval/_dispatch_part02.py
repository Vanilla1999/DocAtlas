"""RetrievalDispatcher implementation shard 2."""
from __future__ import annotations

from ._dispatch_shared import *  # noqa: F401,F403


class _RetrievalDispatcherPart02:
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

        jobs: dict[str, Any] = {}
        # Backends may score a wider internal window, but only the first
        # verified ``per_source_limit`` hits enter the candidate lane. This is
        # required for sqlite-vec, which cannot push metadata predicates down.
        vector_scoring_limit = min(160, max(40, per_source_limit * 4))
        if mode == "hybrid":
            jobs["lexical"] = lambda: lexical_search(
                self.store, query, limit=min(40, per_source_limit), budget=10_000, filters=filters
            )
            jobs["dense"] = lambda: dense_search(
                vector_store=self.vector_store, provider=self.provider,
                collection=self.collection, query=query,
                limit=vector_scoring_limit, filters=filters,
            )
            if self._sparse_supported():
                jobs["sparse"] = lambda: sparse_search(
                    vector_store=self.vector_store, provider=self.provider,
                    collection=self.collection, query=query,
                    limit=vector_scoring_limit, filters=filters,
                )
        elif mode == "dense":
            jobs["dense"] = lambda: dense_search(
                vector_store=self.vector_store, provider=self.provider,
                collection=self.collection, query=query,
                limit=vector_scoring_limit, filters=filters,
            )
        elif mode == "sparse":
            jobs["sparse"] = lambda: sparse_search(
                vector_store=self.vector_store, provider=self.provider,
                collection=self.collection, query=query,
                limit=vector_scoring_limit, filters=filters,
            )
        else:
            return {}, {}, {}

        can_parallelize = bool(
            len(jobs) > 1
            and getattr(self.vector_store, "supports_concurrent_queries", True)
        )
        if can_parallelize:
            with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
                outcomes = {
                    source: executor.submit(job)
                    for source, job in jobs.items()
                }
                resolved = {
                    source: future.result
                    for source, future in outcomes.items()
                }
        else:
            resolved = jobs

        candidate_lists: dict[str, list[Any]] = {}
        counts: dict[str, int] = {}
        failures: dict[str, str] = {}
        for source, resolve in resolved.items():
            try:
                hits = resolve()
            except Exception as exc:
                logger.warning("retrieval source %s failed (%s)", source, type(exc).__name__)
                failures[source] = f"{type(exc).__name__}: <redacted diagnostic text>"
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
        supplemental: list[Any] = []
        for term in sorted(query_terms)[:8]:
            try:
                supplemental.extend(self.store.query(
                    term, limit=4, budget=budget,
                    expand=expand, filters=backend_filters,
                ))
            except Exception:
                continue
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
