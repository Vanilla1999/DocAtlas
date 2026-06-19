"""Graceful FTS5 fallback when the configured embeddings provider has no API key."""
from __future__ import annotations

import logging

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document


def test_missing_openai_key_falls_back_to_fts5(tmp_path, monkeypatch, caplog):
    """Configuring openai embeddings without OPENAI_API_KEY must not abort ingest.

    Bare ``docmancer ingest`` should still index FTS5; the vector path is
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
