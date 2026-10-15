from __future__ import annotations

from docmancer.core.models import RetrievedChunk
from scripts.run_systemic_retrieval_plan_gate import _candidate_pool_fingerprint


def _chunk(*, section_id: int, stable_id: str, parent_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        source="/tmp/volatile-fixture-root/docs/policy.md",
        chunk_index=7,
        text=text,
        score=1.0,
        metadata={
            "section_id": section_id,
            "stable_chunk_id": stable_id,
            "parent_logical_id": parent_id,
            "project_doc_path": "docs/policy.md",
            "source_path": "docs/policy.md",
            "source_class": "project_file",
        },
    )


def _isolated_chunk(source: str) -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        chunk_index=7,
        text="Policy fact.",
        score=1.0,
        metadata={"source_class": "project_file"},
    )

















