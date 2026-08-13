"""Graceful FTS5 fallback when the configured embeddings provider has no API key."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.retrieval.dispatch import HybridRetrievalError
from docmancer.retrieval.runtime import dispatcher_for_agent


def test_missing_openai_key_falls_back_to_fts5(tmp_path, monkeypatch, caplog):
    """Configuring openai embeddings without OPENAI_API_KEY must not abort ingest.

    Bare ``doc-atlas ingest`` should still index FTS5; the vector path is
    skipped with a clear log line so the user knows what happened.
    """
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")  # opt back into auto-vectors for this test
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.embeddings.provider = "openai"

    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)
    doc = Document(source="doc.md", content="# Auth\n\nUse OAuth.\n", metadata={"format": "markdown"})

    with caplog.at_level(logging.WARNING, logger="docmancer.agent"):
        sections = agent.ingest_documents([doc], with_vectors=True)

    assert sections >= 1
    # FTS5 retrieval still works.
    hits = agent.query("OAuth", limit=2, budget=1500)
    assert hits and "OAuth" in hits[0].text
    # The warning explains why vectors were skipped.
    assert any("OPENAI_API_KEY" in rec.message for rec in caplog.records)


def test_auto_vectors_zero_skips_vector_path(tmp_path, monkeypatch, caplog):
    """``DOCMANCER_AUTO_VECTORS=0`` opts out of the vector path entirely.

    Tests run with this flag; we assert here so the gate cannot regress.
    """
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-stub")  # would have triggered vectors if not for the opt-out

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")

    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)
    doc = Document(source="doc.md", content="# Hello\n\nworld.\n", metadata={"format": "markdown"})
    with caplog.at_level(logging.DEBUG, logger="docmancer.agent"):
        sections = agent.ingest_documents([doc], with_vectors=True)
    assert sections >= 1
    # No vector log lines, no embeddings provider load attempt.
    assert not any("embedded=" in rec.message for rec in caplog.records)


def test_vector_mode_does_not_activate_generation_when_sync_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "0")

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.retrieval.default_mode = "hybrid"

    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)
    doc = Document(
        source="doc.md",
        content="# Hybrid\n\nVector-required content.\n",
        metadata={"format": "markdown"},
    )

    with pytest.raises(RuntimeError, match="requires a complete vector index"):
        agent.ingest_documents([doc], with_vectors=True)

    assert agent.store.active_generation_id() is None
    assert agent.last_vector_sync_metrics["status"] == "failed"
    assert agent.last_vector_sync_metrics["reason"] == "disabled_by_environment"


def test_vector_sync_failure_after_fts_ingest_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)

    def fail_vectors(**_kwargs):
        raise RuntimeError("qdrant collection missing")

    monkeypatch.setattr(agent, "_sync_vectors_if_enabled", fail_vectors)
    doc = Document(source="doc.md", content="# BlocProvider\n\nBlocProvider provides a bloc.", metadata={"format": "markdown"})

    with pytest.raises(RuntimeError, match="vector indexing failed after FTS5 ingest: qdrant collection missing"):
        agent.ingest_documents([doc], with_vectors=True)


def test_vector_sync_failure_after_record_ingest_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)

    def fail_vectors(**_kwargs):
        raise RuntimeError("qdrant collection missing")

    monkeypatch.setattr(agent, "_sync_vectors_if_enabled", fail_vectors)
    records = [Document(source="record.md", content="# Record\n\nRecord content.", metadata={"format": "markdown"})]

    with pytest.raises(RuntimeError, match="vector indexing failed after FTS5 ingest: qdrant collection missing"):
        agent.ingest_records(records, with_vectors=True)


def test_retrieval_reuses_persisted_sqlite_backend_after_qdrant_recovers(monkeypatch):
    config = DocmancerConfig()
    config.retrieval.default_mode = "dense"
    config.vector_store.provider = "qdrant"
    config.vector_store.url = None
    captured = {}
    class VectorStore:
        @staticmethod
        def backend_identity():
            return "persisted-identity"

    vector_store = VectorStore()
    provider = object()

    class Store:
        @staticmethod
        def generation_info():
            return {
                "vector_backend": "sqlite-vec",
                "vector_backend_identity": "persisted-identity",
            }

    agent = SimpleNamespace(
        config=config,
        store=Store(),
        _vector_collection_name=lambda: "persisted_collection",
    )
    monkeypatch.setattr(
        "docmancer.runtime.qdrant_manager.ensure_running",
        lambda: pytest.fail("managed qdrant must not be probed for a sqlite-bound generation"),
    )

    def build_store(vector_config, *, embeddings_dim):
        captured["provider"] = vector_config.provider
        captured["dimensions"] = embeddings_dim
        return vector_store

    monkeypatch.setattr("docmancer.stores.base.get_vector_store", build_store)
    monkeypatch.setattr("docmancer.embeddings.get_embeddings_provider", lambda _config: provider)

    dispatcher = dispatcher_for_agent(agent)

    assert dispatcher.vector_store is vector_store
    assert captured["provider"] == "sqlite-vec"


def test_retrieval_does_not_switch_qdrant_generation_to_sqlite_fallback(monkeypatch):
    config = DocmancerConfig()
    config.retrieval.default_mode = "dense"
    config.vector_store.provider = "qdrant"
    config.vector_store.url = None

    class Store:
        @staticmethod
        def generation_info():
            return {"vector_backend": "qdrant"}

    agent = SimpleNamespace(
        config=config,
        store=Store(),
        _vector_collection_name=lambda: "persisted_collection",
    )
    monkeypatch.setattr(
        "docmancer.runtime.qdrant_manager.ensure_running",
        lambda: SimpleNamespace(fallback=True, url=None),
    )

    with pytest.raises(HybridRetrievalError, match="active generation requires qdrant"):
        dispatcher_for_agent(agent)


def test_active_staging_generation_gets_unique_collection_before_vector_sync(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "staging.db")

    from docmancer.agent import DocmancerAgent

    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(
            source="guide.md",
            content="# Guide\n\nCandidate content.",
            metadata={"format": "markdown"},
        )],
        with_vectors=False,
    )
    generation_id = agent.store.active_generation_id()
    before = agent.store.generation_info(generation_id)

    prepared = agent.prepare_vector_generation(generation_id)

    after = agent.store.generation_info(generation_id)
    assert before is not None and after is not None
    assert prepared != before["vector_collection"]
    assert after["vector_collection"] == prepared
    assert generation_id.removeprefix("gen-")[:12] in prepared
    agent.store.set_generation_vector_backend(generation_id, "sqlite-vec")
    with pytest.raises(ValueError, match="candidate generation"):
        agent.prepare_vector_generation(generation_id)
