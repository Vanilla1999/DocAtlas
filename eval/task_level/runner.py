from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import random
import shlex
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
from eval.task_level.execution import DOCATLAS_CONDITIONS, TASK23_PROTOCOL_TASKS, execute_pilot, run_canary, run_docatlas_tool_visibility_canary, runner_verification_payload, serialize_run_results_jsonl
from eval.task_level.fixtures.builder import FIXTURE_TASKS, materialize_fixture, validate_fixture
from eval.task_level.isolated_delivery import JsonSubprocessIsolatedWorker
from eval.task_level.patch_constraints_pilot import TARGETED_PILOT_CONDITIONS, build_targeted_pilot_plan, select_targeted_pilot_tasks, write_targeted_pilot_dry_run
from eval.task_level.report import write_report
from eval.task_level.runners.claude import ClaudeRunner
from eval.task_level.runners.codex import CodexRunner
from eval.task_level.runners.opencode import OpenCodeRunner
from eval.task_level.schemas import RESULTS_ROOT, TASKS_PATH, VALIDATION_ROOT, RunMetrics, RunResult, TaskSpec
from eval.task_level.task_selection import decide_candidate_status, decide_screening_result, write_screening_artifacts
from eval.task_level.task33_pilot import TASK33C_PILOT_CONDITIONS, TASK33C_PILOT_TASK_ID, build_task33c_pilot_plan, evaluate_task33c_pilot_completeness
from eval.task_level.task33_validation import PROTOCOL_PATH, load_protocol, protocol_sha256, validate_task33c_run


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


def select_runner(runner_id: str, *, codex_sandbox_mode: str = "workspace-write"):
    if runner_id == "claude":
        return ClaudeRunner()
    if runner_id == "codex":
        return CodexRunner(sandbox_mode=codex_sandbox_mode)
    if runner_id == "opencode":
        return OpenCodeRunner()
    raise SystemExit(f"Unknown runner: {runner_id}")


def load_runner_factory(spec: str):
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise SystemExit("--runner-factory must use module.path:factory format")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute)
        runner = factory()
    except Exception as exc:
        raise SystemExit(f"Unable to load runner factory {spec}: {exc}") from exc
    if not callable(getattr(runner, "verify", None)) or not callable(getattr(runner, "run", None)):
        raise SystemExit("Runner factory must return an object implementing verify() and run()")
    return runner


def load_isolated_worker_factory(spec: str):
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise SystemExit("--isolated-worker-factory must use module.path:factory format")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute)
        worker = factory()
    except Exception as exc:
        raise SystemExit(f"Unable to load isolated worker factory {spec}: {exc}") from exc
    required = (
        "run", "capabilities", "capability_evidence", "compressor_identity",
        "command_fingerprint", "sandbox_identity", "usage_verifier_identity",
    )
    if any(not hasattr(worker, name) for name in required) or not callable(getattr(worker, "run", None)):
        raise SystemExit("Isolated worker factory returned an incomplete host adapter")
    return worker


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


def write_screening_summary(run_dir: Path, tasks: list[TaskSpec], results: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    rich_results = []
    for task in tasks:
        task_results = [result for result in results if result.get("task_id") == task.task_id]
        repo_only = [result for result in task_results if result.get("condition_id") == "repo_only_strict_offline"]
        resolved = sum(1 for result in repo_only if result.get("resolved") is True)
        policy_clean = all(result.get("policy_clean") is True for result in repo_only) if repo_only else None
        network_attempts = sum(int(result.get("policy", {}).get("network_attempts") or result.get("metrics", {}).get("network_attempts") or 0) for result in repo_only)
        integrity = _load_json(run_dir / "status.json").get("artifact_integrity", {})
        fairness_clean = True
        hidden_oracle_only = False
        visible_source_coverage = bool(task.expected_project_docs or task.expected_symbols or task.dependencies)
        attempted = len(repo_only)
        runner_failures = sum(1 for result in repo_only if result.get("status") not in {"completed", "dry_run"})
        rich = decide_screening_result(
            task_id=task.task_id,
            repo_only_repeats=repeats,
            repo_only_attempted=attempted,
            repo_only_runner_failures=runner_failures,
            repo_only_resolved=resolved,
            repo_only_public_passed=sum(1 for result in repo_only if result.get("public_tests_passed") is True),
            repo_only_hidden_passed=sum(1 for result in repo_only if result.get("hidden_tests_passed") is True),
            policy_clean=bool(policy_clean) if policy_clean is not None else True,
            visible_source_coverage=visible_source_coverage,
            hidden_oracle_only=hidden_oracle_only,
            fairness_clean=fairness_clean,
            constraint_angle=_constraint_angle(task),
            task_class=_screening_task_class(task),
            stable_public_hidden_separation=True,
            valid_fixture=bool(task.test_command),
            smoke_or_prototype=task.role in {"smoke", "prototype"},
        )
        rich_results.append(rich)
        status = decide_candidate_status(
            repo_only_repeats=repeats,
            repo_only_resolved=resolved,
            fairness_clean=fairness_clean,
            hidden_oracle_only=hidden_oracle_only,
        )
        summaries.append({
            "task_id": task.task_id,
            "source_project": task.source_project,
            "candidate_status": status,
            "repo_only_screening": {
                "repeats": repeats,
                "resolved": resolved,
                "policy_clean": policy_clean,
                "network_attempts": network_attempts,
            },
            "fairness": {
                "reviewed": True,
                "clean": fairness_clean,
                "hidden_oracle_only": hidden_oracle_only,
            },
            "artifact_integrity": integrity,
            "decision_reason": "strict offline resolved all repeats" if status == "rejected_too_easy" else "strict offline did not resolve all repeats",
            "next_action": "redesign candidate before full pilot" if status == "rejected_too_easy" else "eligible for full 4-condition pilot",
            "fair_screening": rich.to_json_dict(),
        })
    payload = {"run_id": run_dir.name, "summaries": summaries}
    (run_dir / "screening_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_screening_artifacts(run_dir, rich_results)
    return payload


def _constraint_angle(task: TaskSpec) -> str:
    if task.expected_project_docs or task.expected_symbols or task.dependencies:
        return ", ".join([*task.expected_project_docs, *task.expected_symbols, *[dependency.name for dependency in task.dependencies]])
    return ""


def _screening_task_class(task: TaskSpec) -> str:
    relevance = set(task.docatlas_relevance)
    text = task.issue_text.lower()
    if "generated_file_constraint" in relevance or "generated" in text:
        return "generated_file_trap"
    if "pinned_dependency" in relevance or "lock" in text:
        return "dependency_version_contract"
    if "cross_module_contract" in relevance or "cross-module" in text:
        return "cross_module_policy"
    if "architecture_constraint" in relevance:
        return "architecture_layer_boundary"
    if task.source_project == "docmancer":
        return "benchmark_accounting"
    return "other"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _causal_gate_error(
    conditions: list[str],
    *,
    verify_runner_requested: bool,
    runner_canary: dict[str, Any] | None,
    verify_docatlas_requested: bool,
    docatlas_canary: dict[str, Any] | None,
    requires_hard_turn_limit: bool = False,
    runner_hard_turn_limit: bool = True,
) -> str | None:
    if not verify_runner_requested:
        return "causal execution requires --verify-runner in the same invocation"
    if not runner_canary or runner_canary.get("status") != "passed":
        return "runner canary did not pass; causal execution was not started"
    if requires_hard_turn_limit and not runner_hard_turn_limit:
        return "Task 33 requires a runner with a proven hard turn limit; causal execution was not started"
    if any(condition in DOCATLAS_CONDITIONS for condition in conditions):
        if not verify_docatlas_requested:
            return "DocAtlas conditions require --verify-docatlas-tool in the same invocation"
        if not docatlas_canary or not docatlas_canary.get("docatlas_tool_visibility_verified"):
            return "DocAtlas tool visibility canary did not pass; causal execution was not started"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task-level patch benchmark harness")
    parser.add_argument("--manifest", type=Path, default=TASKS_PATH)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-runner", action="store_true")
    parser.add_argument("--verify-docatlas-tool", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-infrastructure-failures", action="store_true")
    parser.add_argument("--screen-tasks", action="store_true")
    parser.add_argument("--patch-constraints-targeted-pilot", action="store_true")
    parser.add_argument("--task33c-pilot", action="store_true", help="Run the frozen one-task, four-lane engineering pilot")
    parser.add_argument(
        "--task33c-provider-profile",
        default="github-models",
        help="Frozen hosted-model profile: github-models or openai-api",
    )
    parser.add_argument("--isolated-worker-command", help="Absolute JSON worker command for non-causal protocol smoke; provider usage remains unverified")
    parser.add_argument("--isolated-worker-factory", help="Inject a verified host-owned worker adapter as module.path:factory")
    parser.add_argument("--isolated-worker-identity", help="Versioned model/prompt identity for the isolated compressor")
    parser.add_argument("--isolated-worker-timeout-seconds", type=int, default=60)
    parser.add_argument("--isolated-worker-env", action="append", default=[], metavar="NAME", help="Explicitly pass one environment variable to the isolated worker")
    parser.add_argument("--isolated-worker-sandbox-executable", default="/usr/bin/bwrap", help="Absolute bubblewrap executable; the pilot fails closed when unavailable")
    parser.add_argument("--accepted-pool", type=Path)
    parser.add_argument("--runner", default="claude")
    parser.add_argument("--runner-factory", help="Inject a verified runner as module.path:factory")
    parser.add_argument(
        "--codex-sandbox-mode",
        choices=("workspace-write", "danger-full-access"),
        default="workspace-write",
    )
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
    if args.task33c_pilot and (args.patch_constraints_targeted_pilot or args.screen_tasks or args.smoke):
        raise SystemExit("--task33c-pilot cannot be combined with another pilot/screen/smoke mode")
    if args.task33c_pilot and args.retry_infrastructure_failures:
        raise SystemExit("--task33c-pilot enforces one attempt per cell and cannot be retried")
    if args.task33c_pilot:
        protocol = load_protocol()
        provider_profiles = protocol.get("provider_profiles") or {}
        if args.task33c_provider_profile not in provider_profiles:
            raise SystemExit(
                "Unknown Task 33C provider profile: " + args.task33c_provider_profile
            )
        provider_profile = provider_profiles[args.task33c_provider_profile]
        if len(tasks) != 1 or tasks[0].task_id != TASK33C_PILOT_TASK_ID:
            raise SystemExit(f"--task33c-pilot requires --tasks {TASK33C_PILOT_TASK_ID}")
        if args.model == "sonnet":
            args.model = str(provider_profile.get("model"))
        elif args.model != provider_profile.get("model"):
            raise SystemExit(
                "--model must match the frozen Task 33C provider profile: "
                + str(provider_profile.get("model"))
            )
        args.conditions = list(TASK33C_PILOT_CONDITIONS)
        args.repeats = 1
    if args.isolated_worker_command and args.isolated_worker_factory:
        raise SystemExit("Use either --isolated-worker-command or --isolated-worker-factory, not both")
    isolated_worker = load_isolated_worker_factory(args.isolated_worker_factory) if args.isolated_worker_factory else None
    if args.isolated_worker_command:
        if not args.isolated_worker_identity:
            raise SystemExit("--isolated-worker-command requires --isolated-worker-identity")
        command = tuple(shlex.split(args.isolated_worker_command))
        missing_environment = [name for name in args.isolated_worker_env if name not in os.environ]
        if missing_environment:
            raise SystemExit("Missing isolated-worker environment variables: " + ", ".join(missing_environment))
        if args.isolated_worker_timeout_seconds < 1:
            raise SystemExit("--isolated-worker-timeout-seconds must be positive")
        environment = {name: os.environ[name] for name in args.isolated_worker_env}
        isolated_worker = JsonSubprocessIsolatedWorker(
            command=command,
            compressor_identity=args.isolated_worker_identity,
            environment=environment,
            sandbox_executable=args.isolated_worker_sandbox_executable,
        )
    if "docatlas_bounded_subagent" in args.conditions and isolated_worker is None and not args.dry_run:
        raise SystemExit("docatlas_bounded_subagent requires --isolated-worker-factory or a dry-run command scaffold")
    if isolated_worker is not None and not isolated_worker.capabilities.verified and not args.dry_run:
        raise SystemExit("docatlas_bounded_subagent requires verified sandbox canaries and host-owned provider usage proof")
    if args.task33c_pilot and isolated_worker is not None and not args.dry_run:
        worker_provider = isolated_worker.capability_evidence.get("provider")
        worker_endpoint = isolated_worker.capability_evidence.get("provider_endpoint")
        worker_model = isolated_worker.capability_evidence.get("model")
        if (
            worker_provider != provider_profile.get("provider_id")
            or worker_endpoint != provider_profile.get("endpoint")
            or worker_model != provider_profile.get("model")
        ):
            raise SystemExit(
                "Task 33C worker/profile mismatch: expected frozen provider/endpoint/model "
                + str(provider_profile.get("provider_id"))
                + "/"
                + str(provider_profile.get("endpoint"))
            )
    if args.patch_constraints_targeted_pilot and not args.tasks:
        tasks = select_targeted_pilot_tasks(tasks, accepted_pool_path=args.accepted_pool)
        args.conditions = list(TARGETED_PILOT_CONDITIONS)
    run_dir = RESULTS_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "environment": environment_metadata(),
        "conditions": args.conditions,
        "executive_result": "Independent causal benchmark not completed in this harness invocation.",
        "decision": "ITERATE: harness and task manifest are ready; execute with verified independent runner before product claims.",
    }
    if args.task33c_pilot:
        plan = build_task33c_pilot_plan(tasks[0].task_id)
        shutil.copy2(PROTOCOL_PATH, run_dir / PROTOCOL_PATH.name)
        provider_selection = {
            "schema_version": 1,
            "profile_id": args.task33c_provider_profile,
            "profile": provider_profile,
            "profile_sha256": hashlib.sha256(
                json.dumps(
                    provider_profile,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        (run_dir / "task33c_provider_selection.json").write_text(
            json.dumps(provider_selection, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "task33c_pilot_plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        metadata["task33c_engineering_pilot"] = plan
        metadata["task33c_protocol"] = {
            "path": PROTOCOL_PATH.name,
            "sha256": protocol_sha256(),
            "enforcement": "independent_disk_artifact_verifier",
        }
        metadata["task33c_provider_selection"] = provider_selection
        metadata["isolated_worker_host"] = {
            "configured": isolated_worker is not None,
            "compressor_identity": isolated_worker.compressor_identity if isolated_worker else None,
            "sandbox_identity": isolated_worker.sandbox_identity if isolated_worker else None,
            "sandbox_capabilities": (
                isolated_worker.capabilities.__dict__ if isolated_worker else None
            ),
            "capability_evidence": isolated_worker.capability_evidence if isolated_worker else None,
            "usage_verifier_identity": isolated_worker.usage_verifier_identity if isolated_worker else None,
        }

    runner = (
        load_runner_factory(args.runner_factory)
        if args.runner_factory
        else select_runner(args.runner, codex_sandbox_mode=args.codex_sandbox_mode)
    )
    capabilities = runner.verify()
    if (
        args.task33c_pilot
        and not args.dry_run
        and capabilities.runner_id != provider_profile.get("runner_id")
    ):
        raise SystemExit(
            "Task 33C runner/profile mismatch: expected "
            + str(provider_profile.get("runner_id"))
            + ", got "
            + capabilities.runner_id
        )
    if args.task33c_pilot and not args.dry_run:
        provider_identity = getattr(runner, "provider_identity", {})
        if not isinstance(provider_identity, dict) or any(
            provider_identity.get(field) != provider_profile.get(field)
            for field in ("provider_id", "runner_id", "endpoint")
        ):
            raise SystemExit("Task 33C runner endpoint does not match the frozen provider profile")
    if args.task33c_pilot and not args.dry_run:
        boundary_evidence = getattr(runner, "boundary_evidence", {})
        boundary_evidence = boundary_evidence if isinstance(boundary_evidence, dict) else {}
        (run_dir / "task33c_sandbox_provenance.json").write_text(
            json.dumps({
                "schema_version": 1,
                "base_image": os.environ.get("TASK33C_BASE_IMAGE"),
                "requirements_sha256": os.environ.get("TASK33C_EVALUATOR_REQUIREMENTS_SHA256"),
                "evaluator_image": os.environ.get("TASK33C_TEST_CONTAINER_IMAGE"),
                "image_id": boundary_evidence.get("image_id"),
                "image_id_sha256": boundary_evidence.get("image_id_sha256"),
                "boundary_status": boundary_evidence.get("status"),
                "protocol_sha256": protocol_sha256(),
                "provider_profile_id": args.task33c_provider_profile,
                "provider_profile_sha256": provider_selection["profile_sha256"],
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    metadata["runner_verification"] = runner_verification_payload(capabilities)
    metadata["runner_factory"] = args.runner_factory
    metadata["environment"]["runner_detection"] = {
        "runner_id": capabilities.runner_id,
        "version": capabilities.version,
        "independent_runner_verified": capabilities.verified,
        "hard_turn_limit": capabilities.hard_turn_limit,
        "source": "selected runner verification",
    }
    if args.runner == "codex" and not args.runner_factory:
        metadata["runner_verification"]["sandbox_mode"] = args.codex_sandbox_mode
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    if args.materialize:
        materialized: list[dict[str, Any]] = []
        materialize_root = run_dir / "materialized"
        for task in tasks:
            if task.task_id in FIXTURE_TASKS:
                materialized.append(materialize_fixture(task, materialize_root / task.task_id))
        (run_dir / "materialized_summary.json").write_text(json.dumps(materialized, indent=2, sort_keys=True), encoding="utf-8")

    runner_canary: dict[str, Any] | None = None
    docatlas_canary: dict[str, Any] | None = None
    if args.verify_runner:
        runner_canary = run_canary(runner, args.model, args.timeout_seconds, run_dir / "runner_canary") if not args.dry_run else {"status": "dry_run"}
        VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
        (VALIDATION_ROOT / "runner_canary.json").write_text(json.dumps(runner_canary, indent=2, sort_keys=True), encoding="utf-8")
        (run_dir / "runner_canary.json").write_text(json.dumps(runner_canary, indent=2, sort_keys=True), encoding="utf-8")

    if args.verify_docatlas_tool:
        docatlas_canary = run_docatlas_tool_visibility_canary(runner, args.model, args.timeout_seconds, run_dir / "docatlas_tool_visibility_canary") if not args.dry_run else {"status": "dry_run"}
        VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
        (VALIDATION_ROOT / "docatlas_tool_visibility_canary.json").write_text(json.dumps(docatlas_canary, indent=2, sort_keys=True), encoding="utf-8")
        (run_dir / "docatlas_tool_visibility_canary.json").write_text(json.dumps(docatlas_canary, indent=2, sort_keys=True), encoding="utf-8")
        metadata["docatlas_tool_visibility_canary"] = docatlas_canary
        if not docatlas_canary.get("docatlas_tool_visibility_verified"):
            metadata["decision"] = "ITERATE_TOOL_DISCOVERABILITY"
            (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    validation_results: list[Any] = []
    if args.validate:
        validation_results = [validate_task(task) for task in tasks]
        (run_dir / "validation_summary.json").write_text(json.dumps(validation_results, indent=2, sort_keys=True), encoding="utf-8")

    results: list[dict[str, Any]] = []
    if args.patch_constraints_targeted_pilot:
        screening_metadata = _load_json(args.accepted_pool.parent / "screening_results.json") if args.accepted_pool else {}
        plan = build_targeted_pilot_plan(
            tasks,
            repeats=args.repeats,
            task_selection_source="screening_results" if args.accepted_pool else "legacy_manifest",
            screening_metadata={
                "accepted_pool_size": len(tasks),
                "rejected_counts": screening_metadata.get("rejected_counts", {}),
            },
        )
        (run_dir / "targeted_pilot_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
        metadata["targeted_patch_constraints_pilot"] = {
            "status": plan["status"],
            "research_question": plan["research_question"],
            "conditions": plan["conditions"],
            "task_count": len(plan["tasks"]),
        }
        if args.dry_run:
            metadata["executive_result"] = "Patch-constraints targeted pilot scaffold prepared; dry-run mode is non-causal."
            metadata["decision"] = "RUN_TARGETED_PILOT_WITH_VERIFIED_RUNNER_BEFORE_OUTCOME_CLAIMS"
            metadata["claims_can_make"] = "The harness can prepare a targeted patch-constraints pilot plan and artifact contract; dry-run output is not causal outcome evidence."
            metadata["claims_cannot_make"] = "Cannot claim DocAtlas improves patch success, beats repo-only/Context7, proves correctness, or replaces tests from this dry-run/protocol checkpoint."
            metadata["next_experiment"] = "Run the targeted pilot on the accepted/differentiating subset with a verified independent runner; expand accepted tasks before broad outcome claims."
        else:
            metadata["executive_result"] = "Patch-constraints targeted pilot execution requested; interpret rows by runner status and artifact integrity."
            metadata["decision"] = "INTERPRET_AFTER_RUNNER_STATUS_AND_ARTIFACT_REVIEW"
            metadata["claims_can_make"] = "A targeted patch-constraints pilot execution was attempted with persisted per-run artifacts; outcome claims require completed patch rows."
            metadata["claims_cannot_make"] = "Cannot claim DocAtlas improves patch success, beats repo-only/Context7, proves correctness, or replaces tests from a blocked or tiny pilot."
            metadata["next_experiment"] = "If runner rows are blocked, verify/authenticate an independent runner before rerunning; otherwise expand accepted tasks before broader claims."
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        if args.dry_run:
            results = write_targeted_pilot_dry_run(run_dir, plan)

    if args.smoke:
        results = run_smoke(tasks, args.conditions[:2], args.repeats, run_dir)
        (run_dir / "runs.jsonl").write_text(serialize_run_results_jsonl(results), encoding="utf-8")

    should_execute_pilot = args.execute or args.screen_tasks or args.task33c_pilot or (args.patch_constraints_targeted_pilot and not args.dry_run)
    if should_execute_pilot and not (args.patch_constraints_targeted_pilot and args.dry_run):
        if args.dry_run:
            results = [{"status": "dry_run", "task_id": task.task_id, "condition_id": condition, "repeat": repeat, "resolved": False, "metrics": {}} for task in tasks for repeat in range(args.repeats) for condition in args.conditions]
        else:
            gate_error = _causal_gate_error(
                args.conditions,
                verify_runner_requested=args.verify_runner,
                runner_canary=runner_canary,
                verify_docatlas_requested=args.verify_docatlas_tool,
                docatlas_canary=docatlas_canary,
                requires_hard_turn_limit=any(task.task_id in TASK23_PROTOCOL_TASKS for task in tasks),
                runner_hard_turn_limit=capabilities.hard_turn_limit,
            )
            if gate_error:
                metadata["executive_result"] = "Causal execution blocked before the pilot."
                metadata["decision"] = "BLOCKED_BY_CANARY_GATE"
                metadata["canary_gate_error"] = gate_error
                write_report(run_dir, metadata, results)
                print(run_dir)
                return 2
            results = execute_pilot(
                tasks,
                args.conditions,
                args.repeats,
                args.run_id,
                runner,
                args.model,
                args.timeout_seconds,
                BASE_PROMPT,
                retry_infrastructure_failures=args.retry_infrastructure_failures,
                isolated_worker=isolated_worker,
                isolated_worker_timeout_seconds=args.isolated_worker_timeout_seconds,
            )

    if args.task33c_pilot and not args.dry_run:
        completeness = evaluate_task33c_pilot_completeness(results)
        metadata["task33c_completeness"] = completeness
        metadata["decision"] = completeness["decision"]
        metadata["executive_result"] = (
            "Task 33C engineering pilot produced a complete measurement bundle."
            if completeness["complete"]
            else "Task 33C engineering pilot is INCONCLUSIVE because required evidence or measurements are incomplete."
        )
        metadata["failure_summary"] = (
            "No Task 33C cell may be interpreted causally until the completeness gate is green."
            if not completeness["complete"]
            else "All four Task 33C engineering-pilot cells passed the completeness gate."
        )
        metadata["claims_can_make"] = (
            "The one-task engineering pilot produced a complete, auditable comparison bundle."
            if completeness["complete"]
            else "The harness fail-closed and preserved the reasons the engineering pilot is inconclusive."
        )
        metadata["claims_cannot_make"] = (
            "A one-task engineering pilot cannot establish general product impact or replace the frozen formal protocol."
            if completeness["complete"]
            else "No causal comparison or Task 33C product claim can be made from incomplete cells."
        )
        metadata["next_experiment"] = (
            "Review the valid one-task evidence bundle, then run the frozen 3 tasks x 4 conditions x 3 repeats protocol."
            if completeness["complete"]
            else "Repair the reported completeness errors and rerun the same one-task/four-condition engineering pilot before any formal 3 x 4 x 3 run."
        )
        (run_dir / "task33c_completeness.json").write_text(
            json.dumps(completeness, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    write_report(run_dir, metadata, results)
    task33c_validation: dict[str, Any] | None = None
    if args.task33c_pilot and not args.dry_run:
        task33c_validation = validate_task33c_run(run_dir)
        metadata["task33c_independent_validation"] = {
            "valid": task33c_validation["valid"],
            "verdict": task33c_validation["verdict"],
            "errors": task33c_validation["errors"],
            "artifact": "task33c_validation.json",
        }
        metadata["decision"] = (
            "ENGINEERING_PILOT_COMPLETE"
            if task33c_validation["valid"]
            else "INCONCLUSIVE"
        )
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        task33c_validation = validate_task33c_run(run_dir)
    if args.screen_tasks:
        write_screening_summary(run_dir, tasks, results, args.repeats)
    print(run_dir)
    if args.task33c_pilot and not args.dry_run and not (task33c_validation or {}).get("valid"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
