from __future__ import annotations

import copy
from pathlib import Path

import pytest

from eval.product_truth_v1.protocol import (
    load_json,
    protocol_sha256,
    validate_ledger,
    validate_protocol,
    validate_repository,
    validate_result_semantics,
    validate_task_run_binding,
)


ROOT = Path(__file__).resolve().parents[2]
P2 = ROOT / "eval" / "product_truth_v1"


def test_repository_protocol_and_samples_are_reproducible() -> None:
    result = validate_repository(ROOT)
    assert result["canary_scored_runs"] == 16
    assert result["minimum_scored_runs"] == 576
    assert result["maximum_scored_runs"] == 720


def test_preregistration_claim_boundary_fails_closed() -> None:
    protocol = load_json(P2 / "protocol.lock.json")
    unsafe = copy.deepcopy(protocol)
    unsafe["claim_boundary"]["product_truth_proven"] = True
    unsafe["protocol_sha256"] = protocol_sha256(unsafe)
    with pytest.raises(ValueError, match="overclaims"):
        validate_protocol(unsafe)


def test_cardinality_and_positive_controls_are_immutable() -> None:
    protocol = load_json(P2 / "protocol.lock.json")
    drifted = copy.deepcopy(protocol)
    drifted["benchmark_design"]["tasks_per_repository"]["minimum"] = 7
    drifted["protocol_sha256"] = protocol_sha256(drifted)
    with pytest.raises(ValueError, match="cardinality"):
        validate_protocol(drifted)

    drifted = copy.deepcopy(protocol)
    drifted["task_validity"]["required_positive_controls"] = ["gold_patch"]
    drifted["protocol_sha256"] = protocol_sha256(drifted)
    with pytest.raises(ValueError, match="gold and oracle"):
        validate_protocol(drifted)


def test_task_run_and_result_semantics_fail_closed() -> None:
    task = load_json(P2 / "fixtures" / "sample-task.json")
    run = load_json(P2 / "fixtures" / "sample-run.json")
    result = load_json(P2 / "fixtures" / "sample-result.json")

    wrong_task = copy.deepcopy(task)
    wrong_task["fixture_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="fixture_sha256"):
        validate_task_run_binding(wrong_task, run)

    wrong_result = copy.deepcopy(result)
    wrong_result["safety"]["forbidden_file_touches"] = 1
    with pytest.raises(ValueError, match="critical safety"):
        validate_result_semantics(wrong_result)


def test_ledger_mutation_is_detected() -> None:
    ledger = load_json(P2 / "fixtures" / "sample-ledger.json")
    ledger["events"][0]["payload"]["run_id"] = "forged"
    with pytest.raises(ValueError, match="payload digest"):
        validate_ledger(ledger)
