from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace

from eval.task_level.analysis import task23_report
from eval.task_level.analysis.task23_decision import apply_protocol_amendment
from eval.task_level.analysis.task23_report import _failure_reason, build_task23_report
from eval.task_level.evaluators.task_contract import evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_effective_task23_protocol_tasks, load_task_evaluation_contracts, validate_task_evaluation_artifacts, validate_task_evaluation_contract
from eval.task_level.execution import _assert_task33_run_preconditions
from eval.task_level.fixtures import builder
from eval.task_level.fixtures.builder import materialize_fixture, validate_fixture
from eval.task_level.hidden_tests.decisive_nbo_cross_module_gate_large_001.test_hidden_cross_module_gate_large import (
    _delegates_and_requires_allow,
    _method_body as _hidden_method_body,
)
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH, TASK_LEVEL_ROOT


def _effective_protocol() -> dict:
    protocol = json.loads((TASK_LEVEL_ROOT / "task23_protocol.json").read_text(encoding="utf-8"))
    amendment = json.loads((TASK_LEVEL_ROOT / "task23_protocol_amendment_001.json").read_text(encoding="utf-8"))
    return apply_protocol_amendment(protocol, amendment)


def _materialize_task33_gold(tmp_path):
    task = next(
        task
        for task in load_tasks(TASKS_PATH)
        if task.task_id == "decisive_nbo_cross_module_gate_large_001"
    )
    workspace = tmp_path / task.task_id
    materialize_fixture(task, workspace)
    oracle = TASK_LEVEL_ROOT / "oracles" / f"{task.task_id}.patch"
    applied = subprocess.run(
        ["git", "apply", str(oracle)],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert applied.returncode == 0, applied.stdout
    builder.copy_hidden_tests(task.task_id, workspace)
    return workspace


def _run_task33_oracles(workspace):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_browser_permission_gate.py",
            "tests/hidden",
            "-q",
        ],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


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


def test_scan_gate_oracle_requires_exact_shared_entry_call_semantics():
    assert _delegates_and_requires_allow(
        "return _permissionService.evaluateFlowEntry(result) == PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "final decision = _permissionService.evaluateFlowEntry(result);\n"
        "return decision == PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "return _permissionService.evaluateFlowEntry("
        "result, allowOfflineFallback: false) == PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "final decision = _permissionService.evaluateFlowEntry(\n"
        "  result,\n"
        "  allowOfflineFallback: false,\n"
        ");\n"
        "return decision == PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "return PermissionService.evaluateFlowEntry("
        "result, allowOfflineFallback: true) == PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "return wrap(PermissionService.evaluateFlowEntry(result)) "
        "== PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "if (flag) return true;\n"
        "return PermissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "final decision = PermissionService.evaluateFlowEntry(result);\n"
        "if (decision == PermissionDecision.deferFollowUp) return true;\n"
        "return decision == PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "return _permissionService.evaluateFlowEntry("
        "result, allowOfflineFallback: true) == PermissionDecision.allow;",
        required_fallback=True,
    )
    assert not _delegates_and_requires_allow(
        "return PermissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;",
        required_fallback=False,
    )
    assert not _delegates_and_requires_allow(
        "if (flag) return true;\n"
        "return PermissionService.evaluateFlowEntry("
        "result, allowOfflineFallback: true) == PermissionDecision.allow;",
        required_fallback=True,
    )
    assert _delegates_and_requires_allow(
        "return this._permissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "final PermissionDecision decision = "
        "this._permissionService.evaluateFlowEntry(result);\n"
        "return decision == PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "return rogue.evaluateFlowEntry(result) == PermissionDecision.allow;"
    )


def test_hidden_method_body_ignores_comment_decoys(tmp_path):
    gate = tmp_path / "gate.dart"
    gate.write_text(
        "/* bool canEnter(PermissionResult result) {\n"
        "  return PermissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;\n"
        "  } */\n"
        "class BrowserPermissionGate {\n"
        "  bool canEnter(PermissionResult result) {\n"
        "    return true;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    assert "return true;" in _hidden_method_body(
        gate, "BrowserPermissionGate", "canEnter"
    )


def test_task33_hidden_service_check_is_method_order_independent(tmp_path):
    workspace = _materialize_task33_gold(tmp_path)
    service = workspace / "lib/modules/permission/application/permission_service.dart"
    source = service.read_text(encoding="utf-8")
    entry_start = source.index("  PermissionDecision evaluateFlowEntry")
    review_start = source.index("  PermissionDecision evaluateReview")
    class_end = source.rindex("\n}")
    entry = source[entry_start:review_start]
    review = source[review_start:class_end]
    service.write_text(
        source[:entry_start] + review + "\n" + entry + source[class_end:],
        encoding="utf-8",
    )
    browser = workspace / "lib/modules/browser/application/browser_permission_gate.dart"
    browser.write_text(
        browser.read_text(encoding="utf-8")
        + "\n// hasMissingImmediatePermission is a non-code architecture note.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/hidden", "-q"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout


def test_task33_hidden_sync_check_rejects_early_return(tmp_path):
    workspace = _materialize_task33_gold(tmp_path)
    command = [sys.executable, "-m", "pytest", "tests/hidden", "-q"]
    gold = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert gold.returncode == 0, gold.stdout

    sync = workspace / "lib/modules/sync/application/offline_sync_gate.dart"
    source = sync.read_text(encoding="utf-8")
    signature = "bool canAcceptQueuedWork(PermissionResult result) {"
    assert signature in source
    sync.write_text(
        source.replace(signature, signature + "\n    if (flag) return true;", 1),
        encoding="utf-8",
    )
    mutant = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert mutant.returncode != 0, mutant.stdout


def test_task33_public_browser_check_does_not_name_hidden_flow_surfaces():
    public_test = (
        TASK_LEVEL_ROOT
        / "fixtures/templates/decisive_nbo_cross_module_gate_large_001/tests/test_browser_permission_gate.py"
    ).read_text(encoding="utf-8")

    for hidden_surface in (
        "ScanPermissionGate",
        "scan_permission_gate.dart",
        "OfflineSyncGate",
        "offline_sync_gate.dart",
    ):
        assert hidden_surface not in public_test


def test_task33_public_browser_check_rejects_allow_or_defer_mutant(tmp_path):
    workspace = _materialize_task33_gold(tmp_path)

    command = [sys.executable, "-m", "pytest", "tests/test_browser_permission_gate.py", "-q"]
    gold = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert gold.returncode == 0, gold.stdout

    browser = workspace / "lib/modules/browser/application/browser_permission_gate.dart"
    source = browser.read_text(encoding="utf-8")
    gold_return = (
        "return _permissionService.evaluateFlowEntry(\n"
        "      result,\n"
        "      allowOfflineFallback: true,\n"
        "    ) == PermissionDecision.allow;"
    )
    assert gold_return in source

    browser.write_text(
        source.replace(gold_return, gold_return.replace("_permissionService", "this._permissionService")),
        encoding="utf-8",
    )
    qualified_receiver = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert qualified_receiver.returncode == 0, qualified_receiver.stdout

    typed_assignment = (
        "final PermissionDecision decision = this._permissionService.evaluateFlowEntry(\n"
        "      result,\n"
        "      allowOfflineFallback: true,\n"
        "    );\n"
        "    return decision == PermissionDecision.allow;"
    )
    browser.write_text(source.replace(gold_return, typed_assignment), encoding="utf-8")
    typed_result = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert typed_result.returncode == 0, typed_result.stdout

    browser.write_text(
        source.replace(gold_return, gold_return.replace("_permissionService", "rogue")),
        encoding="utf-8",
    )
    rogue_receiver = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert rogue_receiver.returncode != 0, rogue_receiver.stdout

    mutant_return = (
        "final decision = _permissionService.evaluateFlowEntry(\n"
        "      result,\n"
        "      allowOfflineFallback: true,\n"
        "    );\n"
        "    return decision == PermissionDecision.allow ||\n"
        "        decision == PermissionDecision.deferFollowUp;"
    )
    assert gold_return in source
    browser.write_text(source.replace(gold_return, mutant_return), encoding="utf-8")

    result = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode != 0, result.stdout

    browser.write_text(
        source.replace(gold_return, "if (flag) return true;\n    " + gold_return),
        encoding="utf-8",
    )
    early_return = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert early_return.returncode != 0, early_return.stdout

    block_or_other = (
        "return _permissionService.evaluateFlowEntry(\n"
        "      result,\n"
        "      allowOfflineFallback: true,\n"
        "    ) == PermissionDecision.block ||\n"
        "        otherDecision() == PermissionDecision.allow;"
    )
    browser.write_text(source.replace(gold_return, block_or_other), encoding="utf-8")
    alternate_allow = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert alternate_allow.returncode != 0, alternate_allow.stdout

    comment_decoy = (
        "/* bool canEnter(PermissionResult result) {\n"
        "  " + gold_return + "\n"
        "  } */\n"
    )
    unsafe_browser = source.replace(gold_return, "return true;")
    browser.write_text(comment_decoy + unsafe_browser, encoding="utf-8")
    decoy_result = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert decoy_result.returncode != 0, decoy_result.stdout

    correct_method = (
        "  final PermissionService _permissionService;\n"
        "  bool canEnter(PermissionResult result) {\n    "
        + gold_return
        + "\n  }\n"
    )
    unsafe_browser = source.replace(gold_return, "return true;")
    browser.write_text(
        "class DecoyGate {\n" + correct_method + "}\n" + unsafe_browser,
        encoding="utf-8",
    )
    class_decoy = _run_task33_oracles(workspace)
    assert class_decoy.returncode != 0, class_decoy.stdout

    browser.write_text(
        source.replace(
            "final PermissionService _permissionService;",
            "final RoguePermissionService _permissionService;",
        ),
        encoding="utf-8",
    )
    rogue_field = _run_task33_oracles(workspace)
    assert rogue_field.returncode != 0, rogue_field.stdout

    browser.write_text(
        "/* outer comment\n/* nested comment */\n"
        "class DecoyGate {\n"
        + correct_method
        + "}\n*/\n"
        + unsafe_browser,
        encoding="utf-8",
    )
    nested_comment_decoy = _run_task33_oracles(workspace)
    assert nested_comment_decoy.returncode != 0, nested_comment_decoy.stdout


def test_task33_public_service_check_rejects_reordered_defer_entry_mutant(tmp_path):
    workspace = _materialize_task33_gold(tmp_path)

    command = [sys.executable, "-m", "pytest", "tests/test_browser_permission_gate.py", "-q"]
    gold = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert gold.returncode == 0, gold.stdout

    service = workspace / "lib/modules/permission/application/permission_service.dart"
    source = service.read_text(encoding="utf-8")
    entry_start = source.index("  PermissionDecision evaluateFlowEntry")
    review_start = source.index("  PermissionDecision evaluateReview")
    class_end = source.rindex("\n}")
    entry = source[entry_start:review_start]
    review = source[review_start:class_end]
    mutant_entry = entry.replace(
        "return PermissionDecision.block;",
        "return PermissionDecision.deferFollowUp;",
        1,
    )
    assert mutant_entry != entry
    service.write_text(
        source[:entry_start] + review + "\n" + mutant_entry + source[class_end:],
        encoding="utf-8",
    )

    result = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode != 0, result.stdout

    missing_branch = (
        "if (result.hasMissingImmediatePermission) {\n"
        "      return PermissionDecision.block;\n"
        "    }"
    )
    unrelated_block = (
        "if (result.hasMissingImmediatePermission) {\n"
        "      return PermissionDecision.allow;\n"
        "    }\n"
        "    if (allowOfflineFallback) {\n"
        "      return PermissionDecision.block;\n"
        "    }"
    )
    assert missing_branch in source
    service.write_text(source.replace(missing_branch, unrelated_block), encoding="utf-8")
    linked_branch = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_browser_permission_gate.py",
            "tests/hidden",
            "-q",
        ],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert linked_branch.returncode != 0, linked_branch.stdout

    nested_branch = (
        "if (allowOfflineFallback) {\n"
        "      if (result.hasMissingImmediatePermission) {\n"
        "        return PermissionDecision.block;\n"
        "      }\n"
        "    }"
    )
    service.write_text(source.replace(missing_branch, nested_branch), encoding="utf-8")
    nested_guard = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_browser_permission_gate.py",
            "tests/hidden",
            "-q",
        ],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert nested_guard.returncode != 0, nested_guard.stdout

    unsafe_service = source.replace(
        "return PermissionDecision.block;",
        "return PermissionDecision.allow;",
        1,
    )
    service.write_text(
        "class DecoyService {\n" + entry + "}\n" + unsafe_service,
        encoding="utf-8",
    )
    class_decoy = _run_task33_oracles(workspace)
    assert class_decoy.returncode != 0, class_decoy.stdout


def test_task33_browser_docs_distinguish_entry_and_review_methods():
    docs = (
        TASK_LEVEL_ROOT
        / "fixtures/templates/decisive_nbo_cross_module_gate_large_001/docs/browser-flow.md"
    ).read_text(encoding="utf-8")

    assert "`PermissionService.evaluateFlowEntry`" in docs
    assert "`PermissionService.evaluateReview`" in docs


def test_three_task33_fixtures_validate_locally_without_language_sdks(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "VALIDATION_ROOT", tmp_path / "validation")
    monkeypatch.setenv(
        "PATH",
        os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""),
    )
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

    assert task.max_input_tokens == 120_000

    class HardTurnOnlyRunner:
        hard_turn_limit_enforced = True
        hard_input_budget_enforced = False

    try:
        _assert_task33_run_preconditions([task], HardTurnOnlyRunner())  # type: ignore[arg-type]
    except ValueError as exc:
        assert "hard cumulative input budget" in str(exc)
    else:
        raise AssertionError(
            "Task 33 run must be blocked without cumulative input-budget enforcement"
        )

    monkeypatch.delitem(task23_report.TASK33_EVALUATION_CONTRACTS, task.task_id)
    missing_registry_report = build_task23_report(rows, protocol=protocol)
    assert missing_registry_report["evaluation_contract_integrity"]["ok"] is False
    assert task.task_id in missing_registry_report["evaluation_contract_integrity"]["missing_registry_task_ids"]


def test_task33_semantic_checks_report_per_check_execution_status():
    from eval.task_level.evaluators.task_contract import SemanticCheck
    from eval.task_level.evaluators.tests import CommandResult
    from eval.task_level.execution import _semantic_check_execution_rows

    checks = (
        SemanticCheck("service", "service behavior", ("test_service",)),
        SemanticCheck("flow_gates", "flow gate behavior", ("test_browser", "test_scan")),
    )
    failed = CommandResult(
        command="pytest tests/hidden",
        returncode=1,
        stdout=(
            "PASSED tests/hidden/test_gate.py::test_service\n"
            "PASSED tests/hidden/test_gate.py::test_browser\n"
            "FAILED tests/hidden/test_gate.py::test_scan - AssertionError\n"
            "1 failed, 2 passed in 0.01s\n"
        ),
        stderr="",
    )

    rows = _semantic_check_execution_rows(checks, failed)

    assert rows == [
        {
            "id": "service",
            "description": "service behavior",
            "test_ids": ["test_service"],
            "status": "passed",
        },
        {
            "id": "flow_gates",
            "description": "flow gate behavior",
            "test_ids": ["test_browser", "test_scan"],
            "status": "failed",
        },
    ]
    failed_only = CommandResult(
        command="pytest tests/hidden",
        returncode=1,
        stdout="FAILED tests/hidden/test_gate.py::test_scan - AssertionError\n",
        stderr="",
    )
    assert [row["status"] for row in _semantic_check_execution_rows(checks, failed_only)] == [
        "unknown",
        "failed",
    ]
    incomplete = CommandResult(
        command="pytest tests/hidden",
        returncode=1,
        stdout=(
            "PASSED tests/hidden/test_gate.py::test_service[param]\n"
            "PASSED tests/hidden/test_gate.py::test_browser\n"
        ),
        stderr="",
    )
    assert [row["status"] for row in _semantic_check_execution_rows(checks, incomplete)] == [
        "passed",
        "unknown",
    ]
    assert {row["status"] for row in _semantic_check_execution_rows(checks, None)} == {"not_run"}
    assert {
        row["status"]
        for row in _semantic_check_execution_rows(
            checks,
            CommandResult("pytest", 2, "collection interrupted", ""),
        )
    } == {"unknown"}
    assert {
        row["status"]
        for row in _semantic_check_execution_rows(
            checks,
            CommandResult("pytest", 1, "1 failed", ""),
        )
    } == {"unknown"}


def test_task33_contract_evaluator_scores_public_actionability_requirements(tmp_path):
    from eval.task_level.evaluators.contract import evaluate_contract

    task = next(
        task
        for task in load_tasks(TASKS_PATH)
        if task.task_id == "decisive_nbo_cross_module_gate_large_001"
    )
    workspace = _materialize_task33_gold(tmp_path)
    empty_patch = tmp_path / "empty.patch"
    empty_patch.write_text("", encoding="utf-8")

    gold = evaluate_contract(task, workspace, empty_patch)
    public_requirements = {
        "shared_entry_decision",
        "browser_gate_delegates",
        "scan_gate_delegates",
        "offline_sync_uses_shared_gate",
    }

    assert gold.behavioral_contract_score == 1.0
    assert gold.form_contract_score == 1.0
    assert gold.project_convention_score == 1.0
    assert public_requirements <= set(gold.satisfied_requirements)
    assert "contract_not_defined" not in gold.missing_requirements

    scan = workspace / "lib/modules/scan/application/scan_permission_gate.dart"
    scan_source = scan.read_text(encoding="utf-8")
    shared_return = (
        "return _permissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert shared_return in scan_source
    scan.write_text(scan_source.replace(shared_return, "return true;"), encoding="utf-8")

    mutant = evaluate_contract(task, workspace, empty_patch)

    assert mutant.behavioral_contract_score == 0.75
    assert "scan_gate_delegates" in mutant.missing_requirements

    class_workspace = _materialize_task33_gold(tmp_path / "class-decoy")
    class_scan = class_workspace / "lib/modules/scan/application/scan_permission_gate.dart"
    class_source = class_scan.read_text(encoding="utf-8")
    class_scan.write_text(
        "class DecoyGate {\n"
        "  final PermissionService _permissionService;\n"
        "  bool canEnter(PermissionResult result) {\n    "
        + shared_return
        + "\n  }\n}\n"
        + class_source.replace(shared_return, "return true;"),
        encoding="utf-8",
    )
    class_decoy = evaluate_contract(task, class_workspace, empty_patch)
    assert "scan_gate_delegates" in class_decoy.missing_requirements

    rogue_workspace = _materialize_task33_gold(tmp_path / "rogue-field")
    rogue_scan = rogue_workspace / "lib/modules/scan/application/scan_permission_gate.dart"
    rogue_source = rogue_scan.read_text(encoding="utf-8")
    rogue_scan.write_text(
        rogue_source.replace(
            "final PermissionService _permissionService;",
            "final RoguePermissionService _permissionService;",
        ),
        encoding="utf-8",
    )
    rogue = evaluate_contract(task, rogue_workspace, empty_patch)
    assert "shared_service_dependencies" in rogue.missing_requirements

    duplicate_workspace = _materialize_task33_gold(tmp_path / "duplicate")
    duplicate_scan = duplicate_workspace / "lib/modules/scan/application/scan_permission_gate.dart"
    duplicate_source = duplicate_scan.read_text(encoding="utf-8")
    duplicate_scan.write_text(
        duplicate_source.rsplit("}", 1)[0]
        + "  bool duplicates(PermissionResult result) {\n"
        "    return result.hasMissingImmediatePermission;\n"
        "  }\n}\n",
        encoding="utf-8",
    )
    duplicate = evaluate_contract(task, duplicate_workspace, empty_patch)
    assert "no_duplicate_flow_interpretation" in duplicate.missing_requirements
