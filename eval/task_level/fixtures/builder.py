from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.evaluators.task_contract import ContractValidation, directory_sha256, evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_effective_task23_protocol_tasks, load_task_evaluation_contracts, run_compile_gate, validate_task_evaluation_artifacts, validate_task_evaluation_contract
from eval.task_level.schemas import TASK_LEVEL_ROOT, VALIDATION_ROOT, TaskSpec


FIXTURE_TASKS = {
    "fastapi_depends_001",
    "mixed_fastapi_project_001",
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
    "decisive_nbo_generated_policy_source_001",
    "decisive_nbo_permission_handler_version_001",
    "decisive_docmancer_vector_timeout_fallback_001",
    "decisive_nbo_browser_scan_policy_001",
    "decisive_nbo_cross_module_gate_large_001",
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_cross_module_permission_contract_001",
    "real_project_nbo_flavor_scoped_external_links_001",
    "real_project_help_chat_linearizable_module_lifecycle_001",
    "real_project_viscanner_client_owned_disable_signal_001",
}
TEMPLATE_ROOT = TASK_LEVEL_ROOT / "fixtures" / "templates"
ORACLE_ROOT = TASK_LEVEL_ROOT / "oracles"
HIDDEN_TEST_ROOT = TASK_LEVEL_ROOT / "hidden_tests"
TASK33_EVALUATION_CONTRACTS = load_task_evaluation_contracts()
TASK23_PROTOCOL_TASKS = load_effective_task23_protocol_tasks()


def materialize_fixture(task: TaskSpec, destination: Path) -> dict[str, Any]:
    if task.task_id not in FIXTURE_TASKS:
        raise ValueError(f"No materialized fixture is available for {task.task_id}")
    template = TEMPLATE_ROOT / task.task_id
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(template, destination)
    _run(["git", "init"], destination, 30)
    _run(["git", "config", "user.email", "benchmark@example.invalid"], destination, 30)
    _run(["git", "config", "user.name", "Task Benchmark"], destination, 30)
    _run(["git", "add", "."], destination, 30)
    _run(["git", "commit", "-m", "base fixture"], destination, 30)
    base_commit = _run(["git", "rev-parse", "HEAD"], destination, 30).stdout.strip()
    return {
        "task_id": task.task_id,
        "workspace": str(destination),
        "base_commit": base_commit,
        "fixture_hash_algorithm": "sha256-length-prefixed-v2",
        "fixture_hash": fixture_hash(template),
        "protocol_fixture_hash_algorithm": "sha256-concat-v1",
        "protocol_fixture_hash": fixture_hash(template, algorithm="sha256-concat-v1"),
    }


def validate_fixture(
    task: TaskSpec,
    workspace: Path,
    oracle_patch: Path | None = None,
    hidden_tests: Path | None = None,
    *,
    local_commands: bool = False,
) -> dict[str, Any]:
    oracle_patch = oracle_patch or ORACLE_ROOT / f"{task.task_id}.patch"
    hidden_tests = hidden_tests or HIDDEN_TEST_ROOT / task.task_id
    task_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    protocol_task = TASK23_PROTOCOL_TASKS.get(task.task_id)
    contract_validation = _combined_contract_validation(task, task_contract, protocol_task)
    test_command = task_contract.local_test_command if local_commands and task_contract else task.test_command
    setup_command = "python -c \"import pytest\"" if local_commands else task.setup_command
    command_env = _local_validation_env() if local_commands else None
    setup = _run_shell(setup_command, workspace, 300, env=command_env) if setup_command else _ok("no setup")
    base_public = _run_shell(test_command, workspace, 120, env=command_env)
    if task.task_id in TASK23_PROTOCOL_TASKS and not contract_validation.valid:
        compile_base = _invalid_contract_gate(contract_validation)
    elif task_contract and contract_validation.valid:
        compile_base = run_compile_gate(task_contract, workspace)
    else:
        legacy_base = _run_shell("python -m compileall -q src", workspace, 120)
        compile_base = {
            "status": "passed" if legacy_base.returncode == 0 else "failed",
            "passed": legacy_base.returncode == 0,
            "command": "python -m compileall -q src",
            "reason": "legacy_unfrozen_contract",
            "returncode": legacy_base.returncode,
            "stdout": legacy_base.stdout,
            "stderr": legacy_base.stderr,
        }
    leak_check = workspace_has_no_oracles(workspace)

    gold_apply = _run(["git", "apply", str(oracle_patch)], workspace, 30)
    gold_public = _run_shell(test_command, workspace, 120, env=command_env) if gold_apply.returncode == 0 else _fail("gold patch did not apply")
    hidden_result = _run_hidden_tests(task, workspace, hidden_tests, env=command_env) if gold_apply.returncode == 0 else _fail("gold patch did not apply")
    if gold_apply.returncode == 0 and task.task_id in TASK23_PROTOCOL_TASKS and not contract_validation.valid:
        compile_gold = _invalid_contract_gate(contract_validation)
        patch_surface = {"status": "not_run", "violations": []}
    elif gold_apply.returncode == 0 and task_contract and contract_validation.valid:
        compile_gold = run_compile_gate(task_contract, workspace)
        changed = _run(["git", "diff", "--name-only", "HEAD"], workspace, 30).stdout.splitlines()
        patch_surface = evaluate_patch_surface(task_contract, changed)
    elif gold_apply.returncode == 0:
        legacy_gold = _run_shell("python -m compileall -q src", workspace, 120)
        compile_gold = {
            "status": "passed" if legacy_gold.returncode == 0 else "failed",
            "passed": legacy_gold.returncode == 0,
            "command": "python -m compileall -q src",
            "reason": "legacy_unfrozen_contract",
            "returncode": legacy_gold.returncode,
            "stdout": legacy_gold.stdout,
            "stderr": legacy_gold.stderr,
        }
        patch_surface = {"status": "legacy", "violations": []}
    else:
        compile_gold = {
            "status": "not_run",
            "passed": False,
            "command": task_contract.compile_gate.command if task_contract else "python -m compileall -q src",
            "reason": "gold_patch_did_not_apply",
            "returncode": None,
            "stdout": "",
            "stderr": "gold patch did not apply",
        }
        patch_surface = {"status": "not_run", "violations": []}
    contract_ok = contract_validation.valid
    semantic_gate = {
        "command": task_contract.semantic_test_command if task_contract else None,
        "status": "passed" if hidden_result.returncode == 0 else "failed",
        "passed": hidden_result.returncode == 0,
        "returncode": hidden_result.returncode,
        "hidden_tests_sha256": task_contract.hidden_tests_sha256 if task_contract else None,
        "checks": [
            {
                "id": check.check_id,
                "test_ids": list(check.test_ids),
                "status": "passed" if hidden_result.returncode == 0 else "failed",
            }
            for check in task_contract.semantic_checks
        ] if task_contract else [],
    }
    payload = {
        "task_id": task.task_id,
        "status": "validated" if setup.returncode == 0 and base_public.returncode != 0 and gold_public.returncode == 0 and hidden_result.returncode == 0 and compile_gold["passed"] and contract_ok and patch_surface["status"] in {"passed", "legacy"} and leak_check else "validation_failed",
        "evaluation_contract": {
            "status": contract_validation.status if task.task_id in TASK23_PROTOCOL_TASKS or task_contract else "legacy_unfrozen",
            "errors": list(contract_validation.errors),
            "patch_contract_id": task_contract.patch_contract_id if task_contract else None,
            "contract_sha256": evaluation_contract_sha256(task_contract) if task_contract else None,
            "registry_sha256": evaluation_contract_registry_sha256() if task_contract else None,
            "compile_gate": compile_gold,
            "semantic_gate": semantic_gate,
            "patch_surface": patch_surface,
            "test_command": test_command,
            "local_commands": local_commands,
        },
        "base": {
            "setup_success": setup.returncode == 0,
            "expected_tests_failed": base_public.returncode != 0,
            "compile_success": None if compile_base["status"] == "not_applicable" else compile_base["passed"],
            "compile_status": compile_base["status"],
            "unexpected_failures": [] if setup.returncode == 0 else [setup.stderr[-1000:]],
        },
        "gold": {
            "patch_applied": gold_apply.returncode == 0,
            "public_tests_passed": gold_public.returncode == 0,
            "hidden_tests_passed": hidden_result.returncode == 0,
            "compile_success": None if compile_gold["status"] == "not_applicable" else compile_gold["passed"],
            "compile_status": compile_gold["status"],
        },
        "oracle_isolated": leak_check,
        "fixture_hash_algorithm": "sha256-length-prefixed-v2",
        "fixture_hash": fixture_hash(TEMPLATE_ROOT / task.task_id),
        "protocol_fixture_hash_algorithm": "sha256-concat-v1",
        "protocol_fixture_hash": fixture_hash(TEMPLATE_ROOT / task.task_id, algorithm="sha256-concat-v1"),
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    (VALIDATION_ROOT / f"{task.task_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def workspace_has_no_oracles(workspace: Path) -> bool:
    forbidden = ("gold_patch", "oracle", "hidden_tests")
    return not any(any(marker in str(path.relative_to(workspace)) for marker in forbidden) for path in workspace.rglob("*"))


def run_local_test_command(command: str, workspace: Path, timeout_seconds: int = 120) -> subprocess.CompletedProcess[str]:
    if command.startswith("pytest "):
        command = "python -m pytest " + command.removeprefix("pytest ")
    elif command.startswith("uv run --offline pytest "):
        command = "python -m pytest " + command.removeprefix("uv run --offline pytest ")
    return _run_shell(command, workspace, timeout_seconds, env=_local_validation_env())


def copy_hidden_tests(task_id: str, workspace: Path) -> Path:
    source = HIDDEN_TEST_ROOT / task_id
    target = workspace / "tests" / "hidden"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def fixture_hash(path: Path, *, algorithm: str = "sha256-length-prefixed-v2") -> str:
    digest = directory_sha256(path, algorithm=algorithm)
    if digest is None:
        raise ValueError(f"Cannot hash fixture with algorithm {algorithm}: {path}")
    return digest


def _combined_contract_validation(
    task: TaskSpec,
    contract: Any,
    protocol_task: dict[str, Any] | None,
) -> ContractValidation:
    if task.task_id not in TASK23_PROTOCOL_TASKS and contract is None:
        return ContractValidation("valid", ())
    definition = validate_task_evaluation_contract(task, contract)
    artifacts = validate_task_evaluation_artifacts(contract, protocol_task)
    errors = tuple(dict.fromkeys((*definition.errors, *artifacts.errors)))
    return ContractValidation("invalid" if errors else "valid", errors)


def _invalid_contract_gate(validation: ContractValidation) -> dict[str, Any]:
    return {
        "status": "not_run",
        "passed": False,
        "command": None,
        "reason": "evaluation_contract_invalid:" + ",".join(validation.errors),
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }


def _run_hidden_tests(task: TaskSpec, workspace: Path, hidden_tests: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    target = copy_hidden_tests(task.task_id, workspace)
    return _run_shell(f"python -m pytest {target.relative_to(workspace)}", workspace, 120, env=env)


def _run(command: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)


def _run_shell(command: str, cwd: Path, timeout_seconds: int, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    if command.startswith("python -m pip "):
        command = "uv pip " + command.removeprefix("python -m pip ") + f" --python {sys.executable}"
    return subprocess.run(command, cwd=cwd, env=env, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)


def _local_validation_env() -> dict[str, str]:
    env = os.environ.copy()
    import_paths = [
        str(Path(path).resolve())
        for path in sys.path
        if path and ("site-packages" in path or "dist-packages" in path)
    ]
    existing = env.get("PYTHONPATH")
    if existing:
        import_paths.extend(
            str(Path(path).resolve())
            for path in existing.split(os.pathsep)
            if path and ("site-packages" in path or "dist-packages" in path)
        )
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    return env


def _ok(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=message, returncode=0, stdout=message, stderr="")


def _fail(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=message, returncode=1, stdout="", stderr=message)
