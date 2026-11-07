from __future__ import annotations

import pytest
import copy
import hashlib

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.retrieval.contextual_indexing import (
    _canonical_url,
    build_context_prefix,
    embedding_input,
    extract_symbol_aliases,
    normalized_filter_metadata,
)
from docmancer.retrieval.contracts import CandidateHit, ContextConfig
from docmancer.retrieval.query_planning import build_query_plan, compile_backend_filters
from docmancer.retrieval.runtime import dispatcher_for_agent














def test_generation_reserves_catalog_description_token_budget(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "index.db")
    agent = DocmancerAgent(config=config)
    description = "canonical migration runbook"
    content = "# Guide\n\n" + "bounded project documentation content " * 600

    sections = agent.ingest_documents([
        Document(
            source="guide.md",
            content=content,
            metadata={
                "format": "markdown",
                "source_class": "project_file",
                "project_docs": True,
                "project_doc_description": description,
            },
        ),
    ], with_vectors=False)

    assert sections > 0
    generation = agent.store.generation_info()
    assert generation is not None
    assert generation["status"] == "active"
    with agent.store._connect() as connection:
        rows = connection.execute(
            "SELECT retrieval_text, retrieval_token_estimate "
            "FROM retrieval_children WHERE generation_id = ?",
            (generation["generation_id"],),
        ).fetchall()
    assert rows
    assert all(row["retrieval_text"].count(description) == 2 for row in rows)
    assert all(row["retrieval_token_estimate"] <= 512 for row in rows)


def test_source_bound_search_descriptions_public_lifecycle(tmp_path, monkeypatch):
    """Real lexical ingestion/selection; annotations never become source evidence."""
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "index.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    agent = DocmancerAgent(config=config)
    text = ("# Receiver\n\nCooling prevents restart. The receiver waits 19 seconds.\n\n"
            "# Archive\n\nRecords are retained for 41 nights.\n\n"
            "# Long procedure\n\n" + "The operator checks the receiver before restarting it. " * 30)
    metadata = {"format": "markdown", "source_path": "receiver.md",
                "doc_scope": "project", "project_identity": "fixture-project",
                "source_class": "project_file", "resolved_version": "snapshot-1"}
    document = Document(source="receiver.md", content=text, metadata=metadata)
    agent.ingest_documents([document, Document(
        source="private.md", content="# Lockout\n\nPRIVATE_ONLY lockout.\n",
        metadata={**metadata, "source_path": "private.md", "project_identity": "other"},
    )], with_vectors=False)
    baseline = [row for row in agent.store.list_sections_for_embedding() if row["source"] == "receiver.md"]
    filters = {"project_identity": "fixture-project", "doc_scope": "project",
               "source_class": "project_file", "resolved_version": "snapshot-1"}
    before = dispatcher_for_agent(agent, mode="lexical").run(
        "lockout", mode="lexical", filters=filters, limit=5, budget=4096, expand="none")
    assert not before.chunks
    sha = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    receiver = next(row for row in baseline if "The receiver waits 19 seconds." in row["display_text"])
    archive = next(row for row in baseline if "Records are retained for 41 nights." in row["display_text"])
    large = max(baseline, key=lambda row: row["retrieval_token_estimate"])
    assert large["retrieval_token_estimate"] > 384
    descriptions = [(receiver, "Receiver cooling lockout prevents restart for 19 seconds."),
                    (archive, "Archive retention. " * 40), (large, "x" * 512)]
    artifact = {"source_path": "receiver.md", "source_sha256": sha(text),
                "context_sha256": sha(text), "recipe": "integration-fixture", "version": "1",
                "model": "fixture-authored", "model_revision": None,
                "records": [{"char_start": row["char_start"], "char_end": row["char_end"],
                             "display_sha256": sha(row["display_text"]), "description": description,
                             "description_sha256": sha(description)} for row, description in descriptions]}
    enriched = Document(source="receiver.md", content=text,
                        metadata={**metadata, "experimental_search_descriptions_v1": artifact})
    agent.ingest_documents([enriched], with_vectors=False)
    rows = [row for row in agent.store.list_sections_for_embedding() if row["source"] == "receiver.md"]
    assert [(r["char_start"], r["char_end"], r["display_text"], r["stable_chunk_id"], r["vector_id"])
            for r in rows] == [(r["char_start"], r["char_end"], r["display_text"], r["stable_chunk_id"], r["vector_id"])
                              for r in baseline]
    selected = next(row for row in rows if row["stable_chunk_id"] == receiver["stable_chunk_id"])
    assert selected["text"] == receiver["text"] + "\n" + descriptions[0][1]
    assert selected["content_hash"] != receiver["content_hash"]
    for original in (archive, large):
        assert next(r for r in rows if r["stable_chunk_id"] == original["stable_chunk_id"])["text"] == original["text"]
    hydrated = agent.store.fetch_sections_by_id([r["section_id"] for r in rows], budget=4096)
    statuses = {chunk.metadata["experimental_search_description_v1"]["status"]
                for chunk in hydrated if "experimental_search_description_v1" in chunk.metadata}
    assert statuses == {"appended", "skipped_description_bytes", "skipped_retrieval_budget"}
    for chunk in hydrated:
        assert "experimental_search_descriptions_v1" not in chunk.metadata
        start, end = chunk.metadata["char_span"]
        assert chunk.text == text[start:end]
        assert chunk.metadata["content_hash"] == sha(chunk.text)
        assert chunk.metadata["source_content_hash"] == sha(text)
    result = dispatcher_for_agent(agent, mode="lexical").run(
        "lockout", mode="lexical", filters=filters, limit=5, budget=4096, expand="none")
    assert any("The receiver waits 19 seconds." in chunk.text for chunk in result.chunks)
    for chunk in result.chunks:
        assert chunk.source == "receiver.md"
        assert chunk.text in text
        assert "lockout" not in chunk.text
        assert "PRIVATE_ONLY" not in chunk.text
    generation = agent.store.active_generation_id()
    stale = copy.deepcopy(artifact)
    stale["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="binding mismatch"):
        agent.ingest_documents([Document(source="receiver.md", content=text,
            metadata={**metadata, "experimental_search_descriptions_v1": stale})], with_vectors=False)
    assert agent.store.active_generation_id() == generation
    assert [r["text"] for r in agent.store.list_sections_for_embedding() if r["source"] == "receiver.md"] == [r["text"] for r in rows]







