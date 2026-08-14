"""Hierarchical retrieval, query routing, and hybrid neighbor expansion."""
from __future__ import annotations

import hashlib

import pytest

from docmancer.core.config import (
    DocmancerConfig,
    HierarchicalConfig,
    QueryRouter,
    VectorStoreConfig,
)
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.embeddings.base import SparseEmbeddings
from docmancer.retrieval.dispatch import (
    HybridRetrievalError,
    RetrievalDispatcher as _RetrievalDispatcher,
)
from docmancer.stores.base import VectorHit


class FakeVectorStore:
    """Minimal in-memory vector store stub for dispatcher tests.

    Returns dense/sparse hits keyed by section_id with payloads that
    expose ``document_title_hash`` for hierarchical retrieval.
    """

    def __init__(
        self,
        hits_by_filter,
        *,
        contract="ready",
        count_override=None,
    ):
        self._hits_by_filter = hits_by_filter
        self.calls: list[dict] = []
        self.contract = contract
        self.count_override = count_override
        self._bound_count: int | None = None

    def ensure_collection(self, *args, **kwargs):
        return None

    def collection_metadata(self, collection):
        return {"provider": "fake", "model": "fake", "dim": 4, "sparse_model": "fake-sparse"}

    def count(self, collection):
        if self.count_override is not None:
            return self.count_override
        return self._bound_count if self._bound_count is not None else 1

    def backend_identity(self):
        return "fake-vector-store:v1"

    def health_check(self):
        return True

    def generation_contract(self, store):
        generation = store.generation_info()
        if generation is None:
            return None

        info = dict(generation)
        rows = store.list_sections_for_embedding()
        expected_ids = {
            str(row["vector_id"])
            for row in rows
        }
        self._bound_count = len(expected_ids)

        if self.contract == "legacy":
            return info

        backend_identity = self.backend_identity()
        info["vector_backend_identity"] = backend_identity

        if self.contract == "identity_only":
            return info

        collection = str(info["vector_collection"])
        digest = hashlib.sha256(
            "\n".join(sorted(expected_ids)).encode("utf-8")
        ).hexdigest()

        info.update({
            "vector_parity_schema": "vector-parity-v1",
            "vector_parity_digest": digest,
            "vector_parity_count": len(expected_ids),
            "vector_parity_backend": "fake",
            "vector_parity_backend_identity": backend_identity,
            "vector_parity_collection": collection,
            "vector_parity_verified_at": "2026-01-01T00:00:00+00:00",
        })
        return info

    def point_ids(self, collection):
        return {"wrong-id"}

    def search(self, collection, query_vector, *, limit, filters=None, sparse_vector=None, mode="dense"):
        key = _filter_key(filters)
        self.calls.append({"mode": mode, "filters": filters, "limit": limit})
        return list(self._hits_by_filter.get((mode, key), []))[:limit]


class DenseOnlyVectorStore(FakeVectorStore):
    def collection_metadata(self, collection):
        return {"provider": "fake", "model": "fake", "dim": 4, "sparse_model": None}


class FailingVectorStore(FakeVectorStore):
    def __init__(self):
        super().__init__({})

    def search(self, collection, query_vector, *, limit, filters=None, sparse_vector=None, mode="dense"):
        raise ValueError("Vector dimension error: expected dim: 768, got 384")


class EmptyVectorStore(FakeVectorStore):
    def __init__(self):
        super().__init__({}, count_override=0)


class MismatchedVectorStore(FakeVectorStore):
    def collection_metadata(self, collection):
        return {"provider": "other", "model": "other", "dim": 99, "sparse_model": None}


class Stage2FailingVectorStore(FakeVectorStore):
    def search(self, collection, query_vector, *, limit, filters=None, sparse_vector=None, mode="dense"):
        if filters and "document_title_hash" in filters:
            raise ValueError("stage two unavailable")
        return super().search(
            collection, query_vector, limit=limit, filters=filters,
            sparse_vector=sparse_vector, mode=mode,
        )


class FakeProvider:
    name = "fake"
    dimensions = 4
    max_batch_size = 8

    def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, q):
        return [1.0, 0.0, 0.0, 0.0]

    def embed_sparse_query(self, q):
        return SparseEmbeddings(indices=[0], values=[1.0])


def _filter_key(filters):
    if not filters:
        return None
    return tuple(sorted((k, _hashable(v)) for k, v in filters.items()))


def _hashable(v):
    if isinstance(v, dict):
        return tuple(sorted(((k, _hashable(val)) for k, val in v.items()), key=lambda kv: kv[0]))
    if isinstance(v, list):
        return tuple(_hashable(x) for x in v)
    return v


def _hit(sid, score=1.0, **payload):
    return VectorHit(id=str(sid), score=score, payload=payload)


def _agent(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.embeddings.dimensions = 4
    config.vector_store = VectorStoreConfig(provider="qdrant", url="http://stub")
    store = SQLiteStore(config.index.db_path)
    return config, store


def _populate(store, docs):
    documents = [
        Document(source=src, content=content, metadata={"title": title})
        for title, src, content in docs
    ]
    store.add_documents(documents, recreate=True)


class _GenerationInfoView:
    """Read-side view of a successfully published generation contract."""

    def __init__(self, store, generation_info):
        self._store = store
        self._generation_info = dict(generation_info)

    def generation_info(self):
        return dict(self._generation_info)

    def __getattr__(self, name):
        return getattr(self._store, name)


class RetrievalDispatcher(_RetrievalDispatcher):
    """Make legacy dispatcher fixtures explicit about publication readiness."""

    def __init__(
        self,
        *,
        store,
        config,
        vector_store=None,
        provider=None,
        collection=None,
    ):
        if isinstance(vector_store, FakeVectorStore):
            generation_info = vector_store.generation_contract(store)
            if generation_info is not None:
                active_collection = str(
                    generation_info.get("vector_collection") or ""
                )
                # Historical positive fixtures used "c" as a placeholder.
                # Deliberate stale/wrong collections must remain untouched.
                if collection == "c":
                    collection = active_collection
                store = _GenerationInfoView(store, generation_info)
        super().__init__(
            store=store,
            config=config,
            vector_store=vector_store,
            provider=provider,
            collection=collection,
        )


# ---------------- query router ----------------


def test_router_injects_filters(tmp_path):
    config, store = _agent(tmp_path)
    config.retrieval.routers = [
        QueryRouter(
            match=r"latest version",
            filters={"status_code": "LIVE"},
            description="version-latest",
        )
    ]
    vstore = FakeVectorStore(hits_by_filter={})
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vstore,
        provider=FakeProvider(),
        collection="c",
    )
    dispatcher.run("what is the latest version?", mode="dense", limit=5)
    # The fake store records the filters the dispatcher passed.
    assert vstore.calls
    assert vstore.calls[0]["filters"] == {"status_code": "LIVE"}


def test_router_first_match_wins(tmp_path):
    config, store = _agent(tmp_path)
    config.retrieval.routers = [
        QueryRouter(match=r"foo", filters={"a": 1}),
        QueryRouter(match=r"bar", filters={"b": 2}),
    ]
    vstore = FakeVectorStore(hits_by_filter={})
    RetrievalDispatcher(
        store=store, config=config, vector_store=vstore, provider=FakeProvider(), collection="c"
    ).run("foo bar baz", mode="dense", limit=2)
    assert vstore.calls and vstore.calls[0]["filters"] == {"a": 1}


def test_router_does_not_override_caller_filter(tmp_path):
    config, store = _agent(tmp_path)
    config.retrieval.routers = [
        QueryRouter(match=r"latest", filters={"status_code": "LIVE", "scope": "docs"}),
    ]
    vstore = FakeVectorStore(hits_by_filter={})
    RetrievalDispatcher(
        store=store, config=config, vector_store=vstore,
        provider=FakeProvider(), collection="c",
    ).run(
        "latest", mode="dense", limit=1,
        filters={"status_code": "PINNED"},
    )

    assert vstore.calls[0]["filters"] == {"status_code": "PINNED", "scope": "docs"}


def test_router_invalid_regex_is_skipped(tmp_path):
    config, store = _agent(tmp_path)
    # An unbalanced bracket would raise re.error; the dispatcher must skip it
    # rather than aborting the whole query.
    config.retrieval.routers = [
        QueryRouter(match=r"[unbalanced", filters={"x": 1}),
        QueryRouter(match=r"hello", filters={"ok": True}),
    ]
    vstore = FakeVectorStore(hits_by_filter={})
    RetrievalDispatcher(
        store=store, config=config, vector_store=vstore, provider=FakeProvider(), collection="c"
    ).run("hello world", mode="dense", limit=1)
    assert vstore.calls[0]["filters"] == {"ok": True}


def test_dense_failure_is_hard_error_by_default(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha.\n")])
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=FailingVectorStore(),
        provider=FakeProvider(),
        collection="c",
    )
    with pytest.raises(HybridRetrievalError, match="<redacted diagnostic text>"):
        dispatcher.run("alpha", mode="dense", limit=1)


def test_dense_failure_can_degrade_when_requested(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha.\n")])
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=FailingVectorStore(),
        provider=FakeProvider(),
        collection="c",
    )
    result = dispatcher.run("alpha", mode="dense", limit=1, allow_degraded=True)
    assert result.mode_used == "dense/lexical_fallback_degraded"
    assert "dense" in result.failures


def test_dense_zero_hits_stays_empty_in_strict_mode(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha lexical fallback bait.\n")])
    result = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=FakeVectorStore(hits_by_filter={}),
        provider=FakeProvider(),
        collection="c",
    ).run("alpha", mode="dense", limit=1)

    assert result.chunks == []
    assert result.mode_used == "dense"
    assert result.failures == {}


def test_empty_vector_collection_is_hard_error(tmp_path):
    config, store = _agent(tmp_path)
    store.add_documents([Document(
        source="doc", content="# Doc\n\nalpha.\n",
        metadata={"chunking_schema": "parent-child-v1"},
    )], recreate=True)
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=EmptyVectorStore(),
        provider=FakeProvider(),
        collection="c",
    )
    with pytest.raises(HybridRetrievalError, match="count_mismatch"):
        dispatcher.run("alpha", mode="hybrid", limit=1)
    assert dispatcher.vector_store.calls == []


def test_vector_collection_requires_exact_active_generation_parity(tmp_path):
    config, store = _agent(tmp_path)
    documents = [
        Document(
            source=f"doc-{index}.md",
            content=f"# Doc {index}\n\nalpha {index}.\n",
            metadata={"format": "markdown", "chunking_schema": "parent-child-v1"},
        )
        for index in range(2)
    ]
    store.add_documents(documents, recreate=True)
    collection = str(store.generation_info()["vector_collection"])
    dispatcher = RetrievalDispatcher(
        store=store, config=config,
        vector_store=FakeVectorStore({}, contract="identity_only"),
        provider=FakeProvider(), collection=collection,
    )

    with pytest.raises(HybridRetrievalError, match="unverified_parity_witness"):
        dispatcher.run("alpha", mode="dense", limit=1)


def test_equal_count_without_persisted_witness_fails_strict_readiness(tmp_path):
    config, store = _agent(tmp_path)
    store.add_documents([Document(
        source="doc.md", content="# Doc\n\nalpha.\n",
        metadata={"format": "markdown", "chunking_schema": "parent-child-v1"},
    )], recreate=True)
    collection = str(store.generation_info()["vector_collection"])
    vectors = FakeVectorStore({}, contract="identity_only")
    assert vectors.count(collection) == len(store.list_sections_for_embedding())
    dispatcher = RetrievalDispatcher(
        store=store, config=config, vector_store=vectors,
        provider=FakeProvider(), collection=collection,
    )

    with pytest.raises(HybridRetrievalError, match="unverified_parity_witness"):
        dispatcher.run("alpha", mode="dense", limit=1)
    assert vectors.calls == []


def test_missing_vector_capabilities_are_explicit_and_require_degraded_opt_in(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha.\n")])
    dispatcher = RetrievalDispatcher(store=store, config=config)

    with pytest.raises(HybridRetrievalError, match="vector store is not configured"):
        dispatcher.run("alpha", mode="hybrid", limit=1)

    result = dispatcher.run(
        "alpha", mode="hybrid", limit=1, allow_degraded=True
    )
    assert result.mode_used == "hybrid/lexical_fallback_degraded"
    assert set(result.failures) == {"vector", "embedding"}


def test_degraded_mismatch_never_queries_unverified_vector_lane(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha.\n")])
    vstore = MismatchedVectorStore({})
    result = RetrievalDispatcher(
        store=store, config=config, vector_store=vstore,
        provider=FakeProvider(), collection="c",
    ).run("alpha", mode="dense", limit=1, allow_degraded=True)

    assert not vstore.calls
    assert result.mode_used == "dense/lexical_fallback_degraded"
    assert result.failures["vector"].startswith("capability_mismatch:")


def test_lexical_and_supplemental_paths_enforce_forbidden_sources(tmp_path):
    config, store = _agent(tmp_path)
    store.add_documents([
        Document(source="allowed", content="# Allowed\n\nUse `Client.open`."),
        Document(source="forbidden", content="# Forbidden\n\nUse `Client.open`."),
    ], recreate=True)

    result = RetrievalDispatcher(store=store, config=config).run(
        "How do I call `Client.open`?", mode="lexical", limit=10,
        filters={"forbidden_sources": ["forbidden"]},
    )

    assert result.chunks
    assert {chunk.source for chunk in result.chunks} == {"allowed"}
    assert all("final_rank" in chunk.metadata["retrieval_trace"] for chunk in result.chunks)


@pytest.mark.parametrize("mode", ["lexical", "dense", "sparse", "hybrid"])
def test_named_document_filter_is_hard_across_retrieval_modes(tmp_path, mode):
    config, store = _agent(tmp_path)
    store.add_documents([
        Document(
            source="project::docs/PLAN.md",
            content="# Plan\n\nSharedTerm requested marker.",
            metadata={"source_path": "docs/PLAN.md", "project_doc_path": "docs/PLAN.md"},
        ),
        Document(
            source="project::ARCHITECTURE.md",
            content="# Architecture\n\nSharedTerm forbidden marker.",
            metadata={"source_path": "ARCHITECTURE.md", "project_doc_path": "ARCHITECTURE.md"},
        ),
    ], recreate=True)
    rows = store.list_sections_for_embedding()
    vector_hits = [
        _hit(
            int(row["section_id"]),
            project_doc_path=(
                "docs/PLAN.md"
                if row["source"] == "project::docs/PLAN.md"
                else "ARCHITECTURE.md"
            ),
        )
        for row in rows
    ]
    class UnfilteredVectorStore(FakeVectorStore):
        def search(self, collection, query_vector, *, limit, filters=None, sparse_vector=None, mode="dense"):
            self.calls.append({"mode": mode, "filters": filters, "limit": limit})
            return list(reversed(vector_hits))[:limit]

    vector_store = UnfilteredVectorStore({})
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vector_store,
        provider=FakeProvider(),
        collection="c",
    )

    result = dispatcher.run(
        "SharedTerm", mode=mode, limit=10,
        filters={"project_doc_path": "docs/PLAN.md"},
    )

    assert result.chunks
    assert {chunk.metadata["source_path"] for chunk in result.chunks} == {"docs/PLAN.md"}
    if mode != "lexical":
        assert vector_store.calls
        assert all(call["filters"] == {"project_doc_path": "docs/PLAN.md"} for call in vector_store.calls)


def test_named_document_filter_survives_degraded_vector_fallback(tmp_path):
    config, store = _agent(tmp_path)
    store.add_documents([
        Document(
            source="project::docs/PLAN.md", content="# Plan\n\nSharedTerm requested.",
            metadata={"source_path": "docs/PLAN.md", "project_doc_path": "docs/PLAN.md"},
        ),
        Document(
            source="project::ARCHITECTURE.md", content="# Architecture\n\nSharedTerm forbidden.",
            metadata={"source_path": "ARCHITECTURE.md", "project_doc_path": "ARCHITECTURE.md"},
        ),
    ], recreate=True)

    result = RetrievalDispatcher(store=store, config=config).run(
        "SharedTerm", mode="hybrid", limit=10, allow_degraded=True,
        filters={"project_doc_path": "docs/PLAN.md"},
    )

    assert result.mode_used == "hybrid/lexical_fallback_degraded"
    assert result.chunks
    assert {chunk.metadata["source_path"] for chunk in result.chunks} == {"docs/PLAN.md"}


def test_hybrid_rejects_collection_without_sparse_capability(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\nalpha.")])
    section_id = int(store.list_sections_for_embedding()[0]["section_id"])
    vstore = DenseOnlyVectorStore(hits_by_filter={("dense", None): [_hit(section_id)]})

    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vstore,
        provider=FakeProvider(),
        collection="c",
    )

    with pytest.raises(HybridRetrievalError, match="sparse_model"):
        dispatcher.run("alpha", mode="hybrid", limit=1)
    assert vstore.calls == []


def test_hybrid_fuses_on_stable_child_id_and_hydrates_integer_id(tmp_path):
    config, store = _agent(tmp_path)
    store.add_documents([Document(
        source="doc.md",
        content="# Doc\n\nalpha.\n",
        metadata={
            "title": "Doc",
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 32,
            "child_hard_max_tokens": 64,
        },
    )])
    section = store.list_sections_for_embedding()[0]
    collection = str(store.generation_info()["vector_collection"])
    section_id = int(section["section_id"])
    stable_id = section["stable_chunk_id"]
    vector_hit = VectorHit(
        id=section["vector_id"],
        score=1.0,
        payload={"section_id": section_id, "stable_chunk_id": stable_id},
    )
    vstore = DenseOnlyVectorStore(hits_by_filter={
        ("dense", None): [vector_hit],
    })
    vstore.point_ids = lambda _collection: {str(section["vector_id"])}

    result = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vstore,
        provider=FakeProvider(),
        collection=collection,
    ).run("alpha", mode="dense", limit=1)

    assert result.chunks[0].metadata["section_id"] == section_id
    assert result.contributions[section_id] == {"dense": 1}


# ---------------- hierarchical retrieval ----------------


def test_hierarchical_two_stage_filters_to_top_docs(tmp_path):
    config, store = _agent(tmp_path)
    _populate(
        store,
        [
            ("Product A", "doc-a", "# Product A\n\n## Auth\nOAuth here.\n\n## API\nEndpoints."),
            ("Product B", "doc-b", "# Product B\n\n## Auth\nKeys here.\n\n## Pricing\nFree tier."),
        ],
    )
    # Walk every section so we can pre-program the fake store. Each Document
    # produces multiple sections (one per ``##`` heading), so we group by source.
    all_sections = store.list_sections_for_embedding()
    by_source: dict[str, list[int]] = {}
    for s in all_sections:
        by_source.setdefault(s["source"], []).append(int(s["section_id"]))
    section_ids = [sid for sids in by_source.values() for sid in sids]
    assert len(section_ids) >= 4

    # Stage 1: dense returns three ids — two from doc-a, one from doc-b. doc-a wins.
    a_ids = next(sids for src, sids in by_source.items() if "doc-a" in src)[:2]
    b_ids = next(sids for src, sids in by_source.items() if "doc-b" in src)[:1]
    stage1 = [_hit(a_ids[0]), _hit(a_ids[1]), _hit(b_ids[0])]
    # Get document_title_hash values for the filter expectation.
    doc_hashes = store.document_title_hashes_for(section_ids)
    a_doc_hash = doc_hashes[a_ids[0]]
    # Stage 2: filtered call returns only doc-a sections.
    stage2 = [_hit(a_ids[0], document_title_hash=a_doc_hash)]

    hits_by_filter = {
        ("dense", None): stage1,
        ("dense", _filter_key({"document_title_hash": {"in": [a_doc_hash]}})): stage2,
    }
    vstore = FakeVectorStore(hits_by_filter=hits_by_filter)

    config.retrieval.hierarchical = HierarchicalConfig(
        enabled=True, documents_limit=1, candidate_pool=10, sections_per_document=5
    )
    dispatcher = RetrievalDispatcher(
        store=store,
        config=config,
        vector_store=vstore,
        provider=FakeProvider(),
        collection="c",
    )
    result = dispatcher.run("authentication", mode="dense", limit=2)
    assert "hierarchical" in result.mode_used
    # Two calls: stage 1 (no filter) and stage 2 (document_title_hash IN [a_doc_hash]).
    assert len(vstore.calls) == 2
    assert vstore.calls[0]["filters"] is None
    assert vstore.calls[1]["filters"] == {"document_title_hash": {"in": [a_doc_hash]}}


def test_hierarchical_degraded_result_preserves_stage_failures(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Doc", "doc", "# Doc\n\n## Auth\nalpha authentication.\n")])
    section_id = int(store.list_sections_for_embedding()[0]["section_id"])
    config.retrieval.hierarchical = HierarchicalConfig(
        enabled=True, documents_limit=1, candidate_pool=10, sections_per_document=2
    )
    vstore = Stage2FailingVectorStore({("dense", None): [_hit(section_id)]})

    result = RetrievalDispatcher(
        store=store, config=config, vector_store=vstore,
        provider=FakeProvider(), collection="c",
    ).run("authentication", mode="dense", limit=1, allow_degraded=True)

    assert "dense.stage2" in result.failures
    assert "degraded" in result.mode_used


def test_hierarchical_fusion_honors_weighted_rrf(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [
        ("First", "first", "# First\n\nalpha first.\n"),
        ("Second", "second", "# Second\n\nalpha second.\n"),
    ])
    rows = store.list_sections_for_embedding()
    first_id = int(next(row for row in rows if row["source"] == "first")["section_id"])
    second_id = int(next(row for row in rows if row["source"] == "second")["section_id"])
    config.retrieval.fusion.method = "weighted_rrf"
    config.retrieval.fusion.weights = {"dense": 10.0, "lexical": 1.0}
    dispatcher = RetrievalDispatcher(store=store, config=config)

    result = dispatcher._fuse_and_hydrate(
        {
            "lexical": [
                {"id": "first", "hydration_id": first_id},
                {"id": "second", "hydration_id": second_id},
            ],
            "dense": [
                {"id": "second", "hydration_id": second_id},
                {"id": "first", "hydration_id": first_id},
            ],
        },
        query="alpha", limit=1, budget=100, expand=None,
        counts={"lexical": 2, "dense": 2}, mode="hybrid/hierarchical", filters=None,
    )

    assert result.chunks[0].metadata["section_id"] == second_id


# ---------------- hierarchical auto-enable ----------------


def test_hierarchical_auto_enables_above_threshold(tmp_path):
    config, store = _agent(tmp_path)
    # Three distinct documents, threshold of 2 -> auto path engages.
    _populate(
        store,
        [
            ("Doc One", "doc-1", "# Doc One\n\n## A\nalpha.\n"),
            ("Doc Two", "doc-2", "# Doc Two\n\n## B\nbeta.\n"),
            ("Doc Three", "doc-3", "# Doc Three\n\n## C\ngamma.\n"),
        ],
    )
    config.retrieval.hierarchical = HierarchicalConfig(
        enabled=False, auto=True, auto_min_documents=2, documents_limit=1
    )
    sections = store.list_sections_for_embedding()
    by_source: dict[str, list[int]] = {}
    for s in sections:
        by_source.setdefault(s["source"], []).append(int(s["section_id"]))
    a_id = by_source["doc-1"][0]
    a_doc_hash = store.document_title_hashes_for([a_id])[a_id]
    hits_by_filter = {
        ("dense", None): [_hit(a_id)],
        ("dense", _filter_key({"document_title_hash": {"in": [a_doc_hash]}})): [
            _hit(a_id, document_title_hash=a_doc_hash)
        ],
    }
    vstore = FakeVectorStore(hits_by_filter=hits_by_filter)
    result = RetrievalDispatcher(
        store=store, config=config, vector_store=vstore, provider=FakeProvider(), collection="c"
    ).run("alpha", mode="dense", limit=1)
    assert "hierarchical" in result.mode_used
    # Stage 2 must have applied a document_title_hash filter.
    assert any(
        (call["filters"] or {}).get("document_title_hash") is not None
        for call in vstore.calls
    )


def test_hierarchical_auto_skips_below_threshold(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Only Doc", "doc-1", "# Only Doc\n\n## A\nalpha.\n")])
    config.retrieval.hierarchical = HierarchicalConfig(
        enabled=False, auto=True, auto_min_documents=10
    )
    a_id = int(store.list_sections_for_embedding()[0]["section_id"])
    vstore = FakeVectorStore(hits_by_filter={("dense", None): [_hit(a_id)]})
    result = RetrievalDispatcher(
        store=store, config=config, vector_store=vstore, provider=FakeProvider(), collection="c"
    ).run("alpha", mode="dense", limit=1)
    assert "hierarchical" not in result.mode_used
    # Only one search call: no second filtered pass.
    assert len(vstore.calls) == 1


# ---------------- neighbor expansion in hybrid mode ----------------


def test_hybrid_neighbor_expansion_pulls_adjacent_sections(tmp_path):
    config, store = _agent(tmp_path)
    _populate(
        store,
        [
            (
                "Big Doc",
                "big-doc",
                "# Big Doc\n\n## A\nfirst.\n\n## B\nsecond.\n\n## C\nthird.\n",
            )
        ],
    )
    sections = store.list_sections_for_embedding()
    sections.sort(key=lambda s: s["chunk_index"])
    sid_a = int(sections[1]["section_id"])  # B's neighbors: A and C

    hits_by_filter = {("dense", None): [_hit(sid_a)]}
    vstore = FakeVectorStore(hits_by_filter=hits_by_filter)
    config.retrieval.expand = "adjacent"
    result = RetrievalDispatcher(
        store=store, config=config, vector_store=vstore, provider=FakeProvider(), collection="c"
    ).run("anything", mode="dense", limit=1)
    # Hybrid mode now returns the hit plus its two neighbors.
    chunk_indices = {c.chunk_index for c in result.chunks}
    assert chunk_indices.issuperset({sections[0]["chunk_index"], sections[2]["chunk_index"]})


def test_lexical_compact_results_limit_sections_per_source_by_default(tmp_path):
    config, store = _agent(tmp_path)
    docs = []
    for i in range(5):
        docs.append((f"Alpha {i}", "doc-a", f"# Alpha {i}\n\nalpha repeated evidence {i}."))
    docs.append(("Beta", "doc-b", "# Beta\n\nalpha useful beta evidence."))
    _populate(store, docs)

    result = RetrievalDispatcher(store=store, config=config).run("alpha evidence", mode="lexical", limit=5)

    assert len([chunk for chunk in result.chunks if chunk.source == "doc-a"]) <= 2
    assert any(chunk.source == "doc-b" for chunk in result.chunks)


def test_expand_bypasses_sections_per_source_cap(tmp_path):
    config, store = _agent(tmp_path)
    _populate(store, [("Big Doc", "big-doc", "# Big Doc\n\n## A\nalpha.\n\n## B\nalpha.\n\n## C\nalpha.\n")])

    result = RetrievalDispatcher(store=store, config=config).run("alpha", mode="lexical", limit=3, expand="adjacent")

    assert len([chunk for chunk in result.chunks if chunk.source == "big-doc"]) >= 3


def test_intent_rerank_prefers_matching_api_docs_page(tmp_path):
    config, store = _agent(tmp_path)
    dispatcher = RetrievalDispatcher(store=store, config=config)
    migration = RetrievedChunk(
        source="https://example.com/docs/migration/from_state_notifier",
        chunk_index=0,
        text="Lifecycle differences mention ref.watch and ref.listen in migration examples.",
        score=1.0,
        metadata={"canonical_url": "https://example.com/docs/migration/from_state_notifier", "title": "Lifecycle differences"},
    )
    refs = RetrievedChunk(
        source="https://example.com/docs/concepts2/refs",
        chunk_index=1,
        text="Refs explain when to listen to providers.",
        score=0.9,
        metadata={
            "canonical_url": "https://example.com/docs/concepts2/refs",
            "title": "Ref.watch",
            "document_title": "Refs",
            "anchor": "Refs > Ref.watch > Ref.listen",
        },
    )

    reranked = dispatcher._rerank_intent_matches(
        "ref.watch vs ref.listen lifecycle differences",
        [migration, refs],
    )

    assert reranked[0].source == "https://example.com/docs/concepts2/refs"


def test_api_term_matches_are_appended_from_lexical_search(tmp_path):
    config, store = _agent(tmp_path)
    _populate(
        store,
        [
            ("Migration", "https://example.com/docs/migration", "# Migration\n\nLifecycle differences."),
            ("Refs", "https://example.com/docs/concepts2/refs", "# Refs\n\n## Ref.watch\nUse ref.watch.\n\n## Ref.listen\nUse ref.listen."),
        ],
    )
    dispatcher = RetrievalDispatcher(store=store, config=config)
    initial = [
        RetrievedChunk(
            source="https://example.com/docs/migration",
            chunk_index=0,
            text="Lifecycle differences.",
            score=1.0,
            metadata={"section_id": 999, "canonical_url": "https://example.com/docs/migration"},
        )
    ]

    chunks = dispatcher._append_api_term_matches("ref.watch vs ref.listen", initial, budget=3000)

    assert any(chunk.source == "https://example.com/docs/concepts2/refs" for chunk in chunks)


def test_intent_rerank_prefers_tutorial_for_basic_example_query(tmp_path):
    config, store = _agent(tmp_path)
    dispatcher = RetrievalDispatcher(store=store, config=config)
    advanced = RetrievedChunk(
        source="https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield",
        chunk_index=0,
        text="Advanced dependencies with yield and HTTPException examples.",
        score=1.0,
        metadata={"title": "Dependencies with yield - FastAPI"},
    )
    tutorial = RetrievedChunk(
        source="https://fastapi.tiangolo.com/tutorial/dependencies",
        chunk_index=1,
        text="Use Depends with common_parameters in a path operation.",
        score=0.9,
        metadata={"title": "Dependencies - FastAPI"},
    )

    reranked = dispatcher._rerank_intent_matches(
        "FastAPI basic Depends example in a path operation",
        [advanced, tutorial],
    )

    assert reranked[0].source == "https://fastapi.tiangolo.com/tutorial/dependencies"


def test_intent_rerank_prefers_testing_tutorial_over_reference(tmp_path):
    config, store = _agent(tmp_path)
    dispatcher = RetrievalDispatcher(store=store, config=config)
    reference = RetrievedChunk(
        source="https://fastapi.tiangolo.com/reference/testclient",
        chunk_index=0,
        text="Reference details for TestClient methods.",
        score=1.0,
        metadata={"title": "Test Client - TestClient - FastAPI"},
    )
    tutorial = RetrievedChunk(
        source="https://fastapi.tiangolo.com/tutorial/testing",
        chunk_index=1,
        text="from fastapi.testclient import TestClient\nclient = TestClient(app)\nassert response.status_code == 200",
        score=0.9,
        metadata={"title": "Testing - FastAPI"},
    )

    reranked = dispatcher._rerank_intent_matches(
        "FastAPI test app with fastapi.testclient.TestClient client and pytest assertions",
        [reference, tutorial],
    )

    assert reranked[0].source == "https://fastapi.tiangolo.com/tutorial/testing"


def test_snippet_aware_rerank_prefers_matching_code_example(tmp_path):
    config, store = _agent(tmp_path)
    dispatcher = RetrievalDispatcher(store=store, config=config)
    prose = RetrievedChunk(
        source="https://example.com/reference/testclient",
        chunk_index=0,
        text="Reference prose about TestClient behavior and response objects.",
        score=1.0,
        metadata={"title": "TestClient reference"},
    )
    snippet = RetrievedChunk(
        source="https://example.com/tutorial/testing",
        chunk_index=1,
        text="Testing example.",
        score=0.9,
        metadata={
            "title": "Testing tutorial",
            "has_code_snippet": True,
            "code_snippets": [
                {
                    "language": "python",
                    "code": "from fastapi.testclient import TestClient\nclient = TestClient(app)\nassert response.status_code == 200",
                }
            ],
        },
    )

    reranked = dispatcher._rerank_intent_matches(
        "FastAPI TestClient pytest code example with assert",
        [prose, snippet],
    )

    assert reranked[0].source == "https://example.com/tutorial/testing"
