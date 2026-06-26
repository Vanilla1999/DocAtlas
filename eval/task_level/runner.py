from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS, DEFAULT_CONDITIONS
from eval.task_level.evaluators.tests import run_command
from eval.task_level.execution import execute_pilot, run_canary, runner_verification_payload
from eval.task_level.fixtures.builder import FIXTURE_TASKS, materialize_fixture, validate_fixture
from eval.task_level.report import write_report
from eval.task_level.runners.claude import ClaudeRunner
from eval.task_level.runners.codex import CodexRunner
from eval.task_level.runners.opencode import OpenCodeRunner
from eval.task_level.schemas import RESULTS_ROOT, TASKS_PATH, VALIDATION_ROOT, RunMetrics, RunResult, TaskSpec


BASE_PROMPT = """You are working in a software repository at the supplied base commit.

Resolve the issue described below by inspecting the repository, editing the necessary files, and running tests.

Do not merely describe the solution. Produce a working patch.

Requirements:
- Do not access the internet unless the assigned condition explicitly provides a documentation tool.
- Do not inspect git history beyond the supplied base commit.
- Do not search for the upstream fix or pull request.
- Preserve backward compatibility unless the issue requires otherwise.
- Run the relevant tests before finishing.
- Report the changed files and test results.

Issue:
{issue_text}
"""


def load_tasks(path: Path = TASKS_PATH) -> list[TaskSpec]:
    tasks: list[TaskSpec] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            tasks.append(TaskSpec.from_json(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid task manifest line {line_no}: {exc}") from exc
    return tasks


def detect_runner() -> dict[str, Any]:
    candidates = {
        "mini-SWE-agent": shutil.which("mini-swe-agent"),
        "SWE-agent": shutil.which("sweagent"),
        "OpenHands": shutil.which("openhands"),
        "Claude Code headless": shutil.which("claude"),
        "OpenCode headless": shutil.which("opencode"),
    }
    usable = {name: path for name, path in candidates.items() if path}
    return {
        "candidates": candidates,
        "usable": usable,
        "independent_runner_verified": False,
        "reason": "Generic headless CLIs were found, but SWE-style tool policy isolation and normalized trajectory metrics must be verified before causal runs.",
    }


def environment_metadata() -> dict[str, Any]:
    def capture(command: list[str]) -> str:
        try:
            return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()
        except Exception as exc:
            return repr(exc)

    return {
        "docatlas_commit_sha": capture(["git", "rev-parse", "HEAD"]),
        "branch": capture(["git", "branch", "--show-current"]),
        "model_agent_version": "opencode 1.17.11 available; Claude Code 2.1.138 available; cx/gpt-5.5-medium current interactive agent",
        "python_version": capture(["python3", "--version"]),
        "os": capture(["uname", "-a"]),
        "docker_version": capture(["docker", "--version"]),
        "context7_mcp_version": "MCP server exposed via current opencode tool schema; exact package version not reported by available tools",
        "benchmark_run_timestamp": datetime.now(timezone.utc).isoformat(),
        "runner_detection": detect_runner(),
    }


def _write_validation(task: TaskSpec, status: str, details: dict[str, Any]) -> Path:
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_ROOT / f"{task.task_id}.json"
    payload = {
        "task_id": task.task_id,
        "status": status,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def validate_task(task: TaskSpec) -> dict[str, Any]:
    if task.task_id in FIXTURE_TASKS:
        with tempfile.TemporaryDirectory(prefix=f"docatlas-fixture-validate-{task.task_id}-") as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            materialize_fixture(task, workspace)
            return validate_fixture(task, workspace)
    if task.repo.startswith("fixture://"):
        # Curated fixture tasks are intentionally materialized by a future fixture builder.
        # They are excluded from causal results until base-fail/gold-pass validation exists.
        path = _write_validation(task, "pending_fixture_materialization", {"reason": "fixture repository generator not executed"})
        return {"task_id": task.task_id, "status": "pending_fixture_materialization", "path": str(path)}
    return _write_validation(task, "external_repo_not_checked_out", {"repo": task.repo}).read_text(encoding="utf-8")


def select_runner(runner_id: str):
    if runner_id == "claude":
        return ClaudeRunner()
    if runner_id == "codex":
        return CodexRunner()
    if runner_id == "opencode":
        return OpenCodeRunner()
    raise SystemExit(f"Unknown runner: {runner_id}")


def filter_tasks(tasks: list[TaskSpec], selected: list[str] | None) -> list[TaskSpec]:
    if not selected:
        return tasks
    wanted = set(selected)
    filtered = [task for task in tasks if task.task_id in wanted]
    missing = wanted - {task.task_id for task in filtered}
    if missing:
        raise SystemExit(f"Unknown tasks: {', '.join(sorted(missing))}")
    return filtered


def run_smoke(tasks: list[TaskSpec], conditions: list[str], repeats: int, run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    selected = tasks[:2]
    for task in selected:
        for repeat in range(repeats):
            randomized = conditions[:]
            random.Random(f"{task.task_id}:{repeat}").shuffle(randomized)
            for condition_id in randomized:
                started = time.monotonic()
                result = RunResult(
                    run_id=run_dir.name,
                    task_id=task.task_id,
                    condition_id=condition_id,
                    repeat=repeat,
                    status="smoke_not_causal",
                    resolved=False,
                    tests_passed=False,
                    compile_success=False,
                    metrics=RunMetrics(wall_time_seconds=round(time.monotonic() - started, 4)),
                    notes=["No independent agent process was launched in smoke mode."],
                )
                results.append({
                    "run_id": result.run_id,
                    "task_id": result.task_id,
                    "condition_id": result.condition_id,
                    "repeat": result.repeat,
                    "status": result.status,
                    "resolved": result.resolved,
                    "tests_passed": result.tests_passed,
                    "compile_success": result.compile_success,
                    "metrics": result.metrics.__dict__,
                    "notes": result.notes,
                })
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task-level patch benchmark harness")
    parser.add_argument("--manifest", type=Path, default=TASKS_PATH)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-runner", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runner", default="claude")
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--conditions", nargs="*", default=list(DEFAULT_CONDITIONS))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args(argv)

    unknown = [condition for condition in args.conditions if condition not in CONDITIONS]
    if unknown:
        raise SystemExit(f"Unknown conditions: {', '.join(unknown)}")

    tasks = filter_tasks(load_tasks(args.manifest), args.tasks)
    run_dir = RESULTS_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "environment": environment_metadata(),
        "conditions": args.conditions,
        "executive_result": "Independent causal benchmark not completed in this harness invocation.",
        "decision": "ITERATE: harness and task manifest are ready; execute with verified independent runner before product claims.",
    }

    runner = select_runner(args.runner)
    capabilities = runner.verify()
    metadata["runner_verification"] = runner_verification_payload(capabilities)
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    if args.materialize:
        materialized: list[dict[str, Any]] = []
        materialize_root = run_dir / "materialized"
        for task in tasks:
            if task.task_id in FIXTURE_TASKS:
                materialized.append(materialize_fixture(task, materialize_root / task.task_id))
        (run_dir / "materialized_summary.json").write_text(json.dumps(materialized, indent=2, sort_keys=True), encoding="utf-8")

    if args.verify_runner:
        canary = run_canary(runner, args.model, args.timeout_seconds, run_dir / "runner_canary") if not args.dry_run else {"status": "dry_run"}
        VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
        (VALIDATION_ROOT / "runner_canary.json").write_text(json.dumps(canary, indent=2, sort_keys=True), encoding="utf-8")
        (run_dir / "runner_canary.json").write_text(json.dumps(canary, indent=2, sort_keys=True), encoding="utf-8")

    validation_results: list[Any] = []
    if args.validate:
        validation_results = [validate_task(task) for task in tasks]
        (run_dir / "validation_summary.json").write_text(json.dumps(validation_results, indent=2, sort_keys=True), encoding="utf-8")

    results: list[dict[str, Any]] = []
    if args.smoke:
        results = run_smoke(tasks, args.conditions[:2], args.repeats, run_dir)
        (run_dir / "runs.jsonl").write_text("\n".join(json.dumps(x, sort_keys=True) for x in results), encoding="utf-8")

    if args.execute:
        if args.dry_run:
            results = [{"status": "dry_run", "task_id": task.task_id, "condition_id": condition, "repeat": repeat, "resolved": False, "metrics": {}} for task in tasks for repeat in range(args.repeats) for condition in args.conditions]
        else:
            results = execute_pilot(tasks, args.conditions, args.repeats, args.run_id, runner, args.model, args.timeout_seconds, BASE_PROMPT)

    write_report(run_dir, metadata, results)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
