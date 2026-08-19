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
        "target_metrics": oracle.get("target_metrics") or {},
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


def _call_matches_target(call: dict[str, Any], payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("status") or "") != str(call.get("target_expected_status") or ""):
        return False
    if not _matches_sources(_source_paths(payload), call.get("target_required_sources")):
        return False
    action = _recommended_action(payload)
    target_tool = str(call.get("target_next_action_tool") or "")
    if target_tool and str(action.get("tool") or "") != target_tool:
        return False
    target_confirmation = str(call.get("target_confirmation_reason") or "")
    if target_confirmation and str(
        action.get("confirmation_reason") or payload.get("confirmation_reason") or ""
    ) != target_confirmation:
        return False
    return True


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
                for index, call in enumerate(task["calls"], 1):
                    args = {
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
                    ):
                        if call.get(key) is not None:
                            args[key] = call[key]
                    payload = handle_context_tool("get_docs_context", args, service)
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

                    if actual_status != baseline_status:
                        errors.append(
                            f"{task_id}:{index}: baseline status drift "
                            f"{actual_status!r} != {baseline_status!r}"
                        )
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
                    if baseline_status != "ok" and actual_status == "ok":
                        false_supported += 1
                        errors.append(f"{task_id}:{index}: false-supported baseline negative case")

                    target_closed = _call_matches_target(call, payload)
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
                            "confirmation_reason": confirmation_reason or None,
                            "target_closed": target_closed,
                        }
                    )

                task_results.append(
                    {
                        "task_id": task_id,
                        "class": str(task["class"]),
                        "known_gap": task.get("known_gap"),
                        "target_closed": task_target_closed,
                        "calls": actual_calls,
                    }
                )
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home

    target_closed_tasks = sum(1 for item in task_results if item["target_closed"])
    return {
        "schema_version": 1,
        "protocol": "agent-developer-v1",
        "baseline_ok": not errors,
        "task_count": len(protocol["tasks"]),
        "executed_task_count": len(task_results),
        "target_closed_tasks": target_closed_tasks,
        "target_gap_count": len(target_gaps),
        "target_gaps": target_gaps,
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "class_counts": dict(sorted(class_counts.items())),
        "errors": errors,
        "tasks": task_results,
    }


def main() -> int:
    report = run_protocol()
    for task in report["tasks"]:
        state = "TARGET-CLOSED" if task["target_closed"] else "BASELINE-ONLY"
        gap = f" gap={task['known_gap']}" if task.get("known_gap") else ""
        print(f"{task['task_id']}: {state}{gap}")
    if report["errors"]:
        print("Agent Developer Protocol v1: BASELINE FAIL")
        for error in report["errors"]:
            print(f"- {error}")
        return 1
    print("Agent Developer Protocol v1: BASELINE PASS")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
