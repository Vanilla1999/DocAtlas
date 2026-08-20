from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


PUBLIC_TASKS_PATH = Path(__file__).resolve().parent / "tasks.json"
ORACLE_PATH = Path(__file__).resolve().parent / "expected_trajectories.json"
REPORT_PROTOCOL = "agent-developer-model-v1"
REPORT_SCHEMA_VERSION = 1
REPORT_CONTRACT_VERSION = 1
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_TOOLS = {"get_docs_context", "docs_status", "finish"}
_FORBIDDEN_KEYS = {
    "class",
    "fixture",
    "calls",
    "required_scopes",
    "required_sources",
    "forbidden_sources",
    "known_gap",
    "mutation_before_calls",
    "target_expected_status",
    "target_required_sources",
    "target_recovery",
}
_TOP_LEVEL_KEYS = {
    "schema_version",
    "protocol",
    "report_contract_version",
    "public_tasks_sha256",
    "oracle_contract_sha256",
    "provider_id",
    "model",
    "task_count",
    "executed_task_count",
    "passed_tasks",
    "pass_rate",
    "scope_accuracy",
    "recovery_accuracy",
    "false_supported",
    "forbidden_source_contamination",
    "input_tokens",
    "output_tokens",
    "infrastructure_errors",
    "tasks",
}


class ReportContractError(ValueError):
    pass


def _canonical_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract_fingerprints() -> dict[str, str]:
    return {
        "public_tasks_sha256": _canonical_sha256(PUBLIC_TASKS_PATH),
        "oracle_contract_sha256": _canonical_sha256(ORACLE_PATH),
    }


def seal_report(report: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(report)
    sealed["report_contract_version"] = REPORT_CONTRACT_VERSION
    sealed.update(contract_fingerprints())
    return sealed


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportContractError(message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _bounded_rate(value: Any, field: str) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{field} must be numeric",
    )
    rate = float(value)
    _require(
        math.isfinite(rate) and 0.0 <= rate <= 1.0,
        f"{field} must be within [0, 1]",
    )
    return rate


def _non_negative_int(value: Any, field: str) -> int:
    _require(
        _is_int(value) and int(value) >= 0,
        f"{field} must be a non-negative integer",
    )
    return int(value)


def _walk_forbidden_keys(value: Any, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            _require(
                key_text not in _FORBIDDEN_KEYS,
                f"evaluator-only field leaked at {path}.{key_text}",
            )
            _walk_forbidden_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_keys(child, f"{path}[{index}]")


def _public_task_contract() -> tuple[dict[str, dict[str, Any]], set[str]]:
    payload = json.loads(PUBLIC_TASKS_PATH.read_text(encoding="utf-8"))
    tasks = payload.get("tasks")
    _require(isinstance(tasks, list) and tasks, "public task contract is empty")
    by_id: dict[str, dict[str, Any]] = {}
    recovery_ids: set[str] = set()
    for task in tasks:
        _require(
            isinstance(task, dict),
            "public task contract contains a non-object task",
        )
        task_id = str(task.get("id") or "")
        _require(
            task_id and task_id not in by_id,
            f"invalid or duplicate public task id: {task_id!r}",
        )
        by_id[task_id] = task
        if task.get("class") in {"recovery", "module_plus_dependency"}:
            recovery_ids.add(task_id)
    return by_id, recovery_ids


def _validate_action(action: Any, tool: str, task_id: str) -> None:
    _require(
        isinstance(action, dict),
        f"{task_id}: trajectory action must be an object",
    )
    _require(
        str(action.get("action") or "") == tool,
        f"{task_id}: tool/action mismatch",
    )
    _require(
        "project_path" not in action,
        f"{task_id}: host project_path leaked into model action",
    )
    if tool != "get_docs_context":
        return

    _require(
        bool(str(action.get("question") or "").strip()),
        f"{task_id}: empty context question",
    )
    scope = str(action.get("scope") or "")
    mode = str(action.get("mode") or "")
    module = str(action.get("module") or "").strip()
    module_path = str(action.get("module_path") or "").strip()
    if mode == "dependency":
        _require(
            not scope and not module and not module_path,
            f"{task_id}: dependency action carries scope filters",
        )
        return

    _require(
        scope in {"project", "module", "all"},
        f"{task_id}: invalid context scope",
    )
    if scope == "module":
        _require(
            bool(module) != bool(module_path),
            f"{task_id}: module action needs exactly one selector",
        )
    else:
        _require(
            not module and not module_path,
            f"{task_id}: non-module scope carries module selector",
        )


def _validate_trajectory(
    task: dict[str, Any],
    task_id: str,
    trajectory: Any,
    *,
    passed: bool,
) -> int:
    _require(
        isinstance(trajectory, list),
        f"{task_id}: trajectory must be a list",
    )
    if passed:
        _require(
            bool(trajectory),
            f"{task_id}: passing result must contain an executed trajectory",
        )

    context_calls = 0
    docs_status_calls = 0
    finish_calls = 0
    for index, record in enumerate(trajectory):
        _require(
            isinstance(record, dict),
            f"{task_id}: trajectory[{index}] must be an object",
        )
        tool = str(record.get("tool") or "")
        _require(
            tool in _ALLOWED_TOOLS,
            f"{task_id}: unsupported trajectory tool {tool!r}",
        )
        _validate_action(record.get("action"), tool, task_id)
        if tool == "get_docs_context":
            context_calls += 1
        elif tool == "docs_status":
            docs_status_calls += 1
        else:
            finish_calls += 1

        sources = record.get("sources")
        _require(
            isinstance(sources, list),
            f"{task_id}: trajectory sources must be a list",
        )
        _require(
            all(isinstance(source, str) for source in sources),
            f"{task_id}: trajectory source must be text",
        )
        candidates = record.get("module_candidates")
        _require(
            isinstance(candidates, list),
            f"{task_id}: module_candidates must be a list",
        )
        _require(
            all(isinstance(candidate, str) for candidate in candidates),
            f"{task_id}: module candidate must be text",
        )

    budget = _non_negative_int(
        task.get("max_get_docs_context_calls"),
        f"{task_id}.max_get_docs_context_calls",
    )
    _require(
        context_calls <= budget,
        f"{task_id}: context call budget exceeded: {context_calls}>{budget}",
    )
    _require(
        docs_status_calls <= 1,
        f"{task_id}: more than one docs_status action",
    )
    _require(
        finish_calls <= 1,
        f"{task_id}: more than one finish action",
    )
    _require(
        len(trajectory) <= budget + 2,
        f"{task_id}: trajectory exceeds bounded action budget",
    )
    return context_calls


def _validate_usage(task_id: str, usage: Any) -> tuple[int, int]:
    _require(
        isinstance(usage, list) and usage,
        f"{task_id}: usage must be a non-empty list",
    )
    total_input = 0
    total_output = 0
    seen_turns: set[int] = set()
    for row in usage:
        _require(
            isinstance(row, dict),
            f"{task_id}: usage row must be an object",
        )
        turn = _non_negative_int(row.get("turn"), f"{task_id}.usage.turn")
        _require(
            turn >= 1 and turn not in seen_turns,
            f"{task_id}: invalid or duplicate usage turn",
        )
        seen_turns.add(turn)
        _require(
            bool(str(row.get("model") or "").strip()),
            f"{task_id}: usage model is missing",
        )
        digest = str(row.get("request_payload_sha256") or "").lower()
        _require(
            bool(_HEX64.fullmatch(digest)),
            f"{task_id}: invalid request payload digest",
        )
        request_id = row.get("request_id")
        _require(
            isinstance(request_id, str) and bool(request_id.strip()),
            f"{task_id}: request_id must be non-empty text",
        )
        request_ids = row.get("request_ids")
        _require(
            isinstance(request_ids, dict) and bool(request_ids),
            f"{task_id}: request_ids must be a non-empty object",
        )
        _require(
            all(
                isinstance(key, str)
                and bool(key.strip())
                and isinstance(value, str)
                and bool(value.strip())
                for key, value in request_ids.items()
            ),
            f"{task_id}: request_ids must contain non-empty text pairs",
        )
        _require(
            request_id in request_ids.values(),
            f"{task_id}: primary request_id is not bound to request_ids",
        )
        total_input += _non_negative_int(
            row.get("input_tokens"),
            f"{task_id}.usage.input_tokens",
        )
        total_output += _non_negative_int(
            row.get("output_tokens"),
            f"{task_id}.usage.output_tokens",
        )
        for optional in ("reasoning_tokens", "estimated_input_tokens"):
            value = row.get(optional)
            if value is not None:
                _non_negative_int(value, f"{task_id}.usage.{optional}")
    return total_input, total_output


def validate_report(
    report: dict[str, Any],
    *,
    expected_model: str | None = None,
    min_pass_rate: float = 0.0,
    require_full: bool = True,
) -> dict[str, Any]:
    _require(isinstance(report, dict), "report must be an object")
    _walk_forbidden_keys(report)
    _require(
        set(report) == _TOP_LEVEL_KEYS,
        "report top-level schema drift",
    )
    _require(
        report.get("schema_version") == REPORT_SCHEMA_VERSION,
        "report schema version mismatch",
    )
    _require(
        report.get("protocol") == REPORT_PROTOCOL,
        "report protocol mismatch",
    )
    _require(
        report.get("report_contract_version") == REPORT_CONTRACT_VERSION,
        "report contract version mismatch",
    )

    for key, expected in contract_fingerprints().items():
        _require(
            str(report.get(key) or "") == expected,
            f"{key} does not match the current evaluator contract",
        )

    provider_id = str(report.get("provider_id") or "").strip()
    model = str(report.get("model") or "").strip()
    _require(provider_id, "provider_id is missing")
    _require(model, "model is missing")
    if expected_model is not None:
        _require(
            model == expected_model,
            f"model mismatch: {model!r} != {expected_model!r}",
        )
    _bounded_rate(min_pass_rate, "min_pass_rate")

    public_by_id, recovery_ids = _public_task_contract()
    results = report.get("tasks")
    _require(
        isinstance(results, list) and results,
        "tasks must be a non-empty list",
    )
    task_count = _non_negative_int(report.get("task_count"), "task_count")
    executed = _non_negative_int(
        report.get("executed_task_count"),
        "executed_task_count",
    )
    _require(
        task_count == len(results),
        "task_count does not match tasks length",
    )
    _require(
        executed == len(results),
        "executed_task_count does not match tasks length",
    )

    seen: set[str] = set()
    passed = 0
    scope_ok = 0
    recovery_ok = 0
    recovery_total = 0
    false_supported = 0
    contamination = 0
    input_tokens = 0
    output_tokens = 0

    for result in results:
        _require(isinstance(result, dict), "task result must be an object")
        task_id = str(result.get("task_id") or "")
        _require(
            task_id in public_by_id,
            f"unknown task id: {task_id!r}",
        )
        _require(
            task_id not in seen,
            f"duplicate task id: {task_id}",
        )
        seen.add(task_id)

        result_passed = result.get("passed")
        _require(
            isinstance(result_passed, bool),
            f"{task_id}: passed must be boolean",
        )
        score = result.get("score")
        _require(
            isinstance(score, dict),
            f"{task_id}: score must be an object",
        )
        _require(
            isinstance(score.get("passed"), bool),
            f"{task_id}: score.passed must be boolean",
        )
        _require(
            result_passed == score["passed"],
            f"{task_id}: result/score pass mismatch",
        )
        _require(
            isinstance(score.get("scope_contract_ok"), bool),
            f"{task_id}: scope_contract_ok must be boolean",
        )
        _require(
            isinstance(score.get("recovery_contract_ok"), bool),
            f"{task_id}: recovery_contract_ok must be boolean",
        )
        errors = score.get("errors")
        _require(
            isinstance(errors, list)
            and all(isinstance(item, str) for item in errors),
            f"{task_id}: score errors must be text",
        )

        context_calls = _validate_trajectory(
            public_by_id[task_id],
            task_id,
            result.get("trajectory"),
            passed=result_passed,
        )
        _require(
            _non_negative_int(
                score.get("context_call_count"),
                f"{task_id}.context_call_count",
            )
            == context_calls,
            f"{task_id}: context call count drift",
        )
        task_input, task_output = _validate_usage(
            task_id,
            result.get("usage"),
        )
        input_tokens += task_input
        output_tokens += task_output

        if result_passed:
            passed += 1
        if score["scope_contract_ok"]:
            scope_ok += 1
        if task_id in recovery_ids:
            recovery_total += 1
            if score["recovery_contract_ok"]:
                recovery_ok += 1
        false_supported += _non_negative_int(
            score.get("false_supported"),
            f"{task_id}.false_supported",
        )
        contamination += _non_negative_int(
            score.get("forbidden_source_contamination"),
            f"{task_id}.forbidden_source_contamination",
        )

    if require_full:
        _require(
            seen == set(public_by_id),
            "full report does not cover the exact public task set",
        )
        _require(
            task_count == len(public_by_id),
            "full report task_count does not match public task count",
        )

    expected_pass_rate = passed / task_count
    expected_scope = scope_ok / task_count
    expected_recovery = (
        recovery_ok / recovery_total if recovery_total else 1.0
    )
    _require(
        _non_negative_int(report.get("passed_tasks"), "passed_tasks") == passed,
        "passed_tasks aggregate drift",
    )
    _require(
        math.isclose(
            _bounded_rate(report.get("pass_rate"), "pass_rate"),
            expected_pass_rate,
            abs_tol=1e-12,
        ),
        "pass_rate aggregate drift",
    )
    _require(
        math.isclose(
            _bounded_rate(report.get("scope_accuracy"), "scope_accuracy"),
            expected_scope,
            abs_tol=1e-12,
        ),
        "scope_accuracy aggregate drift",
    )
    _require(
        math.isclose(
            _bounded_rate(
                report.get("recovery_accuracy"),
                "recovery_accuracy",
            ),
            expected_recovery,
            abs_tol=1e-12,
        ),
        "recovery_accuracy aggregate drift",
    )
    _require(
        _non_negative_int(report.get("false_supported"), "false_supported")
        == false_supported,
        "false_supported aggregate drift",
    )
    _require(
        _non_negative_int(
            report.get("forbidden_source_contamination"),
            "forbidden_source_contamination",
        )
        == contamination,
        "contamination aggregate drift",
    )
    _require(
        _non_negative_int(report.get("input_tokens"), "input_tokens")
        == input_tokens,
        "input_tokens aggregate drift",
    )
    _require(
        _non_negative_int(report.get("output_tokens"), "output_tokens")
        == output_tokens,
        "output_tokens aggregate drift",
    )

    infrastructure = report.get("infrastructure_errors")
    _require(
        isinstance(infrastructure, list)
        and all(isinstance(item, str) for item in infrastructure),
        "infrastructure_errors must be a text list",
    )
    _require(
        not infrastructure,
        "trusted benchmark report contains infrastructure errors",
    )
    _require(
        false_supported == 0,
        "trusted benchmark report contains false-supported results",
    )
    _require(
        contamination == 0,
        "trusted benchmark report contains forbidden-source contamination",
    )
    _require(
        expected_pass_rate >= min_pass_rate,
        f"pass rate {expected_pass_rate:.3f} is below required {min_pass_rate:.3f}",
    )

    return {
        "task_count": task_count,
        "passed_tasks": passed,
        "pass_rate": expected_pass_rate,
        "scope_accuracy": expected_scope,
        "recovery_accuracy": expected_recovery,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "provider_id": provider_id,
        "model": model,
    }


def _synthetic_report() -> dict[str, Any]:
    public_by_id, _ = _public_task_contract()
    tasks: list[dict[str, Any]] = []
    for turn, task_id in enumerate(sorted(public_by_id), start=1):
        request_id = f"self-test-{turn}"
        tasks.append(
            {
                "task_id": task_id,
                "passed": True,
                "score": {
                    "passed": True,
                    "scope_contract_ok": True,
                    "recovery_contract_ok": True,
                    "direct_recovery_shortcut": False,
                    "context_call_count": 0,
                    "false_supported": 0,
                    "forbidden_source_contamination": 0,
                    "errors": [],
                },
                "trajectory": [
                    {
                        "tool": "finish",
                        "action": {
                            "action": "finish",
                            "question": "",
                            "scope": "",
                            "mode": "",
                            "module": "",
                            "module_path": "",
                            "reason": "synthetic report-contract self-test",
                        },
                        "status": None,
                        "sources": [],
                        "next_action_tool": None,
                        "operational_reason_code": None,
                        "module_candidates": [],
                    }
                ],
                "usage": [
                    {
                        "turn": 1,
                        "request_id": request_id,
                        "request_ids": {
                            "x-ms-request-id": request_id,
                            "x-client-request-id": f"client-{turn}",
                        },
                        "model": "self-test/model",
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "reasoning_tokens": 0,
                        "request_payload_sha256": hashlib.sha256(
                            task_id.encode("utf-8")
                        ).hexdigest(),
                        "estimated_input_tokens": 1,
                    }
                ],
            }
        )

    count = len(tasks)
    return seal_report(
        {
            "schema_version": REPORT_SCHEMA_VERSION,
            "protocol": REPORT_PROTOCOL,
            "provider_id": "self-test",
            "model": "self-test/model",
            "task_count": count,
            "executed_task_count": count,
            "passed_tasks": count,
            "pass_rate": 1.0,
            "scope_accuracy": 1.0,
            "recovery_accuracy": 1.0,
            "false_supported": 0,
            "forbidden_source_contamination": 0,
            "input_tokens": count,
            "output_tokens": count,
            "infrastructure_errors": [],
            "tasks": tasks,
        }
    )


def _quality_failure_report(good: dict[str, Any]) -> dict[str, Any]:
    failed = json.loads(json.dumps(good))
    task = failed["tasks"][0]
    task["passed"] = False
    task["score"]["passed"] = False
    task["score"]["scope_contract_ok"] = False
    task["score"]["errors"] = ["model returned an invalid action"]
    task["trajectory"] = []
    count = int(failed["task_count"])
    failed["passed_tasks"] = count - 1
    failed["pass_rate"] = (count - 1) / count
    failed["scope_accuracy"] = (count - 1) / count
    return failed


def self_test() -> None:
    good = _synthetic_report()
    validate_report(
        good,
        expected_model="self-test/model",
        min_pass_rate=1.0,
    )

    quality_failure = _quality_failure_report(good)
    validate_report(
        quality_failure,
        expected_model="self-test/model",
        min_pass_rate=0.0,
    )
    try:
        validate_report(quality_failure, min_pass_rate=1.0)
    except ReportContractError:
        pass
    else:
        raise AssertionError("report contract ignored the quality threshold")

    leaked = json.loads(json.dumps(good))
    leaked["tasks"][0]["fixture"] = "oracle-only"
    try:
        validate_report(leaked)
    except ReportContractError:
        pass
    else:
        raise AssertionError("report contract accepted evaluator-only leakage")

    contaminated = json.loads(json.dumps(good))
    contaminated["tasks"][0]["score"][
        "forbidden_source_contamination"
    ] = 1
    contaminated["forbidden_source_contamination"] = 1
    try:
        validate_report(contaminated)
    except ReportContractError:
        pass
    else:
        raise AssertionError("report contract accepted source contamination")

    drifted = json.loads(json.dumps(good))
    drifted["public_tasks_sha256"] = "0" * 64
    try:
        validate_report(drifted)
    except ReportContractError:
        pass
    else:
        raise AssertionError("report contract accepted stale task binding")
