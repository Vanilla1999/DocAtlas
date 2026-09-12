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


def test_candidate_pool_fingerprint_ignores_fresh_index_ids() -> None:
    first = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Policy fact.")]
    rebuilt = [_chunk(section_id=907, stable_id="stable-b", parent_id="parent-b", text="Policy fact.")]

    assert _candidate_pool_fingerprint(first) == _candidate_pool_fingerprint(rebuilt)


def test_candidate_pool_fingerprint_detects_semantic_candidate_change() -> None:
    first = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Policy fact.")]
    changed = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Different policy fact.")]

    assert _candidate_pool_fingerprint(first) != _candidate_pool_fingerprint(changed)
