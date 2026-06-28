from __future__ import annotations

import json
import os
import random
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS
from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.evaluators.patch import diff_stats, patch_touches_forbidden_paths
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.evaluators.tests import run_command
from eval.task_level.fixtures.builder import copy_hidden_tests, materialize_fixture
from eval.task_level.runners.base import AgentRunRequest, AgentRunner, RunnerCapabilities
from eval.task_level.schemas import RESULTS_ROOT, TASK_LEVEL_ROOT, RunMetrics, TaskSpec


RUNTIME_ROOT = TASK_LEVEL_ROOT / "runtime"
ALLOWED_PATCH_PREFIXES = ("src/", "tests/", "lib/", "README.md", "docs/", "pyproject.toml", "pubspec.yaml", "pubspec.lock")
DOCATLAS_CONDITIONS = {
    "docatlas_snippet_first",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_context_injected",
    "docatlas_action_checklist_injected",
    "docatlas_action_checklist_only",
    "docatlas_tool_required_once",
}
CONTEXT_INJECTION_LIMIT_CHARS = 10000


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def serialize_run_results_jsonl(results: list[dict[str, Any]]) -> str:
    """Serialize run results as JSONL with one physical line per record."""

    if not results:
        return ""
    return "\n".join(json.dumps(result, sort_keys=True) for result in results) + "\n"


def count_jsonl_records(path: Path) -> int:
    """Count non-empty JSONL records on disk."""

    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_artifact_integrity(run_dir: Path, *, in_memory_results: int, total_runs: int, finished: bool) -> dict[str, Any]:
    """Return a machine-checkable consistency summary for run artifacts."""

    runs_jsonl_records = count_jsonl_records(run_dir / "runs.jsonl")
    jsonl_matches_memory = runs_jsonl_records == in_memory_results
    final_run_count_matches = (not finished) or (in_memory_results == total_runs)
    ok = jsonl_matches_memory and final_run_count_matches

    reasons: list[str] = []
    if not jsonl_matches_memory:
        reasons.append("runs_jsonl_record_count_mismatch")
    if not final_run_count_matches:
        reasons.append("finished_before_expected_run_count")

    return {
        "ok": ok,
        "finished": finished,
        "runs_jsonl_records": runs_jsonl_records,
        "in_memory_results": in_memory_results,
        "expected_total_runs": total_runs,
        "reason": reasons or None,
    }


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
        "inject_docatlas_context": policy.inject_docatlas_context,
        "inject_action_checklist": policy.inject_action_checklist,
        "recommend_docatlas_before_edit": policy.recommend_docatlas_before_edit,
        "require_docatlas_call_before_edit": policy.require_docatlas_call_before_edit,
        "network_enforcement": "policy_and_trajectory_audit",
    }, indent=2, sort_keys=True), encoding="utf-8")

    mcp_path = output_dir / "mcp_config.json"
    if condition_id in {"repo_only", "repo_only_strict_offline", "repo_only_web_audited"}:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    elif condition_id in DOCATLAS_CONDITIONS:
        mcp_path.write_text(json.dumps({
            "mcpServers": {
                "docmancer-docs": {
                    "command": "uv",
                    "args": ["run", "--project", str(Path(__file__).resolve().parents[2]), "doc-atlas", "mcp", "docs-serve"],
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
        "DOCMANCER_AUTO_VECTORS": "0",
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
    setup = _run_setup(task, workspace) if patch_exists and task.setup_command else None
    public = run_command(task.test_command, workspace, 180) if patch_exists and (setup is None or setup.returncode == 0) else None
    hidden = None
    if patch_exists:
        copy_hidden_tests(task.task_id, workspace)
        hidden = run_command("pytest tests/hidden", workspace, 180)
    compile_result = run_command("python -m compileall -q src", workspace, 120) if patch_exists and (setup is None or setup.returncode == 0) else None
    forbidden = patch_touches_forbidden_paths(workspace, ALLOWED_PATCH_PREFIXES) if patch_exists else []
    audit = audit_trajectory(condition_id, Path(trajectory_path) if trajectory_path else None, run_output_dir / "policy_audit.json")
    stats = diff_stats(workspace) if patch_exists else None
    utilization = evaluate_docatlas_utilization(
        task=task,
        condition_id=condition_id,
        run_output_dir=run_output_dir,
        patch_path=patch_path,
        trajectory_path=Path(trajectory_path) if trajectory_path else None,
        agent_docatlas_calls=audit.docatlas_calls,
    )
    contract = evaluate_contract(task, workspace, patch_path)
    actionability = evaluate_actionability(
        task=task,
        condition_id=condition_id,
        run_output_dir=run_output_dir,
        patch_path=patch_path,
        trajectory_path=Path(trajectory_path) if trajectory_path else None,
        contract=contract,
    )
    public_passed = bool(public and public.passed)
    hidden_passed = bool(hidden and hidden.passed)
    compile_success = bool(compile_result and compile_result.passed)
    resolved = patch_exists and public_passed and hidden_passed and compile_success and audit.clean and not forbidden
    status = "completed" if resolved or patch_exists else "no_patch"
    if not audit.clean:
        status = "policy_violation"
    injection = _load_optional_json(run_output_dir / "docatlas_context_injection.json")
    checklist_injection = _load_optional_json(run_output_dir / "action_checklist_injection.json")
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
        context_chunks_returned=int(injection.get("sources", 0)) if isinstance(injection, dict) else 0,
        injected_context_tokens=int(injection.get("injected_context_tokens")) if isinstance(injection.get("injected_context_tokens"), int) else None,
        retrieved_context_tokens=int(injection.get("retrieved_context_tokens")) if isinstance(injection.get("retrieved_context_tokens"), int) else None,
        raw_doc_context_tokens=int(injection.get("raw_doc_context_tokens")) if isinstance(injection.get("raw_doc_context_tokens"), int) else None,
        checklist_tokens=int(checklist_injection.get("checklist_tokens")) if isinstance(checklist_injection.get("checklist_tokens"), int) else None,
    )
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": "codex" if "codex" in str(getattr(runner_output, "runner_version", "")).lower() else "claude",
        "runner_version": getattr(runner_output, "runner_version", "unknown"),
        "model": getattr(runner_output, "model", "unknown"),
        "status": status,
        "resolved": resolved,
        "public_tests_passed": public_passed,
        "hidden_tests_passed": hidden_passed,
        "tests_passed": public_passed,
        "compile_success": compile_success,
        "policy_clean": audit.clean,
        "policy": audit.to_json(),
        "docatlas": utilization.to_json(),
        "contract": contract.to_json(),
        "actionability": actionability.to_json(),
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
            "agent_docatlas_calls": audit.docatlas_calls,
            "network_attempts": audit.network_attempts,
            "harness_docatlas_calls": utilization.harness_calls,
            "injected_context_tokens": metrics.injected_context_tokens,
            "checklist_tokens": metrics.checklist_tokens,
            "retrieved_context_tokens": metrics.retrieved_context_tokens,
            "constraint_packet_tokens": metrics.constraint_packet_tokens,
            "raw_doc_context_tokens": metrics.raw_doc_context_tokens,
            "fallback_used": utilization.fallback_used,
            "fallback_source": getattr(utilization, "fallback_source", None),
            "docatlas_retrieval_status": utilization.docatlas_retrieval_status,
            "vector_indexing_timed_out": utilization.vector_indexing_timed_out,
        },
        "context": {
            "retrieved_count": int(utilization.context_retrieved) + audit.docatlas_calls,
            "used_count": int(utilization.context_used),
            "utilization_rate": 1.0 if utilization.context_used else 0.0 if utilization.context_retrieved or audit.docatlas_calls else None,
        },
        "notes": getattr(runner_output, "notes", []),
    }
    if setup is not None and setup.returncode != 0:
        result["notes"].append("setup command failed before evaluator tests")
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _run_setup(task: TaskSpec, workspace: Path) -> subprocess.CompletedProcess[str]:
    command = task.setup_command
    if command.startswith("python -m pip "):
        command = "uv pip " + command.removeprefix("python -m pip ") + f" --python {sys.executable}"
    return subprocess.run(command, cwd=workspace, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False)


def execute_pilot(tasks: list[TaskSpec], conditions: list[str], repeats: int, run_id: str, runner: AgentRunner, model: str, timeout_seconds: int, prompt_template: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = Path(tempfile.mkdtemp(prefix=f"docatlas-task-level-{run_id}-"))
    try:
        total_runs = len(tasks) * len(conditions) * repeats
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
                    setup_failed = False
                    if condition_id in DOCATLAS_CONDITIONS:
                        diagnostics = prepare_docatlas(task, workspace, run_output_dir, env)
                        setup_failed = diagnostics.get("status") == "condition_setup_failed"
                    prompt = prompt_template.format(issue_text=task.issue_text) + "\nUse the tools available in this environment when they are useful.\n"
                    if CONDITIONS[condition_id].tool_policy.inject_docatlas_context or CONDITIONS[condition_id].tool_policy.inject_action_checklist:
                        injected = inject_docatlas_context(task, workspace, run_output_dir, env)
                        if injected.get("status") == "condition_setup_failed":
                            setup_failed = True
                        else:
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist:
                                checklist = inject_action_checklist(task, workspace, run_output_dir)
                                if checklist.get("status") == "condition_setup_failed":
                                    setup_failed = True
                            if CONDITIONS[condition_id].tool_policy.inject_docatlas_context:
                                prompt += "\n" + (run_output_dir / "injected_context.md").read_text(encoding="utf-8") + "\n"
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist and (run_output_dir / "action_checklist.md").exists():
                                prompt += "\n" + (run_output_dir / "action_checklist.md").read_text(encoding="utf-8") + "\n"
                    if CONDITIONS[condition_id].tool_policy.recommend_docatlas_before_edit:
                        prompt += "\nDocAtlas workflow guidance: Use DocAtlas/docmancer documentation context before making code changes when the task may depend on library APIs, exact dependency versions, or project docs. Ask a task-specific documentation question, then use or ignore the returned context based on relevance.\n"
                    if CONDITIONS[condition_id].tool_policy.require_docatlas_call_before_edit:
                        prompt += "\nDiagnostic policy: Before your first code edit, call the available documentation-context tool once with a task-specific question. Use or ignore the returned context based on relevance.\n"
                    if setup_failed:
                        result = condition_setup_failed_result(task, condition_id, run_output_dir)
                        results.append(result)
                        write_run_progress(run_dir, results, total_runs, current={"task_id": task.task_id, "condition_id": condition_id, "repeat": repeat, "status": result["status"]})
                        continue
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
                    write_run_progress(run_dir, results, total_runs, current={"task_id": task.task_id, "condition_id": condition_id, "repeat": repeat, "status": result["status"]})
    finally:
        shutil.rmtree(runtime_root, ignore_errors=True)
    write_run_progress(run_dir, results, len(tasks) * len(conditions) * repeats, current=None, finished=True)
    return results


def write_run_progress(run_dir: Path, results: list[dict[str, Any]], total_runs: int, *, current: dict[str, Any] | None, finished: bool = False) -> None:
    completed = len(results)
    _write_text_atomic(run_dir / "runs.jsonl", serialize_run_results_jsonl(results))
    integrity = run_artifact_integrity(run_dir, in_memory_results=completed, total_runs=total_runs, finished=finished)
    status = "finished" if finished else "running"
    if finished and not integrity["ok"]:
        status = "artifact_integrity_failed"
    payload = {
        "status": status,
        "completed_runs": completed,
        "total_runs": total_runs,
        "remaining_runs": max(total_runs - completed, 0),
        "current": current,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_integrity": integrity,
        "latest_results": [
            {
                "task_id": result.get("task_id"),
                "condition_id": result.get("condition_id"),
                "status": result.get("status"),
                "resolved": result.get("resolved"),
                "public_tests_passed": result.get("public_tests_passed"),
                "hidden_tests_passed": result.get("hidden_tests_passed"),
                "agent_docatlas_calls": result.get("docatlas", {}).get("agent_calls") if isinstance(result.get("docatlas"), dict) else None,
                "context_used": result.get("docatlas", {}).get("context_used") if isinstance(result.get("docatlas"), dict) else None,
                "policy_clean": result.get("policy_clean"),
                "checklist_items": len(result.get("actionability", {}).get("checklist_items", [])) if isinstance(result.get("actionability"), dict) else 0,
                "checklist_used": result.get("actionability", {}).get("action_checklist_used") if isinstance(result.get("actionability"), dict) else None,
            }
            for result in results[-8:]
        ],
    }
    _write_json_atomic(run_dir / "status.json", payload)


def prepare_docatlas(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    sync_status = "not_run"
    sync_error = None
    try:
        from docmancer.docs.service import LibraryDocsService

        old_home = os.environ.get("DOCMANCER_HOME")
        os.environ["DOCMANCER_HOME"] = env["DOCMANCER_HOME"]
        try:
            sync_result = LibraryDocsService().sync_project_docs(str(workspace), with_vectors=False)
            sync_status = getattr(sync_result, "status", "success")
        finally:
            if old_home is None:
                os.environ.pop("DOCMANCER_HOME", None)
            else:
                os.environ["DOCMANCER_HOME"] = old_home
    except Exception as exc:
        sync_status = "failed"
        sync_error = repr(exc)

    diagnostics = {
        "task_id": task.task_id,
        "status": "prepared_with_local_project_docs_only" if sync_status != "failed" else "condition_setup_failed",
        "allow_network": False,
        "docmancer_home": env["DOCMANCER_HOME"],
        "project_docs_sync_status": sync_status,
        "project_docs_sync_error": sync_error,
        "sources": ["fixture README/docs", "FastAPI docs preindex not fetched during unit validation"],
        "pages": 1 if sync_status != "failed" else 0,
        "chunks": 1 if sync_status != "failed" else 0,
        "expected_domains_present": [],
        "contamination": 0,
        "wall_time_seconds": round(time.monotonic() - started, 4),
        "limitation": "Offline pilot preparation syncs project-owned docs only. Exact dependency docs must already be locally cached; no network fetch is performed.",
    }
    (output_dir / "docatlas_preparation.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8")
    return diagnostics


def inject_docatlas_context(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    fallback_reason: str | None = None
    try:
        from docmancer.docs.service import LibraryDocsService

        old_home = os.environ.get("DOCMANCER_HOME")
        os.environ["DOCMANCER_HOME"] = env["DOCMANCER_HOME"]
        old_handler = signal.getsignal(signal.SIGALRM)

        def _timeout_handler(_signum: int, _frame: Any) -> None:
            raise TimeoutError("DocAtlas context injection exceeded 45 seconds")

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(45)
        try:
            dependency = task.dependencies[0] if task.dependencies else None
            result = LibraryDocsService().get_docs_context(
                task.issue_text,
                project_path=str(workspace),
                library=None if task.task_id.startswith("real_project_") else dependency.name if dependency else None,
                ecosystem=task.ecosystem,
                version=None if task.task_id.startswith("real_project_") else dependency.version if dependency else None,
                mode="project" if task.task_id.startswith("real_project_") else "auto",
                response_style="snippet-first",
                allow_network=False,
                allow_latest_fallback=False,
                tokens=2500,
                limit=6,
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            if old_home is None:
                os.environ.pop("DOCMANCER_HOME", None)
            else:
                os.environ["DOCMANCER_HOME"] = old_home
    except Exception as exc:
        fallback_reason = repr(exc)
        result = _fallback_project_context(task, workspace, fallback_reason)

    response = _jsonable(result)
    (output_dir / "docatlas_response.json").write_text(json.dumps(response, indent=2, sort_keys=True), encoding="utf-8")
    sources = _extract_context_sources(response)[:6]
    (output_dir / "context_sources.json").write_text(json.dumps(sources, indent=2, sort_keys=True), encoding="utf-8")
    markdown = format_injected_context(response, sources)
    if len(markdown) > CONTEXT_INJECTION_LIMIT_CHARS:
        markdown = markdown[:CONTEXT_INJECTION_LIMIT_CHARS] + "\n\n[truncated by benchmark harness]\n"
    (output_dir / "injected_context.md").write_text(markdown, encoding="utf-8")
    raw_json = json.dumps(response, sort_keys=True)
    payload = {
        "status": "success" if fallback_reason is None else "fallback_local_project_context",
        "docatlas_retrieval_status": "success" if fallback_reason is None else "fallback_local_project_context",
        "vector_indexing_timed_out": bool(fallback_reason and "exceeded 45 seconds" in fallback_reason),
        "fallback_used": fallback_reason is not None,
        "fallback_source": "visible_fixture_project_docs" if fallback_reason is not None else None,
        "docatlas_tool_success": fallback_reason is None,
        "docatlas_fallback_success": fallback_reason is not None,
        "harness_docatlas_calls": 1 if fallback_reason is None else 0,
        "sources": len(sources),
        "injected_context_tokens": _estimate_tokens(markdown),
        "retrieved_context_tokens": _estimate_tokens(raw_json),
        "raw_doc_context_tokens": _estimate_tokens(raw_json),
        "fallback_reason": fallback_reason,
        "wall_time_seconds": round(time.monotonic() - started, 4),
    }
    (output_dir / "docatlas_context_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _fallback_project_context(task: TaskSpec, workspace: Path, reason: str) -> dict[str, Any]:
    items = []
    selected = []
    for relative in task.expected_project_docs[:6]:
        path = workspace / relative
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")[:1600]
            items.append({"content": text, "source": {"kind": "project_doc", "path": relative}})
            selected.append({"source": {"kind": "project_doc", "path": relative}, "reason": "fallback expected project doc"})
    return {
        "mode": "project_fallback",
        "reason_code": "docatlas_context_timeout_fallback",
        "warnings": [f"DocAtlas context retrieval failed; benchmark used visible project-doc fallback: {reason}"],
        "context_pack": items,
        "trust_contract": {"selected": selected, "risky": [], "rejected": []},
    }


def inject_action_checklist(task: TaskSpec, workspace: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    response_path = output_dir / "docatlas_response.json"
    try:
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else {}
        items = build_action_checklist(
            task_id=task.task_id,
            issue_text=task.issue_text,
            docatlas_response=response,
            workspace=workspace,
        )
        save_action_checklist(items, output_dir)
    except Exception as exc:
        payload = {"status": "condition_setup_failed", "error": repr(exc), "wall_time_seconds": round(time.monotonic() - started, 4)}
        (output_dir / "action_checklist_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    markdown = (output_dir / "action_checklist.md").read_text(encoding="utf-8") if (output_dir / "action_checklist.md").exists() else ""
    payload = {"status": "success", "checklist_items": len(items), "checklist_tokens": _estimate_tokens(markdown), "wall_time_seconds": round(time.monotonic() - started, 4)}
    (output_dir / "action_checklist_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def format_injected_context(response: dict[str, Any], sources: list[dict[str, Any]]) -> str:
    trust = response.get("trust_contract", {}) if isinstance(response.get("trust_contract"), dict) else {}
    routing = response.get("routing", {}) if isinstance(response.get("routing"), dict) else {}
    items = response.get("context_pack") or response.get("items") or response.get("context") or []
    snippets: list[str] = []
    if isinstance(items, list):
        for item in items[:2]:
            if isinstance(item, dict):
                snippet = item.get("snippet") or item.get("content") or item.get("text") or item.get("summary")
                if snippet:
                    snippets.append(str(snippet)[:1600])
    lines = [
        "## Verified DocAtlas context",
        "",
        "Routing:",
        f"- mode_selected: {response.get('mode') or routing.get('mode_selected') or 'auto'}",
        f"- reason: {routing.get('reason') or response.get('reason_code') or 'DocAtlas offline context route'}",
        "",
    ]
    for index, snippet in enumerate(snippets, start=1):
        lines.extend([f"Primary snippet {index}:", "```text", snippet, "```", ""])
    lines.extend(["Project constraints:"])
    for source in sources:
        if str(source.get("kind", "")).startswith("project"):
            lines.append(f"- Follow project source {source.get('path') or source.get('title')}")
    if not any(str(source.get("kind", "")).startswith("project") for source in sources):
        lines.append("- No project-specific constraint source selected by DocAtlas.")
    lines.extend(["", "Sources:"])
    for index, source in enumerate(sources, start=1):
        label = source.get("kind") or "source"
        path = source.get("path") or source.get("url") or source.get("title") or "unknown"
        why = source.get("why") or source.get("freshness") or "selected by DocAtlas"
        lines.append(f"{index}. [{label}] {path} - {why}")
    selected = trust.get("selected") or trust.get("selected_sources") or []
    risky = trust.get("risky") or []
    rejected = trust.get("rejected") or []
    lines.extend([
        "",
        "Trust Contract:",
        f"- selected: {len(selected) if isinstance(selected, list) else 0}",
        f"- risky: {len(risky) if isinstance(risky, list) else 0}",
        f"- rejected: {len(rejected) if isinstance(rejected, list) else 0}",
        "",
        "Warnings:",
    ])
    warnings = response.get("warnings") if isinstance(response.get("warnings"), list) else []
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings[:4])
    else:
        lines.append("- No DocAtlas warnings reported.")
    return "\n".join(lines)


def _extract_context_sources(response: dict[str, Any]) -> list[dict[str, Any]]:
    trust = response.get("trust_contract", {}) if isinstance(response.get("trust_contract"), dict) else {}
    candidates = trust.get("selected") or trust.get("selected_sources") or response.get("sources") or []
    sources: list[dict[str, Any]] = []
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                source = item.get("source") if isinstance(item.get("source"), dict) else item
                sources.append({
                    "kind": source.get("kind") or source.get("type") or source.get("source_type") or "project",
                    "path": source.get("path") or source.get("url") or source.get("title"),
                    "title": source.get("title"),
                    "why": item.get("why") or item.get("reason"),
                    "freshness": source.get("freshness"),
                })
    return sources


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return _jsonable(value.__dict__)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def condition_setup_failed_result(task: TaskSpec, condition_id: str, run_output_dir: Path) -> dict[str, Any]:
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": "not_run",
        "status": "condition_setup_failed",
        "resolved": False,
        "public_tests_passed": False,
        "hidden_tests_passed": False,
        "tests_passed": False,
        "compile_success": False,
        "policy_clean": False,
        "policy": {"clean": False, "violations": ["condition_setup_failed"]},
        "docatlas": {"available": True, "harness_calls": 0, "agent_calls": 0, "context_retrieved": False, "context_injected": False, "context_used": False, "context_used_confidence": "none", "used_symbols": [], "used_sources": []},
        "contract": {},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
        "metrics": {},
        "notes": ["DocAtlas condition setup failed; agent was not run."],
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


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
        raw_stdout = Path(runner_output.raw_stdout_path).read_text(encoding="utf-8") if Path(runner_output.raw_stdout_path).exists() else ""
        network_probe_denied = "blocked by benchmark network policy" in raw_stdout
        canary_policy_clean = audit.clean or (network_probe_denied and audit.docatlas_calls == 0 and audit.context7_calls == 0)
        payload = {
            "task_id": "runner_canary",
            "status": "passed" if patch_path.read_text(encoding="utf-8").strip() and tests.passed and canary_policy_clean and runner_output.exit_code is not None else "failed",
            "runner_status": runner_output.status,
            "runner_exit_code": runner_output.exit_code,
            "patch_exists": bool(patch_path.read_text(encoding="utf-8").strip()),
            "pytest_passes": tests.passed,
            "trajectory_exists": bool(runner_output.trajectory_path and Path(runner_output.trajectory_path).exists()),
            "runner_exit_interpretable": runner_output.exit_code is not None,
            "policy_clean": canary_policy_clean,
            "network_probe_denied": network_probe_denied,
            "changed_files": changed,
            "failure_summary": "runner did not produce a patch" if not patch_path.read_text(encoding="utf-8").strip() else "",
            "workspace": str(workspace),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def run_docatlas_tool_visibility_canary(runner: AgentRunner, model: str, timeout_seconds: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="docatlas-tool-canary-"))
    try:
        (workspace / "README.md").write_text("# Canary Repo\n\nThis repository is used to verify documentation-context tool visibility.\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=workspace, check=False)
        subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=workspace, check=False)
        subprocess.run(["git", "add", "."], cwd=workspace, check=False)
        subprocess.run(["git", "commit", "-m", "canary base"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        policy_path, mcp_config = build_tool_policy("docatlas_tool_optional", output_dir)
        env = fresh_run_environment(output_dir)
        prepare_docatlas(TaskSpec(
            task_id="docatlas_tool_visibility_canary",
            task_type="curated",
            suite="differentiation",
            repo="fixture://docatlas_tool_visibility_canary",
            base_commit="fixture-base",
            issue_text="Ask the available DocAtlas/documentation-context MCP get_docs_context tool what documentation context is available for this repository. Do not edit files.",
            language="text",
            ecosystem="python",
            dependencies=(),
            setup_command="",
            test_command="true",
        ), workspace, output_dir, env)
        request = AgentRunRequest(
            task_id="docatlas_tool_visibility_canary",
            condition_id="docatlas_tool_visibility_canary",
            workspace=workspace,
            prompt="Ask the available DocAtlas/documentation-context MCP get_docs_context tool what documentation context is available for this repository. Do not edit files.",
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
        audit = audit_trajectory("docatlas_tool_optional", Path(runner_output.trajectory_path) if runner_output.trajectory_path else None, output_dir / "policy_audit.json")
        response_saved = False
        if runner_output.trajectory_path and Path(runner_output.trajectory_path).exists():
            trajectory_text = Path(runner_output.trajectory_path).read_text(encoding="utf-8")
            response_saved = "get_docs_context" in trajectory_text or "docmancer-docs" in trajectory_text
            (output_dir / "docatlas_tool_response_excerpt.txt").write_text(trajectory_text[:8000], encoding="utf-8")
        get_docs_context_seen = False
        if runner_output.trajectory_path and Path(runner_output.trajectory_path).exists():
            get_docs_context_seen = "get_docs_context" in Path(runner_output.trajectory_path).read_text(encoding="utf-8")
        verified = audit.docatlas_calls > 0 and get_docs_context_seen and response_saved and not patch_path.read_text(encoding="utf-8").strip()
        payload = {
            "docatlas_tool_visibility_verified": verified,
            "status": "passed" if verified else "failed",
            "docatlas_calls": audit.docatlas_calls,
            "agent_docatlas_calls": audit.docatlas_calls,
            "tool_name_seen": audit.docatlas_tool_name_seen,
            "get_docs_context_seen": get_docs_context_seen,
            "response_saved": response_saved,
            "trajectory_path": runner_output.trajectory_path,
            "no_code_edits": not patch_path.read_text(encoding="utf-8").strip() and not changed,
            "failure_reason": None if verified else "DocAtlas tool call not observed, response not saved, or files were edited",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "docatlas_tool_visibility_canary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
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
