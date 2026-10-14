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

    # Exercise the real lexical store at the smallest public limit: removing a
    # denied top-ranked source must still expose the next permitted source.
    question = "How do I call `Client.open`?"
    ranked = store.query(question, limit=10, budget=config.query.default_budget)
    assert {chunk.source for chunk in ranked} == {"allowed", "forbidden"}
    denied = ranked[0].source
    remaining = ({"allowed", "forbidden"} - {denied}).pop()
    limited = RetrievalDispatcher(store=store, config=config).run(
        question, mode="lexical", limit=1, filters={"forbidden_sources": [denied]},
    )
    assert [chunk.source for chunk in limited.chunks] == [remaining]


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








# ---------------- hierarchical auto-enable ----------------




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


def test_lexical_compact_results_limit_sections_per_source_when_configured(tmp_path):
    config, store = _agent(tmp_path)
    config.retrieval.max_sections_per_source = 2
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
    config.retrieval.max_sections_per_source = 2
    _populate(store, [("Big Doc", "big-doc", "# Big Doc\n\n## A\nalpha.\n\n## B\nalpha.\n\n## C\nalpha.\n")])

    result = RetrievalDispatcher(store=store, config=config).run("alpha", mode="lexical", limit=3, expand="adjacent")

    assert len([chunk for chunk in result.chunks if chunk.source == "big-doc"]) >= 3
