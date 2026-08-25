from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.task_contract import (
    evaluate_patch_surface,
    load_effective_task23_protocol_tasks,
    load_task_evaluation_contracts,
    validate_task_evaluation_artifacts,
    validate_task_evaluation_contract,
)
from eval.task_level.fixtures import builder
from eval.task_level.schemas import TaskSpec


def collect_public_pytest_inventory(task: TaskSpec, workspace: Path) -> tuple[str, ...]:
    result = builder.run_local_test_command(
        _with_collect_only(task.test_command), workspace
    )
    if result.returncode != 0:
        raise RuntimeError(f"public pytest collection failed: {result.stderr[-500:]}")
    return tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and not line.lstrip().startswith(("<", "="))
    )


def validate_declared_public_tests(
    task: TaskSpec, inventory: tuple[str, ...]
) -> dict[str, Any]:
    declared = (*task.fail_to_pass_tests, *task.pass_to_pass_tests)
    inventory_set = set(inventory)
    missing = sorted(node for node in declared if node not in inventory_set)
    return {
        "status": "invalid" if missing else "valid",
        "declared": list(declared),
        "inventory": list(inventory),
        "missing": missing,
        "requires_versioned_correction": bool(missing),
    }


def validate_captured_final_patch(task: TaskSpec, patch: Path) -> dict[str, Any]:
    """Replay a captured patch in a fresh evaluator-owned fixture."""

    contract = load_task_evaluation_contracts().get(task.task_id)
    protocol_task = load_effective_task23_protocol_tasks().get(task.task_id)
    with tempfile.TemporaryDirectory(prefix="task-level-final-patch-") as directory:
        workspace = Path(directory) / task.task_id
        materialized = builder.materialize_fixture(task, workspace)
        declared_tests = validate_declared_public_tests(
            task, collect_public_pytest_inventory(task, workspace)
        )
        applied = _run(["git", "apply", "--", str(patch.resolve())], workspace)
        if applied.returncode != 0:
            result = _failed_replay("patch_apply_failed", applied.stderr, materialized)
            result["declared_public_tests"] = declared_tests
            return result

        changed = _run(["git", "diff", "--name-only", "HEAD", "--"], workspace)
        changed_files = tuple(line for line in changed.stdout.splitlines() if line)
        definition = validate_task_evaluation_contract(task, contract)
        artifacts = validate_task_evaluation_artifacts(contract, protocol_task)
        surface = (
            evaluate_patch_surface(contract, list(changed_files))
            if contract is not None
            else {"status": "not_run", "violations": []}
        )
        replay_patch = workspace / ".final-patch.diff"
        replay_patch.write_text(
            _run(["git", "diff", "--binary", "HEAD", "--"], workspace).stdout,
            encoding="utf-8",
        )
        semantic_contract = evaluate_contract(task, workspace, replay_patch)
        public = builder.run_local_test_command(
            contract.local_test_command if contract else task.test_command, workspace
        )

        # Hidden tests are evaluator-owned and enter only after patch capture/surface checks.
        hidden = builder.copy_hidden_tests(task.task_id, workspace)
        semantic = builder.run_local_test_command(
            f"python -m pytest {hidden.relative_to(workspace)}", workspace
        )
        contract_valid = definition.valid and artifacts.valid
        valid = (
            public.returncode == 0
            and semantic.returncode == 0
            and contract_valid
            and surface["status"] == "passed"
            and not semantic_contract.missing_requirements
        )
        return {
            "status": "valid" if valid else "invalid",
            "patch_applied": True,
            "materialized": materialized,
            "declared_public_tests": declared_tests,
            "changed_files": list(changed_files),
            "patch_surface": surface,
            "public_tests_passed": public.returncode == 0,
            "hidden_tests_passed": semantic.returncode == 0,
            "contract_valid": contract_valid,
            "contract_errors": [*definition.errors, *artifacts.errors],
            "semantic_contract": semantic_contract.to_json(),
        }


def _with_collect_only(command: str) -> str:
    marker = "pytest "
    if marker not in command:
        raise ValueError("public test command is not pytest")
    return command.replace(marker, marker + "--collect-only -q ", 1)


def _run(command: list[str], workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _failed_replay(reason: str, detail: str, materialized: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "invalid",
        "patch_applied": False,
        "reason": reason,
        "detail": detail[-500:],
        "materialized": materialized,
        "changed_files": [],
        "patch_surface": {"status": "not_run", "violations": []},
        "public_tests_passed": False,
        "hidden_tests_passed": False,
        "contract_valid": False,
    }
