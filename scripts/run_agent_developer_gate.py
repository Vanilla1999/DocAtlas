#!/usr/bin/env python3
"""Provider-free coding-agent trajectory gate for Project Docs.

The public task file is deliberately separated from evaluator-only oracle data so
future model-backed runs cannot see expected scopes, source identities, or tool
queries. The gate executes reviewed context and recovery calls, validates their
complete target contracts, and fails closed on scope, evidence, action, budget,
metric, or edit-readiness drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from eval.evidence_quality_v2.runtime import index_project, isolated_service


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
_REMOVED_REQUEST_FIELDS = {"delivery_strategy", "packet_tokens"}
_REQUIRED_MIGRATION_CONTROL_IDS = {"explicit_catalog_module_supported"}


def handle_context_tool(name: str, args: dict[str, Any], service: Any) -> dict[str, Any]:
    """Exercise the advertised schema, ownership check, handler and serialization."""
    return call_docs_tool_payload(name, args, service)


def handle_prefetch_tool(name: str, args: dict[str, Any], service: Any) -> dict[str, Any]:
    return call_docs_tool_payload(name, args, service)


def _scope_signature(call: dict[str, Any]) -> dict[str, str]:
    scope = str(call.get("scope") or "").strip()
    if not scope and (call.get("library") or str(call.get("mode") or "") == "dependency"):
        scope = "dependency"
    if not scope:
        raise ValueError("agent developer context calls require an explicit scope")
    signature = {"scope": scope}
    for key in ("module", "module_path"):
        value = str(call.get(key) or (call.get("rejected_arguments") or {}).get(key) or "").strip()
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
    controls = oracle.get("migration_controls") or []
    if not isinstance(controls, list):
        raise ValueError("migration_controls must be a list")
    control_ids = {str(row.get("id") or "") for row in controls if isinstance(row, dict)}
    if control_ids != _REQUIRED_MIGRATION_CONTROL_IDS:
        raise ValueError("required explicit-membership positive control is missing or replaced")
    if len(control_ids) != len(controls) or "" in control_ids or control_ids & set(task_by_id):
        raise ValueError("migration controls require distinct nonempty IDs")
    for public_task in [*public_tasks, *controls]:
        task_id = str(public_task["id"])
        task = ({**public_task, **oracle_by_id[task_id]}
                if task_id in oracle_by_id else dict(public_task))
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
        "tasks": [task for task in merged_tasks if task["id"] in task_by_id],
        "migration_controls": [task for task in merged_tasks if task["id"] in control_ids],
    }


@contextmanager
def _service(tmp: Path, project: Path):
    """A catalog is input selection; only confirmed preparation creates members.

    The authored no-catalog fixture stays cold so a public read must fail without
    creating storage. No fallback discovery or legacy eager SQLite fixture exists.
    """
    with isolated_service(tmp / "state") as (service, config):
        assert not service.member_storage_policy.app_home.exists()
        if not (project / "docatlas.project-docs.yaml").is_file():
            yield service._cold
            assert not service.member_storage_policy.app_home.exists(), "cold_read_created_storage"
            return
        prepared = index_project(service, config, project)
        assert prepared["indexed_paths"] == prepared["expected_paths"]
        assert not prepared["excluded_or_failed_paths"]
        assert not prepared["unexpected_paths"]
        metrics = prepared["transaction_metrics"]
        assert metrics["members"] == metrics["new_count"] == len(prepared["expected_paths"])
        assert metrics["changed_count"] == metrics["sources_deleted"] == 0
        yield service


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
    # Any explicit grant or malformed non-false grant is incompatible with a
    # retrieval-only result; edit_ready=False cannot conceal an alternate field.
    if any(payload.get(key) not in (None, False) for key in (
        "edit_ready", "mutation_ready", "mutation_authorized", "edit_authorized",
        "authorized", "authorization_granted", "can_edit",
    )):
        return True
    return any(payload.get(key) not in (None, {}, [], "") for key in (
        "implementation_guidance", "invariants", "targets", "acceptance_conditions",
        "authorized_actions", "mutation_actions",
    ))


def _source_fidelity_mismatches(payload: dict[str, Any], project: Path) -> list[str]:
    """Compare delivered quotes with original fixture bytes, not retrieval output."""
    errors: list[str] = []
    for row in payload.get("sources") or ():
        if not isinstance(row, dict):
            errors.append("source_fidelity: source is not an object")
            continue
        source = _safe_fixture_path(project, row.get("path_or_url"))
        if source is None or not source.is_file():
            errors.append("source_fidelity: source is outside the authored fixture")
            continue
        original = source.read_bytes().decode("utf-8")
        lines = original.splitlines(keepends=True)
        snippet = row.get("snippet")
        start, end = row.get("line_start"), row.get("line_end")
        if (not isinstance(snippet, str) or not snippet.strip()
                or type(start) is not int or type(end) is not int
                or not 1 <= start <= end <= len(lines)
                or snippet not in "".join(lines[start - 1:end])):
            errors.append("source_fidelity: quote or coordinates changed")
        identity = "local:" + hashlib.sha256(str(project.resolve()).encode()).hexdigest()
        if row.get("project_identity") != identity:
            errors.append("source_fidelity: project identity changed")
        digest = row.get("content_sha256")
        # content_sha256 identifies a bound candidate; it is not the file digest.
        if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            errors.append("source_fidelity: missing candidate hash")
        if not row.get("evidence_id") or not row.get("version_binding"):
            errors.append("source_fidelity: missing source identity")
    return errors


def _call_target_mismatches(
    call: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    project_path: str,
) -> list[str]:
    mismatches: list[str] = []
    if not isinstance(payload, dict):
        return ["payload is not an object"]
    if call.get("target_error_reason"):
        error = payload.get("error") or {}
        if not isinstance(error, dict) or error.get("reason_code") != call["target_error_reason"]:
            mismatches.append(f"public_error_reason: expected {call['target_error_reason']!r}")
        if _source_paths(payload) or _authorizes_edit(payload):
            mismatches.append("public_rejection_has_evidence_or_authority")
    if call.get("target_read_only"):
        if call.get("target_expected_status") == "ok" and not call.get("library"):
            if payload.get("kind") != "docs_context":
                mismatches.append("retrieval_only_kind: project evidence must be docs_context")
            if payload.get("context_available") is not True:
                mismatches.append("positive_context_not_available")
        if any(payload.get(key) not in (None, "", {}, []) for key in (
                "answer", "answer_text", "final_answer")):
            mismatches.append("retrieval_only_answer: source context cannot contain a server-composed answer")
        if _authorizes_edit(payload) or payload.get("answer_supported") is True or payload.get("answer_available") is True:
            mismatches.append("retrieval_only_authority: source context cannot certify an answer or edit")
        if payload.get("kind") == "docs_context" and payload.get("context_available"):
            if payload.get("support_status") != "retrieval_only":
                mismatches.append("retrieval_only_support_status")
        if call.get("target_expected_status") == "ok" and not _source_paths(payload):
            mismatches.append("positive_context_has_no_sources")
    if call.get("target_empty_sources") is True and _source_paths(payload):
        mismatches.append("forbidden_visible_context")
    if call.get("target_source_fidelity"):
        mismatches.extend(_source_fidelity_mismatches(payload, Path(project_path)))
    for fact in call.get("target_required_facts") or ():
        if not any(isinstance(row, dict) and str(fact) in str(row.get("snippet") or "")
                   for row in payload.get("sources") or ()):
            mismatches.append(f"required_fact_missing: {fact!r}")
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
        actual_confirmation = (
            action.get("requires_confirmation")
            if "requires_confirmation" in action
            else payload.get("requires_confirmation")
        )
        if actual_confirmation is not bool(call["target_requires_confirmation"]):
            mismatches.append(
                f"requires_confirmation={actual_confirmation!r} "
                f"expected={bool(call['target_requires_confirmation'])!r}"
            )
    if call.get("target_confirmation_reasons"):
        actual_reason = action.get("confirmation_reason") or payload.get("confirmation_reason")
        if actual_reason not in call["target_confirmation_reasons"]:
            mismatches.append("confirmation_reason: neither source selection nor network consent")
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
    if call.get("target_advisory_only") and action:
        if action.get("auto_execute") is True:
            mismatches.append("advisory_auto_execute")
        arguments = action.get("arguments_patch") or {}
        if isinstance(arguments, dict) and any(key in arguments for key in (
                "mutation", "confirm", "allow_network", "force_refresh")):
            mismatches.append("advisory_fabricates_mutation_or_network_grant")
    if call.get("target_no_action") is True and action:
        mismatches.append("unexpected_lifecycle_action")
    target_reason = str(call.get("target_reason_code") or "")
    if target_reason and payload.get("reason_code") != target_reason:
        mismatches.append(f"reason_code={payload.get('reason_code')!r} expected={target_reason!r}")
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
    # Historical mode is evaluator metadata, never a hidden public argument.
    args: dict[str, Any] = {"question": str(call["question"])}
    if not call.get("library"):
        args["project_path"] = str(project)
    for key in ("scope", "module_path", "library", "version", "lookup_queries"):
        if call.get(key) is not None:
            args[key] = call[key]
    # Only explicit schema-negative cases can send removed fields. Keeping them
    # here proves rejection by the public boundary instead of internal routing.
    if call.get("target_error_reason") == "validation_error":
        for key, value in (call.get("rejected_arguments") or {}).items():
            args[key] = value
    return args


def _status_binding_mismatches(
    payload: dict[str, Any] | None, *, project_path: str,
) -> list[str]:
    """Bind a recovery inventory to the requested public tool and project."""
    if not isinstance(payload, dict):
        return ["status_binding: payload is not an object"]
    project = payload.get("project")
    if (payload.get("tool") != "docs_status" or payload.get("action") != "project"
            or not isinstance(project, dict) or project.get("project_path") != project_path):
        return ["status_binding: wrong tool, action or project"]
    # Successful docs_status(project) has no outer status field. Reject explicit
    # errors without inventing a required status=ok flag for the real DTO.
    if payload.get("status") not in (None, "ok") or payload.get("error") not in (None, {}):
        return ["status_binding: failed status response cannot authorize a retry"]
    return []


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
    explicit_status = recovery.get("status_request")
    if isinstance(explicit_status, dict):
        action_tool = "docs_status"
        action_arguments = _resolved_expected(explicit_status, str(project))
    if action_tool != "docs_status" or not isinstance(action_arguments, dict):
        errors.append("recovery requires an executable docs_status action")
    else:
        status_payload = handle_prefetch_tool(
            "docs_status", dict(action_arguments), service,
        )
        errors.extend(_status_binding_mismatches(status_payload, project_path=str(project)))

    retry = recovery.get("retry")
    retry_payload: dict[str, Any] | None = None
    retry_contamination = 0
    if not isinstance(retry, dict):
        errors.append("recovery retry contract is missing")
    else:
        retry_module_path = str(retry.get("module_path") or "")
        first_candidates = (_status_module_paths(status_payload) if isinstance(explicit_status, dict)
                            else _module_candidate_paths(payload))
        expected_modules = tuple(sorted(recovery.get("expected_module_paths") or ()))
        if expected_modules and tuple(sorted(_status_module_paths(status_payload))) != expected_modules:
            errors.append("status_inventory: exact module paths changed")
        if retry_module_path not in first_candidates:
            errors.append(
                f"retry module_path={retry_module_path!r} was not returned as a candidate"
            )
        retry_args = _context_args(retry, project)
        if _scope_signature(retry_args) != _scope_signature(retry):
            errors.append("retry_scope: public arguments changed the exact selector")
        retry_payload = handle_context_tool("get_docs_context", retry_args, service)
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
    control_ids = {task["id"] for task in protocol["migration_controls"]}

    try:
        for task in [*protocol["tasks"], *protocol["migration_controls"]]:
            task_id = str(task["id"])
            if task_id not in control_ids:
                class_counts[str(task["class"])] += 1
            fixture = PROJECTS_ROOT / str(task["fixture"])
            if not fixture.is_dir():
                errors.append(f"{task_id}: fixture missing: {fixture.relative_to(REPO_ROOT)}")
                continue
            with TemporaryDirectory(prefix=f"docatlas-agent-dev-{task_id}-") as raw_tmp, ExitStack() as fixture_lifetime:
                tmp = Path(raw_tmp)
                project = tmp / "project"
                shutil.copytree(fixture, project)
                service = fixture_lifetime.enter_context(_service(tmp, project))

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
                task_scope_contract_ok = True
                context_call_count = 0
                for index, call in enumerate(task["calls"], 1):
                    args = _context_args(call, project)
                    if _scope_signature(args) != _scope_signature(call):
                        task_scope_contract_ok = False
                        errors.append(f"{task_id}:{index}: public scope drift")
                    payload = handle_context_tool("get_docs_context", args, service)
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

                    if (call.get("target_next_action_tool") or call.get("target_recovery")
                            or "target_requires_confirmation" in call):
                        action_contract_total += 1
                        if target_closed:
                            action_contract_passed += 1
                    if str(call.get("target_expected_status") or "") in {"insufficient_evidence", "failed"}:
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
                            "public_error_reason": ((payload or {}).get("error") or {}).get("reason_code"),
                            "operational_reason_code": (
                                str((payload or {}).get("operational_reason_code") or "") or None
                                if isinstance(payload, dict) else None
                            ),
                            "module_candidates": list(_module_candidate_paths(payload)),
                            "recovery": recovery_result or None,
                            "target_closed": target_closed,
                            "target_mismatches": target_mismatches,
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
                        "scope_contract_ok": task_scope_contract_ok,
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

    controls = [item for item in task_results if item["task_id"] in control_ids]
    task_results = [item for item in task_results if item["task_id"] not in control_ids]
    controls_ok = len(controls) == len(control_ids) and all(item["target_closed"] for item in controls)
    target_closed_tasks = sum(1 for item in task_results if item["target_closed"])
    positive_module_ids = {
        task["id"] for task in [*protocol["tasks"], *protocol["migration_controls"]]
        if task["class"] == "module_only"
        and any(call.get("target_expected_status") == "ok" for call in task["calls"])
    }
    module_only = [item for item in [*task_results, *controls] if item["task_id"] in positive_module_ids]
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
        and controls_ok
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
        "migration_controls": controls,
        "migration_control_count": len(control_ids),
        "migration_controls_ok": controls_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_protocol()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
