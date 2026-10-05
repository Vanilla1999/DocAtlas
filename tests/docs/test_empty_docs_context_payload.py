"""Empty-selection constructor contract, not retrieval/answer-quality evidence."""
from copy import deepcopy

import pytest

from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)


@pytest.mark.parametrize("query_plan", [None, {"broad_context_only": True}, {
    "queries": [{"query_id": "q1", "facet_id": "f1", "text": "Missing fact"}],
    "assigned_requirement_ids": ["r1"],
}])
def test_empty_selection_is_valid_insufficient_context(query_plan):
    result = _payload([], query_plan=query_plan)
    assert result["status"] == "insufficient_evidence"
    assert result["kind"] == "docs_context"
    assert result["sources"] == []
    for key in ("context_available", "answer_supported", "answer_available", "edit_ready"):
        assert result[key] is False
    assert result["support_status"] == "insufficient_evidence"
    assert "recommended_next_action" not in result
    assert result["missing"]
    assert validate_model_visible_projection(result, snapshot={}, max_tokens=800) == []


def test_empty_selection_cannot_inherit_a_prior_full_decision():
    # An obsolete decision does not make an empty selection successful.
    result = _payload([], decision=object())
    assert result["status"] == "insufficient_evidence"
    assert not result.get("covered_query_ids")
    assert not result.get("facets")


def test_nonempty_payload_preserves_source_and_read_only_flags():
    source = {"evidence_id": "ev-fixture", "path_or_url": "guide.md",
              "section": "Guide", "snippet": "A documented statement.\n",
              "version_binding": "unversioned", "content_sha256": "a" * 64,
              "project_identity": "project-fixture", "authority": "source_of_truth",
              "scope": "project", "line_start": 1, "line_end": 1}
    before = deepcopy(source)
    result = _payload([source])
    assert source == before and result["sources"] == [before]
    assert result["status"] == "ok" and result["context_status"] == "ready"
    assert result["context_available"] is True
    assert result["answer_supported"] is False and result["edit_ready"] is False
