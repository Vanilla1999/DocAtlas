from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool
from eval.task_level.github_models import (
    DEFAULT_GITHUB_MODEL,
    GITHUB_MODELS_PROVIDER,
    GitHubModelsClient,
)
import scripts.run_agent_developer_gate as oracle_gate


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_TASKS_PATH = Path(__file__).resolve().parent / "tasks.json"
REPORT_PROTOCOL = "agent-developer-model-v1"
_PUBLIC_MODEL_FIELDS = {
    "id",
    "developer_task",
    "working_path",
    "max_get_docs_context_calls",
}
_ORACLE_ONLY_FIELDS = {
    "calls",
    "required_scopes",
    "required_sources",
    "forbidden_sources",
    "known_gap",
    "mutation_before_calls",
}


class Planner(Protocol):
    provider_id: str
    model: str

    def choose(self, messages: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]: ...


class GitHubModelsPlanner:
    provider_id = GITHUB_MODELS_PROVIDER.provider_id

    def __init__(self, token: str, *, model: str = DEFAULT_GITHUB_MODEL) -> None:
        self.model = model
        self._client = GitHubModelsClient(token, provider=GITHUB_MODELS_PROVIDER)

    def choose(self, messages: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
        action, completion = self._client.complete_json(
            model=self.model,
            messages=messages,
            schema_name="agent_developer_evidence_action_v1",
            schema=action_schema(),
            timeout_seconds=90,
            max_tokens=768,
        )
        usage = {
            "request_id": completion.request_id,
            "request_ids": completion.request_ids,
            "model": completion.model,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "reasoning_tokens": completion.reasoning_tokens,
            "request_payload_sha256": completion.request_payload_sha256,
            "estimated_input_tokens": completion.estimated_input_tokens,
        }
        return action, usage


def load_public_tasks() -> list[dict[str, Any]]:
    payload = json.loads(PUBLIC_TASKS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("protocol") != "agent-developer-v1":
        raise ValueError("agent developer public task identity mismatch")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("agent developer model benchmark requires public tasks")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("every public task must be an object")
        task_id = str(task.get("id") or "")
        if not task_id or task_id in seen:
            raise ValueError(f"invalid or duplicate public task id: {task_id!r}")
        seen.add(task_id)
        if _ORACLE_ONLY_FIELDS.intersection(task):
            raise ValueError(f"public task {task_id} leaks evaluator-only fields")
        if not str(task.get("developer_task") or "") or not str(task.get("working_path") or ""):
            raise ValueError(f"public task {task_id} is missing its coding task or working path")
        if int(task.get("max_get_docs_context_calls") or 0) < 1:
            raise ValueError(f"public task {task_id} has no context-call budget")
    return tasks


def model_task_view(task: dict[str, Any]) -> dict[str, Any]:
    """Return the only task fields that may enter the model request."""
    view = {key: task[key] for key in _PUBLIC_MODEL_FIELDS if key in task}
    return {
        "task_id": str(view["id"]),
        "developer_task": str(view["developer_task"]),
        "working_path": str(view["working_path"]),
        "max_get_docs_context_calls": int(view["max_get_docs_context_calls"]),
    }


def task_messages(task: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are the evidence-planning component of a coding agent. Choose only the next read-only "
        "DocAtlas action needed before code changes. The host supplies project_path and executes the action. "
        "Use get_docs_context with scope=module plus an exact module_path for one known module, scope=project "
        "for project-wide policy, scope=all for cross-module evidence, and mode=dependency with empty scope for "
        "pinned dependency documentation. Prefer an exact module_path that is safely derivable from working_path; "
        "do not guess between ambiguous module names. Use docs_status only after a context response explicitly "
        "reports module ambiguity and recommends docs_status. Never request edits, prepare_docs, sync, network "
        "fetches, shell commands, or source searches. Set action=finish only when the whole developer task is "
        "already evidenced or the returned recovery action means evidence is intentionally unavailable."
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(model_task_view(task), ensure_ascii=False, sort_keys=True),
        },
    ]


def action_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_docs_context", "docs_status", "finish"],
            },
            "question": {"type": "string"},
            "scope": {
                "type": "string",
                "enum": ["", "project", "module", "all"],
            },
            "mode": {
                "type": "string",
                "enum": ["", "auto", "project", "dependency", "mixed"],
            },
            "module": {"type": "string"},
            "module_path": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": [
            "action", "question", "scope", "mode", "module", "module_path", "reason",
        ],
    }


def _validate_action(action: dict[str, Any]) -> None:
    tool = str(action.get("action") or "")
    if tool == "get_docs_context":
        if not str(action.get("question") or "").strip():
            raise ValueError("get_docs_context requires a non-empty question")
        scope = str(action.get("scope") or "")
        mode = str(action.get("mode") or "")
        module = str(action.get("module") or "").strip()
        module_path = str(action.get("module_path") or "").strip()
        if mode == "dependency":
            if scope or module or module_path:
                raise ValueError("dependency retrieval must not carry project/module scope filters")
            return
        if scope not in {"project", "module", "all"}:
            raise ValueError("non-dependency retrieval requires an explicit scope")
        if scope == "module":
            if bool(module) == bool(module_path):
                raise ValueError("module retrieval requires exactly one of module or module_path")
        elif module or module_path:
            raise ValueError("module filters are only valid with module scope")
        return
    if tool in {"docs_status", "finish"}:
        return
    raise ValueError(f"unsupported model action: {tool!r}")


def _context_signature(action: dict[str, Any]) -> dict[str, str]:
    return oracle_gate._scope_signature({
        "scope": str(action.get("scope") or ""),
        "mode": str(action.get("mode") or ""),
        "module": str(action.get("module") or ""),
        "module_path": str(action.get("module_path") or ""),
    })


def _context_arguments(action: dict[str, Any], project: Path) -> dict[str, Any]:
    args: dict[str, Any] = {
        "question": str(action["question"]),
        "project_path": str(project),
    }
    mode = str(action.get("mode") or "").strip()
    if mode:
        args["mode"] = mode
    scope = str(action.get("scope") or "").strip()
    if scope:
        args["scope"] = scope
    for key in ("module", "module_path"):
        value = str(action.get(key) or "").strip()
        if value:
            args[key] = value
    return args


def _model_feedback(payload: dict[str, Any] | None, project: Path) -> str:
    if not isinstance(payload, dict):
        return json.dumps({"status": "invalid_payload"}, sort_keys=True)
    keep = {
        key: payload[key]
        for key in (
            "status", "kind", "answer", "sources", "support_summary", "limitations",
            "recommended_next_action", "next_action", "operational_reason_code", "module_candidates",
        )
        if key in payload
    }

    def redact(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace(str(project), "$PROJECT_PATH")
        if isinstance(value, dict):
            return {str(key): redact(child) for key, child in value.items()}
        if isinstance(value, list):
            return [redact(child) for child in value]
        return value

    text = json.dumps(redact(keep), ensure_ascii=False, sort_keys=True)
    return text[:12_000]


def _safe_module_path_from_working_path(task: dict[str, Any], module_path: str) -> bool:
    raw_module = str(module_path or "").replace("\\", "/").strip("/")
    raw_working = str(task.get("working_path") or "").replace("\\", "/").strip("/")
    if not raw_module or not raw_working:
        return False
    module = PurePosixPath(raw_module)
    working = PurePosixPath(raw_working)
    if ".." in module.parts or ".." in working.parts:
        return False
    try:
        working.relative_to(module)
    except ValueError:
        return False
    return True


def _record_for_expected(
    records: list[dict[str, Any]],
    signature: dict[str, str],
    used: set[int],
) -> tuple[int, dict[str, Any]] | None:
    for index, record in enumerate(records):
        if index in used or record.get("tool") != "get_docs_context":
            continue
        try:
            actual = _context_signature(record["action"])
        except ValueError:
            continue
        if actual == signature:
            return index, record
    return None


def _record_contamination(
    payload: dict[str, Any] | None,
    forbidden: list[Any] | tuple[Any, ...] | None,
) -> list[str]:
    forbidden_set = {str(value) for value in (forbidden or ()) if str(value)}
    return sorted(source for source in oracle_gate._source_paths(payload) if source in forbidden_set)


def score_task(task: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a model-chosen trajectory against the evaluator-only target contract."""
    errors: list[str] = []
    context_records = [record for record in records if record.get("tool") == "get_docs_context"]
    expected_calls = oracle_gate._planned_context_calls(task)
    expected_scopes = [
        {str(key): str(value) for key, value in row.items() if value not in (None, "")}
        for row in task.get("required_scopes") or ()
        if isinstance(row, dict)
    ]
    if len(expected_calls) != len(expected_scopes):
        return {"passed": False, "errors": ["evaluator call/scope contract mismatch"]}

    max_calls = int(task.get("max_get_docs_context_calls") or 0)
    if len(context_records) > max_calls:
        errors.append(f"context call budget exceeded: {len(context_records)}>{max_calls}")

    direct_recovery_shortcut = False
    matched: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    used: set[int] = set()
    recovery_initial = next(
        (call for call in task.get("calls") or () if isinstance(call.get("target_recovery"), dict)),
        None,
    )
    if recovery_initial is not None and len(context_records) == 1:
        retry = recovery_initial["target_recovery"].get("retry")
        if isinstance(retry, dict):
            retry_signature = oracle_gate._scope_signature(retry)
            only = context_records[0]
            try:
                only_signature = _context_signature(only["action"])
            except ValueError:
                only_signature = {}
            exact_path = str(only["action"].get("module_path") or "")
            if (
                only_signature == retry_signature
                and _safe_module_path_from_working_path(task, exact_path)
                and not oracle_gate._call_target_mismatches(
                    retry, only.get("payload"), project_path=str(only.get("project_path") or "$PROJECT_PATH"),
                )
            ):
                direct_recovery_shortcut = True
                matched.append((records.index(only), only, retry))
                used.add(records.index(only))

    if not direct_recovery_shortcut:
        for expected_call, signature in zip(expected_calls, expected_scopes, strict=True):
            found = _record_for_expected(records, signature, used)
            if found is None:
                errors.append(f"missing required scope: {signature!r}")
                continue
            index, record = found
            used.add(index)
            matched.append((index, record, expected_call))
            mismatches = oracle_gate._call_target_mismatches(
                expected_call,
                record.get("payload"),
                project_path=str(record.get("project_path") or "$PROJECT_PATH"),
            )
            errors.extend(f"call {signature!r}: {message}" for message in mismatches)

    unmatched_context = [
        record for index, record in enumerate(records)
        if record.get("tool") == "get_docs_context" and index not in used
    ]
    for record in unmatched_context:
        try:
            signature = _context_signature(record["action"])
        except ValueError:
            signature = {"scope": "invalid"}
        errors.append(f"unexpected context scope: {signature!r}")

    contamination = 0
    false_supported = 0
    for _index, record, expected_call in matched:
        forbidden = (
            expected_call.get("forbidden_sources")
            if "forbidden_sources" in expected_call
            else task.get("forbidden_sources")
        )
        contaminated = _record_contamination(record.get("payload"), forbidden)
        if contaminated:
            contamination += 1
            errors.append(f"forbidden source contamination: {contaminated!r}")
        expected_status = str(expected_call.get("target_expected_status") or "")
        actual_status = str((record.get("payload") or {}).get("status") or "")
        if expected_status == "insufficient_evidence" and actual_status == "ok":
            false_supported += 1
            errors.append("unexpected supported result for an insufficient-evidence target")

    recovery_contract_ok = True
    if recovery_initial is not None and not direct_recovery_shortcut:
        retry = recovery_initial["target_recovery"].get("retry")
        initial_signature = oracle_gate._scope_signature(recovery_initial)
        retry_signature = oracle_gate._scope_signature(retry)
        initial_match = _record_for_expected(records, initial_signature, set())
        retry_match = _record_for_expected(records, retry_signature, set())
        if initial_match is None or retry_match is None:
            recovery_contract_ok = False
        else:
            first_index = initial_match[0]
            retry_index = retry_match[0]
            status_records = [
                record for index, record in enumerate(records)
                if first_index < index < retry_index and record.get("tool") == "docs_status"
            ]
            if len(status_records) != 1:
                recovery_contract_ok = False
                errors.append("ambiguous-module recovery requires exactly one docs_status between context calls")
            else:
                expected_candidates = {
                    str(value) for value in recovery_initial.get("target_module_candidates") or ()
                }
                actual_candidates = set(oracle_gate._status_module_paths(status_records[0].get("payload")))
                if expected_candidates and not expected_candidates.issubset(actual_candidates):
                    recovery_contract_ok = False
                    errors.append(
                        f"docs_status module candidates={sorted(actual_candidates)!r} "
                        f"expected={sorted(expected_candidates)!r}"
                    )

    if recovery_initial is None and any(record.get("tool") == "docs_status" for record in records):
        recovery_contract_ok = False
        errors.append("docs_status was used without an ambiguity recovery contract")

    scope_contract_ok = not any(
        message.startswith("missing required scope")
        or message.startswith("unexpected context scope")
        for message in errors
    )
    passed = not errors and recovery_contract_ok
    return {
        "passed": passed,
        "scope_contract_ok": scope_contract_ok,
        "recovery_contract_ok": recovery_contract_ok,
        "direct_recovery_shortcut": direct_recovery_shortcut,
        "context_call_count": len(context_records),
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "errors": errors,
    }


def _execute_action(
    action: dict[str, Any],
    *,
    service: Any,
    project: Path,
) -> tuple[str, dict[str, Any] | None]:
    _validate_action(action)
    tool = str(action["action"])
    if tool == "get_docs_context":
        return tool, handle_context_tool(
            "get_docs_context", _context_arguments(action, project), service,
        )
    if tool == "docs_status":
        return tool, handle_prefetch_tool(
            "docs_status",
            {"action": "project", "project_path": str(project)},
            service,
        )
    return tool, None


def _report_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    return {
        "tool": record.get("tool"),
        "action": record.get("action"),
        "status": str(payload.get("status") or "") if isinstance(payload, dict) else None,
        "sources": list(oracle_gate._source_paths(payload)),
        "next_action_tool": (
            str(oracle_gate._recommended_action(payload).get("tool") or "") or None
            if isinstance(payload, dict) else None
        ),
        "operational_reason_code": (
            str(payload.get("operational_reason_code") or "") or None
            if isinstance(payload, dict) else None
        ),
        "module_candidates": list(oracle_gate._module_candidate_paths(payload)),
    }


def run_task(
    public_task: dict[str, Any],
    oracle_task: dict[str, Any],
    planner: Planner,
) -> dict[str, Any]:
    previous_home = os.environ.get("DOCATLAS_HOME")
    records: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    planning_errors: list[str] = []
    try:
        with TemporaryDirectory(prefix=f"docatlas-agent-model-{public_task['id']}-") as raw_tmp:
            tmp = Path(raw_tmp)
            project = tmp / "project"
            fixture = oracle_gate.PROJECTS_ROOT / str(public_task["fixture"])
            shutil.copytree(fixture, project)
            os.environ["DOCATLAS_HOME"] = str(tmp / "home")
            service = oracle_gate._service(tmp)
            sync = service.sync_project_docs(str(project), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                raise RuntimeError(f"fixture sync failed: {getattr(sync, 'status', None)!r}")

            mutation = oracle_task.get("mutation_before_calls")
            if isinstance(mutation, dict):
                target = project / str(mutation.get("path") or "")
                if not target.is_file():
                    raise RuntimeError(f"fixture mutation target is missing: {target}")
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(str(mutation.get("append") or ""))

            messages = task_messages(public_task)
            max_context_calls = int(public_task["max_get_docs_context_calls"])
            max_turns = max_context_calls + 2
            docs_status_calls = 0
            for turn in range(1, max_turns + 1):
                action, usage = planner.choose(messages)
                usage_rows.append({"turn": turn, **usage})
                try:
                    _validate_action(action)
                except ValueError as exc:
                    planning_errors.append(str(exc))
                    break
                if action["action"] == "finish":
                    records.append({
                        "tool": "finish", "action": action, "payload": None,
                        "project_path": str(project),
                    })
                    break
                if action["action"] == "get_docs_context":
                    if sum(record.get("tool") == "get_docs_context" for record in records) >= max_context_calls:
                        planning_errors.append("model attempted to exceed the context-call budget")
                        break
                if action["action"] == "docs_status":
                    docs_status_calls += 1
                    if docs_status_calls > 1:
                        planning_errors.append("model attempted more than one docs_status recovery call")
                        break

                tool, payload = _execute_action(action, service=service, project=project)
                record = {
                    "tool": tool,
                    "action": action,
                    "payload": payload,
                    "project_path": str(project),
                }
                records.append(record)
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=False, sort_keys=True),
                })
                messages.append({
                    "role": "user",
                    "content": "Observed DocAtlas result:\n" + _model_feedback(payload, project),
                })

                partial = score_task(oracle_task, records)
                if partial["passed"]:
                    break
                context_count = sum(
                    record.get("tool") == "get_docs_context" for record in records
                )
                if context_count >= max_context_calls and tool != "docs_status":
                    break

            score = score_task(oracle_task, records)
            score["errors"] = planning_errors + list(score.get("errors") or ())
            score["passed"] = bool(score["passed"] and not planning_errors)
            return {
                "task_id": str(public_task["id"]),
                "passed": score["passed"],
                "score": score,
                "trajectory": [_report_record(record) for record in records],
                "usage": usage_rows,
            }
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home


def run_benchmark(
    planner: Planner,
    *,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    public_tasks = load_public_tasks()
    protocol = oracle_gate._load_protocol()
    oracle_by_id = {str(task["id"]): task for task in protocol["tasks"]}
    selected = [
        task for task in public_tasks
        if task_ids is None or str(task["id"]) in task_ids
    ]
    if task_ids is not None:
        missing = sorted(task_ids - {str(task["id"]) for task in selected})
        if missing:
            raise ValueError(f"unknown task ids: {missing!r}")
    results: list[dict[str, Any]] = []
    infrastructure_errors: list[str] = []
    for task in selected:
        task_id = str(task["id"])
        try:
            results.append(run_task(task, oracle_by_id[task_id], planner))
        except Exception as exc:
            infrastructure_errors.append(f"{task_id}: {exc.__class__.__name__}: {exc}")
            break

    passed = sum(bool(result["passed"]) for result in results)
    total_input = sum(
        int(row.get("input_tokens") or 0)
        for result in results for row in result.get("usage") or ()
    )
    total_output = sum(
        int(row.get("output_tokens") or 0)
        for result in results for row in result.get("usage") or ()
    )
    false_supported = sum(
        int(result["score"].get("false_supported") or 0) for result in results
    )
    contamination = sum(
        int(result["score"].get("forbidden_source_contamination") or 0)
        for result in results
    )
    scope_accuracy = (
        sum(bool(result["score"].get("scope_contract_ok")) for result in results) / len(results)
        if results else 0.0
    )
    recovery_results = [
        result for result in results
        if oracle_by_id[result["task_id"]].get("class") in {"recovery", "module_plus_dependency"}
    ]
    recovery_accuracy = (
        sum(bool(result["score"].get("recovery_contract_ok")) for result in recovery_results)
        / len(recovery_results)
        if recovery_results else 1.0
    )
    return {
        "schema_version": 1,
        "protocol": REPORT_PROTOCOL,
        "provider_id": planner.provider_id,
        "model": planner.model,
        "task_count": len(selected),
        "executed_task_count": len(results),
        "passed_tasks": passed,
        "pass_rate": passed / len(selected) if selected else 0.0,
        "scope_accuracy": scope_accuracy,
        "recovery_accuracy": recovery_accuracy,
        "false_supported": false_supported,
        "forbidden_source_contamination": contamination,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "infrastructure_errors": infrastructure_errors,
        "tasks": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the model-backed Agent Developer planning benchmark")
    parser.add_argument("--model", default=DEFAULT_GITHUB_MODEL)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "eval" / "agent_developer_v1" / "results" / "model-benchmark.json")
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    token = os.environ.get("AGENT_DEVELOPER_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token.strip():
        print("Agent Developer model benchmark: missing GitHub Models token")
        return 2

    planner = GitHubModelsPlanner(token, model=args.model)
    report = run_benchmark(planner, task_ids=set(args.tasks) if args.tasks else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Agent Developer model benchmark: {report['passed_tasks']}/{report['task_count']} "
        f"pass; scope={report['scope_accuracy']:.3f}; recovery={report['recovery_accuracy']:.3f}; "
        f"false-supported={report['false_supported']}; contamination={report['forbidden_source_contamination']}"
    )
    if report["infrastructure_errors"]:
        for error in report["infrastructure_errors"]:
            print(f"- infrastructure: {error}")
        return 2
    return 0 if float(report["pass_rate"]) >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
