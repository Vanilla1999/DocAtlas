#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

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

    agent_rc = _run(
        "Agent Developer live benchmark",
        [
            sys.executable,
            "scripts/run_agent_developer_opencode_chat.py",
            "--opencode-model",
            args.opencode_model,
            "--min-pass-rate",
            "0.0",
            "--output",
            str(AGENT_REPORT),
        ],
    )

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
        print("Reports were left in place for inspection; do not commit them as passing evidence yet.")
        return 1

    print("\nLive closure PASS. Evidence is ready to commit:")
    print(f"  {TASK21_REPORT.relative_to(REPO_ROOT)}")
    print(f"  {AGENT_REPORT.relative_to(REPO_ROOT)}")
    print("Use git add -f for the Agent Developer report if your ignore rules require it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
