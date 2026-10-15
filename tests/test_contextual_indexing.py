from __future__ import annotations

import pytest

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









