#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from collections import defaultdict, deque
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.run_agent_developer_gate as base  # noqa: E402


CASES_PATH = REPO_ROOT / "eval" / "agent_developer_v2" / "cases.json"
PROJECT_PATH_MARKER = "$PROJECT_PATH"
DEFAULT_CONTEXT_PROJECTION_MAX_TOKENS = 1000
DEFAULT_STATUS_PROJECTION_MAX_TOKENS = 1200
GLOBAL_TRAJECTORY_MAX_TOKENS = 2000


def _budget_exceeded(tokens: int, ceiling: int) -> bool:
    return tokens > ceiling


def _trajectory_budget_exceeded(tokens: int, ceiling: int) -> bool:
    return tokens > ceiling


def _contaminated_sources(
    actual: tuple[str, ...], forbidden: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(sorted(source for source in actual if source in forbidden))


def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:
    return expected == actual


def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:
    return module_path in candidates


def _edit_safe(payload: dict[str, Any] | None) -> bool:
    return not base._authorizes_edit(payload)


def self_test() -> None:
    assert _budget_exceeded(301, 300)
    assert not _budget_exceeded(300, 300)
    assert _trajectory_budget_exceeded(2001, 2000)
    assert not _trajectory_budget_exceeded(2000, 2000)
    assert _contaminated_sources(("docs/a.md", "docs/b.md"), ("docs/b.md",)) == (
        "docs/b.md",
    )
    assert not _scope_matches(
        {"scope": "module", "module_path": "packages/orders"},
        {"scope": "project"},
    )
    assert _scope_matches(
        {"scope": "module", "module_path": "packages/orders"},
        {"scope": "module", "module_path": "packages/orders"},
    )
    assert not _retry_candidate_valid("packages/auth", ("services/auth",))
    assert _retry_candidate_valid(
        "packages/auth", ("packages/auth", "services/auth")
    )
    assert _edit_safe({"status": "insufficient_evidence", "edit_ready": False})
    assert not _edit_safe({"status": "insufficient_evidence", "edit_ready": True})


def _normalized_for_tokens(value: Any, project_path: str) -> Any:
    if isinstance(value, str):
        return value.replace(project_path, PROJECT_PATH_MARKER) if project_path else value
    if isinstance(value, dict):
        return {
            str(key): _normalized_for_tokens(child, project_path)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_normalized_for_tokens(child, project_path) for child in value]
    if isinstance(value, tuple):
        return [_normalized_for_tokens(child, project_path) for child in value]
    return value


def _projection_tokens(payload: dict[str, Any] | None, project_path: str) -> int:
    if not isinstance(payload, dict):
        return 0
    reported = payload.get("estimated_tokens")
    if isinstance(reported, int) and not isinstance(reported, bool) and reported > 0:
        return reported
    normalized = _normalized_for_tokens(payload, project_path)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return max(1, math.ceil(len(encoded) / 4))


def _load_cases() -> dict[str, Any]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("adversarial protocol schema version mismatch")
    if payload.get("protocol") != "agent-developer-adversarial-v2":
        raise ValueError("adversarial protocol identity mismatch")
    global_limit = int(payload.get("global_max_trajectory_tokens") or 0)
    if global_limit != GLOBAL_TRAJECTORY_MAX_TOKENS:
        raise ValueError(
            f"global trajectory ceiling must remain {GLOBAL_TRAJECTORY_MAX_TOKENS}"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("adversarial protocol requires cases")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every adversarial case must be an object")
        case_id = str(case.get("id") or "")
        if not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate adversarial case id: {case_id!r}")
        seen.add(case_id)
        trajectory_ceiling = int(case.get("max_trajectory_tokens") or 0)
        if not 1 <= trajectory_ceiling <= global_limit:
            raise ValueError(f"{case_id}: invalid trajectory token ceiling")
        max_calls = int(case.get("max_get_docs_context_calls") or 0)
        if max_calls < 1:
            raise ValueError(f"{case_id}: invalid context-call budget")
        calls = case.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"{case_id}: calls are required")
        planned_calls = 0
        for call in calls:
            if not isinstance(call, dict) or not str(call.get("question") or ""):
                raise ValueError(f"{case_id}: invalid context call")
            ceiling = int(call.get("max_projection_tokens") or 0)
            if not 1 <= ceiling <= GLOBAL_TRAJECTORY_MAX_TOKENS:
                raise ValueError(f"{case_id}: invalid per-call token ceiling")
            packet_tokens = call.get("packet_tokens")
            if packet_tokens is not None and ceiling > int(packet_tokens):
                raise ValueError(
                    f"{case_id}: projection ceiling exceeds requested packet_tokens"
                )
            planned_calls += 1
            recovery = call.get("recovery")
            if recovery is not None:
                if not isinstance(recovery, dict) or not isinstance(
                    recovery.get("retry"), dict
                ):
                    raise ValueError(f"{case_id}: recovery requires retry")
                status_ceiling = int(
                    recovery.get("max_status_projection_tokens") or 0
                )
                if not 1 <= status_ceiling <= GLOBAL_TRAJECTORY_MAX_TOKENS:
                    raise ValueError(f"{case_id}: invalid docs_status token ceiling")
                retry = recovery["retry"]
                retry_ceiling = int(retry.get("max_projection_tokens") or 0)
                if not 1 <= retry_ceiling <= GLOBAL_TRAJECTORY_MAX_TOKENS:
                    raise ValueError(f"{case_id}: invalid retry token ceiling")
                retry_packet = retry.get("packet_tokens")
                if retry_packet is not None and retry_ceiling > int(retry_packet):
                    raise ValueError(
                        f"{case_id}: retry ceiling exceeds requested packet_tokens"
                    )
                planned_calls += 1
        if planned_calls > max_calls:
            raise ValueError(f"{case_id}: planned calls exceed call budget")
    return payload


def _v1_event_plan() -> tuple[deque[dict[str, Any]], dict[str, int]]:
    protocol = base._load_protocol()
    events: deque[dict[str, Any]] = deque()
    ceilings: dict[str, int] = {}
    for task in protocol["tasks"]:
        task_id = str(task["id"])
        ceilings[task_id] = GLOBAL_TRAJECTORY_MAX_TOKENS
        for call in task["calls"]:
            ceiling = int(
                call.get("packet_tokens")
                or DEFAULT_CONTEXT_PROJECTION_MAX_TOKENS
            )
            events.append(
                {
                    "task_id": task_id,
                    "kind": "context",
                    "call": call,
                    "ceiling": min(
                        ceiling, DEFAULT_CONTEXT_PROJECTION_MAX_TOKENS
                    ),
                }
            )
            recovery = call.get("target_recovery")
            retry = recovery.get("retry") if isinstance(recovery, dict) else None
            if isinstance(retry, dict):
                events.append(
                    {
                        "task_id": task_id,
                        "kind": "status",
                        "ceiling": DEFAULT_STATUS_PROJECTION_MAX_TOKENS,
                    }
                )
                retry_ceiling = int(
                    retry.get("packet_tokens")
                    or DEFAULT_CONTEXT_PROJECTION_MAX_TOKENS
                )
                events.append(
                    {
                        "task_id": task_id,
                        "kind": "context",
                        "call": retry,
                        "ceiling": min(
                            retry_ceiling, DEFAULT_CONTEXT_PROJECTION_MAX_TOKENS
                        ),
                    }
                )
    return events, ceilings


def _capture_v1_token_contract() -> dict[str, Any]:
    events, trajectory_ceilings = _v1_event_plan()
    original_context = base.handle_context_tool
    original_prefetch = base.handle_prefetch_tool
    event_results: list[dict[str, Any]] = []
    totals: dict[str, int] = defaultdict(int)
    violations: list[str] = []

    def next_event(kind: str) -> dict[str, Any]:
        if not events:
            raise RuntimeError(f"unexpected v1 {kind} call after event plan exhausted")
        event = events.popleft()
        if event["kind"] != kind:
            raise RuntimeError(
                f"v1 event order drift: expected {event['kind']}, observed {kind}"
            )
        return event

    def context_wrapper(
        name: str, args: dict[str, Any], service: Any
    ) -> dict[str, Any] | None:
        event = next_event("context")
        expected_scope = base._scope_signature(event["call"])
        actual_scope = base._scope_signature(args)
        if not _scope_matches(expected_scope, actual_scope):
            violations.append(
                f"{event['task_id']}: v1 scope drift {actual_scope!r} != {expected_scope!r}"
            )
        payload = original_context(name, args, service)
        project_path = str(args.get("project_path") or "")
        tokens = _projection_tokens(payload, project_path)
        ceiling = int(event["ceiling"])
        if _budget_exceeded(tokens, ceiling):
            violations.append(
                f"{event['task_id']}: context projection {tokens}>{ceiling} tokens"
            )
        totals[event["task_id"]] += tokens
        event_results.append(
            {
                "task_id": event["task_id"],
                "kind": "context",
                "tokens": tokens,
                "ceiling": ceiling,
            }
        )
        return payload

    def status_wrapper(
        name: str, args: dict[str, Any], service: Any
    ) -> dict[str, Any] | None:
        if name != "docs_status":
            return original_prefetch(name, args, service)
        event = next_event("status")
        payload = original_prefetch(name, args, service)
        project_path = str(args.get("project_path") or "")
        tokens = _projection_tokens(payload, project_path)
        ceiling = int(event["ceiling"])
        if _budget_exceeded(tokens, ceiling):
            violations.append(
                f"{event['task_id']}: docs_status projection {tokens}>{ceiling} tokens"
            )
        totals[event["task_id"]] += tokens
        event_results.append(
            {
                "task_id": event["task_id"],
                "kind": "docs_status",
                "tokens": tokens,
                "ceiling": ceiling,
            }
        )
        return payload

    base.handle_context_tool = context_wrapper
    base.handle_prefetch_tool = status_wrapper
    try:
        report = base.run_protocol()
    finally:
        base.handle_context_tool = original_context
        base.handle_prefetch_tool = original_prefetch

    if events:
        violations.append(f"v1 token event plan left {len(events)} unconsumed events")
    if not report.get("target_ok"):
        violations.append("Agent Developer Protocol v1 is not target-green")
    for task_id, total in sorted(totals.items()):
        ceiling = trajectory_ceilings[task_id]
        if _trajectory_budget_exceeded(total, ceiling):
            violations.append(
                f"{task_id}: v1 trajectory {total}>{ceiling} tokens"
            )
    return {
        "target_ok": bool(report.get("target_ok")),
        "task_count": int(report.get("task_count") or 0),
        "events": event_results,
        "trajectory_tokens": dict(sorted(totals.items())),
        "max_trajectory_tokens": max(totals.values(), default=0),
        "violations": violations,
    }


def _case_scope(call: dict[str, Any]) -> dict[str, str]:
    return base._scope_signature(call)


def _run_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["id"])
    fixture = base.PROJECTS_ROOT / str(case["fixture"])
    working = base._safe_fixture_path(fixture, case.get("working_path"))
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    trajectory_tokens = 0
    context_calls = 0
    previous_home = os.environ.get("DOCMANCER_HOME")

    if working is None or not working.is_file():
        return {
            "case_id": case_id,
            "passed": False,
            "trajectory_tokens": 0,
            "errors": ["working_path is missing or unsafe"],
            "events": [],
        }

    try:
        with TemporaryDirectory(prefix=f"docatlas-agent-v2-{case_id}-") as raw_tmp:
            tmp = Path(raw_tmp)
            project = tmp / "project"
            shutil.copytree(fixture, project)
            os.environ["DOCMANCER_HOME"] = str(tmp / "home")
            service = base._service(tmp)
            sync = service.sync_project_docs(str(project), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                return {
                    "case_id": case_id,
                    "passed": False,
                    "trajectory_tokens": 0,
                    "errors": [f"sync status={getattr(sync, 'status', None)!r}"],
                    "events": [],
                }

            mutation = case.get("mutation_before_calls")
            if isinstance(mutation, dict):
                target = project / str(mutation.get("path") or "")
                if not target.is_file():
                    errors.append(f"mutation target missing: {target}")
                else:
                    with target.open("a", encoding="utf-8") as stream:
                        stream.write(str(mutation.get("append") or ""))

            for index, call in enumerate(case["calls"], 1):
                args = base._context_args(call, project)
                actual_scope = base._scope_signature(args)
                expected_scope = _case_scope(call)
                if not _scope_matches(expected_scope, actual_scope):
                    errors.append(
                        f"call {index}: scope drift {actual_scope!r} != {expected_scope!r}"
                    )
                payload = base.handle_context_tool(
                    "get_docs_context", args, service
                )
                context_calls += 1
                tokens = _projection_tokens(payload, str(project))
                ceiling = int(call["max_projection_tokens"])
                trajectory_tokens += tokens
                if _budget_exceeded(tokens, ceiling):
                    errors.append(
                        f"call {index}: context projection {tokens}>{ceiling} tokens"
                    )
                mismatches = base._call_target_mismatches(
                    call, payload, project_path=str(project)
                )
                errors.extend(f"call {index}: {message}" for message in mismatches)
                forbidden = tuple(
                    str(value)
                    for value in call.get("forbidden_sources") or ()
                    if str(value)
                )
                contaminated = _contaminated_sources(
                    base._source_paths(payload), forbidden
                )
                if contaminated:
                    errors.append(
                        f"call {index}: forbidden source contamination {contaminated!r}"
                    )
                if str(call.get("target_expected_status") or "") == "insufficient_evidence":
                    if not _edit_safe(payload):
                        errors.append(
                            f"call {index}: insufficient evidence authorized edits"
                        )
                events.append(
                    {
                        "kind": "context",
                        "tokens": tokens,
                        "ceiling": ceiling,
                        "status": str((payload or {}).get("status") or ""),
                        "sources": list(base._source_paths(payload)),
                    }
                )

                recovery = call.get("recovery")
                if not isinstance(recovery, dict):
                    continue
                action = base._recommended_action(payload)
                action_args = action.get("arguments_patch")
                if str(action.get("tool") or "") != "docs_status" or not isinstance(
                    action_args, dict
                ):
                    errors.append(f"call {index}: recovery lacks docs_status action")
                    continue
                status_payload = base.handle_prefetch_tool(
                    "docs_status", dict(action_args), service
                )
                status_tokens = _projection_tokens(status_payload, str(project))
                status_ceiling = int(recovery["max_status_projection_tokens"])
                trajectory_tokens += status_tokens
                if _budget_exceeded(status_tokens, status_ceiling):
                    errors.append(
                        f"call {index}: docs_status projection "
                        f"{status_tokens}>{status_ceiling} tokens"
                    )
                expected_modules = tuple(
                    sorted(str(value) for value in recovery.get("expected_module_paths") or ())
                )
                actual_modules = tuple(sorted(base._status_module_paths(status_payload)))
                if expected_modules and actual_modules != expected_modules:
                    errors.append(
                        f"call {index}: docs_status modules={actual_modules!r} "
                        f"expected={expected_modules!r}"
                    )
                events.append(
                    {
                        "kind": "docs_status",
                        "tokens": status_tokens,
                        "ceiling": status_ceiling,
                        "modules": list(actual_modules),
                    }
                )

                retry = recovery["retry"]
                retry_module_path = str(retry.get("module_path") or "")
                candidates = base._module_candidate_paths(payload)
                if not _retry_candidate_valid(retry_module_path, candidates):
                    errors.append(
                        f"call {index}: retry module_path={retry_module_path!r} "
                        f"not in candidates={candidates!r}"
                    )
                retry_payload = base.handle_context_tool(
                    "get_docs_context", base._context_args(retry, project), service
                )
                context_calls += 1
                retry_tokens = _projection_tokens(retry_payload, str(project))
                retry_ceiling = int(retry["max_projection_tokens"])
                trajectory_tokens += retry_tokens
                if _budget_exceeded(retry_tokens, retry_ceiling):
                    errors.append(
                        f"call {index}: retry projection "
                        f"{retry_tokens}>{retry_ceiling} tokens"
                    )
                retry_mismatches = base._call_target_mismatches(
                    retry, retry_payload, project_path=str(project)
                )
                errors.extend(
                    f"call {index}: retry {message}" for message in retry_mismatches
                )
                retry_forbidden = tuple(
                    str(value)
                    for value in retry.get("forbidden_sources") or ()
                    if str(value)
                )
                retry_contaminated = _contaminated_sources(
                    base._source_paths(retry_payload), retry_forbidden
                )
                if retry_contaminated:
                    errors.append(
                        f"call {index}: retry forbidden contamination "
                        f"{retry_contaminated!r}"
                    )
                events.append(
                    {
                        "kind": "retry",
                        "tokens": retry_tokens,
                        "ceiling": retry_ceiling,
                        "status": str((retry_payload or {}).get("status") or ""),
                        "sources": list(base._source_paths(retry_payload)),
                    }
                )

            context_ceiling = int(case["max_get_docs_context_calls"])
            if context_calls > context_ceiling:
                errors.append(
                    f"executed {context_calls}>{context_ceiling} context calls"
                )
            trajectory_ceiling = int(case["max_trajectory_tokens"])
            if _trajectory_budget_exceeded(
                trajectory_tokens, trajectory_ceiling
            ):
                errors.append(
                    f"trajectory projection {trajectory_tokens}>{trajectory_ceiling} tokens"
                )
            return {
                "case_id": case_id,
                "class": str(case.get("class") or ""),
                "passed": not errors,
                "context_call_count": context_calls,
                "trajectory_tokens": trajectory_tokens,
                "trajectory_ceiling": trajectory_ceiling,
                "events": events,
                "errors": errors,
            }
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home


def run_gate() -> dict[str, Any]:
    cases_payload = _load_cases()
    v1 = _capture_v1_token_contract()
    case_results = [_run_adversarial_case(case) for case in cases_payload["cases"]]
    errors = list(v1["violations"])
    for result in case_results:
        errors.extend(
            f"{result['case_id']}: {message}"
            for message in result.get("errors") or ()
        )
    passed_cases = sum(bool(result["passed"]) for result in case_results)
    max_v2 = max(
        (int(result["trajectory_tokens"]) for result in case_results), default=0
    )
    return {
        "schema_version": 1,
        "protocol": "agent-developer-adversarial-v2",
        "v1_target_ok": v1["target_ok"],
        "v1_task_count": v1["task_count"],
        "v1_max_trajectory_tokens": v1["max_trajectory_tokens"],
        "adversarial_case_count": len(case_results),
        "adversarial_passed_cases": passed_cases,
        "adversarial_max_trajectory_tokens": max_v2,
        "global_max_trajectory_tokens": GLOBAL_TRAJECTORY_MAX_TOKENS,
        "token_budget_violations": sum(
            "tokens" in error or "projection" in error for error in errors
        ),
        "passed": not errors and passed_cases == len(case_results),
        "errors": errors,
        "v1": v1,
        "cases": case_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Agent Developer adversarial and token-budget gate"
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.self_test:
        try:
            self_test()
        except AssertionError as exc:
            print(f"Agent Developer adversarial gate self-test: FAIL: {exc}")
            return 1
        print("Agent Developer adversarial gate self-test: PASS")
        return 0

    report = run_gate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        "Agent Developer adversarial v2: "
        f"{report['adversarial_passed_cases']}/{report['adversarial_case_count']} cases; "
        f"v1={report['v1_task_count']} target-green; "
        f"v1-max-tokens={report['v1_max_trajectory_tokens']}; "
        f"v2-max-tokens={report['adversarial_max_trajectory_tokens']}; "
        f"violations={len(report['errors'])}"
    )
    if not report["passed"]:
        for error in report["errors"]:
            print(f"- {error}")
        print("Agent Developer adversarial v2: FAIL")
        return 1
    print("Agent Developer adversarial v2: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
