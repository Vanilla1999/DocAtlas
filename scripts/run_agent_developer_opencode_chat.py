#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.agent_developer_v1.model_benchmark import (
    REPORT_PROTOCOL,
    action_schema,
    load_public_tasks,
    run_benchmark,
)
from scripts.opencode_chat_support import (
    DEFAULT_OPENCODE_MODEL,
    OPENCODE_VARIANT,
    REPORT_MODEL,
    OpenCodeJSONClient,
    OpenCodeModelOutputError,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class OpenCodeChatPlanner:
    provider_id = "opencode-chat"
    model = REPORT_MODEL

    def __init__(self, *, model_id: str = DEFAULT_OPENCODE_MODEL) -> None:
        self.model_id = model_id
        self._client = OpenCodeJSONClient(model_id=model_id)

    def choose(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            return self._client.complete_json(
                messages=[dict(message) for message in messages],
                schema=action_schema(),
                purpose="Agent Developer next read-only DocAtlas evidence action",
            )
        except OpenCodeModelOutputError as exc:
            # A normal model response that still violates the structured-output
            # contract after bounded format repair is model-quality evidence, not
            # an infrastructure outage. Return a deliberately invalid action so
            # the existing scorer fails this task and continues to the next one.
            usage = dict(exc.usage)
            usage["model_output_valid"] = False
            usage["model_output_error"] = "schema_invalid_after_format_repair"
            return (
                {
                    "action": "invalid_model_output",
                    "question": "",
                    "scope": "",
                    "mode": "",
                    "module": "",
                    "module_path": "",
                    "reason": "model did not return one schema-valid JSON object",
                },
                usage,
            )


def _load_reusable_results(
    output: Path,
    *,
    selected_ids: set[str],
) -> list[dict[str, Any]]:
    if not output.is_file():
        return []
    try:
        report = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if (
        report.get("provider_id") != "opencode-chat"
        or report.get("model") != REPORT_MODEL
        or report.get("protocol") != REPORT_PROTOCOL
    ):
        return []
    reusable: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in report.get("tasks") or []:
        if not isinstance(result, dict):
            continue
        task_id = str(result.get("task_id") or "")
        if task_id not in selected_ids or task_id in seen:
            continue
        if not isinstance(result.get("score"), dict):
            continue
        if not isinstance(result.get("usage"), list) or not result["usage"]:
            continue
        reusable.append(result)
        seen.add(task_id)
    return reusable


def _aggregate_report(
    *,
    selected_tasks: list[dict[str, Any]],
    results: list[dict[str, Any]],
    infrastructure_errors: list[str],
) -> dict[str, Any]:
    order = {str(task["id"]): index for index, task in enumerate(selected_tasks)}
    results = sorted(results, key=lambda row: order[str(row["task_id"])])
    task_by_id = {str(task["id"]): task for task in selected_tasks}
    passed = sum(bool(result.get("passed")) for result in results)
    total_input = sum(
        int(row.get("input_tokens") or 0)
        for result in results
        for row in result.get("usage") or ()
    )
    total_output = sum(
        int(row.get("output_tokens") or 0)
        for result in results
        for row in result.get("usage") or ()
    )
    false_supported = sum(
        int((result.get("score") or {}).get("false_supported") or 0)
        for result in results
    )
    contamination = sum(
        int((result.get("score") or {}).get("forbidden_source_contamination") or 0)
        for result in results
    )
    scope_accuracy = (
        sum(bool((result.get("score") or {}).get("scope_contract_ok")) for result in results)
        / len(results)
        if results
        else 0.0
    )
    recovery_results = [
        result
        for result in results
        if task_by_id[str(result["task_id"])].get("class")
        in {"recovery", "module_plus_dependency"}
    ]
    recovery_accuracy = (
        sum(
            bool((result.get("score") or {}).get("recovery_contract_ok"))
            for result in recovery_results
        )
        / len(recovery_results)
        if recovery_results
        else 1.0
    )
    return {
        "schema_version": 1,
        "protocol": REPORT_PROTOCOL,
        "provider_id": "opencode-chat",
        "model": REPORT_MODEL,
        "task_count": len(selected_tasks),
        "executed_task_count": len(results),
        "passed_tasks": passed,
        "pass_rate": passed / len(selected_tasks) if selected_tasks else 0.0,
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
    parser = argparse.ArgumentParser(
        description="Run Agent Developer through the authenticated OpenCode chat provider"
    )
    parser.add_argument("--opencode-model", default=DEFAULT_OPENCODE_MODEL)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            REPO_ROOT
            / "eval"
            / "agent_developer_v1"
            / "results"
            / "model-benchmark.json"
        ),
    )
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse already executed OpenCode task results from --output",
    )
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    public_tasks = load_public_tasks()
    selected_ids = set(args.tasks) if args.tasks else {str(task["id"]) for task in public_tasks}
    selected_tasks = [task for task in public_tasks if str(task["id"]) in selected_ids]
    unknown = sorted(selected_ids - {str(task["id"]) for task in selected_tasks})
    if unknown:
        parser.error(f"unknown task ids: {unknown!r}")

    reusable = (
        _load_reusable_results(args.output, selected_ids=selected_ids)
        if args.resume
        else []
    )
    reusable_ids = {str(result["task_id"]) for result in reusable}
    remaining_ids = selected_ids - reusable_ids
    if reusable:
        print(
            "Resuming Agent Developer: "
            f"reusing {len(reusable)}/{len(selected_tasks)} completed tasks; "
            f"running {len(remaining_ids)} remaining."
        )

    planner = OpenCodeChatPlanner(model_id=args.opencode_model)
    fresh_results: list[dict[str, Any]] = []
    infrastructure_errors: list[str] = []
    if remaining_ids:
        fresh = run_benchmark(planner, task_ids=remaining_ids)
        fresh_results = list(fresh.get("tasks") or [])
        infrastructure_errors = list(fresh.get("infrastructure_errors") or [])

    report = _aggregate_report(
        selected_tasks=selected_tasks,
        results=[*reusable, *fresh_results],
        infrastructure_errors=infrastructure_errors,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Agent Developer OpenCode chat: "
        f"model={REPORT_MODEL}; variant={OPENCODE_VARIANT}; "
        f"{report['passed_tasks']}/{report['task_count']} pass; "
        f"executed={report['executed_task_count']}/{report['task_count']}; "
        f"scope={report['scope_accuracy']:.3f}; "
        f"recovery={report['recovery_accuracy']:.3f}; "
        f"false-supported={report['false_supported']}; "
        f"contamination={report['forbidden_source_contamination']}"
    )
    if report["infrastructure_errors"]:
        for error in report["infrastructure_errors"]:
            print(f"- infrastructure: {error}")
        return 2
    return 0 if float(report["pass_rate"]) >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
