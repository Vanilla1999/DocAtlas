"""Mechanical source audit regression; semantic gold and labels are not changed."""
from copy import deepcopy

import pytest

from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import (
    _docs_source, _refresh_estimate, _snapshot_entry, validate_model_visible_projection,
)
from eval.evidence_quality_v2.run import audit_payload


def bound_context(tmp_path, raw):
    (tmp_path / "guide.md").write_bytes(raw.encode("utf-8"))
    original = {"path": "guide.md", "title": "Guide", "content": raw, "snippet": raw}
    source = _docs_source(original)
    assert source is not None
    # Explicit exact producer fixture, including its original final terminator.
    # This tests snapshot/range validation, not source authorization or relevance.
    source.update(snippet=raw, project_identity="project-fixture", authority="source_of_truth",
                  scope="project", line_start=1, line_end=len(raw.splitlines()))
    payload = _payload([source])
    snapshot = {source["evidence_id"]: _snapshot_entry(original, source)}
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    return payload, snapshot


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
@pytest.mark.parametrize("final_ending", [False, True])
def test_original_line_endings_and_last_terminator_are_accepted(tmp_path, ending, final_ending):
    raw = ending.join(["# Guide", "", "A documented fact.", "", "Only for the stated condition."])
    if final_ending:
        raw += ending
    payload, snapshot = bound_context(tmp_path, raw)
    before = deepcopy(payload)
    assert audit_payload(payload, snapshot, tmp_path) == []
    assert payload == before


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1), (True, 5), (1, 999)])
def test_invalid_or_out_of_file_range_is_rejected_after_positive(tmp_path, start, end):
    payload, snapshot = bound_context(tmp_path, "# Guide\n\nFact.\n\nCondition.\n")
    assert audit_payload(payload, snapshot, tmp_path) == []
    payload["sources"][0].update(line_start=start, line_end=end)
    _refresh_estimate(payload)
    assert "invalid source line range" in audit_payload(payload, snapshot, tmp_path)


def test_shifted_range_cannot_borrow_text_from_elsewhere(tmp_path):
    payload, snapshot = bound_context(tmp_path, "# Guide\n\nFact.\n\nCondition.\n")
    assert audit_payload(payload, snapshot, tmp_path) == []
    payload["sources"][0].update(line_start=3, line_end=5)
    _refresh_estimate(payload)
    errors = audit_payload(payload, snapshot, tmp_path)
    assert "source span does not occur inside claimed line range" in errors
    assert any("line_start" in error and "snapshot" in error for error in errors)


def test_forged_quote_is_not_accepted(tmp_path):
    payload, snapshot = bound_context(tmp_path, "# Guide\n\nFact.\n")
    assert audit_payload(payload, snapshot, tmp_path) == []
    payload["sources"][0]["snippet"] += "A fabricated addition."
    _refresh_estimate(payload)
    errors = audit_payload(payload, snapshot, tmp_path)
    assert "noncontiguous or nonexistent source snippet" in errors
    assert any("snippet" in error and "snapshot" in error for error in errors)


def test_edited_snapshot_does_not_validate_with_old_hash(tmp_path):
    payload, snapshot = bound_context(tmp_path, "# Guide\n\nFact.\n")
    assert audit_payload(payload, snapshot, tmp_path) == []
    key = payload["sources"][0]["evidence_id"]
    snapshot[key]["source"]["content"] += "changed"
    errors = audit_payload(payload, snapshot, tmp_path)
    assert "internal snapshot hash does not match its source content" in errors


def test_other_source_is_not_accepted(tmp_path):
    payload, snapshot = bound_context(tmp_path, "# Guide\n\nFact.\n")
    assert audit_payload(payload, snapshot, tmp_path) == []
    payload["sources"][0]["path_or_url"] = "missing.md"
    _refresh_estimate(payload)
    errors = audit_payload(payload, snapshot, tmp_path)
    assert "source escapes the isolated corpus" in errors
    assert any("path_or_url" in error and "snapshot" in error for error in errors)
