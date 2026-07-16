from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.conditions import CONDITIONS, TOOL_REQUIRED_ONCE_INSTRUCTION
from eval.task_level.artifact_hygiene import diff_stats_from_patch, is_runtime_artifact, write_patch_hygiene_artifacts
from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.context.patch_constraints import build_patch_constraint_packet, save_patch_constraint_packet
from docmancer.docs.interfaces.mcp.context_tools import bounded_retrieval_issues
from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.constraint_validation import validate_patch_against_constraints
from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.evaluators.patch import forbidden_changed_paths
from eval.task_level.evaluators.patch_constraints import evaluate_patch_constraint_usage, load_patch_constraint_packet
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.evaluators.task_contract import ContractValidation, evaluate_patch_surface, evaluation_contract_registry_sha256, evaluation_contract_sha256, load_effective_task23_protocol_tasks, load_task_evaluation_contracts, run_compile_gate, validate_task_evaluation_artifacts, validate_task_evaluation_contract
from eval.task_level.evaluators.tests import CommandResult, run_command
from eval.task_level.fixtures.builder import copy_hidden_tests, materialize_fixture
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorker,
    TASK33_QUERY_DERIVATION,
    derive_task33_retrieval_query,
    deliver_with_exploratory_worker,
    deliver_with_isolated_worker,
    missing_packet_evidence_categories,
    missing_packet_evidence_paths,
    persist_host_evidence,
)
from eval.task_level.runners.base import AgentRunRequest, AgentRunner, RunnerCapabilities
from eval.task_level.sandbox_execution import (
    configured_runtime_root,
    persist_boundary,
    verified_task33_sandbox,
)
from eval.task_level.schemas import RESULTS_ROOT, TASK_LEVEL_ROOT, RunMetrics, TaskSpec
from eval.task_level.task33_pilot import (
    TASK33C_AGENT_TURN_LIMIT,
    TASK33C_PILOT_CONDITIONS,
    TASK33C_PILOT_TASK_ID,
    TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    TASK33C_REQUIRED_EVIDENCE_PATHS,
    TASK33C_REQUIRED_TARGET_PATHS,
    build_task33c_validation_evidence,
)


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
    "docatlas_bounded_direct",
    "docatlas_bounded_subagent",
}
CONTEXT_INJECTION_LIMIT_CHARS = 10000
AUDITED_EXTERNAL_CONTEXT_ROOT = TASK_LEVEL_ROOT / "external_context"
TASK33_EVALUATION_CONTRACTS = load_task_evaluation_contracts()
TASK23_PROTOCOL_TASKS = load_effective_task23_protocol_tasks()


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


_SHELL_TOOL_NAMES = frozenset({"bash", "shell", "command", "command_execution"})
_SUCCESS_STATUSES = frozenset({"completed", "success", "succeeded", "ok"})
_FAILURE_STATUSES = frozenset({"failed", "failure", "error", "cancelled", "canceled", "timeout", "timed_out"})


def _shell_command(call: dict[str, Any]) -> str | None:
    tool_name = str(
        call.get("tool_name") or call.get("name") or call.get("tool") or ""
    ).strip().lower()
    if tool_name not in _SHELL_TOOL_NAMES and not tool_name.startswith("bash."):
        return None
    arguments = call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = call.get("input") if isinstance(call.get("input"), dict) else {}
    command = arguments.get("command") or arguments.get("cmd") or arguments.get("script")
    if isinstance(command, list):
        command = " ".join(str(item) for item in command)
    return str(command).strip() if command not in (None, "") else ""


def _shell_outcome(call: dict[str, Any]) -> bool | None:
    exit_code = call.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return exit_code == 0
    is_error = call.get("is_error")
    if isinstance(is_error, bool):
        return not is_error
    status = str(call.get("execution_status") or call.get("status") or "").strip().lower()
    if status in _SUCCESS_STATUSES:
        return True
    if status in _FAILURE_STATUSES:
        return False
    return None


def _shell_exec_error(call: dict[str, Any]) -> bool:
    """Distinguish runner/spawn failure from a command that executed and exited non-zero."""

    exit_code = call.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return False
    status = str(call.get("execution_status") or call.get("status") or "").strip().lower()
    if status in {"runner_failed", "spawn_failed", "exec_error", "transport_error"}:
        return True
    return call.get("is_error") is True and exit_code is None


def _unwrap_shell_command(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return re.sub(r"\s+", " ", command).strip()
    if not tokens:
        return ""
    executable = Path(tokens[0]).name.lower()
    if executable in {"bash", "sh", "zsh"}:
        for index, token in enumerate(tokens[1:], start=1):
            if token in {"-c", "-lc", "-cl"} and index + 1 < len(tokens):
                return re.sub(r"\s+", " ", tokens[index + 1]).strip()
    return re.sub(r"\s+", " ", command).strip()


def _command_fingerprint(command: str) -> str:
    normalized = _unwrap_shell_command(command)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _test_runner_for_segment(segment: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return None
    while tokens and "=" in tokens[0] and not tokens[0].startswith(("/", "./")):
        tokens.pop(0)
    if not tokens:
        return None
    executable = Path(tokens[0]).name.lower()
    rest = [token.lower() for token in tokens[1:]]
    if executable in {"pytest", "py.test"}:
        return "pytest"
    if executable in {"python", "python3", "pypy", "pypy3"}:
        if len(rest) >= 2 and rest[0] == "-m" and rest[1] in {"pytest", "unittest"}:
            return rest[1]
        return None
    if executable == "uv" and "run" in rest:
        run_index = rest.index("run") + 1
        nested = tokens[run_index + 1 :]
        while nested and nested[0].startswith("-"):
            nested.pop(0)
        return _test_runner_for_segment(shlex.join(nested)) if nested else None
    if executable in {"flutter", "dart", "cargo", "go", "npm", "pnpm", "yarn", "dotnet", "mvn", "swift"}:
        return executable if rest and rest[0] == "test" else None
    if executable in {"gradle", "gradlew"} or executable.endswith("gradlew"):
        return "gradle" if any(token == "test" or token.endswith(":test") for token in rest) else None
    return None


def _test_runner(command: str) -> str | None:
    unwrapped = _unwrap_shell_command(command)
    for segment in re.split(r"\s*(?:&&|\|\||;)\s*", unwrapped):
        runner = _test_runner_for_segment(segment)
        if runner:
            return runner
    return None


def shell_call_metrics(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    """Normalize shell/test outcomes without assuming one runner event shape."""

    shell_calls = 0
    successful = 0
    failed = 0
    unknown = 0
    retries = 0
    test_runs = 0
    pytest_invocations = 0
    exec_errors = 0
    failed_fingerprints: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        command = _shell_command(call)
        if command is None:
            continue
        shell_calls += 1
        fingerprint = _command_fingerprint(command) if command else None
        if fingerprint is not None and fingerprint in failed_fingerprints:
            retries += 1
        outcome = _shell_outcome(call)
        if _shell_exec_error(call):
            exec_errors += 1
        if outcome is True:
            successful += 1
        elif outcome is False:
            failed += 1
            if fingerprint is not None:
                failed_fingerprints.add(fingerprint)
        else:
            unknown += 1
        runner = _test_runner(command)
        if runner:
            test_runs += 1
            if runner == "pytest":
                pytest_invocations += 1
    return {
        "shell_calls": shell_calls,
        "successful_shell_calls": successful,
        "failed_shell_calls": failed,
        "unknown_shell_outcomes": unknown,
        "exec_error_count": exec_errors,
        "retried_command_count": retries,
        "test_runs": test_runs,
        "pytest_invocations": pytest_invocations,
    }


def action_packet_project_doc_metrics(task: Any, packet: dict[str, Any]) -> dict[str, Any]:
    expected = {
        str(path).strip().replace("\\", "/").lower()
        for path in getattr(task, "expected_project_docs", ())
        if str(path).strip()
    }
    rows = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    packet_paths = {
        str(row.get("path") or "").strip().replace("\\", "/").lower()
        for row in rows
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    found = expected & packet_paths
    target = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    target_paths = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in target.get("likely_files", [])
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    return {
        "action_packet_project_docs_total": len(expected),
        "action_packet_project_docs_found": len(found),
        "action_packet_project_doc_coverage": len(found) / len(expected) if expected else None,
        "action_packet_project_doc_paths": sorted(found),
        "action_packet_target_paths": sorted(target_paths),
    }


def _persist_delivery_prompt_sources(output_dir: Path, packet: dict[str, Any]) -> None:
    rows = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    sources = [
        {
            "evidence_id": row.get("evidence_id"),
            "path": row.get("path"),
        }
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str) and row["path"]
    ]
    _write_json_atomic(output_dir / "delivery_prompt_sources.json", sources)


def _estimate_tokens_from_chars(chars: int) -> int:
    return max(1, (chars + 3) // 4) if chars else 0


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first_optional_int(*values: Any) -> int | None:
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            return parsed
    return None


def _directory_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _trajectory_elapsed_seconds(
    trajectory_path: Path,
    started_at: str | None,
    *,
    event_kind: str,
) -> float | None:
    if not started_at or not trajectory_path.exists():
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        events = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict) or not _trajectory_event_matches(event, event_kind):
            continue
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str):
            continue
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        return round(max(0.0, (observed - started).total_seconds()), 6)
    return None


def _trajectory_event_matches(event: dict[str, Any], event_kind: str) -> bool:
    if str(event.get("event_type") or "").lower() != "tool_call":
        return False
    tool_name = str(event.get("tool_name") or "").lower()
    arguments = json.dumps(event.get("arguments") or {}, sort_keys=True).lower()
    if event_kind == "edit":
        return any(token in tool_name for token in ("edit", "write", "apply_patch")) or '"changes"' in arguments
    if event_kind == "test":
        return '"executed": true' in arguments and any(token in arguments for token in (
            "pytest", "unittest", "npm test", "cargo test", "go test", "dart test", "flutter test",
        ))
    return False


def _task_contract_validation(
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


def _write_json_atomic(path: Path, payload: Any) -> None:
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


def build_tool_policy(condition_id: str, output_dir: Path) -> tuple[Path, Path]:
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
        "delivery_strategy": policy.delivery_strategy,
        "isolated_worker_required": policy.isolated_worker_required,
        "network_enforcement": "policy_and_trajectory_audit",
    }, indent=2, sort_keys=True), encoding="utf-8")

    mcp_path = output_dir / "mcp_config.json"
    if condition_id in {"repo_only", "repo_only_strict_offline", "repo_only_web_audited", "repo_plus_audited_external_context"}:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    elif condition_id in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
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
    environment = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "DOCMANCER_HOME": str(docmancer_home),
        "DOCMANCER_AUTO_VECTORS": "0",
        "DOCMANCER_INDEX_DB_PATH": str(docmancer_home / "docmancer.db"),
        "DOCMANCER_EMBEDDINGS_CACHE": str(docmancer_home / "embeddings-cache"),
        # Keep dependency environments outside the repository so setup output
        # cannot appear in the agent patch or repository inventory.
        "UV_PROJECT_ENVIRONMENT": str(env_root / "project_venv"),
    }
    if os.environ.get("UV_CACHE_DIR"):
        environment["UV_CACHE_DIR"] = os.environ["UV_CACHE_DIR"]
    return environment


@contextmanager
def _activated_run_environment(env: dict[str, str]):
    previous = {name: os.environ.get(name) for name in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


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


def evaluate_agent_patch(
    task: TaskSpec,
    workspace: Path,
    run_output_dir: Path,
    condition_id: str,
    trajectory_path: str | None,
    runner_output: Any,
    *,
    evaluation_backend: str = "docker",
) -> dict[str, Any]:
    patch_path, _, _, changed_files = capture_patch(workspace, run_output_dir)
    patch_exists = bool(patch_path.read_text(encoding="utf-8").strip())
    task_evaluation_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    protocol_task = TASK23_PROTOCOL_TASKS.get(task.task_id)
    contract_validation = _task_contract_validation(task, task_evaluation_contract, protocol_task)
    setup_evidence = _load_optional_json(run_output_dir / "condition_setup.json")
    if not setup_evidence:
        # Direct evaluator callers predate the pre-run setup gate. Keep them
        # functional, but mark this fallback so Task 33 completeness cannot
        # mistake a post-run setup for causal precondition evidence.
        setup_evidence = _run_condition_setup(
            task,
            workspace,
            run_output_dir,
            {},
            phase="evaluator_fallback",
        )
    setup_ok = setup_evidence.get("status") in {"success", "not_required"}
    evaluation_errors: list[str] = []
    public = None
    if setup_ok:
        try:
            public = _run_evaluation_command(
                task,
                task.test_command,
                workspace,
                run_output_dir,
                "public",
                180,
                evaluation_backend=evaluation_backend,
            )
        except Exception as exc:
            evaluation_errors.append(f"public:{exc.__class__.__name__}:{str(exc)[:1_000]}")
    _write_json_atomic(run_output_dir / "public_test_result.json", {
        "schema_version": 1,
        "status": "executed" if public is not None else "execution_failed" if evaluation_errors else "not_run",
        "command": public.command if public is not None else task.test_command,
        "returncode": public.returncode if public is not None else None,
        "stdout": public.stdout if public is not None else "",
        "stderr": public.stderr if public is not None else "",
        "errors": list(evaluation_errors),
    })
    hidden = None
    if setup_ok and contract_validation.valid and not evaluation_errors:
        copy_hidden_tests(task.task_id, workspace)
        hidden_command = task_evaluation_contract.semantic_test_command if task_evaluation_contract else "python -m pytest tests/hidden"
        try:
            hidden = _run_evaluation_command(
                task,
                hidden_command,
                workspace,
                run_output_dir,
                "hidden",
                180,
                evaluation_backend=evaluation_backend,
            )
        except Exception as exc:
            evaluation_errors.append(f"hidden:{exc.__class__.__name__}:{str(exc)[:1_000]}")
    _write_json_atomic(run_output_dir / "hidden_test_result.json", {
        "schema_version": 1,
        "status": "executed" if hidden is not None else "execution_failed" if evaluation_errors else "not_run",
        "command": hidden.command if hidden is not None else (
            task_evaluation_contract.semantic_test_command if task_evaluation_contract else None
        ),
        "returncode": hidden.returncode if hidden is not None else None,
        "stdout": hidden.stdout if hidden is not None else "",
        "stderr": hidden.stderr if hidden is not None else "",
        "errors": list(evaluation_errors),
    })
    if task.task_id in TASK23_PROTOCOL_TASKS or task_evaluation_contract is not None:
        compile_gate = (
            _run_compile_gate(
                task,
                task_evaluation_contract,
                workspace,
                run_output_dir,
                evaluation_backend=evaluation_backend,
            )
            if task_evaluation_contract is not None and setup_ok and contract_validation.valid and not evaluation_errors
            else {
                "status": "not_run",
                "passed": False,
                "command": task_evaluation_contract.compile_gate.command if task_evaluation_contract else None,
                "reason": "evaluation_contract_invalid_or_setup_failed",
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        )
        patch_surface = evaluate_patch_surface(task_evaluation_contract, changed_files) if task_evaluation_contract and contract_validation.valid else {
            "status": "not_run",
            "violations": [],
        }
        evaluation_contract_status = contract_validation.status
        evaluation_contract_errors = list(contract_validation.errors)
    else:
        legacy_compile = run_command("python -m compileall -q src", workspace, 120) if patch_exists and setup_ok else None
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
    semantic_gate = {
        "command": task_evaluation_contract.semantic_test_command if task_evaluation_contract else None,
        "status": "passed" if hidden_passed else "failed" if hidden is not None else "not_run",
        "passed": hidden_passed,
        "returncode": hidden.returncode if hidden is not None else None,
        "hidden_tests_sha256": task_evaluation_contract.hidden_tests_sha256 if task_evaluation_contract else None,
        "checks": [
            {
                "id": check.check_id,
                "test_ids": list(check.test_ids),
                "status": "passed" if hidden_passed else "failed" if hidden is not None else "not_run",
            }
            for check in task_evaluation_contract.semantic_checks
        ] if task_evaluation_contract else [],
    }
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
    runner_status = str(getattr(runner_output, "status", "completed") or "completed")
    if not setup_ok:
        status = "condition_setup_failed"
    elif runner_status in INFRASTRUCTURE_FAILURE_STATUSES:
        status = runner_status
    elif runner_status == "completed":
        status = "completed" if resolved or patch_exists else "no_patch"
    else:
        # Budget exhaustion and an explicit non-successful finish are valid
        # agent outcomes. Preserve them rather than relabelling any patch as a
        # successful runner completion.
        status = runner_status
    if not audit.clean:
        status = "policy_violation"
    if evaluation_errors:
        status = "runner_failed"
    injection = _load_optional_json(run_output_dir / "docatlas_context_injection.json")
    checklist_injection = _load_optional_json(run_output_dir / "action_checklist_injection.json")
    constraints_injection = _load_optional_json(run_output_dir / "patch_constraints_injection.json")
    external_injection = _load_optional_json(run_output_dir / "audited_external_context.json")
    docatlas_preparation = _load_optional_json(run_output_dir / "docatlas_preparation.json")
    isolated_delivery = _load_optional_json(run_output_dir / "isolated_delivery_metrics.json")
    bounded_direct = _load_optional_json(run_output_dir / "bounded_direct_metrics.json")
    host_retrieval = _load_optional_json(run_output_dir / "host_retrieval_metrics.json")
    action_packet = _load_optional_json(run_output_dir / "action_packet.json")
    runner_boundary = _load_optional_json(run_output_dir / "runner_execution_boundary.json")
    evaluator_boundary = _load_optional_json(run_output_dir / "evaluator_execution_boundary.json")
    packet_evidence_metrics = action_packet_project_doc_metrics(task, action_packet)
    materialized_identity = _load_optional_json(run_output_dir / "materialized.json")
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
    completed_turn_events = _optional_int(provider_usage.get("completed_turn_events"))
    effective_max_turns = _optional_int(provider_usage.get("effective_max_turns"))
    uncached_input_tokens = (
        input_tokens - cached_input_tokens
        if isinstance(input_tokens, int)
        and isinstance(cached_input_tokens, int)
        and 0 <= cached_input_tokens <= input_tokens
        else None
    )
    total_tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    worker_input_tokens = _optional_int(isolated_delivery.get("worker_input_tokens"))
    worker_output_tokens = _optional_int(isolated_delivery.get("worker_output_tokens"))
    worker_total_tokens = (
        worker_input_tokens + worker_output_tokens
        if worker_input_tokens is not None and worker_output_tokens is not None else None
    )
    system_total_tokens = (
        total_tokens + worker_total_tokens
        if total_tokens is not None and worker_total_tokens is not None
        else total_tokens if not isolated_delivery and total_tokens is not None else None
    )
    time_to_first_edit = _trajectory_elapsed_seconds(
        trajectory, getattr(runner_output, "started_at", None), event_kind="edit"
    )
    time_to_first_test = _trajectory_elapsed_seconds(
        trajectory, getattr(runner_output, "started_at", None), event_kind="test"
    )
    budget = {
        "max_input_tokens": task.max_input_tokens,
        "max_output_tokens": task.max_output_tokens,
        "measured_input_tokens": input_tokens,
        "input_token_basis": (
            "parent_provider_reported_input_including_cached"
            if isinstance(input_tokens, int)
            else None
        ),
        "indexing_provider_tokens_included": False,
        "configured_max_turns": task.max_turns,
        "effective_max_turns": effective_max_turns,
        "max_turns": effective_max_turns,
        "input_tokens_exceeded": isinstance(input_tokens, int) and input_tokens > task.max_input_tokens,
        "output_tokens_exceeded": isinstance(output_tokens, int) and output_tokens > task.max_output_tokens,
        "max_turns_enforced_by_runner": bool(getattr(runner_output, "max_turns_enforced", False)),
        "attempt_control": "one_ephemeral_process_with_timeout",
    }
    setup_wall_time = float(setup_evidence.get("wall_time_seconds") or 0.0) + sum(
        float(payload.get("wall_time_seconds", 0.0))
        for payload in (external_injection, docatlas_preparation, injection, checklist_injection, constraints_injection)
        if isinstance(payload.get("wall_time_seconds"), (int, float))
    )
    setup_wall_time += float(host_retrieval.get("retrieval_wall_time_seconds") or 0.0)
    setup_wall_time += float(isolated_delivery.get("broker_wall_time_seconds") or 0.0)
    total_latency = (
        setup_wall_time + float(getattr(runner_output, "wall_time_seconds", 0.0))
        if isinstance(getattr(runner_output, "wall_time_seconds", None), (int, float))
        else None
    )
    parent_retained_context_tokens = _first_optional_int(
        action_packet.get("estimated_tokens"),
        injection.get("injected_context_tokens"),
        tool_output_metrics.get("tool_output_tokens_estimate"),
    )
    normalized_shell_metrics = shell_call_metrics(tool_calls)
    metrics = RunMetrics(
        wall_time_seconds=getattr(runner_output, "wall_time_seconds", None),
        time_to_first_edit=time_to_first_edit,
        time_to_first_test=time_to_first_test,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        uncached_input_tokens=uncached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_turn_events=completed_turn_events,
        shell_calls=normalized_shell_metrics["shell_calls"],
        successful_shell_calls=normalized_shell_metrics["successful_shell_calls"],
        failed_shell_calls=normalized_shell_metrics["failed_shell_calls"],
        unknown_shell_outcomes=normalized_shell_metrics["unknown_shell_outcomes"],
        exec_error_count=normalized_shell_metrics["exec_error_count"],
        retried_command_count=normalized_shell_metrics["retried_command_count"],
        pytest_invocations=normalized_shell_metrics["pytest_invocations"],
        edit_calls=sum(1 for call in tool_calls if "edit" in json.dumps(call).lower()),
        test_runs=normalized_shell_metrics["test_runs"],
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
        "runner_id": _runner_id_from_version(
            str(getattr(runner_output, "runner_version", ""))
        ),
        "runner_version": getattr(runner_output, "runner_version", "unknown"),
        "model": getattr(runner_output, "model", "unknown"),
        "status": status,
        "resolved": resolved,
        "public_tests_passed": public_passed,
        "hidden_tests_passed": hidden_passed,
        "tests_passed": public_passed,
        "compile_success": compile_success,
        "compile_status": compile_gate["status"],
        "evaluation_execution": {
            "setup": setup_evidence,
            "boundaries": {
                "runner": runner_boundary,
                "evaluator": evaluator_boundary,
            },
            "public_tests": {
                "status": "executed" if public is not None else "execution_failed" if evaluation_errors else "not_run",
                "command": task.test_command,
                "returncode": public.returncode if public is not None else None,
                "errors": evaluation_errors,
            },
            "hidden_tests": {
                "status": "executed" if hidden is not None else "execution_failed" if evaluation_errors else "not_run",
                "command": task_evaluation_contract.semantic_test_command if task_evaluation_contract else None,
                "returncode": hidden.returncode if hidden is not None else None,
                "errors": evaluation_errors,
            },
        },
        "evaluation_contract": {
            "status": evaluation_contract_status,
            "errors": evaluation_contract_errors,
            "patch_contract_id": task_evaluation_contract.patch_contract_id if task_evaluation_contract else None,
            "contract_sha256": evaluation_contract_sha256(task_evaluation_contract) if task_evaluation_contract else None,
            "registry_sha256": evaluation_contract_registry_sha256() if task_evaluation_contract else None,
            "artifact_identity": {
                "fixture_hash_algorithm": materialized_identity.get("fixture_hash_algorithm"),
                "fixture_sha256": materialized_identity.get("fixture_hash"),
                "protocol_fixture_hash_algorithm": materialized_identity.get("protocol_fixture_hash_algorithm"),
                "protocol_fixture_sha256": materialized_identity.get("protocol_fixture_hash"),
                "oracle_sha256": task_evaluation_contract.oracle_sha256 if task_evaluation_contract else None,
                "hidden_tests_sha256": task_evaluation_contract.hidden_tests_sha256 if task_evaluation_contract else None,
                "external_context_sha256": task_evaluation_contract.external_context_sha256 if task_evaluation_contract else None,
            },
            "compile_gate": compile_gate,
            "semantic_gate": semantic_gate,
            "patch_surface": patch_surface,
            "semantic_checks": [check.to_json() for check in task_evaluation_contract.semantic_checks] if task_evaluation_contract else [],
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
            "time_to_first_edit": metrics.time_to_first_edit,
            "made_edit": metrics.time_to_first_edit is not None,
            "time_to_first_test": metrics.time_to_first_test,
            "total_latency": total_latency,
            "parent_retained_context_tokens": parent_retained_context_tokens,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "total_tokens": total_tokens,
            "cached_input_tokens": metrics.cached_input_tokens,
            "uncached_input_tokens": metrics.uncached_input_tokens,
            "reasoning_tokens": metrics.reasoning_tokens,
            **tool_output_metrics,
            "condition_setup_wall_time_seconds": setup_wall_time,
            "audited_external_context_tokens": _optional_int(external_injection.get("injected_context_tokens")),
            "completed_turn_events": metrics.completed_turn_events,
            "shell_calls": metrics.shell_calls,
            "successful_shell_calls": metrics.successful_shell_calls,
            "failed_shell_calls": metrics.failed_shell_calls,
            "unknown_shell_outcomes": metrics.unknown_shell_outcomes,
            "exec_error_count": metrics.exec_error_count,
            "retried_command_count": metrics.retried_command_count,
            "pytest_invocations": metrics.pytest_invocations,
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
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
            "worker_reasoning_tokens": _optional_int(isolated_delivery.get("worker_reasoning_tokens")),
            "worker_total_tokens": worker_total_tokens,
            "system_total_tokens": system_total_tokens,
            "delivery_retrieval_calls": _optional_int(
                (isolated_delivery or bounded_direct).get("retrieval_calls")
            ),
            "delivery_attempts": _optional_int(
                (isolated_delivery or bounded_direct).get("attempts")
            ),
            "action_packet_status": action_packet.get("status"),
            "action_packet_truncated": action_packet.get("status") == "truncated",
            "action_packet_insufficient_evidence": action_packet.get("status") == "insufficient_evidence",
            "action_packet_fidelity": "validated" if action_packet else "not_applicable",
            **packet_evidence_metrics,
            "evidence_fingerprint": (
                isolated_delivery.get("evidence_fingerprint")
                or bounded_direct.get("evidence_fingerprint")
                or host_retrieval.get("evidence_fingerprint")
            ),
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
                "status": (
                    "measured" if isolated_delivery and worker_total_tokens is not None
                    else "partial" if isolated_delivery else "not_applicable"
                ),
                "input_tokens": worker_input_tokens,
                "output_tokens": worker_output_tokens,
                "reasoning_tokens": _optional_int(isolated_delivery.get("worker_reasoning_tokens")),
                "total_tokens": worker_total_tokens,
            },
            "indexing": {
                "status": docatlas_preparation.get("status") or "not_applicable",
                "provider_input_tokens": (
                    _optional_int(docatlas_preparation.get("provider_input_tokens")) or 0
                ),
                "provider_output_tokens": (
                    _optional_int(docatlas_preparation.get("provider_output_tokens")) or 0
                ),
                "included_in_parent_budget": False,
            },
            "raw_tool_output_tokens_estimate": _first_optional_int(
                isolated_delivery.get("raw_retrieval_tokens"),
                bounded_direct.get("raw_retrieval_tokens"),
                tool_output_metrics.get("tool_output_tokens_estimate"),
            ),
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "system_total_tokens": system_total_tokens,
            "system_total_definition": "parent provider total plus worker provider input/output; raw retrieval is reported separately to avoid double counting worker input",
            "system_total_complete": total_tokens is not None and (
                not isolated_delivery or worker_total_tokens is not None
            ),
            "provider_fields_available": sorted(
                key for key in ("cached_input_tokens", "reasoning_tokens", "completed_turn_events")
                if provider_usage.get(key) is not None
            ),
        },
    }
    if not setup_ok:
        result["notes"].append("condition setup was not valid; evaluator tests were not run")
    if evaluation_errors:
        result["notes"].append("evaluator command boundary failed: " + "; ".join(evaluation_errors))
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _run_evaluation_command(
    task: TaskSpec,
    command: str,
    workspace: Path,
    run_output_dir: Path,
    phase: str,
    timeout_seconds: int,
    *,
    evaluation_backend: str = "docker",
) -> CommandResult:
    if evaluation_backend == "host_exploratory":
        persist_boundary(
            run_output_dir / "evaluator_execution_boundary.json",
            {
                "schema_version": 1,
                "status": "exploratory_unisolated",
                "backend": "host",
                "causal_claim_allowed": False,
                "validator_eligible": False,
            },
        )
        return run_command(command, workspace, timeout_seconds)
    if evaluation_backend != "docker":
        raise ValueError("Unknown evaluation backend: " + evaluation_backend)
    if task.task_id not in TASK23_PROTOCOL_TASKS:
        return run_command(command, workspace, timeout_seconds)
    image = os.environ.get("TASK33C_TEST_CONTAINER_IMAGE", "")
    sandbox, boundary = verified_task33_sandbox(image)
    persist_boundary(run_output_dir / "evaluator_execution_boundary.json", boundary)
    if boundary.get("status") != "verified":
        raise RuntimeError(f"Task 33 evaluator sandbox is not verified for {phase}")
    completed = sandbox.run(command, workspace, timeout_seconds)
    return CommandResult(
        command=shlex.join(completed.command),
        returncode=completed.returncode,
        stdout=completed.stdout[-20_000:],
        stderr=completed.stderr[-20_000:],
    )


def _run_compile_gate(
    task: TaskSpec,
    contract: Any,
    workspace: Path,
    run_output_dir: Path,
    *,
    evaluation_backend: str = "docker",
) -> dict[str, Any]:
    gate = contract.compile_gate
    if gate.mode == "not_applicable":
        return run_compile_gate(contract, workspace)
    completed = _run_evaluation_command(
        task,
        gate.command or "",
        workspace,
        run_output_dir,
        "compile",
        120,
        evaluation_backend=evaluation_backend,
    )
    return {
        "status": "passed" if completed.passed else "failed",
        "passed": completed.passed,
        "command": completed.command,
        "reason": None,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_setup(task: TaskSpec, workspace: Path) -> subprocess.CompletedProcess[str]:
    command = task.setup_command
    if task.task_id not in TASK23_PROTOCOL_TASKS and command.startswith("python -m pip "):
        command = "uv pip " + command.removeprefix("python -m pip ") + f" --python {sys.executable}"
    return subprocess.run(command, cwd=workspace, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False)


def _run_condition_setup(
    task: TaskSpec,
    workspace: Path,
    run_output_dir: Path,
    env: dict[str, str],
    *,
    phase: str = "pre_runner",
) -> dict[str, Any]:
    started = time.monotonic()
    command = task.setup_command.strip()
    if not command:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "not_required",
            "command": "",
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "wall_time_seconds": 0.0,
        }
        _write_json_atomic(run_output_dir / "condition_setup.json", payload)
        return payload
    try:
        with _activated_run_environment(env):
            completed = _run_setup(task, workspace)
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "condition_setup_failed",
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": f"{exc.__class__.__name__}: {str(exc)[:2_000]}",
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
    else:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "success" if completed.returncode == 0 else "condition_setup_failed",
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-20_000:],
            "stderr": completed.stderr[-20_000:],
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
        if completed.returncode == 0:
            baseline = _seal_condition_setup_baseline(
                workspace,
                run_output_dir,
                allowed_changed_files=("uv.lock",) if task.task_id in TASK23_PROTOCOL_TASKS else None,
            )
            payload.update(baseline)
            if baseline.get("baseline_status") != "sealed":
                payload["status"] = "condition_setup_failed"
                payload["stderr"] = (
                    payload["stderr"] + "\nsetup baseline sealing failed: "
                    + str(baseline.get("baseline_error") or "unknown")
                ).strip()
    _write_json_atomic(run_output_dir / "condition_setup.json", payload)
    return payload


def _seal_condition_setup_baseline(
    workspace: Path,
    run_output_dir: Path,
    *,
    allowed_changed_files: tuple[str, ...] | None,
) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": status.stderr[-2_000:]}
    changed_files = sorted({
        line[3:].split(" -> ")[-1].strip()
        for line in status.stdout.splitlines()
        if len(line) > 3 and line[3:].strip()
    })
    if allowed_changed_files is not None:
        unexpected = sorted(set(changed_files) - set(allowed_changed_files))
        if unexpected:
            return {
                "baseline_status": "failed",
                "baseline_error": "setup changed files outside frozen allowlist: " + ", ".join(unexpected),
                "baseline_changed_files": changed_files,
                "baseline_allowed_changed_files": list(allowed_changed_files),
            }
    artifact_hashes: dict[str, str] = {}
    artifact_dir = run_output_dir / "setup_baseline_artifacts"
    for relative in changed_files if allowed_changed_files is not None else ():
        source = (workspace / relative).resolve()
        if workspace.resolve() not in source.parents or not source.is_file():
            continue
        artifact_dir.mkdir(parents=True, exist_ok=True)
        destination = artifact_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        artifact_hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    if changed_files:
        added = subprocess.run(
            ["git", "add", "-A"], cwd=workspace, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if added.returncode != 0:
            return {"baseline_status": "failed", "baseline_error": added.stderr[-2_000:]}
        commit_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
        }
        committed = subprocess.run(
            ["git", "commit", "-m", "condition setup baseline"],
            cwd=workspace,
            env=commit_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if committed.returncode != 0:
            return {"baseline_status": "failed", "baseline_error": committed.stderr[-2_000:]}
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if revision.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": revision.stderr[-2_000:]}
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=workspace, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if tree.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": tree.stderr[-2_000:]}
    return {
        "baseline_status": "sealed",
        "baseline_revision": revision.stdout.strip(),
        "baseline_tree": tree.stdout.strip(),
        "baseline_changed_files": changed_files,
        "baseline_allowed_changed_files": list(allowed_changed_files or ()),
        "baseline_artifact_sha256": artifact_hashes,
    }


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


def _prepare_shared_task33_evidence(
    task: TaskSpec,
    runtime_root: Path,
    repeat: int,
) -> tuple[HostEvidenceSnapshot, dict[str, Any]]:
    seed_root = runtime_root / task.task_id / f"repeat_{repeat}" / "bounded-evidence-seed"
    workspace = seed_root / "workspace"
    output_dir = seed_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    materialized = materialize_fixture(task, workspace)
    contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    if task.task_id in TASK23_PROTOCOL_TASKS and (
        contract is None
        or materialized.get("fixture_hash") != contract.fixture_sha256
        or materialized.get("protocol_fixture_hash") != contract.protocol_fixture_sha256
    ):
        raise IsolatedDeliveryError("task33_shared_fixture_identity_mismatch")
    env = fresh_run_environment(output_dir)
    preparation = prepare_docatlas(task, workspace, output_dir, env)
    if preparation.get("status") == "condition_setup_failed":
        raise IsolatedDeliveryError("task33_shared_docatlas_preparation_failed")
    index_revision = _directory_sha256(Path(env["DOCMANCER_HOME"]))
    evidence = capture_task33_host_evidence(
        task,
        workspace,
        output_dir,
        env,
        project_revision=str(materialized["fixture_hash"]),
        index_revision=index_revision,
    )
    missing = sorted(set(TASK33C_REQUIRED_EVIDENCE_CATEGORIES) - set(evidence.evidence_categories))
    if missing:
        raise IsolatedDeliveryError("task33_shared_evidence_categories_missing:" + ",".join(missing))
    sanitized_preparation = _replace_path_in_json(preparation, seed_root, "<task33-shared-capture>")
    sanitized_preparation["shared_frozen_capture"] = True
    sanitized_preparation["evidence_fingerprint"] = evidence.fingerprint
    sanitized_preparation["index_revision"] = evidence.index_revision
    return evidence, sanitized_preparation


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
    isolated_worker: IsolatedWorker | None = None,
    isolated_worker_timeout_seconds: int = 60,
    evidence_tier: str = "causal",
    evaluation_backend: str = "docker",
) -> list[dict[str, Any]]:
    _assert_task33_run_preconditions(
        tasks,
        runner,
        evidence_tier=evidence_tier,
        conditions=conditions,
        repeats=repeats,
        evaluation_backend=evaluation_backend,
    )
    if retry_infrastructure_failures and any(task.task_id in TASK23_PROTOCOL_TASKS for task in tasks):
        raise ValueError("Task 33 one-attempt cells cannot use infrastructure retry")
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
    configured_root = configured_runtime_root()
    runtime_root = Path(
        tempfile.mkdtemp(
            prefix=f"docatlas-task-level-{run_id}-",
            dir=str(configured_root) if configured_root is not None else None,
        )
    )
    try:
        total_runs = len(tasks) * len(conditions) * repeats
        for task in tasks:
            for repeat in range(repeats):
                shared_evidence: HostEvidenceSnapshot | None = None
                shared_preparation: dict[str, Any] = {}
                shared_evidence_error: str | None = None
                if any(CONDITIONS[condition].tool_policy.delivery_strategy for condition in conditions):
                    try:
                        shared_evidence, shared_preparation = _prepare_shared_task33_evidence(
                            task, runtime_root, repeat
                        )
                    except IsolatedDeliveryError as exc:
                        shared_evidence_error = str(exc)
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
                    task_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
                    if task.task_id in TASK23_PROTOCOL_TASKS and (
                        task_contract is None
                        or materialized.get("fixture_hash") != task_contract.fixture_sha256
                        or materialized.get("protocol_fixture_hash") != task_contract.protocol_fixture_sha256
                    ):
                        raise ValueError(f"Task 33 materialized fixture identity mismatch: {task.task_id}")
                    (run_output_dir / "materialized.json").write_text(json.dumps(materialized, indent=2, sort_keys=True), encoding="utf-8")
                    policy_path, mcp_config = build_tool_policy(condition_id, run_output_dir)
                    env = fresh_run_environment(run_output_dir)
                    condition_setup = _run_condition_setup(
                        task,
                        workspace,
                        run_output_dir,
                        env,
                    )
                    setup_failed = condition_setup.get("status") == "condition_setup_failed"
                    delivery_strategy = CONDITIONS[condition_id].tool_policy.delivery_strategy
                    if not setup_failed and delivery_strategy:
                        if shared_evidence is None:
                            setup_failed = True
                            _write_json_atomic(run_output_dir / "host_retrieval_error.json", {
                                "status": "condition_setup_failed",
                                "reason": shared_evidence_error or "shared_host_evidence_unavailable",
                            })
                        else:
                            stage_task33_host_evidence(shared_evidence, shared_preparation, run_output_dir)
                    elif not setup_failed and condition_id in DOCATLAS_CONDITIONS:
                        diagnostics = prepare_docatlas(task, workspace, run_output_dir, env)
                        setup_failed = diagnostics.get("status") == "condition_setup_failed"
                    prompt = prompt_template.format(issue_text=task.issue_text) + "\nUse the tools available in this environment when they are useful.\n"
                    if delivery_strategy == "bounded_direct":
                        if not setup_failed and shared_evidence is not None:
                            try:
                                packet = build_bounded_direct_packet(
                                    task, workspace, run_output_dir, shared_evidence
                                )
                            except IsolatedDeliveryError as exc:
                                setup_failed = True
                                _write_json_atomic(run_output_dir / "bounded_direct_error.json", {
                                    "status": "condition_setup_failed", "reason": str(exc),
                                })
                            else:
                                if packet.get("status") == "insufficient_evidence":
                                    setup_failed = True
                                    _write_json_atomic(run_output_dir / "bounded_direct_error.json", {
                                        "status": "condition_setup_failed",
                                        "reason": "bounded_direct_insufficient_evidence",
                                    })
                                else:
                                    _persist_delivery_prompt_sources(run_output_dir, packet)
                                    prompt += "\nDocAtlas ActionPacket (bounded direct):\n" + json.dumps(packet, sort_keys=True) + "\n"
                    elif delivery_strategy == "bounded_subagent":
                        if isolated_worker is None:
                            setup_failed = True
                            _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                "status": "condition_setup_failed",
                                "reason": "isolated_worker_capability_unavailable",
                            })
                        elif not setup_failed and shared_evidence is not None:
                            envelope = DelegationEnvelope(
                                task_objective=task.issue_text,
                                suspected_modules=task_contract.allowed_paths if task_contract else (),
                                changed_files=(),
                                required_evidence_categories=TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
                                project_revision=shared_evidence.project_revision,
                                index_revision=shared_evidence.index_revision,
                                required_evidence_paths=TASK33C_REQUIRED_EVIDENCE_PATHS,
                                token_budget=2_000,
                            )
                            try:
                                delivery = (
                                    deliver_with_exploratory_worker
                                    if evidence_tier == "exploratory"
                                    else deliver_with_isolated_worker
                                )
                                handoff = delivery(
                                    worker=isolated_worker,
                                    envelope=envelope,
                                    evidence=shared_evidence,
                                    output_dir=run_output_dir,
                                    timeout_seconds=isolated_worker_timeout_seconds,
                                )
                            except IsolatedDeliveryError as exc:
                                setup_failed = True
                                _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                    "status": "condition_setup_failed", "reason": str(exc),
                                })
                            else:
                                if handoff["status"] == "insufficient_evidence":
                                    setup_failed = True
                                    _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                        "status": "condition_setup_failed",
                                        "reason": "isolated_action_packet_insufficient_evidence",
                                    })
                                else:
                                    _persist_delivery_prompt_sources(run_output_dir, handoff["packet"])
                                    prompt += "\nDocAtlas ActionPacket (isolated worker):\n" + json.dumps(handoff["packet"], sort_keys=True) + "\n"
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
                        prompt += "\n" + TOOL_REQUIRED_ONCE_INSTRUCTION + "\n"
                    if setup_failed:
                        result = condition_setup_failed_result(task, condition_id, run_output_dir)
                        _mark_exploratory_result(result, run_output_dir, evidence_tier)
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
                        max_turns=(
                            min(task.max_turns, TASK33C_AGENT_TURN_LIMIT)
                            if task.task_id in TASK23_PROTOCOL_TASKS
                            else task.max_turns
                        ),
                        environment=env,
                        mcp_config_path=mcp_config,
                        tool_policy_path=policy_path,
                        output_dir=run_output_dir,
                        test_command=task.test_command,
                        allowed_write_paths=task_contract.allowed_paths if task_contract else (),
                        task_objective=task.issue_text,
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
                        result = evaluate_agent_patch(
                            task,
                            workspace,
                            run_output_dir,
                            condition_id,
                            output.trajectory_path,
                            output,
                            evaluation_backend=evaluation_backend,
                        )
                    _mark_exploratory_result(result, run_output_dir, evidence_tier)
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


def _mark_exploratory_result(
    result: dict[str, Any],
    output_dir: Path,
    evidence_tier: str,
) -> None:
    if evidence_tier != "exploratory":
        return
    result["execution_classification"] = "EXPLORATORY_NON_CAUSAL"
    result["causal_eligible"] = False
    result["hard_turn_limit_verified"] = False
    _write_json_atomic(output_dir / "result.json", result)


def _assert_task33_run_preconditions(
    tasks: list[TaskSpec],
    runner: AgentRunner,
    *,
    evidence_tier: str = "causal",
    conditions: list[str] | tuple[str, ...] | None = None,
    repeats: int | None = None,
    evaluation_backend: str = "docker",
) -> None:
    if evidence_tier not in {"causal", "exploratory"}:
        raise ValueError("Unknown Task 33 evidence tier: " + evidence_tier)
    formal_tasks = [task for task in tasks if task.task_id in TASK23_PROTOCOL_TASKS]
    if not formal_tasks:
        return
    if evaluation_backend not in {"docker", "host_exploratory"}:
        raise ValueError("Unknown evaluation backend: " + evaluation_backend)
    if evaluation_backend == "host_exploratory" and evidence_tier != "exploratory":
        raise ValueError("Task 33 host evaluator requires exploratory evidence tier")
    errors: list[str] = []
    for task in formal_tasks:
        validation = _task_contract_validation(
            task,
            TASK33_EVALUATION_CONTRACTS.get(task.task_id),
            TASK23_PROTOCOL_TASKS.get(task.task_id),
        )
        errors.extend(f"{task.task_id}:{error}" for error in validation.errors)
    if errors:
        raise ValueError("Task 33 evaluation preconditions failed: " + ",".join(errors))
    if evidence_tier == "causal":
        if not bool(getattr(runner, "hard_turn_limit_enforced", False)):
            raise ValueError(
                "Task 33 causal execution requires a runner with a proven hard turn limit"
            )
        return
    if (
        [task.task_id for task in tasks] != [TASK33C_PILOT_TASK_ID]
        or list(conditions or ()) != list(TASK33C_PILOT_CONDITIONS)
        or repeats != 1
        or getattr(runner, "runner_id", None) != "codex"
    ):
        raise ValueError(
            "Task 33 exploratory execution requires Codex and exactly the frozen protocol cells"
        )


def _runner_id_from_version(version: str) -> str:
    normalized = version.lower()
    for runner_id in ("github-models", "openai-api", "codex"):
        if runner_id in normalized:
            return runner_id
    return "claude"


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
    sync_counts = {
        "current": 0,
        "new": 0,
        "changed": 0,
        "orphaned_removed": 0,
        "stale_removed": 0,
        "sections_indexed": 0,
    }
    try:
        from docmancer.docs.service import LibraryDocsService

        with _activated_run_environment(env):
            sync_result = LibraryDocsService().sync_project_docs(str(workspace), with_vectors=False)
            sync_status = getattr(sync_result, "status", "success")
            sync_counts = {
                "current": int(getattr(sync_result, "current_count", 0) or 0),
                "new": int(getattr(sync_result, "new_count", 0) or 0),
                "changed": int(getattr(sync_result, "changed_count", 0) or 0),
                "orphaned_removed": int(
                    getattr(sync_result, "orphaned_removed", 0) or 0
                ),
                "stale_removed": int(getattr(sync_result, "stale_removed", 0) or 0),
                "sections_indexed": int(
                    getattr(sync_result, "sections_indexed", 0) or 0
                ),
            }
    except Exception as exc:
        sync_status = "failed"
        sync_error = repr(exc)

    index_changed = any(
        sync_counts[key]
        for key in (
            "new",
            "changed",
            "orphaned_removed",
            "stale_removed",
            "sections_indexed",
        )
    )
    if sync_status == "failed":
        index_state = "condition_setup_failed"
    elif sync_counts["current"] > 0 and not index_changed:
        index_state = "already_current"
    else:
        index_state = "updated_local"
    diagnostics = {
        "task_id": task.task_id,
        "status": "prepared_with_local_project_docs_only" if sync_status != "failed" else "condition_setup_failed",
        "allow_network": False,
        "docmancer_home": env["DOCMANCER_HOME"],
        "project_docs_sync_status": sync_status,
        "project_docs_sync_error": sync_error,
        "index_state": index_state,
        "with_vectors": False,
        "provider_input_tokens": 0,
        "provider_output_tokens": 0,
        "sync_counts": sync_counts,
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


def capture_task33_host_evidence(
    task: TaskSpec,
    workspace: Path,
    output_dir: Path,
    env: dict[str, str],
    *,
    project_revision: str,
    index_revision: str,
) -> HostEvidenceSnapshot:
    """Run the frozen host retrieval once for both bounded delivery lanes."""

    from docmancer.docs.service import LibraryDocsService

    started = time.monotonic()
    retrieval_query = derive_task33_retrieval_query(task.issue_text)
    objective_sha256 = hashlib.sha256(task.issue_text.encode("utf-8")).hexdigest()
    old_handler = signal.getsignal(signal.SIGALRM)

    def _timeout_handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError("Task 33 host retrieval exceeded 45 seconds")

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(45)
    try:
        with _activated_run_environment(env):
            result = LibraryDocsService().get_docs_context(
                retrieval_query,
                project_path=str(workspace),
                library=None,
                ecosystem=task.ecosystem,
                version=None,
                mode="project",
                response_style="snippet-first",
                allow_network=False,
                allow_latest_fallback=False,
                tokens=4_000,
                limit=12,
            )
    except Exception as exc:
        raise IsolatedDeliveryError(f"host_retrieval_failed:{exc.__class__.__name__}") from exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    response = _replace_path_in_json(_jsonable(result), workspace, "<repo>")
    status = str(response.get("status") or "unknown")
    context_pack = tuple(
        dict(item) for item in response.get("context_pack", []) if isinstance(item, dict)
    )
    trust_contract = response.get("trust_contract") if isinstance(response.get("trust_contract"), dict) else {}
    retrieval_issues = list(bounded_retrieval_issues(response, project_evidence_required=True))
    available_paths = {
        str(item.get("path") or "").strip().replace("\\", "/") for item in context_pack
    }
    for required_path in TASK33C_REQUIRED_EVIDENCE_PATHS:
        if required_path not in available_paths:
            retrieval_issues.append("missing_required_evidence_path:" + required_path)
    issues = tuple(dict.fromkeys(retrieval_issues))
    categories = _host_evidence_categories(context_pack)
    wall = round(time.monotonic() - started, 6)
    snapshot = HostEvidenceSnapshot(
        query=retrieval_query,
        objective_sha256=objective_sha256,
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=context_pack,
        trust_contract=trust_contract,
        retrieval_issues=issues,
        evidence_categories=categories,
        project_revision=project_revision,
        index_revision=index_revision,
        response_status=status,
        raw_retrieval_tokens=_estimate_tokens(json.dumps(response, ensure_ascii=False, sort_keys=True)),
        retrieval_wall_time_seconds=wall,
    )
    snapshot.validate()
    persist_host_evidence(snapshot, output_dir)
    _write_json_atomic(output_dir / "host_retrieval_metrics.json", {
        "schema_version": 1,
        "status": status,
        "retrieval_calls": 1,
        "query": retrieval_query,
        "query_sha256": hashlib.sha256(retrieval_query.encode("utf-8")).hexdigest(),
        "objective_sha256": objective_sha256,
        "query_derivation": snapshot.query_derivation,
        "evidence_fingerprint": snapshot.fingerprint,
        "evidence_count": len(context_pack),
        "evidence_categories": list(categories),
        "project_revision": project_revision,
        "index_revision": index_revision,
        "raw_retrieval_tokens": snapshot.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": wall,
        "retrieval_issues": list(issues),
    })
    return snapshot


def stage_task33_host_evidence(
    evidence: HostEvidenceSnapshot,
    preparation: dict[str, Any],
    output_dir: Path,
) -> None:
    persist_host_evidence(evidence, output_dir)
    _write_json_atomic(output_dir / "docatlas_preparation.json", preparation)
    _write_json_atomic(output_dir / "host_retrieval_metrics.json", {
        "schema_version": 1,
        "status": evidence.response_status,
        "retrieval_calls": evidence.retrieval_calls,
        "query_sha256": hashlib.sha256(evidence.query.encode("utf-8")).hexdigest(),
        "objective_sha256": evidence.objective_sha256,
        "query_derivation": evidence.query_derivation,
        "evidence_fingerprint": evidence.fingerprint,
        "evidence_count": len(evidence.evidence_items),
        "evidence_categories": list(evidence.evidence_categories),
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
        "raw_retrieval_tokens": evidence.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": evidence.retrieval_wall_time_seconds,
        "retrieval_issues": list(evidence.retrieval_issues),
        "shared_frozen_capture": True,
    })


def _host_evidence_categories(items: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    categories: set[str] = set()
    for item in items:
        source_class = str(item.get("source_class") or item.get("source_kind") or "").lower()
        if "project" in source_class or source_class in {"readme", "agent_policy"}:
            categories.add("project_docs")
        if source_class in {"repo_map", "source_evidence", "code_graph"}:
            categories.add("symbols")
        if source_class in {"library_doc", "dependency_doc", "package_doc"}:
            categories.add("dependencies")
    return tuple(sorted(categories))


def _replace_path_in_json(value: Any, path: Path, replacement: str) -> Any:
    needle = str(path)
    if isinstance(value, dict):
        return {str(key): _replace_path_in_json(item, path, replacement) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_path_in_json(item, path, replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_path_in_json(item, path, replacement) for item in value)
    if isinstance(value, str):
        return value.replace(needle, replacement)
    return value


def inject_docatlas_context(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    fallback_reason: str | None = None
    try:
        from docmancer.docs.service import LibraryDocsService

        old_handler = signal.getsignal(signal.SIGALRM)

        def _timeout_handler(_signum: int, _frame: Any) -> None:
            raise TimeoutError("DocAtlas context injection exceeded 45 seconds")

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(45)
        try:
            with _activated_run_environment(env):
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


def build_bounded_direct_packet(
    task: TaskSpec,
    workspace: Path,
    output_dir: Path,
    evidence: HostEvidenceSnapshot,
) -> dict[str, Any]:
    """Format the same frozen host evidence supplied to the isolated worker."""

    from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet

    evidence.validate()
    packet_evidence = [
        *evidence.evidence_items,
        build_task33c_validation_evidence(task.test_command),
    ]
    packet = build_action_packet(
        question=task.issue_text,
        context_pack=packet_evidence,
        trust_contract=evidence.trust_contract,
        max_tokens=2_000,
        project_path=str(workspace),
        retrieval_issues=evidence.retrieval_issues,
        required_evidence_paths=TASK33C_REQUIRED_EVIDENCE_PATHS,
        required_target_paths=TASK33C_REQUIRED_TARGET_PATHS,
    )
    errors = validate_action_packet(
        packet,
        evidence_items=packet_evidence,
        max_tokens=2_000,
        project_path=str(workspace),
    )
    if errors:
        raise IsolatedDeliveryError("invalid_bounded_direct_packet:" + ";".join(errors))
    missing_categories = missing_packet_evidence_categories(
        packet,
        evidence.evidence_items,
        TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    )
    if packet.get("status") != "insufficient_evidence" and missing_categories:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_evidence_categories:" + ",".join(missing_categories)
        )
    missing_paths = missing_packet_evidence_paths(
        packet, evidence.evidence_items, TASK33C_REQUIRED_EVIDENCE_PATHS
    )
    if packet.get("status") != "insufficient_evidence" and missing_paths:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_evidence_paths:" + ",".join(missing_paths)
        )
    contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    target_surface = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    packet_targets = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in target_surface.get("likely_files", [])
        if isinstance(row, dict)
    }
    missing_targets = sorted(set(contract.allowed_paths if contract else ()) - packet_targets)
    if packet.get("status") != "insufficient_evidence" and missing_targets:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_target_modules:" + ",".join(missing_targets)
        )
    persist_host_evidence(evidence, output_dir)
    _write_json_atomic(output_dir / "action_packet.json", packet)
    _write_json_atomic(output_dir / "bounded_direct_metrics.json", {
        "schema_version": 2,
        "strategy": "bounded_direct",
        "status": packet["status"],
        "attempts": 1,
        "retrieval_calls": evidence.retrieval_calls,
        "parent_visible_raw_retrieval": False,
        "parent_packet_tokens": packet["estimated_tokens"],
        "raw_retrieval_tokens": evidence.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": evidence.retrieval_wall_time_seconds,
        "evidence_fingerprint": evidence.fingerprint,
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
    })
    return packet


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
    action_packet = _load_optional_json(run_output_dir / "action_packet.json")
    delivery = (
        _load_optional_json(run_output_dir / "isolated_delivery_metrics.json")
        or _load_optional_json(run_output_dir / "bounded_direct_metrics.json")
    )
    host_retrieval = _load_optional_json(run_output_dir / "host_retrieval_metrics.json")
    condition_setup = _load_optional_json(run_output_dir / "condition_setup.json")
    reason_payload = (
        condition_setup
        if condition_setup.get("status") == "condition_setup_failed"
        else {}
    ) or (
        _load_optional_json(run_output_dir / "isolated_delivery_error.json")
        or _load_optional_json(run_output_dir / "bounded_direct_error.json")
        or _load_optional_json(run_output_dir / "host_retrieval_error.json")
    )
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
        "compile_status": "not_run",
        "evaluation_execution": {
            "setup": condition_setup,
            "public_tests": {"status": "not_run", "command": task.test_command, "returncode": None},
            "hidden_tests": {"status": "not_run", "command": None, "returncode": None},
        },
        "policy_clean": False,
        "policy": {"clean": False, "violations": ["condition_setup_failed"]},
        "docatlas": {
            "available": True,
            "harness_calls": _optional_int(host_retrieval.get("retrieval_calls")) or 0,
            "agent_calls": 0,
            "context_retrieved": bool(host_retrieval.get("evidence_count")),
            "context_injected": False,
            "context_used": False,
            "context_used_confidence": "none",
            "used_symbols": [],
            "used_sources": [],
            "docatlas_retrieval_status": host_retrieval.get("status"),
        },
        "contract": {},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
        "metrics": {
            "delivery_retrieval_calls": _optional_int(host_retrieval.get("retrieval_calls")),
            "raw_doc_context_tokens": _optional_int(host_retrieval.get("raw_retrieval_tokens")),
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "action_packet_status": action_packet.get("status"),
            "action_packet_truncated": action_packet.get("status") == "truncated",
            "action_packet_insufficient_evidence": action_packet.get("status") == "insufficient_evidence",
            "action_packet_fidelity": "validated" if action_packet else "not_available",
            "evidence_fingerprint": delivery.get("evidence_fingerprint") or host_retrieval.get("evidence_fingerprint"),
            "worker_input_tokens": _optional_int(delivery.get("worker_input_tokens")),
            "worker_output_tokens": _optional_int(delivery.get("worker_output_tokens")),
            "time_to_first_edit": None,
            "total_latency": (
                float(condition_setup["wall_time_seconds"])
                if isinstance(condition_setup.get("wall_time_seconds"), (int, float))
                and not isinstance(condition_setup.get("wall_time_seconds"), bool)
                else None
            ),
        },
        "notes": [
            "Condition setup failed; agent and evaluator tests were not run.",
            str(
                reason_payload.get("reason")
                or reason_payload.get("stderr")
                or "condition_setup_failed"
            )[:2_000],
        ],
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def run_canary(runner: AgentRunner, model: str, timeout_seconds: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="docatlas-runner-canary-"))
    try:
        (workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (workspace / "normalization.py").write_text("def normalize(value):\n    return value - 1\n", encoding="utf-8")
        (workspace / "policy.py").write_text("def may_enter(allowed):\n    return not allowed\n", encoding="utf-8")
        (workspace / "test_calc.py").write_text(
            "from calc import add\nfrom normalization import normalize\nfrom policy import may_enter\n\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n\n\n"
            "def test_normalize():\n    assert normalize(-4) == 4\n\n\n"
            "def test_policy():\n    assert may_enter(True) is True\n    assert may_enter(False) is False\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=workspace, check=False)
        subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=workspace, check=False)
        subprocess.run(["git", "add", "."], cwd=workspace, check=False)
        subprocess.run(["git", "commit", "-m", "canary base"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        policy_path, mcp_config = build_tool_policy("repo_only", output_dir)
        env = fresh_run_environment(output_dir)
        canary_test_command = f"{shlex.quote(sys.executable)} -m pytest test_calc.py -q"
        request = AgentRunRequest(
            task_id="runner_canary",
            condition_id="repo_only",
            workspace=workspace,
            prompt=(
                "Fix three independent defects: add(a, b) currently subtracts, normalize(value) "
                "must return the absolute magnitude, and may_enter(allowed) must preserve the allowed boolean. "
                "Change all three source files and run the tests. "
                "Do not use web, curl, wget, or external network."
            ),
            model=model,
            timeout_seconds=timeout_seconds,
            max_turns=8,
            environment=env,
            mcp_config_path=mcp_config,
            tool_policy_path=policy_path,
            output_dir=output_dir,
            test_command=canary_test_command,
            allowed_write_paths=("calc.py", "normalization.py", "policy.py"),
        )
        runner_output = runner.run(request)
        patch_path, _, _, changed = capture_patch(workspace, output_dir)
        if os.environ.get("TASK33C_REQUIRE_DOCKER_SANDBOX") == "1":
            sandbox, boundary = verified_task33_sandbox(os.environ.get("TASK33C_TEST_CONTAINER_IMAGE", ""))
            persist_boundary(output_dir / "canary_execution_boundary.json", boundary)
            if boundary.get("status") != "verified":
                raise RuntimeError("runner canary requires a verified Docker execution boundary")
            sandbox_result = sandbox.run(canary_test_command, workspace, 60)
            tests = CommandResult(
                command=shlex.join(sandbox_result.command),
                returncode=sandbox_result.returncode,
                stdout=sandbox_result.stdout,
                stderr=sandbox_result.stderr,
            )
        else:
            tests = run_command(canary_test_command, workspace, 60)
        audit = audit_trajectory("repo_only", Path(runner_output.trajectory_path) if runner_output.trajectory_path else None, output_dir / "policy_audit.json")
        raw_stdout = Path(runner_output.raw_stdout_path).read_text(encoding="utf-8") if Path(runner_output.raw_stdout_path).exists() else ""
        network_probe_denied = "blocked by benchmark network policy" in raw_stdout
        canary_policy_clean = audit.clean or (network_probe_denied and audit.docatlas_calls == 0 and audit.context7_calls == 0)
        payload = {
            "task_id": "runner_canary",
            "status": "passed" if patch_path.read_text(encoding="utf-8").strip() and tests.passed and canary_policy_clean and runner_output.exit_code is not None and {"calc.py", "normalization.py", "policy.py"}.issubset(changed) else "failed",
            "runner_status": runner_output.status,
            "runner_exit_code": runner_output.exit_code,
            "patch_exists": bool(patch_path.read_text(encoding="utf-8").strip()),
            "pytest_passes": tests.passed,
            "trajectory_exists": bool(runner_output.trajectory_path and Path(runner_output.trajectory_path).exists()),
            "runner_exit_interpretable": runner_output.exit_code is not None,
            "policy_clean": canary_policy_clean,
            "network_probe_denied": network_probe_denied,
            "changed_files": changed,
            "multi_file_edit_proven": {"calc.py", "normalization.py", "policy.py"}.issubset(changed),
            "same_shape_three_file_canary": True,
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
        "hard_turn_limit_verified": capabilities.hard_turn_limit,
        "trajectory_format": "stream-json normalized to trajectory.normalized.json" if capabilities.structured_trajectory else "unverified",
        "tool_isolation": "strict MCP config plus allowed/disallowed tools plus trajectory audit" if capabilities.tool_isolation else "unverified",
        "network_enforcement": "policy_and_trajectory_audit",
        "notes": capabilities.verification_notes,
    }
