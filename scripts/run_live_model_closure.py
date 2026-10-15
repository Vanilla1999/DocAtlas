#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from docmancer.docs.tool_choice_eval import (
    REPEATS,
    SCENARIOS,
    THRESHOLDS,
    _schema_version,
    installed_guidance,
    public_tool_schemas,
    tool_choice_contract_sha256,
)
from scripts.opencode_chat_support import (
    DEFAULT_OPENCODE_MODEL,
    OPENCODE_VARIANT,
    REPORT_MODEL,
    canonical_model_name,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK21_REPORT = REPO_ROOT / "eval" / "results" / "task21_tool_choice_gate.json"
AGENT_REPORT = (
    REPO_ROOT
    / "eval"
    / "agent_developer_v1"
    / "results"
    / "model-benchmark.json"
)


def _run(label: str, args: Sequence[str]) -> int:
    print(f"\n== {label} ==", flush=True)
    completed = subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=False,
    )
    print(f"{label}: exit={completed.returncode}", flush=True)
    return completed.returncode


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _task21_outcomes_match_current_contract(report: dict, results: list[dict]) -> bool:
    """Recompute outcome consistency and quality from the recorded decisions."""
    scenarios = {scenario.scenario_id: scenario for scenario in SCENARIOS}
    public_names = {"get_docs_context", "prepare_docs", "docs_status"}
    actions: list[bool] = []
    retries: list[bool] = []
    for row in results:
        scenario = scenarios.get(row.get("scenario_id"))
        if scenario is None:
            return False
        tool = row.get("tool")
        if tool is not None and not isinstance(tool, str):
            return False
        expected_flags = {
            "first_tool_correct": tool == scenario.expected_first_tool,
            "legacy_tool_hallucinated": bool(tool and tool not in public_names),
            "unnecessary_prepare_or_status": (
                scenario.expected_first_tool not in {"prepare_docs", "docs_status"}
                and tool in {"prepare_docs", "docs_status"}
            ),
        }
        if any(type(row.get(key)) is not bool or row[key] != value
               for key, value in expected_flags.items()):
            return False
        for key, required, values in (
            ("next_action_correct", bool(scenario.expected_next_action), actions),
            ("original_question_retried", scenario.expected_retry_question is not None, retries),
        ):
            value = row.get(key)
            if required:
                if type(value) is not bool:
                    return False
                values.append(value)
            elif value is not None:
                return False
    count = len(results)
    if not count or not actions or not retries:
        return False
    computed = {
        "first_tool_accuracy": sum(row["first_tool_correct"] for row in results) / count,
        "legacy_tool_hallucination_rate": sum(row["legacy_tool_hallucinated"] for row in results) / count,
        "unnecessary_prepare_or_status_rate": sum(row["unnecessary_prepare_or_status"] for row in results) / count,
        "next_action_copy_accuracy": sum(actions) / len(actions),
        "original_question_retry_rate": sum(retries) / len(retries),
    }
    metrics = report.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(computed):
        return False
    for key, actual in computed.items():
        recorded = metrics[key]
        if (not isinstance(recorded, (int, float)) or isinstance(recorded, bool)
                or not math.isfinite(recorded)
                or not math.isclose(recorded, actual, rel_tol=0.0, abs_tol=1e-12)):
            return False
    return (
        computed["first_tool_accuracy"] >= THRESHOLDS["first_tool_accuracy"]
        and computed["legacy_tool_hallucination_rate"] <= THRESHOLDS["legacy_tool_hallucination_rate"]
        and computed["unnecessary_prepare_or_status_rate"] <= THRESHOLDS["unnecessary_prepare_or_status_rate"]
        and computed["next_action_copy_accuracy"] >= THRESHOLDS["next_action_copy_accuracy"]
        and computed["original_question_retry_rate"] >= THRESHOLDS["original_question_retry_rate"]
    )


def _task21_report_reusable() -> bool:
    if not TASK21_REPORT.is_file():
        return False
    try:
        report = _load(TASK21_REPORT)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict):
        return False
    results = report.get("results")
    if not isinstance(results, list) or any(not isinstance(row, dict) for row in results):
        return False
    adapter = report.get("adapter")
    if not isinstance(adapter, dict):
        return False
    schemas = public_tool_schemas()
    contract = tool_choice_contract_sha256(guidance=installed_guidance(), tool_schemas=schemas)
    expected_rows = {(scenario.scenario_id, repeat): scenario.expected_first_tool
                     for scenario in SCENARIOS for repeat in range(1, REPEATS + 1)}
    observed_rows = [(row.get("scenario_id"), row.get("repeat")) for row in results]
    if any(not isinstance(key[0], str) or type(key[1]) is not int for key in observed_rows):
        return False
    return (
        report.get("passed") is True
        and report.get("tool_schema_version") == _schema_version(schemas)
        and report.get("tool_choice_contract_sha256") == contract
        and report.get("thresholds") == THRESHOLDS
        and report.get("provider_id") == "opencode-chat"
        and adapter.get("model_version") == REPORT_MODEL
        and report.get("reasoning_effort") == OPENCODE_VARIANT
        and report.get("scenario_count") == len(SCENARIOS)
        and report.get("repeats") == REPEATS
        and len(results) == len(expected_rows)
        and set(observed_rows) == set(expected_rows)
        and all(row.get("expected_tool") == expected_rows[key]
                for row, key in zip(results, observed_rows))
        and all(item.get("status") != "not_run" for item in results)
        and _task21_outcomes_match_current_contract(report, results)
    )


def _print_summary() -> None:
    if TASK21_REPORT.is_file():
        report = _load(TASK21_REPORT)
        metrics = report.get("metrics") or {}
        print(
            "Task 21: "
            f"passed={report.get('passed')}; "
            f"provider={report.get('provider_id')}; "
            f"model={(report.get('adapter') or {}).get('model_version')}; "
            f"variant={report.get('reasoning_effort')}; "
            f"first-tool={metrics.get('first_tool_accuracy')}; "
            f"copy={metrics.get('next_action_copy_accuracy')}; "
            f"retry={metrics.get('original_question_retry_rate')}"
        )
        provider_error = report.get("provider_error")
        if isinstance(provider_error, dict):
            print(
                "Task 21 provider error: "
                + json.dumps(provider_error, sort_keys=True)
            )

    if AGENT_REPORT.is_file():
        report = _load(AGENT_REPORT)
        print(
            "Agent Developer: "
            f"provider={report.get('provider_id')}; "
            f"executed={report.get('executed_task_count')}/{report.get('task_count')}; "
            f"passed={report.get('passed_tasks')}; "
            f"pass-rate={report.get('pass_rate')}; "
            f"scope={report.get('scope_accuracy')}; "
            f"recovery={report.get('recovery_accuracy')}; "
            f"false-supported={report.get('false_supported')}; "
            f"contamination={report.get('forbidden_source_contamination')}; "
            f"infra-errors={len(report.get('infrastructure_errors') or [])}"
        )
        for error in report.get("infrastructure_errors") or []:
            print(f"Agent Developer infrastructure: {error}")


def _agent_report_complete() -> bool:
    if not AGENT_REPORT.is_file():
        return False
    report = _load(AGENT_REPORT)
    return (
        report.get("executed_task_count") == report.get("task_count") == 11
        and not (report.get("infrastructure_errors") or [])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run DocAtlas live closure through the authenticated OpenCode chat provider"
    )
    parser.add_argument("--opencode-model", default=DEFAULT_OPENCODE_MODEL)
    parser.add_argument(
        "--force-task21",
        action="store_true",
        help="rerun Task 21 even when a complete passing OpenCode report already exists",
    )
    parser.add_argument(
        "--fresh-agent",
        action="store_true",
        help="ignore even exact-contract reusable Agent Developer results and rerun all 11 tasks",
    )
    args = parser.parse_args(argv)

    if canonical_model_name(args.opencode_model) != REPORT_MODEL:
        parser.error(f"live closure is pinned to {REPORT_MODEL}")
    if not shutil.which("opencode"):
        print(
            "opencode executable was not found in PATH. No live evaluation was started.",
            file=sys.stderr,
        )
        return 2

    print(
        f"DocAtlas live closure: provider=opencode-chat; "
        f"model={args.opencode_model}; variant={OPENCODE_VARIANT}; "
        "Task21=20x3; AgentDeveloper=11 tasks",
        flush=True,
    )

    if not args.force_task21 and _task21_report_reusable():
        print("\n== Task 21 live tool choice ==", flush=True)
        print(
            "Reusing existing complete passing Task 21 OpenCode evidence; "
            "use --force-task21 to rerun 20x3.",
            flush=True,
        )
        task21_rc = 0
    else:
        task21_rc = _run(
            "Task 21 live tool choice",
            [
                sys.executable,
                "scripts/run_task21_opencode_chat.py",
                "--opencode-model",
                args.opencode_model,
                "--output",
                str(TASK21_REPORT),
            ],
        )

    agent_args = [
        sys.executable,
        "scripts/run_agent_developer_opencode_chat.py",
        "--opencode-model",
        args.opencode_model,
        "--min-pass-rate",
        "0.0",
        "--output",
        str(AGENT_REPORT),
    ]
    if not args.fresh_agent:
        agent_args.append("--resume")
    agent_rc = _run("Agent Developer live benchmark", agent_args)

    verify_rc = 0
    if _agent_report_complete():
        verify_rc = _run(
            "Seal and verify Agent Developer report",
            [
                sys.executable,
                "scripts/verify_agent_developer_model_report.py",
                str(AGENT_REPORT),
                "--seal",
                "--expected-model",
                REPORT_MODEL,
                "--min-pass-rate",
                "0.0",
            ],
        )
    elif agent_rc == 0:
        print("Agent Developer runner returned success without a complete report.")
        verify_rc = 1
    else:
        print("Agent Developer verifier skipped because the provider run is incomplete.")

    _print_summary()

    evidence_rc = 0
    if task21_rc == 0 and agent_rc == 0 and verify_rc == 0:
        evidence_rc = _run(
            "Provider-free committed-evidence contract",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/docs/test_tool_choice_eval.py",
                "-q",
            ],
        )
    else:
        print("Committed-evidence tests skipped until both live reports are complete.")

    failed = {
        "task21": task21_rc,
        "agent": agent_rc,
        "verify": verify_rc,
        "evidence_tests": evidence_rc,
    }
    failures = {name: code for name, code in failed.items() if code != 0}
    if failures:
        print(f"\nLive closure is NOT ready: {failures}")
        print("Reports were left in place for inspection; do not commit them as complete evidence yet.")
        return 1

    print("\nLive closure EVIDENCE COMPLETE. Evidence is ready to commit:")
    print(f"  {TASK21_REPORT.relative_to(REPO_ROOT)}")
    print(f"  {AGENT_REPORT.relative_to(REPO_ROOT)}")
    print(
        "Agent pass-rate is reported as model-quality evidence; the frozen closure "
        "contract intentionally does not impose a retrospective minimum pass-rate."
    )
    print("Use git add -f for the Agent Developer report if your ignore rules require it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
