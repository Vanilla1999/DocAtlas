"""Qualified-window retention controls; backend rank never grants admission."""
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks


@dataclass
class Window:
    path: str = "connected.md"
    score: float = 1.0
    stale: bool = False
    lifecycle_status: str = "active"
    metadata: dict = field(default_factory=dict)


def window(query_id, *, qualified=True, **kwargs):
    return Window(metadata={"retrieval_query_matches": {
        query_id: {"qualified": qualified},
    }}, **kwargs)


def rank(chunks, **kwargs):
    return rerank_project_doc_chunks(chunks, question="unchanged original question",
        intent=SimpleNamespace(broad=True), retain_found_windows=True, limit=1,
        broad_max_per_source=1, **kwargs)


@pytest.mark.parametrize("query_id", ["query-original", "query-lookup-1"])
def test_every_public_qualified_window_survives_retention(query_id):
    chunks = [window(query_id, score=float(32 - index)) for index in range(32)]
    before = [dict(chunk.metadata) for chunk in chunks]
    selected = rank(chunks)
    assert len(selected) == 32
    assert [chunk.score for chunk in selected] == [chunk.score for chunk in chunks]
    for chunk, metadata in zip(selected, before, strict=True):
        assert chunk.metadata["retrieval_query_matches"] == metadata["retrieval_query_matches"]
        assert not ({"answer_supported", "answer_available", "edit_ready"} & chunk.metadata.keys())
        assert set(chunk.metadata["retrieval_query_matches"]) == {query_id}


@pytest.mark.parametrize("query_id,qualified", [
    ("query-original", False), ("query-lookup-1", False),
    ("query-internal-1", True),
])
def test_backend_score_and_incoming_flags_do_not_admit_unqualified_windows(query_id, qualified):
    positive = window("query-original")
    assert len(rank([positive])) == 1
    rejected = window(query_id, qualified=qualified, score=1_000_000.0)
    rejected.metadata.update(context_eligible=True, qualified=True,
        answer_supported=True, edit_ready=True)
    selected = rank([positive, rejected], context_candidate_ids=frozenset({id(rejected)}))
    assert len(selected) == 1
    assert selected[0].score == positive.score
    assert selected[0].metadata["retrieval_query_matches"] == positive.metadata["retrieval_query_matches"]


@pytest.mark.parametrize("guard", ["stale", "lifecycle", "membership"])
def test_qualified_retention_still_reaches_current_guards(guard):
    chunks = [window("query-original")]
    kwargs = {"finite_member_paths": frozenset({"connected.md"})}
    assert len(rank(chunks, **kwargs)) == 1
    if guard == "stale":
        chunks[0].stale = True
    elif guard == "lifecycle":
        chunks[0].lifecycle_status = "archived"
    else:
        kwargs["finite_member_paths"] = frozenset({"irrelevant.md"})
    assert rank(chunks, **kwargs) == []
