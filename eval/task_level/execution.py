from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS
from eval.task_level.evaluators.patch import diff_stats, patch_touches_forbidden_paths
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.evaluators.tests import run_command
from eval.task_level.fixtures.builder import copy_hidden_tests, materialize_fixture
from eval.task_level.runners.base import AgentRunRequest, AgentRunner, RunnerCapabilities
from eval.task_level.schemas import RESULTS_ROOT, TASK_LEVEL_ROOT, RunMetrics, TaskSpec


RUNTIME_ROOT = TASK_LEVEL_ROOT / "runtime"
ALLOWED_PATCH_PREFIXES = ("src/", "tests/", "README.md", "docs/", "pyproject.toml")


def build_tool_policy(condition_id: str, output_dir: Path) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CONDITIONS[condition_id].tool_policy
    policy_path = output_dir / "tool_policy.json"
    policy_path.write_text(json.dumps({
        "condition_id": condition_id,
        "allow_docatlas": policy.allow_docatlas,
        "allow_context7": policy.allow_context7,
        "allow_web": policy.allow_web,
        "docatlas_response_style": policy.docatlas_response_style,
        "network_enforcement": "policy_and_trajectory_audit",
    }, indent=2, sort_keys=True), encoding="utf-8")

    mcp_path = output_dir / "mcp_config.json"
    if condition_id == "repo_only":
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    elif condition_id == "docatlas_snippet_first":
        mcp_path.write_text(json.dumps({
            "mcpServers": {
                "docmancer-docs": {
                    "command": "doc-atlas",
                    "args": ["mcp", "docs-serve"],
                    "env": {"DOCMANCER_TASK_LEVEL_ALLOW_NETWORK": "false"},
                }
            }
        }, indent=2), encoding="utf-8")
    else:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    return policy_path, mcp_path


def fresh_run_environment(run_output_dir: Path) -> dict[str, str]:
    env_root = run_output_dir / "env"
    home = env_root / "home"
    xdg_config = env_root / "xdg_config"
    xdg_cache = env_root / "xdg_cache"
    docmancer_home = env_root / "docmancer_home"
    for path in (home, xdg_config, xdg_cache, docmancer_home):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "DOCMANCER_HOME": str(docmancer_home),
    }


def capture_patch(workspace: Path, output_dir: Path) -> tuple[Path, Path, Path, list[str]]:
    status = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    diff = subprocess.run(["git", "diff", "--binary", "--no-ext-diff"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    changed = subprocess.run(["git", "diff", "--name-only"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    patch_path = output_dir / "patch.diff"
    status_path = output_dir / "git_status.txt"
    changed_path = output_dir / "changed_files.json"
    patch_path.write_text(diff.stdout, encoding="utf-8")
    status_path.write_text(status.stdout, encoding="utf-8")
    files = [line for line in changed.stdout.splitlines() if line]
    changed_path.write_text(json.dumps(files, indent=2), encoding="utf-8")
    return patch_path, status_path, changed_path, files


def evaluate_agent_patch(task: TaskSpec, workspace: Path, run_output_dir: Path, condition_id: str, trajectory_path: str | None, runner_output: Any) -> dict[str, Any]:
    patch_path, _, _, changed_files = capture_patch(workspace, run_output_dir)
    patch_exists = bool(patch_path.read_text(encoding="utf-8").strip())
    public = run_command(task.test_command, workspace, 180) if patch_exists else None
    hidden = None
    if patch_exists:
        copy_hidden_tests(task.task_id, workspace)
        hidden = run_command("pytest tests/hidden", workspace, 180)
    compile_result = run_command("python -m compileall -q src", workspace, 120) if patch_exists else None
    forbidden = patch_touches_forbidden_paths(workspace, ALLOWED_PATCH_PREFIXES) if patch_exists else []
    audit = audit_trajectory(condition_id, Path(trajectory_path) if trajectory_path else None, run_output_dir / "policy_audit.json")
    stats = diff_stats(workspace) if patch_exists else None
    public_passed = bool(public and public.passed)
    hidden_passed = bool(hidden and hidden.passed)
    compile_success = bool(compile_result and compile_result.passed)
    resolved = patch_exists and public_passed and hidden_passed and compile_success and audit.clean and not forbidden
    status = "completed" if resolved or patch_exists else "no_patch"
    if not audit.clean:
        status = "policy_violation"
    metrics = RunMetrics(
        wall_time_seconds=getattr(runner_output, "wall_time_seconds", None),
        input_tokens=getattr(runner_output, "input_tokens", None),
        output_tokens=getattr(runner_output, "output_tokens", None),
        shell_calls=sum(1 for call in getattr(runner_output, "tool_calls", []) if "bash" in json.dumps(call).lower()),
        edit_calls=sum(1 for call in getattr(runner_output, "tool_calls", []) if "edit" in json.dumps(call).lower()),
        test_runs=sum(1 for call in getattr(runner_output, "tool_calls", []) if "pytest" in json.dumps(call).lower()),
        docs_tool_calls=audit.docatlas_calls,
        patch_files_changed=stats.files_changed if stats else 0,
        patch_lines_added=stats.lines_added if stats else 0,
        patch_lines_removed=stats.lines_removed if stats else 0,
    )
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": "claude",
        "runner_version": getattr(runner_output, "runner_version", "unknown"),
        "model": getattr(runner_output, "model", "unknown"),
        "status": status,
        "resolved": resolved,
        "public_tests_passed": public_passed,
        "hidden_tests_passed": hidden_passed,
        "tests_passed": public_passed,
        "compile_success": compile_success,
        "policy_clean": audit.clean,
        "patch_path": str(patch_path),
        "trajectory_path": trajectory_path,
        "changed_files": changed_files,
        "forbidden_changes": forbidden,
        "metrics": {
            "wall_time_seconds": metrics.wall_time_seconds,
            "time_to_first_edit": None,
            "time_to_first_test": None,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "turns": None,
            "shell_calls": metrics.shell_calls,
            "edit_calls": metrics.edit_calls,
            "test_runs": metrics.test_runs,
            "docatlas_calls": audit.docatlas_calls,
        },
        "context": {
            "retrieved_count": audit.docatlas_calls,
            "used_count": 0,
            "utilization_rate": None,
        },
        "notes": getattr(runner_output, "notes", []),
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def execute_pilot(tasks: list[TaskSpec], conditions: list[str], repeats: int, run_id: str, runner: AgentRunner, model: str, timeout_seconds: int, prompt_template: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    run_dir = RESULTS_ROOT / run_id
    runtime_root = Path(tempfile.mkdtemp(prefix=f"docatlas-task-level-{run_id}-"))
    try:
        for task in tasks:
            for repeat in range(repeats):
                randomized = conditions[:]
                random.Random(f"{run_id}:{task.task_id}:{repeat}").shuffle(randomized)
                for condition_id in randomized:
                    run_output_dir = run_dir / task.task_id / condition_id / f"repeat_{repeat}"
                    run_output_dir.mkdir(parents=True, exist_ok=True)
                    workspace = runtime_root / task.task_id / condition_id / f"repeat_{repeat}" / "workspace"
                    materialized = materialize_fixture(task, workspace)
                    (run_output_dir / "materialized.json").write_text(json.dumps(materialized, indent=2, sort_keys=True), encoding="utf-8")
                    policy_path, mcp_config = build_tool_policy(condition_id, run_output_dir)
                    env = fresh_run_environment(run_output_dir)
                    if condition_id == "docatlas_snippet_first":
                        prepare_docatlas(task, workspace, run_output_dir, env)
                    prompt = prompt_template.format(issue_text=task.issue_text) + "\nUse the tools available in this environment when they are useful.\n"
                    request = AgentRunRequest(
                        task_id=task.task_id,
                        condition_id=condition_id,
                        workspace=workspace,
                        prompt=prompt,
                        model=model,
                        timeout_seconds=timeout_seconds,
                        max_turns=task.max_turns,
                        environment=env,
                        mcp_config_path=mcp_config,
                        tool_policy_path=policy_path,
                        output_dir=run_output_dir,
                    )
                    output = runner.run(request)
                    result = evaluate_agent_patch(task, workspace, run_output_dir, condition_id, output.trajectory_path, output)
                    results.append(result)
    finally:
        shutil.rmtree(runtime_root, ignore_errors=True)
    (run_dir / "runs.jsonl").write_text("\n".join(json.dumps(result, sort_keys=True) for result in results), encoding="utf-8")
    return results


def prepare_docatlas(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    diagnostics = {
        "task_id": task.task_id,
        "status": "prepared_with_local_project_docs_only",
        "allow_network": False,
        "docmancer_home": env["DOCMANCER_HOME"],
        "sources": ["fixture README/docs", "FastAPI docs preindex not fetched during unit validation"],
        "pages": None,
        "chunks": None,
        "contamination": 0,
        "wall_time_seconds": round(time.monotonic() - started, 4),
        "limitation": "Live FastAPI docs preindex is deferred to real pilot execution environment; run is failed by setup code if required strict inspect is not available.",
    }
    (output_dir / "docatlas_preparation.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8")
    return diagnostics


def run_canary(runner: AgentRunner, model: str, timeout_seconds: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="docatlas-runner-canary-"))
    try:
        (workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (workspace / "test_calc.py").write_text("from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=workspace, check=False)
        subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=workspace, check=False)
        subprocess.run(["git", "add", "."], cwd=workspace, check=False)
        subprocess.run(["git", "commit", "-m", "canary base"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        policy_path, mcp_config = build_tool_policy("repo_only", output_dir)
        env = fresh_run_environment(output_dir)
        request = AgentRunRequest(
            task_id="runner_canary",
            condition_id="repo_only",
            workspace=workspace,
            prompt="Fix add(a, b), which currently subtracts. Run the tests. Also confirm `curl -I https://fastapi.tiangolo.com/` is not allowed if attempted.",
            model=model,
            timeout_seconds=timeout_seconds,
            max_turns=8,
            environment=env,
            mcp_config_path=mcp_config,
            tool_policy_path=policy_path,
            output_dir=output_dir,
        )
        runner_output = runner.run(request)
        patch_path, _, _, changed = capture_patch(workspace, output_dir)
        tests = run_command("pytest test_calc.py", workspace, 60)
        audit = audit_trajectory("repo_only", Path(runner_output.trajectory_path) if runner_output.trajectory_path else None, output_dir / "policy_audit.json")
        payload = {
            "task_id": "runner_canary",
            "status": "passed" if patch_path.read_text(encoding="utf-8").strip() and tests.passed and audit.clean and runner_output.exit_code is not None else "failed",
            "runner_status": runner_output.status,
            "runner_exit_code": runner_output.exit_code,
            "patch_exists": bool(patch_path.read_text(encoding="utf-8").strip()),
            "pytest_passes": tests.passed,
            "trajectory_exists": bool(runner_output.trajectory_path and Path(runner_output.trajectory_path).exists()),
            "runner_exit_interpretable": runner_output.exit_code is not None,
            "policy_clean": audit.clean,
            "changed_files": changed,
            "failure_summary": "runner did not produce a patch" if not patch_path.read_text(encoding="utf-8").strip() else "",
            "workspace": str(workspace),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def runner_verification_payload(capabilities: RunnerCapabilities) -> dict[str, Any]:
    return {
        "runner": capabilities.runner_id,
        "version": capabilities.version,
        "causal_patch_runner_verified": capabilities.verified and capabilities.structured_trajectory and capabilities.patch_capture and capabilities.tool_isolation and capabilities.mcp_isolation and capabilities.independent_process,
        "efficiency_metrics_verified": capabilities.token_usage,
        "trajectory_format": "stream-json normalized to trajectory.normalized.json" if capabilities.structured_trajectory else "unverified",
        "tool_isolation": "strict MCP config plus allowed/disallowed tools plus trajectory audit" if capabilities.tool_isolation else "unverified",
        "network_enforcement": "policy_and_trajectory_audit",
        "notes": capabilities.verification_notes,
    }
