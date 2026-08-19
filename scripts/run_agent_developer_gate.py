#!/usr/bin/env python3
"""Provider-free coding-agent trajectory gate for Project Docs.

The public task file is deliberately separated from evaluator-only oracle data so
future model-backed runs cannot see expected scopes, source identities, or tool
queries. This first protocol commit freezes the reviewed current baseline apart
from its target behavior. Safety failures are blocking immediately; named safe
gaps remain visible until later production commits close them.
"""
from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from pathlib import Path
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
TASKS_PATH = PROTOCOL_ROOT / "tasks.json"
ORACLE_PATH = PROTOCOL_ROOT / "expected_trajectories.json"
PROJECTS_ROOT = PROTOCOL_ROOT / "projects"

_ALLOWED_CLASSES = {
    "module_only",
    "project_only",
    "module_plus_project",
    "cross_module",
    "module_plus_dependency",
    "negative_contamination",
    "recovery",
}
_ORACLE_ONLY_FIELDS = {
    "calls",
    "required_scopes",
    "required_sources",
    "forbidden_sources",
    "known_gap",
    "mutation_before_calls",
}


def _load_protocol() -> dict[str, Any]:
    public = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    if public.get("schema_version") != 1 or public.get("protocol") != "agent-developer-v1":
        raise ValueError("agent developer public protocol identity mismatch")
    if oracle.get("schema_version") != 1 or oracle.get("protocol") != "agent-developer-v1-oracle":
        raise ValueError("agent developer oracle protocol identity mismatch")
    public_tasks = public.get("tasks")
    trajectories = oracle.get("trajectories")
    target_metrics = oracle.get("target_metrics")
    if not isinstance(public_tasks, list) or not public_tasks:
        raise ValueError("agent developer protocol requires a non-empty tasks list")
    if not isinstance(trajectories, list) or not trajectories:
        raise ValueError("agent developer protocol requires evaluator trajectories")
    if not isinstance(target_metrics, dict) or not target_metrics:
        raise ValueError("agent developer protocol requires target metrics")

    task_by_id: dict[str, dict[str, Any]] = {}
    for task in public_tasks:
        if not isinstance(task, dict):
            raise ValueError("every agent developer task must be an object")
        task_id = str(task.get("id") or "")
        if not task_id or task_id in task_by_id:
            raise ValueError(f"invalid or duplicate task id: {task_id!r}")
        if _ORACLE_ONLY_FIELDS.intersection(task):
            raise ValueError(f"public task {task_id} leaks evaluator-only fields")
        if task.get("class") not in _ALLOWED_CLASSES:
            raise ValueError(f"unknown task class for {task_id}: {task.get('class')!r}")
        if not str(task.get("working_path") or ""):
            raise ValueError(f"task {task_id} requires a working_path")
        if int(task.get("max_get_docs_context_calls") or 0) < 1:
            raise ValueError(f"task {task_id} requires a positive context-call budget")
        task_by_id[task_id] = task

    oracle_by_id: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        if not isinstance(trajectory, dict):
            raise ValueError("every agent developer trajectory must be an object")
        task_id = str(trajectory.get("id") or "")
        if not task_id or task_id in oracle_by_id:
            raise ValueError(f"invalid or duplicate oracle task id: {task_id!r}")
        oracle_by_id[task_id] = trajectory

    if set(task_by_id) != set(oracle_by_id):
        raise ValueError("public task ids and oracle trajectory ids must match exactly")

    merged_tasks: list[dict[str, Any]] = []
    for public_task in public_tasks:
        task_id = str(public_task["id"])
        task = {**public_task, **oracle_by_id[task_id]}
        calls = task.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"task {task_id} requires at least one context call")
        context_calls = _trajectory_context_calls(task)
        if len(context_calls) > int(task.get("max_get_docs_context_calls") or 0):
            raise ValueError(f"task {task_id} exceeds its context-call budget")
        required_scopes = task.get("required_scopes")
        if not isinstance(required_scopes, list) or not required_scopes:
            raise ValueError(f"task {task_id} requires evaluator-owned scope expectations")
        actual_scopes = [_scope_record(call) for call in context_calls]
        if actual_scopes != required_scopes:
            raise ValueError(
                f"task {task_id} scope trajectory mismatch: "
                f"{actual_scopes!r} != {required_scopes!r}"
            )
        for call in calls:
            if not isinstance(call, dict) or not str(call.get("question") or ""):
                raise ValueError(f"task {task_id} has an invalid call")
            if "baseline_expected_status" not in call or "target_expected_status" not in call:
                raise ValueError(f"task {task_id} must freeze baseline and target status")
            if call.get("module_path") and call.get("scope") != "module":
                raise ValueError(f"task {task_id} module_path calls must use module scope")
            recovery = call.get("target_recovery")
            if recovery is not None:
                if not isinstance(recovery, dict) or recovery.get("tool") != "docs_status":
                    raise ValueError(f"task {task_id} has an invalid target recovery")
                retry = recovery.get("retry")
                if not isinstance(retry, dict) or not str(retry.get("question") or ""):
                    raise ValueError(f"task {task_id} target recovery requires a retry")
                if "target_expected_status" not in retry:
                    raise ValueError(f"task {task_id} retry requires a target status")
                if retry.get("module_path") and retry.get("scope") != "module":
                    raise ValueError(f"task {task_id} retry module_path requires module scope")
        if task.get("class") == "cross_module":
            for call in calls:
                if call.get("scope") != "all" or call.get("module_path") or call.get("module"):
                    raise ValueError(f"cross-module task {task_id} must use unfiltered all scope")
        if task.get("class") == "module_plus_project":
            scopes = {
                (str(call.get("scope") or ""), str(call.get("module_path") or ""))
                for call in calls
            }
            if not any(scope == "module" and module_path for scope, module_path in scopes):
                raise ValueError(f"task {task_id} is missing its module-scoped call")
            if ("project", "") not in scopes:
                raise ValueError(f"task {task_id} is missing its project-scoped call")
        merged_tasks.append(task)

    return {
        "schema_version": 1,
        "protocol": "agent-developer-v1",
        "target_metrics": target_metrics,
        "tasks": merged_tasks,
    }


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


def _source_paths(payload: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    rows = payload.get("sources") or ()
    if not isinstance(rows, list):
        return ()
    result: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            path = str(row.get("path_or_url") or "").strip()
            if path:
                result.append(path)
    return tuple(result)


def _recommended_action(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    action = payload.get("recommended_next_action") or payload.get("next_action") or {}
    return action if isinstance(action, dict) else {}


def _matches_sources(actual: tuple[str, ...], expected: list[Any] | tuple[Any, ...] | None) -> bool:
    required = tuple(str(value) for value in (expected or ()) if str(value))
    return not required or all(required_path in actual for required_path in required)


def _module_candidate_paths(payload: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    rows = payload.get("module_candidates")
    if not isinstance(rows, list):
        return ()
    return tuple(
        str(row.get("module_path") or "").strip()
        for row in rows[:8]
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    )


def _trajectory_context_calls(task: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for call in task.get("calls") or []:
        if not isinstance(call, dict):
            continue
        calls.append(call)
        recovery = call.get("target_recovery")
        retry = recovery.get("retry") if isinstance(recovery, dict) else None
        if isinstance(retry, dict):
            calls.append(retry)
    return calls


def _scope_record(call: dict[str, Any]) -> dict[str, str]:
    if str(call.get("mode") or "") == "dependency":
        return {"scope": "dependency"}
    row = {"scope": str(call.get("scope") or "")}
    if call.get("module_path"):
        row["module_path"] = str(call["module_path"])
    elif call.get("module"):
        row["module"] = str(call["module"])
    return row


def _context_args(call: dict[str, Any], project: Path) -> dict[str, Any]:
    args: dict[str, Any] = {
        "question": str(call["question"]),
        "project_path": str(project),
        "mode": call.get("mode"),
        "delivery_strategy": "bounded_direct",
        "prepare_project_docs": False,
    }
    for key in (
        "scope",
        "module",
        "module_path",
        "library",
        "libraries",
        "ecosystem",
        "version",
        "packet_tokens",
    ):
        if call.get(key) is not None:
            args[key] = call[key]
    return args


def _resolve_expected(value: Any, project: Path) -> Any:
    if value == "$PROJECT_PATH":
        return str(project)
    if isinstance(value, dict):
        return {key: _resolve_expected(item, project) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_expected(item, project) for item in value]
    return value


def _edit_authorized(payload: dict[str, Any]) -> bool:
    if payload.get("edit_ready") is True:
        return True
    return any(
        payload.get(key) not in (None, {}, [])
        for key in (
            "implementation_guidance",
            "invariants",
            "targets",
            "acceptance_conditions",
            "forbidden_changes",
        )
    )


def _call_matches_target(
    call: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    project: Path | None = None,
) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("status") or "") != str(call.get("target_expected_status") or ""):
        return False
    target_sources = (
        call.get("target_required_sources")
        if "target_required_sources" in call
        else call.get("required_sources")
    )
    if not _matches_sources(_source_paths(payload), target_sources):
        return False
    action = _recommended_action(payload)
    target_tool_value = (
        call.get("target_next_action_tool")
        if "target_next_action_tool" in call
        else call.get("baseline_next_action_tool")
    )
    target_tool = str(target_tool_value or "")
    if target_tool and str(action.get("tool") or "") != target_tool:
        return False
    if "target_next_action_arguments" in call:
        if project is None:
            return False
        expected_arguments = _resolve_expected(
            call.get("target_next_action_arguments"), project
        )
        actual_arguments = (
            action.get("arguments_patch")
            if isinstance(action.get("arguments_patch"), dict)
            else {}
        )
        if actual_arguments != expected_arguments:
            return False
    if "target_requires_confirmation" in call:
        if bool(action.get("requires_confirmation", False)) != bool(
            call.get("target_requires_confirmation")
        ):
            return False
    if "target_expected_edit_ready" in call:
        if _edit_authorized(payload) != bool(call.get("target_expected_edit_ready")):
            return False
    target_confirmation_value = (
        call.get("target_confirmation_reason")
        if "target_confirmation_reason" in call
        else call.get("baseline_confirmation_reason")
    )
    target_confirmation = str(target_confirmation_value or "")
    if target_confirmation and str(
        action.get("confirmation_reason") or payload.get("confirmation_reason") or ""
    ) != target_confirmation:
        return False
    target_operational_reason = str(call.get("target_operational_reason_code") or "")
    if target_operational_reason and str(payload.get("operational_reason_code") or "") != target_operational_reason:
        return False
    target_candidates = tuple(str(value) for value in call.get("target_module_candidates") or ())
    if target_candidates and tuple(sorted(_module_candidate_paths(payload))) != tuple(sorted(target_candidates)):
        return False
    return True


def _status_module_paths(payload: dict[str, Any] | None) -> tuple[str, ...]:
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


def _execute_target_recovery(
    call: dict[str, Any],
    payload: dict[str, Any],
    *,
    service: LibraryDocsService,
    project: Path,
) -> tuple[bool, dict[str, Any] | None, int, tuple[str, ...], list[str]]:
    recovery = call.get("target_recovery")
    if not isinstance(recovery, dict):
        return True, None, 0, (), []

    errors: list[str] = []
    action = _recommended_action(payload)
    expected_tool = str(recovery.get("tool") or "")
    actual_tool = str(action.get("tool") or "")
    if actual_tool != expected_tool:
        errors.append(f"recovery tool {actual_tool!r} != {expected_tool!r}")
        return False, {"tool": actual_tool or None}, 0, (), errors

    arguments = (
        dict(action.get("arguments_patch") or {})
        if isinstance(action.get("arguments_patch"), dict)
        else {}
    )
    status_payload = handle_prefetch_tool(actual_tool, arguments, service)
    module_paths = _status_module_paths(status_payload)
    required_paths = tuple(
        str(value) for value in recovery.get("required_module_paths") or ()
    )
    if required_paths and not set(required_paths).issubset(module_paths):
        errors.append(
            f"recovery module paths {module_paths!r} do not contain {required_paths!r}"
        )

    retry = recovery.get("retry")
    retry_payload: dict[str, Any] | None = None
    retry_paths: tuple[str, ...] = ()
    contamination: tuple[str, ...] = ()
    retry_ok = False
    if isinstance(retry, dict):
        raw_retry = handle_context_tool(
            "get_docs_context", _context_args(retry, project), service
        )
        retry_payload = raw_retry if isinstance(raw_retry, dict) else {}
        retry_paths = _source_paths(retry_payload)
        retry_ok = _call_matches_target(retry, retry_payload, project=project)
        if not retry_ok:
            errors.append(
                "exact module_path retry did not match its target contract"
            )
        forbidden = tuple(
            str(value) for value in retry.get("forbidden_sources") or ()
        )
        contamination = tuple(
            path for path in retry_paths if path in forbidden
        )
        if contamination:
            errors.append(
                f"retry forbidden source contamination: {contamination!r}"
            )
    else:
        errors.append("recovery retry is missing")

    report = {
        "tool": actual_tool or None,
        "arguments": arguments,
        "module_paths": list(module_paths),
        "retry": {
            "status": (
                str(retry_payload.get("status") or "")
                if isinstance(retry_payload, dict)
                else None
            ),
            "sources": list(retry_paths),
            "target_closed": retry_ok,
        },
    }
    return not errors, report, 1 if isinstance(retry, dict) else 0, contamination, errors


def _target_metrics(
    protocol: dict[str, Any],
    task_results: list[dict[str, Any]],
    *,
    false_supported: int,
    contamination: int,
) -> tuple[dict[str, Any], list[str]]:
    def rate(rows: list[dict[str, Any]]) -> float:
        return (
            sum(bool(row.get("target_closed")) for row in rows) / len(rows)
            if rows else 1.0
        )

    module_only = [
        row for row in task_results if row.get("class") == "module_only"
    ]
    module_project = [
        row for row in task_results if row.get("class") == "module_plus_project"
    ]
    cross_module = [
        row for row in task_results if row.get("class") == "cross_module"
    ]
    recovery = [
        row for row in task_results if row.get("class") == "recovery"
    ]
    actual = {
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "module_only_expected_evidence_rate": rate(module_only),
        "module_project_max_context_calls": max(
            (int(row.get("context_call_count") or 0) for row in module_project),
            default=0,
        ),
        "cross_module_scope_accuracy": rate(cross_module),
        "recovery_contract_accuracy": rate(recovery),
    }
    expected = protocol.get("target_metrics") or {}
    errors: list[str] = []
    for key, expected_value in expected.items():
        if key not in actual:
            errors.append(f"unknown target metric: {key}")
            continue
        actual_value = actual[key]
        if key == "module_project_max_context_calls":
            matches = int(actual_value) <= int(expected_value)
        elif isinstance(expected_value, float):
            matches = abs(float(actual_value) - expected_value) <= 1e-9
        else:
            matches = actual_value == expected_value
        if not matches:
            errors.append(
                f"target metric {key}: actual={actual_value!r} "
                f"expected={expected_value!r}"
            )
    return actual, errors


def run_protocol() -> dict[str, Any]:
    protocol = _load_protocol()
    errors: list[str] = []
    target_gaps: list[dict[str, str]] = []
    task_results: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    false_supported = 0
    contamination = 0
    previous_home = os.environ.get("DOCMANCER_HOME")

    try:
        for task in protocol["tasks"]:
            task_id = str(task["id"])
            class_counts[str(task["class"])] += 1
            fixture = PROJECTS_ROOT / str(task["fixture"])
            if not fixture.is_dir():
                errors.append(f"{task_id}: fixture missing: {fixture.relative_to(REPO_ROOT)}")
                continue
            with TemporaryDirectory(prefix=f"docatlas-agent-dev-{task_id}-") as raw_tmp:
                tmp = Path(raw_tmp)
                project = tmp / "project"
                shutil.copytree(fixture, project)
                os.environ["DOCMANCER_HOME"] = str(tmp / "home")
                working_path = (project / str(task["working_path"])).resolve()
                try:
                    working_path.relative_to(project.resolve())
                except ValueError:
                    errors.append(f"{task_id}: working_path escapes the fixture")
                    continue
                if not working_path.is_file():
                    errors.append(f"{task_id}: working_path is missing: {working_path}")
                    continue
                module_paths = [
                    str(row.get("module_path") or "")
                    for row in task.get("required_scopes") or ()
                    if isinstance(row, dict) and row.get("module_path")
                ]
                if (
                    task.get("class")
                    in {"module_only", "module_plus_project", "negative_contamination"}
                    and module_paths
                    and not any(
                        working_path.is_relative_to((project / path).resolve())
                        for path in module_paths
                    )
                ):
                    errors.append(
                        f"{task_id}: working_path is outside required module scopes"
                    )
                    continue

                service = _service(tmp)
                sync = service.sync_project_docs(str(project), with_vectors=False)
                if getattr(sync, "status", None) != "success":
                    errors.append(f"{task_id}: sync status={getattr(sync, 'status', None)!r}")
                    continue

                mutation = task.get("mutation_before_calls")
                if isinstance(mutation, dict):
                    target = project / str(mutation.get("path") or "")
                    if not target.is_file():
                        errors.append(f"{task_id}: mutation target missing: {target}")
                        continue
                    with target.open("a", encoding="utf-8") as stream:
                        stream.write(str(mutation.get("append") or ""))

                forbidden = tuple(
                    str(value) for value in task.get("forbidden_sources", ()) if str(value)
                )
                actual_calls: list[dict[str, Any]] = []
                task_target_closed = True
                context_call_count = 0
                for index, call in enumerate(task["calls"], 1):
                    payload = handle_context_tool(
                        "get_docs_context", _context_args(call, project), service
                    )
                    context_call_count += 1
                    actual_status = (
                        str(payload.get("status") or "") if isinstance(payload, dict) else ""
                    )
                    baseline_status = str(call["baseline_expected_status"])
                    paths = _source_paths(payload)
                    action = _recommended_action(payload)
                    action_tool = str(action.get("tool") or "")
                    confirmation_reason = (
                        str(
                            action.get("confirmation_reason")
                            or (payload or {}).get("confirmation_reason")
                            or ""
                        )
                        if isinstance(payload, dict)
                        else ""
                    )

                    initial_target_closed = _call_matches_target(
                        call, payload, project=project
                    )
                    (
                        recovery_closed,
                        recovery_report,
                        retry_context_calls,
                        retry_contamination,
                        recovery_errors,
                    ) = _execute_target_recovery(
                        call,
                        payload if isinstance(payload, dict) else {},
                        service=service,
                        project=project,
                    )
                    context_call_count += retry_context_calls
                    for error in recovery_errors:
                        errors.append(f"{task_id}:{index}: {error}")
                    if retry_contamination:
                        contamination += 1
                    target_closed = initial_target_closed and recovery_closed
                    if actual_status != baseline_status:
                        if not initial_target_closed:
                            errors.append(
                                f"{task_id}:{index}: neither frozen baseline nor target status matched; "
                                f"actual={actual_status!r} baseline={baseline_status!r} "
                                f"target={call.get('target_expected_status')!r}"
                            )
                    elif not initial_target_closed:
                        if baseline_status == "ok" and not paths:
                            errors.append(f"{task_id}:{index}: ok without source-backed evidence")
                        if not _matches_sources(paths, call.get("required_sources")):
                            errors.append(
                                f"{task_id}:{index}: required baseline source missing; paths={paths!r}"
                            )
                        baseline_tool = str(call.get("baseline_next_action_tool") or "")
                        if baseline_tool and action_tool != baseline_tool:
                            errors.append(
                                f"{task_id}:{index}: recovery tool drift "
                                f"{action_tool!r} != {baseline_tool!r}"
                            )
                        baseline_confirmation = str(call.get("baseline_confirmation_reason") or "")
                        if baseline_confirmation and confirmation_reason != baseline_confirmation:
                            errors.append(
                                f"{task_id}:{index}: confirmation drift "
                                f"{confirmation_reason!r} != {baseline_confirmation!r}"
                            )
                    contaminated = sorted(source for source in paths if source in forbidden)
                    if contaminated:
                        contamination += 1
                        errors.append(
                            f"{task_id}:{index}: forbidden source contamination: {contaminated!r}"
                        )
                    if baseline_status != "ok" and actual_status == "ok" and not target_closed:
                        false_supported += 1
                        errors.append(f"{task_id}:{index}: unexpected supported result outside target contract")

                    task_target_closed = task_target_closed and target_closed
                    if not target_closed:
                        target_gaps.append(
                            {
                                "task_id": task_id,
                                "gap": str(task.get("known_gap") or "target_not_closed"),
                                "actual_status": actual_status,
                                "target_status": str(call.get("target_expected_status") or ""),
                            }
                        )
                    actual_calls.append(
                        {
                            "question": str(call["question"]),
                            "status": actual_status,
                            "sources": list(paths),
                            "next_action_tool": action_tool or None,
                            "next_action_arguments": (
                                action.get("arguments_patch")
                                if isinstance(action.get("arguments_patch"), dict)
                                else {}
                            ),
                            "requires_confirmation": bool(
                                action.get("requires_confirmation", False)
                            ),
                            "edit_authorized": (
                                _edit_authorized(payload)
                                if isinstance(payload, dict)
                                else False
                            ),
                            "confirmation_reason": confirmation_reason or None,
                            "operational_reason_code": (
                                str((payload or {}).get("operational_reason_code") or "") or None
                                if isinstance(payload, dict) else None
                            ),
                            "module_candidates": list(_module_candidate_paths(payload)),
                            "recovery": recovery_report,
                            "target_closed": target_closed,
                        }
                    )

                task_results.append(
                    {
                        "task_id": task_id,
                        "class": str(task["class"]),
                        "known_gap": task.get("known_gap"),
                        "target_closed": task_target_closed,
                        "context_call_count": context_call_count,
                        "calls": actual_calls,
                    }
                )
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home

    target_closed_tasks = sum(1 for item in task_results if item["target_closed"])
    target_metrics, target_metric_errors = _target_metrics(
        protocol,
        task_results,
        false_supported=false_supported,
        contamination=contamination,
    )
    target_ok = (
        not errors
        and target_closed_tasks == len(protocol["tasks"])
        and not target_gaps
        and false_supported == 0
        and contamination == 0
        and not target_metric_errors
    )
    return {
        "schema_version": 1,
        "protocol": "agent-developer-v1",
        "baseline_ok": not errors,
        "target_ok": target_ok,
        "task_count": len(protocol["tasks"]),
        "executed_task_count": len(task_results),
        "target_closed_tasks": target_closed_tasks,
        "target_gap_count": len(target_gaps),
        "target_gaps": target_gaps,
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "target_metrics": target_metrics,
        "target_metrics_expected": protocol["target_metrics"],
        "target_metric_errors": target_metric_errors,
        "class_counts": dict(sorted(class_counts.items())),
        "errors": errors,
        "tasks": task_results,
    }


def main() -> int:
    report = run_protocol()
    for task in report["tasks"]:
        state = "TARGET-CLOSED" if task["target_closed"] else "BASELINE-ONLY"
        gap = (
            f" gap={task['known_gap']}" if not task["target_closed"] and task.get("known_gap") else ""
        )
        print(f"{task['task_id']}: {state}{gap}")
    print(
        f"target closure: {report['target_closed_tasks']}/{report['task_count']} tasks; "
        f"named target gaps={report['target_gap_count']}; "
        f"false-supported={report['false_supported']}; "
        f"forbidden-source-contamination={report['forbidden_source_contamination']}"
    )
    for gap in report["target_gaps"]:
        print(
            f"- target gap {gap['task_id']}: {gap['gap']} "
            f"actual={gap['actual_status']} target={gap['target_status']}"
        )
    for error in report.get("target_metric_errors", []):
        print(f"- metric error: {error}")
    if not report["target_ok"]:
        print("Agent Developer Protocol v1: TARGET FAIL")
        for error in report["errors"]:
            print(f"- {error}")
        return 1
    print("Agent Developer Protocol v1: TARGET PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
