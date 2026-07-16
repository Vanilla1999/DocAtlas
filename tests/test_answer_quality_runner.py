from __future__ import annotations

import json
import inspect
import os
from pathlib import Path

import pytest

from eval import answer_quality_runner as runner


def test_patch_source_path_validation_is_snapshot_bound():
    projection = {"sources": [{"evidence_id": "ev-1", "path": "src/auth.py"}]}
    snapshot = {"ev-1": {"path": "src/auth.py"}}
    contract = {"acceptable_evidence": ["src/auth.py"]}

    assert runner._validate_patch_source_paths(projection, snapshot, contract) == []

    projection["sources"][0]["path"] = "src/legacy_auth.py"
    assert runner._validate_patch_source_paths(projection, snapshot, contract) == [
        "citation:path_mismatch",
        "citation:unacceptable_evidence:src/legacy_auth.py",
        "citation:acceptable_evidence_missing:src/auth.py",
    ]


def test_integrity_gate_requires_the_specific_snapshot_binding_error(monkeypatch):
    inputs = {
        "docs_answer": (
            {"sources": [{"path_or_url": "docs/auth.md"}]},
            {},
            800,
        ),
        "patch_context": (
            {"sources": [{"path": "src/auth.py"}]},
            {},
            800,
        ),
    }
    monkeypatch.setattr(
        runner,
        "validate_model_visible_projection",
        lambda *_args, **_kwargs: ["projection estimate mismatch or budget exceeded"],
    )

    report = runner._run_integrity_mutation_gate(inputs)

    assert report["status"] == "FAIL"
    assert report["checks"]["docs_answer"]["passed"] is False
    assert report["checks"]["patch_context"]["passed"] is False


def test_integrity_gate_accepts_explicit_snapshot_binding_rejections(monkeypatch):
    inputs = {
        "docs_answer": (
            {"sources": [{"path_or_url": "docs/auth.md"}]},
            {},
            800,
        ),
        "patch_context": (
            {"sources": [{"path": "src/auth.py"}]},
            {},
            800,
        ),
    }

    def reject_path(projection, **_kwargs):
        source = projection["sources"][0]
        key = "path" if "path" in source else "path_or_url"
        return [f"projection source {key} does not match the internal snapshot"]

    monkeypatch.setattr(runner, "validate_model_visible_projection", reject_path)

    report = runner._run_integrity_mutation_gate(inputs)

    assert report["status"] == "PASS"
    assert report["checks"]["docs_answer"]["passed"] is True
    assert report["checks"]["patch_context"]["passed"] is True


def test_checked_provider_free_observation_passes_automated_gates():
    data = Path("eval/answer_quality")
    result = json.loads((data / "result_v1.json").read_text(encoding="utf-8"))
    baseline = json.loads((data / "baseline_v1.json").read_text(encoding="utf-8"))
    human = json.loads(
        (data / "human_review_inputs_v1.json").read_text(encoding="utf-8")
    )

    failed = {row["contract_id"] for row in result["results"] if not row["passed"]}
    assert failed == set()
    assert result["provider_free_verdict"] == "INCONCLUSIVE"
    assert result["automated_quality_gate"] == "PASS"
    assert result["integrity_mutation_gate"]["status"] == "PASS"
    assert result["frozen_baseline_pareto_gate"]["status"] == "PASS"
    assert result["lower_layers"]["task39"]["status"] == "PASS"
    assert result["lower_layers"]["task42"]["status"] == "PASS"
    assert (
        result["lower_layers"]["task42"]["candidate_order_permutation_gate"]
        == "PASS"
    )
    assert "retrieval_projection_p95_ms" not in result["groups"]["docs_answer"]
    assert "retrieval_projection_p95_ms" in baseline["groups"]["docs_answer"]
    assert human["review_status"] == "PENDING_HUMAN_REVIEW"
    assert baseline["deterministic_result_digest"] != result[
        "deterministic_result_digest"
    ]
    assert result["deterministic_result_digest"] == human[
        "deterministic_result_digest"
    ]
    assert len(human["cases"]) == 6
    assert all(
        row["review_context"]["question"].strip() for row in human["cases"]
    )
    forbidden = next(
        row
        for row in human["cases"]
        if row["contract_id"] == "t42-adv-forbidden-source"
    )
    assert forbidden["projection"]["status"] == "ok"
    assert forbidden["projection"]["limitations"] == [
        "The selected evidence does not provide a concrete configuration key, "
        "value, command, or API call."
    ]


def test_paired_baseline_does_not_spawn_a_python_evaluator():
    source = inspect.getsource(runner._paired_baseline_groups)

    assert "sys.executable" not in source
    assert "_measure_product_groups" in source


def test_timing_artifact_requires_one_process():
    protocol = {
        "timing": {
            "warmup_repeats_per_case": 1,
            "measured_repeats_per_case": 2,
        }
    }
    groups = {
        kind: {"retrieval_projection_p95_ms": 1.0}
        for kind in ("docs_answer", "patch_context")
    }

    artifact = runner._timing_artifact(
        protocol,
        {},
        groups,
        groups,
        False,
        {"candidate_pid": os.getpid(), "baseline_pid": os.getpid()},
    )

    assert artifact["measurement_mode"] == "paired_same_process"
    assert artifact["process_identity"]["candidate_pid"] == artifact[
        "process_identity"
    ]["baseline_pid"]
    with pytest.raises(RuntimeError, match="different processes"):
        runner._timing_artifact(
            protocol,
            {},
            groups,
            groups,
            False,
            {"candidate_pid": 1, "baseline_pid": 2},
        )


def test_measure_case_obeys_frozen_repeat_counts():
    calls = 0

    def projection():
        nonlocal calls
        calls += 1
        return ({"status": "ok"}, {}, [])

    measured = runner._measure_case(
        projection,
        {
            "timing": {
                "warmup_repeats_per_case": 3,
                "measured_repeats_per_case": 5,
            }
        },
    )

    assert calls == 8
    assert len(measured["samples_ms"]) == 5


def test_review_context_contains_public_question_without_expected_answer():
    context = runner._review_context(
        {
            "question": "How do I set retries?",
            "exact_version": "2.0",
            "required_evidence_paths": ["docs/retries.md"],
        },
        {"result_kind": "docs_answer"},
    )

    assert context == {
        "question": "How do I set retries?",
        "result_kind": "docs_answer",
        "required_evidence_paths": ["docs/retries.md"],
        "required_target_paths": [],
        "exact_version": "2.0",
    }
    assert not set(context).intersection({"expected_status", "expected_selected"})
