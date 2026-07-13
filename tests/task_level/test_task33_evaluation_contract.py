from __future__ import annotations

import json
from dataclasses import replace

from eval.task_level.analysis import task23_report
from eval.task_level.analysis.task23_decision import apply_protocol_amendment
from eval.task_level.analysis.task23_report import _failure_reason, build_task23_report
from eval.task_level.evaluators.task_contract import evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_effective_task23_protocol_tasks, load_task_evaluation_contracts, validate_task_evaluation_artifacts, validate_task_evaluation_contract
from eval.task_level.execution import _assert_task33_run_preconditions
from eval.task_level.fixtures import builder
from eval.task_level.fixtures.builder import materialize_fixture, validate_fixture
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH, TASK_LEVEL_ROOT


def _effective_protocol() -> dict:
    protocol = json.loads((TASK_LEVEL_ROOT / "task23_protocol.json").read_text(encoding="utf-8"))
    amendment = json.loads((TASK_LEVEL_ROOT / "task23_protocol_amendment_001.json").read_text(encoding="utf-8"))
    return apply_protocol_amendment(protocol, amendment)


def test_task33_contracts_cover_exactly_the_three_effective_tasks():
    tasks = {task.task_id: task for task in load_tasks(TASKS_PATH)}
    effective = _effective_protocol()
    expected = {entry["task_id"] for entry in effective["tasks"]}
    contracts = load_task_evaluation_contracts()
    protocol_tasks = load_effective_task23_protocol_tasks()

    assert len(expected) == 3
    assert set(contracts) == expected
    for task_id, contract in contracts.items():
        validation = validate_task_evaluation_contract(tasks[task_id], contract)
        assert validation.valid, (task_id, validation.errors)
        assert contract.compile_gate.mode == "not_applicable"
        assert contract.compile_gate.reason
        assert contract.local_test_command.startswith("python -m pytest ")
        assert contract.semantic_test_command == "python -m pytest tests/hidden"
        assert validate_task_evaluation_artifacts(contract, protocol_tasks[task_id]).valid
        assert len(evaluation_contract_sha256(contract)) == 64
    broken = replace(next(iter(contracts.values())), fixture_sha256="0" * 64)
    assert "actual_fixture_sha256_mismatch" in validate_task_evaluation_artifacts(
        broken,
        protocol_tasks[broken.task_id],
    ).errors
    assert len(evaluation_contract_registry_sha256()) == 64


def test_three_task33_fixtures_validate_locally_without_language_sdks(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "VALIDATION_ROOT", tmp_path / "validation")
    tasks = {task.task_id: task for task in load_tasks(TASKS_PATH)}
    contracts = load_task_evaluation_contracts()

    for task_id in sorted(contracts):
        workspace = tmp_path / task_id
        materialize_fixture(tasks[task_id], workspace)
        result = validate_fixture(tasks[task_id], workspace, local_commands=True)

        assert result["status"] == "validated", result
        assert result["evaluation_contract"]["status"] == "valid"
        assert result["evaluation_contract"]["compile_gate"]["status"] == "not_applicable"
        assert result["evaluation_contract"]["semantic_gate"]["status"] == "passed"
        assert result["evaluation_contract"]["patch_surface"]["status"] == "passed"
        assert len(result["evaluation_contract"]["contract_sha256"]) == 64
        assert len(result["evaluation_contract"]["registry_sha256"]) == 64
        assert result["gold"]["public_tests_passed"] is True
        assert result["gold"]["hidden_tests_passed"] is True


def test_task33_evaluation_fails_closed_without_relabeling_not_applicable_compile(monkeypatch):
    task = next(task for task in load_tasks(TASKS_PATH) if task.task_id == "decisive_nbo_cross_module_gate_large_001")
    missing = validate_task_evaluation_contract(task, None)
    contract = load_task_evaluation_contracts()[task.task_id]
    surface = evaluate_patch_surface(contract, ["tests/test_browser_permission_gate.py"])

    assert missing.status == "invalid"
    assert missing.errors == ("patch_contract_not_defined",)
    assert surface["status"] == "failed"
    assert surface["violations"] == ["tests/test_browser_permission_gate.py"]
    assert _failure_reason({
        "status": "completed",
        "policy_clean": True,
        "compile_success": None,
        "compile_status": "not_applicable",
        "public_tests_passed": True,
        "hidden_tests_passed": False,
    }) == "hidden_tests_failed"

    protocol = _effective_protocol()
    contracts = load_task_evaluation_contracts()
    rows = []
    for entry in protocol["tasks"]:
        entry_contract = contracts[entry["task_id"]]
        for repeat in range(protocol["repeats_per_task_condition"]):
            for condition in protocol["conditions"]:
                rows.append({
                    "task_id": entry["task_id"],
                    "repeat": repeat,
                    "condition_id": condition,
                    "status": "completed",
                    "resolved": False,
                    "policy_clean": True,
                    "compile_success": None,
                    "compile_status": "not_applicable",
                    "public_tests_passed": True,
                    "hidden_tests_passed": False,
                    "evaluation_contract": {
                        "status": "valid",
                        "patch_contract_id": entry_contract.patch_contract_id,
                        "contract_sha256": evaluation_contract_sha256(entry_contract),
                        "registry_sha256": evaluation_contract_registry_sha256(),
                        "artifact_identity": entry_contract.to_json()["artifact_identity"],
                    },
                    "budget": {
                        "max_input_tokens": 120_000,
                        "max_output_tokens": 30_000,
                        "max_turns": 40,
                        "input_tokens_exceeded": False,
                        "output_tokens_exceeded": False,
                        "max_turns_enforced_by_runner": False,
                    },
                    "metrics": {
                        "input_tokens": 1_000,
                        "output_tokens": 100,
                        "total_tokens": 1_100,
                        "wall_time_seconds": 10.0,
                    },
                })

    report = build_task23_report(rows, protocol=protocol)

    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "max_turn_budget_not_enforced" in report["decision"]["reasons"]
    assert "missing_or_invalid_evaluation_contract" not in report["decision"]["reasons"]
    assert report["evaluation_contract_integrity"]["valid_runs"] == 36
    assert report["budget_integrity"]["ok"] is False
    assert report["conditions"]["repo_only_strict_offline"]["compile_success_rate"] is None
    assert report["failure_taxonomy"]["repo_only_strict_offline"] == {"hidden_tests_failed": 9}

    rows[0].pop("evaluation_contract")
    invalid_report = build_task23_report(rows, protocol=protocol)

    assert invalid_report["decision"]["decision"] == "INCONCLUSIVE"
    assert "missing_or_invalid_evaluation_contract" in invalid_report["decision"]["reasons"]
    assert invalid_report["evaluation_contract_integrity"]["valid_runs"] == 35

    class NoHardTurnRunner:
        hard_turn_limit_enforced = False

    try:
        _assert_task33_run_preconditions([task], NoHardTurnRunner())
    except ValueError as exc:
        assert "proven hard turn limit" in str(exc)
    else:
        raise AssertionError("Task 33 run must be blocked without a hard turn limit")

    monkeypatch.delitem(task23_report.TASK33_EVALUATION_CONTRACTS, task.task_id)
    missing_registry_report = build_task23_report(rows, protocol=protocol)
    assert missing_registry_report["evaluation_contract_integrity"]["ok"] is False
    assert task.task_id in missing_registry_report["evaluation_contract_integrity"]["missing_registry_task_ids"]
