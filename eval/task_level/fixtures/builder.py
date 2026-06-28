from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.schemas import TASK_LEVEL_ROOT, VALIDATION_ROOT, TaskSpec


FIXTURE_TASKS = {
    "fastapi_depends_001",
    "mixed_fastapi_project_001",
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_cross_module_permission_contract_001",
}
TEMPLATE_ROOT = TASK_LEVEL_ROOT / "fixtures" / "templates"
ORACLE_ROOT = TASK_LEVEL_ROOT / "oracles"
HIDDEN_TEST_ROOT = TASK_LEVEL_ROOT / "hidden_tests"


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
    return {"task_id": task.task_id, "workspace": str(destination), "base_commit": base_commit, "fixture_hash": fixture_hash(template)}


def validate_fixture(task: TaskSpec, workspace: Path, oracle_patch: Path | None = None, hidden_tests: Path | None = None) -> dict[str, Any]:
    oracle_patch = oracle_patch or ORACLE_ROOT / f"{task.task_id}.patch"
    hidden_tests = hidden_tests or HIDDEN_TEST_ROOT / task.task_id
    setup = _run_shell(task.setup_command, workspace, 300) if task.setup_command else _ok("no setup")
    base_public = _run_shell(task.test_command, workspace, 120)
    compile_base = _run_shell("python -m compileall -q src", workspace, 120)
    leak_check = workspace_has_no_oracles(workspace)

    gold_apply = _run(["git", "apply", str(oracle_patch)], workspace, 30)
    gold_public = _run_shell(task.test_command, workspace, 120) if gold_apply.returncode == 0 else _fail("gold patch did not apply")
    hidden_result = _run_hidden_tests(task, workspace, hidden_tests) if gold_apply.returncode == 0 else _fail("gold patch did not apply")
    compile_gold = _run_shell("python -m compileall -q src", workspace, 120) if gold_apply.returncode == 0 else _fail("gold patch did not apply")
    payload = {
        "task_id": task.task_id,
        "status": "validated" if setup.returncode == 0 and base_public.returncode != 0 and gold_public.returncode == 0 and hidden_result.returncode == 0 and compile_gold.returncode == 0 and leak_check else "validation_failed",
        "base": {
            "setup_success": setup.returncode == 0,
            "expected_tests_failed": base_public.returncode != 0,
            "compile_success": compile_base.returncode == 0,
            "unexpected_failures": [] if setup.returncode == 0 else [setup.stderr[-1000:]],
        },
        "gold": {
            "patch_applied": gold_apply.returncode == 0,
            "public_tests_passed": gold_public.returncode == 0,
            "hidden_tests_passed": hidden_result.returncode == 0,
            "compile_success": compile_gold.returncode == 0,
        },
        "oracle_isolated": leak_check,
        "fixture_hash": fixture_hash(TEMPLATE_ROOT / task.task_id),
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    (VALIDATION_ROOT / f"{task.task_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def workspace_has_no_oracles(workspace: Path) -> bool:
    forbidden = ("gold_patch", "oracle", "hidden_tests")
    return not any(any(marker in str(path.relative_to(workspace)) for marker in forbidden) for path in workspace.rglob("*"))


def copy_hidden_tests(task_id: str, workspace: Path) -> Path:
    source = HIDDEN_TEST_ROOT / task_id
    target = workspace / "tests" / "hidden"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def fixture_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode())
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _run_hidden_tests(task: TaskSpec, workspace: Path, hidden_tests: Path) -> subprocess.CompletedProcess[str]:
    target = copy_hidden_tests(task.task_id, workspace)
    return _run_shell(f"pytest {target.relative_to(workspace)}", workspace, 120)


def _run(command: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)


def _run_shell(command: str, cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    if command.startswith("python -m pip "):
        command = "uv pip " + command.removeprefix("python -m pip ") + f" --python {sys.executable}"
    return subprocess.run(command, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)


def _ok(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=message, returncode=0, stdout=message, stderr="")


def _fail(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=message, returncode=1, stdout="", stderr=message)
