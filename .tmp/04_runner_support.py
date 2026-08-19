from pathlib import Path
import subprocess

REVIEWED_HEAD = "7a5a88f6188c793c91ea9231d67a99450bcff0c3"
subprocess.run(
    ["git", "checkout", REVIEWED_HEAD, "--", "scripts/run_agent_developer_gate.py"],
    check=True,
)

support = r'''"""Strict extensions for the provider-free Agent Developer Protocol gate."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
PROJECTS_ROOT = PROTOCOL_ROOT / "projects"


def _scope_signature(value: dict[str, Any]) -> tuple[str, str, str]:
    scope = str(value.get("scope") or "").strip()
    if not scope and str(value.get("mode") or "") == "dependency":
        scope = "dependency"
    return (
        scope,
        str(value.get("module") or "").strip(),
        str(value.get("module_path") or "").strip(),
    )


def _target_context_calls(task: dict[str, Any]) -> list[dict[str, Any]]:
    calls = list(task.get("calls") or [])
    for call in task.get("calls") or []:
        follow_up = call.get("target_follow_up")
        retry = follow_up.get("retry") if isinstance(follow_up, dict) else None
        if isinstance(retry, dict):
            calls.append(retry)
    return calls


def _service(tmp: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(tmp / "docmancer.db")
    config.index.extracted_dir = str(tmp / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _source_paths(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        return ()
    return tuple(
        str(row.get("path_or_url") or "").strip()
        for row in payload["sources"]
        if isinstance(row, dict) and str(row.get("path_or_url") or "").strip()
    )


def _recommended_action(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    value = payload.get("recommended_next_action") or payload.get("next_action")
    return value if isinstance(value, dict) else {}


def _module_candidate_paths(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("module_candidates"), list):
        return ()
    return tuple(
        str(row.get("module_path") or "").strip()
        for row in payload["module_candidates"][:8]
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    )


def _docs_status_module_paths(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    project = payload.get("project")
    project_docs = project.get("project_docs") if isinstance(project, dict) else None
    modules = project_docs.get("modules") if isinstance(project_docs, dict) else None
    if not isinstance(modules, list):
        return ()
    return tuple(
        str(row.get("module_path") or "").strip()
        for row in modules
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    )


def _is_edit_ready(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("edit_ready") is True:
        return True
    return any(payload.get(key) not in (None, {}, []) for key in (
        "implementation_guidance", "invariants", "targets",
        "acceptance_conditions", "forbidden_changes",
    ))


def _resolved_expected(value: Any, *, project_path: str) -> Any:
    if value == "$PROJECT":
        return project_path
    if isinstance(value, dict):
        return {
            str(key): _resolved_expected(child, project_path=project_path)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_resolved_expected(child, project_path=project_path) for child in value]
    return value


def _mapping_contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _mapping_contains(actual[key], value)
            for key, value in expected.items()
        )
    return actual == expected


def _context_args(call: dict[str, Any], project: Path) -> dict[str, Any]:
    args: dict[str, Any] = {
        "question": str(call["question"]),
        "project_path": str(project),
        "mode": call.get("mode"),
        "delivery_strategy": "bounded_direct",
        "prepare_project_docs": False,
    }
    for key in (
        "scope", "module", "module_path", "library", "libraries",
        "ecosystem", "version", "packet_tokens",
    ):
        if call.get(key) is not None:
            args[key] = call[key]
    return args


def _validate_declared_protocol(tasks: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for task in tasks:
        task_id = str(task.get("id") or "<missing>")
        fixture = PROJECTS_ROOT / str(task.get("fixture") or "")
        working = str(task.get("working_path") or "").replace("\\", "/")
        pure = PurePosixPath(working)
        if (
            not working or pure.is_absolute() or ".." in pure.parts
            or not (fixture / Path(*pure.parts)).is_file()
        ):
            errors.append(f"{task_id}: working_path is not a real fixture file")
        target_calls = _target_context_calls(task)
        if len(target_calls) > int(task.get("max_get_docs_context_calls") or 0):
            errors.append(f"{task_id}: target trajectory exceeds context-call budget")
        expected = sorted(
            _scope_signature(row)
            for row in task.get("required_scopes") or []
            if isinstance(row, dict)
        )
        actual = sorted(_scope_signature(call) for call in target_calls)
        if expected != actual:
            errors.append(f"{task_id}: required_scopes do not match target trajectory")
        for scope, module, module_path in actual:
            if module_path and scope != "module":
                errors.append(f"{task_id}: module_path does not imply module scope")
            if scope == "all" and (module or module_path):
                errors.append(f"{task_id}: all scope is filtered by a module")
        if task.get("class") in {"module_only", "module_plus_project"}:
            paths = [value for scope, _module, value in actual if scope == "module" and value]
            if paths and not any(
                working == value or working.startswith(value.rstrip("/") + "/")
                for value in paths
            ):
                errors.append(f"{task_id}: working_path is outside required module scope")
    return errors


def _run_recovery_task(task: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    task_id = str(task["id"])
    fixture = PROJECTS_ROOT / str(task["fixture"])
    previous_home = os.environ.get("DOCMANCER_HOME")
    trace: dict[str, Any] = {"task_id": task_id}
    try:
        with TemporaryDirectory(prefix=f"docatlas-agent-extension-{task_id}-") as raw:
            tmp = Path(raw)
            project = tmp / "project"
            shutil.copytree(fixture, project)
            os.environ["DOCMANCER_HOME"] = str(tmp / "home")
            service = _service(tmp)
            sync = service.sync_project_docs(str(project), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                return [f"{task_id}: sync failed"], trace
            mutation = task.get("mutation_before_calls")
            if isinstance(mutation, dict):
                target = project / str(mutation.get("path") or "")
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(str(mutation.get("append") or ""))
            call = task["calls"][0]
            payload = handle_context_tool(
                "get_docs_context", _context_args(call, project), service
            )
            action = _recommended_action(payload)
            status = str(payload.get("status") or "") if isinstance(payload, dict) else ""
            if status != str(call.get("target_expected_status") or ""):
                errors.append(f"{task_id}: target status drifted to {status!r}")
            expected_tool = str(call.get("target_next_action_tool") or "")
            if expected_tool and str(action.get("tool") or "") != expected_tool:
                errors.append(f"{task_id}: recovery tool drifted")
            expected_args = call.get("target_next_action_arguments")
            if isinstance(expected_args, dict) and not _mapping_contains(
                action.get("arguments_patch"),
                _resolved_expected(expected_args, project_path=str(project)),
            ):
                errors.append(f"{task_id}: recovery arguments drifted")
            if "target_requires_confirmation" in call:
                actual = bool(action.get("requires_confirmation") or payload.get("requires_confirmation"))
                if actual is not bool(call["target_requires_confirmation"]):
                    errors.append(f"{task_id}: confirmation contract drifted")
            if "target_edit_ready" in call and _is_edit_ready(payload) is not bool(call["target_edit_ready"]):
                errors.append(f"{task_id}: edit-readiness contract drifted")
            expected_candidates = tuple(call.get("target_module_candidates") or ())
            if expected_candidates and tuple(sorted(_module_candidate_paths(payload))) != tuple(sorted(expected_candidates)):
                errors.append(f"{task_id}: module candidates drifted")
            forbidden = tuple(call.get("forbidden_sources") or task.get("forbidden_sources") or ())
            if any(source in forbidden for source in _source_paths(payload)):
                errors.append(f"{task_id}: recovery leaked a forbidden source")
            follow_up = call.get("target_follow_up")
            if isinstance(follow_up, dict):
                arguments = action.get("arguments_patch")
                if not isinstance(arguments, dict):
                    errors.append(f"{task_id}: docs_status arguments missing")
                else:
                    status_payload = handle_prefetch_tool(
                        str(follow_up.get("tool") or ""), dict(arguments), service
                    )
                    required_modules = tuple(follow_up.get("required_module_candidates") or ())
                    if tuple(sorted(_docs_status_module_paths(status_payload))) != tuple(sorted(required_modules)):
                        errors.append(f"{task_id}: docs_status module inventory drifted")
                    retry = follow_up.get("retry")
                    if isinstance(retry, dict):
                        retry_payload = handle_context_tool(
                            "get_docs_context", _context_args(retry, project), service
                        )
                        retry_status = str(retry_payload.get("status") or "")
                        retry_sources = _source_paths(retry_payload)
                        if retry_status != str(retry.get("target_expected_status") or ""):
                            errors.append(f"{task_id}: exact retry status drifted")
                        if not all(source in retry_sources for source in retry.get("required_sources") or ()):
                            errors.append(f"{task_id}: exact retry lost required source")
                        if any(source in retry_sources for source in retry.get("forbidden_sources") or ()):
                            errors.append(f"{task_id}: exact retry leaked sibling source")
                        trace["retry"] = {
                            "status": retry_status,
                            "sources": list(retry_sources),
                        }
            trace.update({
                "status": status,
                "action_tool": action.get("tool"),
                "module_candidates": list(_module_candidate_paths(payload)),
                "estimated_tokens": payload.get("estimated_tokens") if isinstance(payload, dict) else None,
            })
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home
    return errors, trace


def _metric_report(base_report, tasks, expected, *, recovery_ok):
    results = {item["task_id"]: item for item in base_report.get("tasks") or []}
    def rate(classes):
        rows = [task for task in tasks if task.get("class") in classes]
        return (
            sum(bool(results.get(task["id"], {}).get("target_closed")) for task in rows)
            / len(rows) if rows else 1.0
        )
    module_project_calls = [
        len(_target_context_calls(task))
        for task in tasks if task.get("class") == "module_plus_project"
    ]
    metrics = {
        "false_supported": int(base_report.get("false_supported") or 0),
        "forbidden_source_contamination": int(base_report.get("forbidden_source_contamination") or 0),
        "module_only_expected_evidence_rate": rate({"module_only"}),
        "module_project_max_context_calls": max(module_project_calls, default=0),
        "cross_module_scope_accuracy": rate({"cross_module"}),
        "recovery_contract_accuracy": rate({"recovery", "module_plus_dependency"}) if recovery_ok else 0.0,
    }
    errors = []
    for name, expected_value in expected.items():
        actual = metrics.get(name)
        if actual is None:
            errors.append(f"unknown target metric: {name}")
        elif name.endswith("max_context_calls"):
            if float(actual) > float(expected_value):
                errors.append(f"target metric {name} exceeded")
        elif abs(float(actual) - float(expected_value)) > 1e-9:
            errors.append(f"target metric {name} drifted")
    return metrics, errors


def apply_agent_protocol_extensions(base_report: dict[str, Any]) -> dict[str, Any]:
    public = json.loads((PROTOCOL_ROOT / "tasks.json").read_text(encoding="utf-8"))
    oracle = json.loads((PROTOCOL_ROOT / "expected_trajectories.json").read_text(encoding="utf-8"))
    public_by_id = {row["id"]: row for row in public["tasks"]}
    oracle_by_id = {row["id"]: row for row in oracle["trajectories"]}
    tasks = [{**public_by_id[key], **oracle_by_id[key]} for key in public_by_id]
    errors = _validate_declared_protocol(tasks)
    traces = []
    for task in tasks:
        if task.get("class") not in {"recovery", "module_plus_dependency"}:
            continue
        task_errors, trace = _run_recovery_task(task)
        errors.extend(task_errors)
        traces.append(trace)
    metrics, metric_errors = _metric_report(
        base_report, tasks, oracle.get("target_metrics") or {}, recovery_ok=not errors
    )
    errors.extend(metric_errors)
    report = dict(base_report)
    report["target_metrics"] = metrics
    report["agent_extension"] = {
        "ok": not errors,
        "errors": errors,
        "recovery_traces": traces,
    }
    if errors:
        report["errors"] = [*(report.get("errors") or []), *errors]
        report["baseline_ok"] = False
        report["target_ok"] = False
        report["target_gaps"] = [
            *(report.get("target_gaps") or []),
            {
                "task_id": "agent_protocol_extension",
                "gap": "complete_agent_recovery_contract",
                "actual_status": "failed",
                "target_status": "closed",
            },
        ]
        report["target_gap_count"] = len(report["target_gaps"])
    return report
'''
Path("scripts/agent_developer_gate_support.py").write_text(support, encoding="utf-8")

p = Path("scripts/run_agent_developer_gate.py")
text = p.read_text(encoding="utf-8")
old = "from docmancer.docs.service import DocsJobTracker, LibraryDocsService\n"
new = old + "from scripts.agent_developer_gate_support import apply_agent_protocol_extensions\n"
if text.count(old) != 1:
    raise RuntimeError("runner import anchor drifted")
text = text.replace(old, new, 1)
if text.count("def run_protocol() -> dict[str, Any]:\n") != 1:
    raise RuntimeError("runner function anchor drifted")
text = text.replace(
    "def run_protocol() -> dict[str, Any]:\n",
    "def _run_base_protocol() -> dict[str, Any]:\n",
    1,
)
needle = "\ndef main() -> int:\n"
if text.count(needle) != 1:
    raise RuntimeError("runner main anchor drifted")
text = text.replace(
    needle,
    "\ndef run_protocol() -> dict[str, Any]:\n"
    "    return apply_agent_protocol_extensions(_run_base_protocol())\n\n\n"
    "def main() -> int:\n",
    1,
)
p.write_text(text, encoding="utf-8")
