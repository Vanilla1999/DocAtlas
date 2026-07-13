from __future__ import annotations

import hashlib
import json
import os
import random
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS
from eval.task_level.artifact_hygiene import diff_stats_from_patch, is_runtime_artifact, write_patch_hygiene_artifacts
from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.context.patch_constraints import build_patch_constraint_packet, save_patch_constraint_packet
from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.constraint_validation import validate_patch_against_constraints
from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.evaluators.patch import forbidden_changed_paths
from eval.task_level.evaluators.patch_constraints import evaluate_patch_constraint_usage, load_patch_constraint_packet
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.evaluators.task_contract import evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_task_evaluation_contracts, run_compile_gate, validate_task_evaluation_contract
from eval.task_level.evaluators.tests import run_command
from eval.task_level.fixtures.builder import copy_hidden_tests, materialize_fixture
from eval.task_level.runners.base import AgentRunRequest, AgentRunner, RunnerCapabilities
from eval.task_level.schemas import RESULTS_ROOT, TASK_LEVEL_ROOT, RunMetrics, TaskSpec


RUNTIME_ROOT = TASK_LEVEL_ROOT / "runtime"
INFRASTRUCTURE_FAILURE_STATUSES = frozenset({
    "runner_unavailable",
    "runner_failed",
    "condition_setup_failed",
    "timeout",
})


def is_infrastructure_failure(result: dict[str, Any]) -> bool:
    if result.get("status") in INFRASTRUCTURE_FAILURE_STATUSES:
        return True
    metrics = result.get("metrics") or {}
    return result.get("status") == "no_patch" and metrics.get("total_tokens") is None


ALLOWED_PATCH_PREFIXES = (
    "src/",
    "tests/",
    "lib/",
    "android/",
    "example/",
    "ViScanner/",
    "ViScannerAIDL/",
    "ViScannerService/",
    "README.md",
    "ARCHITECTURE.md",
    "docs/",
    "pyproject.toml",
    "pubspec.yaml",
    "pubspec.lock",
)
DOCATLAS_CONDITIONS = {
    "docatlas_snippet_first",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_context_injected",
    "docatlas_action_checklist_injected",
    "docatlas_patch_constraints_injected",
    "docatlas_patch_constraints_workflow",
    "docatlas_action_checklist_only",
    "docatlas_tool_required_once",
}
CONTEXT_INJECTION_LIMIT_CHARS = 10000
AUDITED_EXTERNAL_CONTEXT_ROOT = TASK_LEVEL_ROOT / "external_context"
TASK33_EVALUATION_CONTRACTS = load_task_evaluation_contracts()


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def trajectory_evidence_metrics(task: Any, trajectory_path: Path) -> dict[str, Any]:
    evidence = list(dict.fromkeys([*task.expected_symbols, *task.expected_project_docs]))
    try:
        events = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        events = []
    ranked_text = [json.dumps(event, sort_keys=True).lower() for event in events if isinstance(event, dict)]
    ranks = [
        index
        for item in evidence
        for index, text in enumerate(ranked_text, start=1)
        if item.lower() in text
        for _ in [None]
    ]
    found = sum(1 for item in evidence if any(item.lower() in text for text in ranked_text))
    return {
        "required_evidence_total": len(evidence),
        "required_evidence_found": found,
        "required_evidence_recall": found / len(evidence) if evidence else None,
        "first_required_evidence_rank": min(ranks) if ranks else None,
    }


def trajectory_tool_output_metrics(task: Any, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [item.lower() for item in dict.fromkeys([*task.expected_symbols, *task.expected_project_docs])]
    total_chars = 0
    docs_chars = 0
    evidence_found: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        summary = str(call.get("result_summary") or "")
        result_chars = call.get("result_chars")
        chars = result_chars if isinstance(result_chars, int) and result_chars >= 0 else len(summary)
        total_chars += chars
        tool_name = str(call.get("tool_name") or "").lower()
        is_docs_context = any(marker in tool_name for marker in ("get_docs_context", "prepare_docs", "docs_status", "docmancer", "doc-atlas"))
        if is_docs_context:
            docs_chars += chars
            summary_lower = summary.lower()
            evidence_found.update(marker for marker in evidence if marker in summary_lower)
    return {
        "tool_output_chars": total_chars,
        "tool_output_tokens_estimate": _estimate_tokens_from_chars(total_chars),
        "docs_context_output_chars": docs_chars,
        "docs_output_evidence_total": len(evidence),
        "docs_output_evidence_found": len(evidence_found),
        "docs_output_evidence_coverage": len(evidence_found) / len(evidence) if evidence else None,
        "useful_context_ratio": None,
        "useful_context_ratio_method": "not_measured_without_chunk_usage_attribution",
    }


def _estimate_tokens_from_chars(chars: int) -> int:
    return max(1, (chars + 3) // 4) if chars else 0


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


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
        "inject_patch_constraints": policy.inject_patch_constraints,
        "inject_external_context": policy.inject_external_context,
        "max_constraint_packet_tokens": policy.max_constraint_packet_tokens,
        "max_constraints": policy.max_constraints,
        "max_sources": policy.max_sources,
        "recommend_docatlas_before_edit": policy.recommend_docatlas_before_edit,
        "require_docatlas_call_before_edit": policy.require_docatlas_call_before_edit,
        "network_enforcement": "policy_and_trajectory_audit",
    }, indent=2, sort_keys=True), encoding="utf-8")

    mcp_path = output_dir / "mcp_config.json"
    if condition_id in {"repo_only", "repo_only_strict_offline", "repo_only_web_audited", "repo_plus_audited_external_context"}:
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
    status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--no-ext-diff"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    changed = subprocess.run(["git", "diff", "HEAD", "--name-only"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    patch_path = output_dir / "patch.diff"
    status_path = output_dir / "git_status.txt"
    changed_path = output_dir / "changed_files.json"
    files = [line for line in changed.stdout.splitlines() if line]
    untracked_files = [line for line in untracked.stdout.splitlines() if line and not is_runtime_artifact(line)]
    files.extend(untracked_files)
    untracked_diff = ""
    for path in untracked_files:
        completed = subprocess.run(
            ["git", "diff", "--binary", "--no-index", "--", "/dev/null", path],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"Could not capture untracked file {path}: {completed.stderr.strip()}")
        untracked_diff += completed.stdout
    hygiene = write_patch_hygiene_artifacts(
        output_dir,
        raw_status=status.stdout,
        raw_changed_files=files,
        raw_patch_diff=diff.stdout + untracked_diff,
    )
    return patch_path, status_path, changed_path, hygiene.filtered_changed_files


def evaluate_agent_patch(task: TaskSpec, workspace: Path, run_output_dir: Path, condition_id: str, trajectory_path: str | None, runner_output: Any) -> dict[str, Any]:
    patch_path, _, _, changed_files = capture_patch(workspace, run_output_dir)
    patch_exists = bool(patch_path.read_text(encoding="utf-8").strip())
    setup = _run_setup(task, workspace) if patch_exists and task.setup_command else None
    public = run_command(task.test_command, workspace, 180) if patch_exists and (setup is None or setup.returncode == 0) else None
    hidden = None
    if patch_exists:
        copy_hidden_tests(task.task_id, workspace)
        hidden = run_command("python -m pytest tests/hidden", workspace, 180)
    task_evaluation_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    if task_evaluation_contract is not None:
        contract_validation = validate_task_evaluation_contract(task, task_evaluation_contract)
        compile_gate = (
            run_compile_gate(task_evaluation_contract, workspace)
            if patch_exists and (setup is None or setup.returncode == 0) and contract_validation.valid
            else {
                "status": "not_run",
                "passed": False,
                "command": task_evaluation_contract.compile_gate.command,
                "reason": "evaluation_contract_invalid_or_setup_failed",
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        )
        patch_surface = evaluate_patch_surface(task_evaluation_contract, changed_files) if patch_exists else {
            "status": "not_run",
            "violations": [],
        }
        evaluation_contract_status = contract_validation.status
        evaluation_contract_errors = list(contract_validation.errors)
    else:
        legacy_compile = run_command("python -m compileall -q src", workspace, 120) if patch_exists and (setup is None or setup.returncode == 0) else None
        compile_gate = {
            "status": "passed" if legacy_compile and legacy_compile.passed else "failed" if legacy_compile else "not_run",
            "passed": bool(legacy_compile and legacy_compile.passed),
            "command": "python -m compileall -q src",
            "reason": "legacy_unfrozen_contract",
            "returncode": legacy_compile.returncode if legacy_compile else None,
            "stdout": legacy_compile.stdout if legacy_compile else "",
            "stderr": legacy_compile.stderr if legacy_compile else "",
        }
        patch_surface = {"status": "legacy", "violations": []}
        evaluation_contract_status = "legacy_unfrozen"
        evaluation_contract_errors = []
    generic_forbidden = forbidden_changed_paths(changed_files, ALLOWED_PATCH_PREFIXES) if patch_exists else []
    forbidden = sorted(set(generic_forbidden + list(patch_surface.get("violations", []))))
    audit = audit_trajectory(condition_id, Path(trajectory_path) if trajectory_path else None, run_output_dir / "policy_audit.json")
    stats = diff_stats_from_patch(patch_path.read_text(encoding="utf-8", errors="replace")) if patch_exists else None
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
    patch_packet = load_patch_constraint_packet(run_output_dir / "patch_constraints.json")
    patch_constraint_usage = evaluate_patch_constraint_usage(
        patch_packet,
        patch_path,
        Path(trajectory_path) if trajectory_path else None,
    )
    constraint_validation = validate_patch_against_constraints(
        packet=patch_packet,
        changed_files=changed_files,
        diff_text=patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else "",
        checks_run=[task.test_command] if public else [],
    ) if patch_packet else {"constraint_validation": {"total_constraints": 0, "satisfied": 0, "violated": 0, "unknown": 0, "violations": []}}
    (run_output_dir / "validation.json").write_text(json.dumps(constraint_validation, indent=2, sort_keys=True), encoding="utf-8")
    public_passed = bool(public and public.passed)
    hidden_passed = bool(hidden and hidden.passed)
    compile_success = (
        None if compile_gate["status"] == "not_applicable" else bool(compile_gate["passed"])
    )
    evaluation_contract_valid = evaluation_contract_status in {"valid", "legacy_unfrozen"}
    resolved = (
        patch_exists
        and public_passed
        and hidden_passed
        and bool(compile_gate["passed"])
        and evaluation_contract_valid
        and audit.clean
        and not forbidden
    )
    status = "completed" if resolved or patch_exists else "no_patch"
    if not audit.clean:
        status = "policy_violation"
    injection = _load_optional_json(run_output_dir / "docatlas_context_injection.json")
    checklist_injection = _load_optional_json(run_output_dir / "action_checklist_injection.json")
    constraints_injection = _load_optional_json(run_output_dir / "patch_constraints_injection.json")
    external_injection = _load_optional_json(run_output_dir / "audited_external_context.json")
    docatlas_preparation = _load_optional_json(run_output_dir / "docatlas_preparation.json")
    trajectory = Path(trajectory_path) if trajectory_path else run_output_dir / "missing-trajectory.json"
    evidence_metrics = trajectory_evidence_metrics(task, trajectory)
    tool_calls = getattr(runner_output, "tool_calls", [])
    tool_output_metrics = trajectory_tool_output_metrics(task, tool_calls)
    input_tokens = getattr(runner_output, "input_tokens", None)
    output_tokens = getattr(runner_output, "output_tokens", None)
    provider_usage = getattr(runner_output, "token_usage", {})
    provider_usage = provider_usage if isinstance(provider_usage, dict) else {}
    cached_input_tokens = _optional_int(provider_usage.get("cached_input_tokens"))
    reasoning_tokens = _optional_int(provider_usage.get("reasoning_tokens"))
    agent_turns = _optional_int(provider_usage.get("agent_turns"))
    uncached_input_tokens = (
        input_tokens - cached_input_tokens
        if isinstance(input_tokens, int)
        and isinstance(cached_input_tokens, int)
        and 0 <= cached_input_tokens <= input_tokens
        else None
    )
    total_tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    budget = {
        "max_input_tokens": task.max_input_tokens,
        "max_output_tokens": task.max_output_tokens,
        "max_turns": task.max_turns,
        "input_tokens_exceeded": isinstance(input_tokens, int) and input_tokens > task.max_input_tokens,
        "output_tokens_exceeded": isinstance(output_tokens, int) and output_tokens > task.max_output_tokens,
        "max_turns_enforced_by_runner": False,
        "attempt_control": "one_ephemeral_process_with_timeout",
    }
    setup_wall_time = sum(
        float(payload.get("wall_time_seconds", 0.0))
        for payload in (external_injection, docatlas_preparation, injection, checklist_injection, constraints_injection)
        if isinstance(payload.get("wall_time_seconds"), (int, float))
    )
    metrics = RunMetrics(
        wall_time_seconds=getattr(runner_output, "wall_time_seconds", None),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        uncached_input_tokens=uncached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        agent_turns=agent_turns,
        shell_calls=sum(1 for call in tool_calls if "bash" in json.dumps(call).lower()),
        edit_calls=sum(1 for call in tool_calls if "edit" in json.dumps(call).lower()),
        test_runs=sum(1 for call in tool_calls if "pytest" in json.dumps(call).lower()),
        docs_tool_calls=audit.docatlas_calls,
        patch_files_changed=stats[0] if stats else 0,
        patch_lines_added=stats[1] if stats else 0,
        patch_lines_removed=stats[2] if stats else 0,
        context_chunks_returned=int(injection.get("sources", 0)) if isinstance(injection, dict) else 0,
        injected_context_tokens=int(injection.get("injected_context_tokens")) if isinstance(injection.get("injected_context_tokens"), int) else None,
        retrieved_context_tokens=int(injection.get("retrieved_context_tokens")) if isinstance(injection.get("retrieved_context_tokens"), int) else None,
        raw_doc_context_tokens=int(injection.get("raw_doc_context_tokens")) if isinstance(injection.get("raw_doc_context_tokens"), int) else None,
        checklist_tokens=int(checklist_injection.get("checklist_tokens")) if isinstance(checklist_injection.get("checklist_tokens"), int) else None,
        constraint_packet_tokens=_optional_int(constraints_injection.get("constraint_packet_tokens")),
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
        "compile_status": compile_gate["status"],
        "evaluation_contract": {
            "status": evaluation_contract_status,
            "errors": evaluation_contract_errors,
            "patch_contract_id": task_evaluation_contract.patch_contract_id if task_evaluation_contract else None,
            "contract_sha256": evaluation_contract_sha256(task_evaluation_contract) if task_evaluation_contract else None,
            "registry_sha256": evaluation_contract_registry_sha256() if task_evaluation_contract else None,
            "compile_gate": compile_gate,
            "patch_surface": patch_surface,
            "semantic_checks": list(task_evaluation_contract.semantic_checks) if task_evaluation_contract else [],
        },
        "policy_clean": audit.clean,
        "policy": audit.to_json(),
        "docatlas": utilization.to_json(),
        "contract": contract.to_json(),
        "actionability": actionability.to_json(),
        "patch_constraints": patch_constraint_usage,
        "constraint_validation": constraint_validation["constraint_validation"],
        "constraint_packet_tokens": patch_constraint_usage.get("constraint_packet_tokens"),
        "constraint_count": patch_constraint_usage.get("constraint_count", 0),
        "constraint_used": patch_constraint_usage.get("constraint_used", False),
        "constraint_violations_after_patch": constraint_validation["constraint_validation"]["violated"],
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
            "total_tokens": total_tokens,
            "cached_input_tokens": metrics.cached_input_tokens,
            "uncached_input_tokens": metrics.uncached_input_tokens,
            "reasoning_tokens": metrics.reasoning_tokens,
            **tool_output_metrics,
            "condition_setup_wall_time_seconds": setup_wall_time,
            "audited_external_context_tokens": _optional_int(external_injection.get("injected_context_tokens")),
            "turns": metrics.agent_turns,
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
            **evidence_metrics,
        },
        "context": {
            "retrieved_count": int(utilization.context_retrieved) + audit.docatlas_calls,
            "used_count": int(utilization.context_used),
            "utilization_rate": 1.0 if utilization.context_used else 0.0 if utilization.context_retrieved or audit.docatlas_calls else None,
        },
        "notes": getattr(runner_output, "notes", []),
        "budget": budget,
        "token_attribution": {
            "schema_version": "task33-token-attribution-1",
            "parent": {
                "input_tokens": metrics.input_tokens,
                "cached_input_tokens": metrics.cached_input_tokens,
                "uncached_input_tokens": metrics.uncached_input_tokens,
                "output_tokens": metrics.output_tokens,
                "reasoning_tokens": metrics.reasoning_tokens,
                "total_tokens": total_tokens,
            },
            "worker": {
                "status": "not_applicable",
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "total_tokens": None,
            },
            "raw_tool_output_tokens_estimate": tool_output_metrics.get("tool_output_tokens_estimate"),
            "action_packet_tokens": None,
            "system_total_tokens": total_tokens,
            "provider_fields_available": sorted(
                key for key in ("cached_input_tokens", "reasoning_tokens", "agent_turns")
                if provider_usage.get(key) is not None
            ),
        },
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


def _archive_run_attempt(run_output_dir: Path) -> None:
    existing = [path for path in run_output_dir.iterdir() if path.name != "attempts"]
    if not existing:
        return
    attempts_dir = run_output_dir / "attempts"
    attempt_dir = attempts_dir / f"attempt_{len(list(attempts_dir.glob('attempt_*'))) + 1}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    for path in existing:
        shutil.move(str(path), str(attempt_dir / path.name))


def _load_run_results(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def execute_pilot(
    tasks: list[TaskSpec],
    conditions: list[str],
    repeats: int,
    run_id: str,
    runner: AgentRunner,
    model: str,
    timeout_seconds: int,
    prompt_template: str,
    *,
    retry_infrastructure_failures: bool = False,
) -> list[dict[str, Any]]:
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_path = run_dir / "runs.jsonl"
    if retry_infrastructure_failures and not runs_path.exists():
        raise FileNotFoundError(f"Cannot retry without existing run results: {runs_path}")
    results = _load_run_results(runs_path) if retry_infrastructure_failures else []
    result_indexes = {
        (result.get("task_id"), result.get("condition_id"), result.get("repeat")): index
        for index, result in enumerate(results)
    }
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
                    cell = (task.task_id, condition_id, repeat)
                    existing_index = result_indexes.get(cell)
                    if existing_index is not None and not is_infrastructure_failure(results[existing_index]):
                        continue
                    if existing_index is not None:
                        _archive_run_attempt(run_output_dir)
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
                    if CONDITIONS[condition_id].tool_policy.inject_external_context:
                        external = inject_audited_external_context(task, run_output_dir)
                        if external.get("status") == "condition_setup_failed":
                            setup_failed = True
                        else:
                            prompt += "\n" + (run_output_dir / "audited_external_context.md").read_text(encoding="utf-8") + "\n"
                    if CONDITIONS[condition_id].tool_policy.inject_docatlas_context or CONDITIONS[condition_id].tool_policy.inject_action_checklist or CONDITIONS[condition_id].tool_policy.inject_patch_constraints:
                        injected = inject_docatlas_context(task, workspace, run_output_dir, env)
                        if injected.get("status") == "condition_setup_failed":
                            setup_failed = True
                        else:
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist:
                                checklist = inject_action_checklist(task, workspace, run_output_dir)
                                if checklist.get("status") == "condition_setup_failed":
                                    setup_failed = True
                            if CONDITIONS[condition_id].tool_policy.inject_patch_constraints:
                                constraints = inject_patch_constraints(task, workspace, run_output_dir)
                                if constraints.get("status") == "condition_setup_failed":
                                    setup_failed = True
                            if CONDITIONS[condition_id].tool_policy.inject_docatlas_context:
                                prompt += "\n" + (run_output_dir / "injected_context.md").read_text(encoding="utf-8") + "\n"
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist and (run_output_dir / "action_checklist.md").exists():
                                prompt += "\n" + (run_output_dir / "action_checklist.md").read_text(encoding="utf-8") + "\n"
                            if CONDITIONS[condition_id].tool_policy.inject_patch_constraints and (run_output_dir / "patch_constraints.md").exists():
                                prompt += "\n" + (run_output_dir / "patch_constraints.md").read_text(encoding="utf-8") + "\n"
                    if condition_id == "docatlas_patch_constraints_workflow":
                        prompt += "\nDocAtlas patch-constraints workflow guidance: before editing, use the available DocAtlas/docmancer docs tool to compile task-specific project constraints, including generated files, lockfiles, source-of-truth layers, architecture rules, dependency versions, and suggested checks. After editing, inspect your changed files and patch against those constraints; perform one repair pass if you find deterministic violations. Do not use hidden tests, gold patches, or oracle files.\n"
                    elif CONDITIONS[condition_id].tool_policy.recommend_docatlas_before_edit:
                        prompt += "\nDocAtlas workflow guidance: Use DocAtlas/docmancer documentation context before making code changes when the task may depend on library APIs, exact dependency versions, or project docs. Ask a task-specific documentation question, then use or ignore the returned context based on relevance.\n"
                    if CONDITIONS[condition_id].tool_policy.require_docatlas_call_before_edit:
                        prompt += "\nDiagnostic policy: Before your first code edit, call the available documentation-context tool once with a task-specific question. Use or ignore the returned context based on relevance.\n"
                    if setup_failed:
                        result = condition_setup_failed_result(task, condition_id, run_output_dir)
                        if existing_index is None:
                            result_indexes[cell] = len(results)
                            results.append(result)
                        else:
                            results[existing_index] = result
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
                    try:
                        output = runner.run(request)
                    except Exception as exc:
                        result = runner_unavailable_result(
                            task,
                            condition_id,
                            run_output_dir,
                            exc,
                            runner_id=getattr(runner, "runner_id", "unknown"),
                            model=model,
                        )
                    else:
                        result = evaluate_agent_patch(task, workspace, run_output_dir, condition_id, output.trajectory_path, output)
                    if existing_index is None:
                        result_indexes[cell] = len(results)
                        results.append(result)
                    else:
                        results[existing_index] = result
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
    infrastructure_failed_runs = sum(is_infrastructure_failure(result) for result in results)
    payload = {
        "status": status,
        "completed_runs": completed,
        "total_runs": total_runs,
        "remaining_runs": max(total_runs - completed, 0),
        "current": current,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_integrity": integrity,
        "runtime_integrity": {
            "ok": integrity["ok"] and infrastructure_failed_runs == 0,
            "valid_runs": completed - infrastructure_failed_runs,
            "infrastructure_failed_runs": infrastructure_failed_runs,
        },
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


def inject_audited_external_context(
    task: TaskSpec,
    output_dir: Path,
    *,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = snapshot_path or AUDITED_EXTERNAL_CONTEXT_ROOT / f"{task.task_id}.json"
    snapshot = _load_optional_json(source_path)
    content = snapshot.get("content") if isinstance(snapshot.get("content"), str) else ""
    actual_hash = hashlib.sha256(content.encode()).hexdigest()
    errors: list[str] = []
    if snapshot.get("schema_version") != "audited-external-context-1":
        errors.append("unsupported_schema_version")
    if snapshot.get("task_id") != task.task_id:
        errors.append("task_id_mismatch")
    if not content:
        errors.append("empty_content")
    if snapshot.get("content_sha256") != actual_hash:
        errors.append("content_hash_mismatch")
    if any(not snapshot.get(field) for field in ("library", "version", "source_url", "retrieved_at")):
        errors.append("missing_provenance")
    if errors:
        payload = {
            "status": "condition_setup_failed",
            "errors": errors,
            "snapshot_path": str(source_path),
            "wall_time_seconds": time.monotonic() - started,
        }
        _write_json_atomic(output_dir / "audited_external_context.json", payload)
        return payload

    markdown = (
        "# Audited external dependency context\n\n"
        f"Library: {snapshot['library']} {snapshot['version']}\n"
        f"Source: {snapshot['source_url']}\n"
        f"Snapshot SHA-256: {actual_hash}\n\n"
        f"{content}\n"
    )
    if len(markdown) > CONTEXT_INJECTION_LIMIT_CHARS:
        markdown = markdown[:CONTEXT_INJECTION_LIMIT_CHARS] + "\n\n[truncated by benchmark harness]\n"
    (output_dir / "audited_external_context.md").write_text(markdown, encoding="utf-8")
    payload = {
        "status": "success",
        "task_id": task.task_id,
        "library": snapshot["library"],
        "version": snapshot["version"],
        "source_url": snapshot["source_url"],
        "retrieved_at": snapshot["retrieved_at"],
        "content_sha256": actual_hash,
        "injected_context_tokens": _estimate_tokens(markdown),
        "wall_time_seconds": time.monotonic() - started,
    }
    _write_json_atomic(output_dir / "audited_external_context.json", payload)
    return payload


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


def inject_patch_constraints(task: TaskSpec, workspace: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    response_path = output_dir / "docatlas_response.json"
    policy = CONDITIONS["docatlas_patch_constraints_workflow"].tool_policy
    try:
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else {}
        packet = build_patch_constraint_packet(
            task=task,
            workspace=workspace,
            docatlas_response=response,
            max_constraints=policy.max_constraints,
            max_sources=policy.max_sources,
            max_tokens=policy.max_constraint_packet_tokens,
        )
        save_patch_constraint_packet(packet, output_dir)
        # Stable artifact names for the targeted patch-constraints workflow.
        (output_dir / "constraints.json").write_text((output_dir / "patch_constraints.json").read_text(encoding="utf-8"), encoding="utf-8")
        (output_dir / "constraints.md").write_text((output_dir / "patch_constraints.md").read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as exc:
        payload = {"status": "condition_setup_failed", "error": repr(exc), "wall_time_seconds": round(time.monotonic() - started, 4)}
        (output_dir / "patch_constraints_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    payload = {
        "status": "success",
        "constraint_count": len(packet.constraints),
        "constraint_packet_tokens": packet.token_estimate,
        "wall_time_seconds": round(time.monotonic() - started, 4),
    }
    (output_dir / "patch_constraints_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
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
    raw_sources = trust.get("sources")
    trust_sources: dict[str, Any] = raw_sources if isinstance(raw_sources, dict) else {}
    selected = trust_sources.get("selected") or trust.get("selected") or trust.get("selected_sources") or []
    risky = trust_sources.get("risky") or trust.get("risky") or []
    rejected = trust_sources.get("rejected") or trust.get("rejected") or []
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
    raw_sources = trust.get("sources")
    trust_sources: dict[str, Any] = raw_sources if isinstance(raw_sources, dict) else {}
    candidates = trust_sources.get("selected") or trust.get("selected") or trust.get("selected_sources") or response.get("sources") or []
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




def runner_unavailable_result(task: TaskSpec, condition_id: str, run_output_dir: Path, exc: Exception, *, runner_id: str, model: str) -> dict[str, Any]:
    (run_output_dir / "patch.diff").write_text("", encoding="utf-8")
    (run_output_dir / "changed_files.json").write_text("[]\n", encoding="utf-8")
    validation = {"constraint_validation": {"total_constraints": 0, "satisfied": 0, "violated": 0, "unknown": 0, "violations": []}}
    (run_output_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    error_payload = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback_tail": traceback.format_exc().splitlines()[-8:],
    }
    (run_output_dir / "runner_error.json").write_text(json.dumps(error_payload, indent=2, sort_keys=True), encoding="utf-8")
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": runner_id,
        "runner_version": "unavailable",
        "model": model,
        "status": "runner_unavailable",
        "resolved": False,
        "public_tests_passed": False,
        "hidden_tests_passed": False,
        "tests_passed": False,
        "compile_success": False,
        "policy_clean": True,
        "policy": {"clean": True, "violations": [], "network_attempts": 0, "runner_unavailable": True},
        "docatlas": {"available": condition_id in DOCATLAS_CONDITIONS, "harness_calls": 0, "agent_calls": 0, "context_retrieved": False, "context_injected": False, "context_used": False, "fallback_used": False},
        "contract": {},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
        "patch_constraints": {"constraint_count": 0, "constraint_used": False, "constraint_packet_tokens": None},
        "constraint_validation": validation["constraint_validation"],
        "constraint_packet_tokens": None,
        "constraint_count": 0,
        "constraint_used": False,
        "constraint_violations_after_patch": 0,
        "unknown_count": 0,
        "patch_path": str(run_output_dir / "patch.diff"),
        "trajectory_path": None,
        "changed_files": [],
        "forbidden_changes": [],
        "metrics": {"wall_time_seconds": 0.0, "input_tokens": None, "output_tokens": None, "fallback_used": False},
        "notes": [f"Runner unavailable before patch generation: {exc.__class__.__name__}: {exc}"],
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result

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
            prompt="Fix add(a, b), which currently subtracts. Run the tests. Do not use web, curl, wget, or external network.",
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
        tests = run_command("python -m pytest test_calc.py", workspace, 60)
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
