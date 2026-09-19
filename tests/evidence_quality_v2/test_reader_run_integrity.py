from __future__ import annotations

import hashlib

import pytest

from eval.evidence_quality_v2.reader_experiment import (
    independent_records,
    make_reader_record,
    pair_by_case_id,
)


MODEL = {
    "model": "qwen2.5:1.5b",
    "model_digest": "sha256:model",
    "runtime_version": "ollama-test",
    "chat_template_digest": "sha256:template",
}


def _row(case_id: str):
    return {"id": case_id, "value": case_id}


def test_pair_by_case_id_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate case id"):
        pair_by_case_id({"A": [_row("x"), _row("x")], "B": [_row("x")]})


def test_pair_by_case_id_rejects_missing_or_extra_ids():
    with pytest.raises(ValueError, match="case id mismatch"):
        pair_by_case_id({"A": [_row("x"), _row("y")], "B": [_row("x")]})


def test_pair_by_case_id_is_order_independent():
    paired = pair_by_case_id({"A": [_row("y"), _row("x")], "B": [_row("x"), _row("y")]})
    assert list(paired) == ["x", "y"]
    assert paired["x"]["A"]["value"] == "x"
    assert paired["y"]["B"]["value"] == "y"


def test_reused_output_is_not_an_independent_draw():
    rows = [
        {"case_id": "x", "arm": "A", "draw": 0},
        {"case_id": "x", "arm": "A", "draw": 1, "reused_from": "A:0"},
        {"case_id": "x", "arm": "A", "draw": 2},
    ]
    assert [row["draw"] for row in independent_records(rows)] == [0, 2]


def test_reader_record_binds_model_and_exact_model_input():
    response = {"message": {"content": "answer"}, "done_reason": "stop", "prompt_eval_count": 42, "eval_count": 5}
    record = make_reader_record(
        case_id="x", arm="view_json", draw=1,
        system_prompt="system", question="question", rendered_context="context",
        model_identity=MODEL, provider_response=response,
    )
    expected = hashlib.sha256("system\n\0question\n\0context".encode()).hexdigest()
    assert record["model_input_sha256"] == expected
    assert record["model_identity"] == MODEL
    assert record["provider_response"] == response
    assert record["provider_response"] is not response


def test_reader_record_requires_frozen_model_identity():
    with pytest.raises(ValueError, match="model identity"):
        make_reader_record(
            case_id="x", arm="A", draw=0,
            system_prompt="s", question="q", rendered_context="c",
            model_identity={"model": "qwen2.5:1.5b"}, provider_response={},
        )
