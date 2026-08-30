#!/usr/bin/env python3
"""Provider-free coding-agent trajectory gate for Project Docs.

The public task file is deliberately separated from evaluator-only oracle data so
future model-backed runs cannot see expected scopes, source identities, or tool
queries. The gate executes reviewed context and recovery calls, validates their
complete target contracts, and fails closed on scope, evidence, action, budget,
metric, or edit-readiness drift.
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
_PROJECT_PATH_MARKER = "$PROJECT_PATH"
_REMOVED_REQUEST_FIELDS = {"delivery_strategy", "packet_tokens", "details"}


def _scope_signature(call: dict[str, Any]) -> dict[str, str]:
    scope = str(call.get("scope") or "").strip()
    if not scope and str(call.get("mode") or "") == "dependency":
        scope = "dependency"
    if not scope:
        raise ValueError("agent developer context calls require an explicit scope")
    signature = {"scope": scope}
    for key in ("module", "module_path"):
        value = str(call.get(key) or "").strip()
        if value:
            signature[key] = value
    return signature


def _planned_context_calls(task: dict[str, Any]) -> list[dict[str, Any]]:
    calls = list(task.get("calls") or [])
    for call in task.get("calls") or []:
        recovery = call.get("target_recovery")
        retry = recovery.get("retry") if isinstance(recovery, dict) else None
        if isinstance(retry, dict):
            calls.append(retry)
    return calls


def _safe_fixture_path(fixture: Path, raw_path: Any) -> Path | None:
    raw = str(raw_path or "").replace("\\", "/")
    value = raw.strip("/")
    parts = Path(value).parts
    if (
        not value or raw.startswith("/") or ".." in parts
        or (parts and str(parts[0]).endswith(":"))
    ):
        return None
    candidate = (fixture / value).resolve()
    try:
        candidate.relative_to(fixture.resolve())
    except ValueError:
        return None
    return candidate


def _load_protocol() -> dict[str, Any]:
    public = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    if public.get("schema_version") != 1 or public.get("protocol") != "agent-developer-v1":
        raise ValueError("agent developer public protocol identity mismatch")
    if oracle.get("schema_version") != 1 or oracle.get("protocol") != "agent-developer-v1-oracle":
        raise ValueError("agent developer oracle protocol identity mismatch")
    public_tasks = public.get("tasks")
    trajectories = oracle.get("trajectories")
    if not isinstance(public_tasks, list) or not public_tasks:
        raise ValueError("agent developer protocol requires a non-empty tasks list")
    if not isinstance(trajectories, list) or not trajectories:
        raise ValueError("agent developer protocol requires evaluator trajectories")

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
        if len(calls) > int(task.get("max_get_docs_context_calls") or 0):
            raise ValueError(f"task {task_id} exceeds its context-call budget")
        if not isinstance(task.get("required_scopes"), list) or not task["required_scopes"]:
            raise ValueError(f"task {task_id} requires evaluator-owned scope expectations")
        for call in calls:
            if not isinstance(call, dict) or not str(call.get("question") or ""):
                raise ValueError(f"task {task_id} has an invalid call")
            if "baseline_expected_status" not in call or "target_expected_status" not in call:
                raise ValueError(f"task {task_id} must freeze baseline and target status")
            if call.get("module_path") and call.get("scope") != "module":
                raise ValueError(f"task {task_id} module_path calls must use module scope")
            recovery = call.get("target_recovery")
            if recovery is not None:
                if not isinstance(recovery, dict) or not isinstance(recovery.get("retry"), dict):
                    raise ValueError(f"task {task_id} target_recovery requires a retry call")
                retry = recovery["retry"]
                if not str(retry.get("question") or ""):
                    raise ValueError(f"task {task_id} recovery retry requires a question")
                if retry.get("module_path") and retry.get("scope") != "module":
                    raise ValueError(f"task {task_id} recovery module_path must use module scope")

        planned_calls = _planned_context_calls(task)
        if len(planned_calls) > int(task.get("max_get_docs_context_calls") or 0):
            raise ValueError(f"task {task_id} recovery exceeds its context-call budget")
        required_scopes = [
            {str(key): str(value) for key, value in row.items() if value not in (None, "")}
            for row in task["required_scopes"]
            if isinstance(row, dict)
        ]
        planned_scopes = [_scope_signature(call) for call in planned_calls]
        if required_scopes != planned_scopes:
            raise ValueError(
                f"task {task_id} required_scopes do not match its planned calls: "
                f"required={required_scopes!r} planned={planned_scopes!r}"
            )

        fixture = PROJECTS_ROOT / str(task.get("fixture") or "")
        if not fixture.is_dir():
            raise ValueError(f"task {task_id} fixture is missing: {fixture}")
        working_path = _safe_fixture_path(fixture, task.get("working_path"))
        if working_path is None or not working_path.is_file():
            raise ValueError(f"task {task_id} working_path is missing or unsafe")
        exact_module_paths = [
            str(row.get("module_path") or "")
            for row in required_scopes
            if str(row.get("module_path") or "")
        ]
        module_roots = [
            _safe_fixture_path(fixture, module_path)
            for module_path in exact_module_paths
        ]
        if any(module_root is None or not module_root.is_dir() for module_root in module_roots):
            raise ValueError(f"task {task_id} has an unsafe or missing exact module scope")
        if exact_module_paths and not any(
            working_path.is_relative_to(module_root)
            for module_root in module_roots
            if module_root is not None
        ):
            raise ValueError(
                f"task {task_id} working_path is outside every exact module scope"
            )
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

    target_metrics = oracle.get("target_metrics") or {}
    if not isinstance(target_metrics, dict) or not target_metrics:
        raise ValueError("agent developer protocol requires target metrics")
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


def _resolved_expected(value: Any, project_path: str) -> Any:
    if value == _PROJECT_PATH_MARKER:
        return project_path
    if isinstance(value, dict):
        return {
            str(key): _resolved_expected(child, project_path)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_resolved_expected(child, project_path) for child in value]
    return value


def _authorizes_edit(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("edit_ready") is True:
        return True
    return any(payload.get(key) not in (None, {}, []) for key in (
        "implementation_guidance", "invariants", "targets", "acceptance_conditions",
    ))


def _call_target_mismatches(
    call: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    project_path: str,
) -> list[str]:
    mismatches: list[str] = []
    if not isinstance(payload, dict):
        return ["payload is not an object"]
    if str(payload.get("status") or "") != str(call.get("target_expected_status") or ""):
        mismatches.append(
            f"status={payload.get('status')!r} expected={call.get('target_expected_status')!r}"
        )
    target_sources = (
        call.get("target_required_sources")
        if "target_required_sources" in call
        else call.get("required_sources")
    )
    if not _matches_sources(_source_paths(payload), target_sources):
        mismatches.append(f"required sources missing from {_source_paths(payload)!r}")
    action = _recommended_action(payload)
    target_tool_value = (
        call.get("target_next_action_tool")
        if "target_next_action_tool" in call
        else call.get("baseline_next_action_tool")
    )
    target_tool = str(target_tool_value or "")
    if target_tool and str(action.get("tool") or "") != target_tool:
        mismatches.append(
            f"next action tool={action.get('tool')!r} expected={target_tool!r}"
        )
    if "target_next_action_arguments" in call:
        expected_arguments = _resolved_expected(
            call.get("target_next_action_arguments") or {}, project_path,
        )
        expected_arguments = {
            key: value
            for key, value in expected_arguments.items()
            if key not in _REMOVED_REQUEST_FIELDS
        }
        actual_arguments = action.get("arguments_patch")
        if actual_arguments != expected_arguments:
            mismatches.append(
                f"next action arguments={actual_arguments!r} expected={expected_arguments!r}"
            )
    target_confirmation_value = (
        call.get("target_confirmation_reason")
        if "target_confirmation_reason" in call
        else call.get("baseline_confirmation_reason")
    )
    target_confirmation = str(target_confirmation_value or "")
    if target_confirmation and str(
        action.get("confirmation_reason") or payload.get("confirmation_reason") or ""
    ) != target_confirmation:
        mismatches.append(f"confirmation reason does not match {target_confirmation!r}")
    if "target_requires_confirmation" in call:
        actual_confirmation = bool(
            action.get("requires_confirmation")
            if "requires_confirmation" in action
            else payload.get("requires_confirmation")
        )
        if actual_confirmation is not bool(call["target_requires_confirmation"]):
            mismatches.append(
                f"requires_confirmation={actual_confirmation!r} "
                f"expected={bool(call['target_requires_confirmation'])!r}"
            )
    if "target_auto_execute" in call:
        if action.get("auto_execute") is not call["target_auto_execute"]:
            mismatches.append(
                f"auto_execute={action.get('auto_execute')!r} "
                f"expected={call['target_auto_execute']!r}"
            )
    if "target_edit_ready" in call:
        actual_edit_ready = _authorizes_edit(payload)
        if actual_edit_ready is not bool(call["target_edit_ready"]):
            mismatches.append(
                f"edit authorization={actual_edit_ready!r} "
                f"expected={bool(call['target_edit_ready'])!r}"
            )
    target_operational_reason = str(call.get("target_operational_reason_code") or "")
    if target_operational_reason and str(payload.get("operational_reason_code") or "") != target_operational_reason:
        mismatches.append(
            f"operational reason={payload.get('operational_reason_code')!r} "
            f"expected={target_operational_reason!r}"
        )
    target_candidates = tuple(str(value) for value in call.get("target_module_candidates") or ())
    if target_candidates and tuple(sorted(_module_candidate_paths(payload))) != tuple(sorted(target_candidates)):
        mismatches.append(
            f"module candidates={_module_candidate_paths(payload)!r} "
            f"expected={target_candidates!r}"
        )
    return mismatches


def _call_matches_target(
    call: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    project_path: str,
) -> bool:
    return not _call_target_mismatches(call, payload, project_path=project_path)


def _context_args(call: dict[str, Any], project: Path) -> dict[str, Any]:
    args = {
        "question": str(call["question"]),
        "project_path": str(project),
        "mode": call.get("mode"),
    }
    for key in (
        "scope", "module", "module_path", "library", "libraries", "ecosystem",
        "version",
    ):
        if call.get(key) is not None:
            args[key] = call[key]
    return args


def _status_module_paths(payload: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    project = payload.get("project")
    project_docs = project.get("project_docs") if isinstance(project, dict) else None
    rows = project_docs.get("modules") if isinstance(project_docs, dict) else None
    if not isinstance(rows, list):
        return ()
    return tuple(
        str(row.get("module_path") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    )


def _execute_target_recovery(
    call: dict[str, Any],
    payload: dict[str, Any],
    *,
    service: LibraryDocsService,
    project: Path,
) -> tuple[bool, dict[str, Any], int, int]:
    recovery = call.get("target_recovery")
    if not isinstance(recovery, dict):
        return True, {}, 0, 0

    action = _recommended_action(payload)
    action_tool = str(action.get("tool") or "")
    action_arguments = action.get("arguments_patch")
    errors: list[str] = []
    status_payload: dict[str, Any] | None = None
    if action_tool != "docs_status" or not isinstance(action_arguments, dict):
        errors.append("recovery requires an executable docs_status action")
    else:
        status_payload = handle_prefetch_tool(
            "docs_status", dict(action_arguments), service,
        )

    retry = recovery.get("retry")
    retry_payload: dict[str, Any] | None = None
    retry_contamination = 0
    if not isinstance(retry, dict):
        errors.append("recovery retry contract is missing")
    else:
        retry_module_path = str(retry.get("module_path") or "")
        first_candidates = _module_candidate_paths(payload)
        if retry_module_path not in first_candidates:
            errors.append(
                f"retry module_path={retry_module_path!r} was not returned as a candidate"
            )
        retry_payload = handle_context_tool(
            "get_docs_context", _context_args(retry, project), service,
        )
        retry_mismatches = _call_target_mismatches(
            retry, retry_payload, project_path=str(project),
        )
        errors.extend(f"retry {message}" for message in retry_mismatches)
        retry_forbidden = tuple(
            str(value) for value in retry.get("forbidden_sources") or () if str(value)
        )
        contaminated = sorted(
            source for source in _source_paths(retry_payload) if source in retry_forbidden
        )
        if contaminated:
            retry_contamination = 1
            errors.append(f"retry forbidden source contamination: {contaminated!r}")

    return (
        not errors,
        {
            "errors": errors,
            "docs_status_modules": list(_status_module_paths(status_payload)),
            "retry": {
                "status": str((retry_payload or {}).get("status") or ""),
                "sources": list(_source_paths(retry_payload)),
                "module_path": str((retry or {}).get("module_path") or ""),
            } if isinstance(retry, dict) else None,
        },
        1 if isinstance(retry, dict) else 0,
        retry_contamination,
    )


def run_protocol() -> dict[str, Any]:
    protocol = _load_protocol()
    errors: list[str] = []
    target_gaps: list[dict[str, str]] = []
    task_results: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    false_supported = 0
    contamination = 0
    action_contract_total = 0
    action_contract_passed = 0
    unsupported_total = 0
    unsupported_non_edit_ready = 0
    previous_home = os.environ.get("DOCATLAS_HOME")

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
                os.environ["DOCATLAS_HOME"] = str(tmp / "home")
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
                task_recovery_contract_ok = True
                context_call_count = 0
                for index, call in enumerate(task["calls"], 1):
                    payload = handle_context_tool(
                        "get_docs_context", _context_args(call, project), service,
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

                    target_mismatches = _call_target_mismatches(
                        call, payload, project_path=str(project),
                    )
                    target_closed = not target_mismatches
                    recovery_result: dict[str, Any] = {}
                    if target_closed and isinstance(call.get("target_recovery"), dict):
                        (
                            recovery_ok,
                            recovery_result,
                            recovery_context_calls,
                            recovery_contamination,
                        ) = _execute_target_recovery(
                            call, payload, service=service, project=project,
                        )
                        context_call_count += recovery_context_calls
                        contamination += recovery_contamination
                        target_closed = target_closed and recovery_ok
                        task_recovery_contract_ok = task_recovery_contract_ok and recovery_ok
                        if not recovery_ok:
                            errors.extend(
                                f"{task_id}:{index}: {message}"
                                for message in recovery_result.get("errors") or []
                            )

                    if call.get("target_next_action_tool"):
                        action_contract_total += 1
                        if target_closed:
                            action_contract_passed += 1
                    if str(call.get("target_expected_status") or "") == "insufficient_evidence":
                        unsupported_total += 1
                        if not _authorizes_edit(payload):
                            unsupported_non_edit_ready += 1

                    if actual_status != baseline_status:
                        if not target_closed:
                            errors.append(
                                f"{task_id}:{index}: neither frozen baseline nor target status matched; "
                                f"actual={actual_status!r} baseline={baseline_status!r} "
                                f"target={call.get('target_expected_status')!r}; "
                                f"mismatches={target_mismatches!r}"
                            )
                    elif not target_closed:
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
                                if isinstance(action.get("arguments_patch"), dict) else None
                            ),
                            "requires_confirmation": (
                                action.get("requires_confirmation")
                                if "requires_confirmation" in action else None
                            ),
                            "confirmation_reason": confirmation_reason or None,
                            "edit_authorized": _authorizes_edit(payload),
                            "operational_reason_code": (
                                str((payload or {}).get("operational_reason_code") or "") or None
                                if isinstance(payload, dict) else None
                            ),
                            "module_candidates": list(_module_candidate_paths(payload)),
                            "recovery": recovery_result or None,
                            "target_closed": target_closed,
                        }
                    )

                if context_call_count > int(task.get("max_get_docs_context_calls") or 0):
                    errors.append(
                        f"{task_id}: executed {context_call_count} context calls above budget "
                        f"{task.get('max_get_docs_context_calls')}"
                    )
                    task_target_closed = False

                task_results.append(
                    {
                        "task_id": task_id,
                        "class": str(task["class"]),
                        "known_gap": task.get("known_gap"),
                        "target_closed": task_target_closed,
                        "scope_contract_ok": True,
                        "recovery_contract_ok": task_recovery_contract_ok,
                        "context_call_count": context_call_count,
                        "calls": actual_calls,
                    }
                )
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home

    target_closed_tasks = sum(1 for item in task_results if item["target_closed"])
    module_only = [item for item in task_results if item["class"] == "module_only"]
    module_project = [item for item in task_results if item["class"] == "module_plus_project"]
    cross_module = [item for item in task_results if item["class"] == "cross_module"]
    module_dependency = [
        item for item in task_results if item["class"] == "module_plus_dependency"
    ]

    def _closed_rate(items: list[dict[str, Any]]) -> float:
        return (
            sum(bool(item["target_closed"]) for item in items) / len(items)
            if items else 1.0
        )

    metrics = {
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "module_only_expected_evidence_rate": _closed_rate(module_only),
        "module_project_max_context_calls": max(
            (int(item["context_call_count"]) for item in module_project), default=0,
        ),
        "cross_module_scope_accuracy": (
            sum(bool(item["scope_contract_ok"]) for item in cross_module) / len(cross_module)
            if cross_module else 1.0
        ),
        "module_dependency_scope_accuracy": (
            sum(bool(item["scope_contract_ok"]) for item in module_dependency)
            / len(module_dependency)
            if module_dependency else 1.0
        ),
        "recovery_contract_accuracy": (
            action_contract_passed / action_contract_total if action_contract_total else 1.0
        ),
        "unsupported_edit_ready_false_rate": (
            unsupported_non_edit_ready / unsupported_total if unsupported_total else 1.0
        ),
    }
    for name, expected in protocol["target_metrics"].items():
        actual = metrics.get(name)
        if actual is None:
            errors.append(f"target metric {name!r} is not computed")
            continue
        if name.endswith("_max_context_calls"):
            if int(actual) > int(expected):
                errors.append(f"target metric {name}={actual!r} exceeds {expected!r}")
        elif abs(float(actual) - float(expected)) > 1e-9:
            errors.append(f"target metric {name}={actual!r} expected {expected!r}")

    target_ok = (
        not errors
        and target_closed_tasks == len(protocol["tasks"])
        and not target_gaps
        and false_supported == 0
        and contamination == 0
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
        "metrics": metrics,
        "target_metrics": protocol["target_metrics"],
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
    if report.get("metrics"):
        print("target metrics: " + json.dumps(report["metrics"], sort_keys=True))
    for gap in report["target_gaps"]:
        print(
            f"- target gap {gap['task_id']}: {gap['gap']} "
            f"actual={gap['actual_status']} target={gap['target_status']}"
        )
    if not report["target_ok"]:
        print("Agent Developer Protocol v1: TARGET FAIL")
        for error in report["errors"]:
            print(f"- {error}")
        return 1
    print("Agent Developer Protocol v1: TARGET PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
