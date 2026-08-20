#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "medium"
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
            f"model={(report.get('adapter') or {}).get('model_version')}; "
            f"reasoning={report.get('reasoning_effort')}; "
            f"first-tool={metrics.get('first_tool_accuracy')}; "
            f"copy={metrics.get('next_action_copy_accuracy')}; "
            f"retry={metrics.get('original_question_retry_rate')}"
        )

    if AGENT_REPORT.is_file():
        report = _load(AGENT_REPORT)
        print(
            "Agent Developer: "
            f"executed={report.get('executed_task_count')}/{report.get('task_count')}; "
            f"passed={report.get('passed_tasks')}; "
            f"pass-rate={report.get('pass_rate')}; "
            f"scope={report.get('scope_accuracy')}; "
            f"recovery={report.get('recovery_accuracy')}; "
            f"false-supported={report.get('false_supported')}; "
            f"contamination={report.get('forbidden_source_contamination')}; "
            f"infra-errors={len(report.get('infrastructure_errors') or [])}"
        )


def main() -> int:
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        print(
            "OPENAI_API_KEY is not set in this shell. "
            "No live evaluation was started.",
            file=sys.stderr,
        )
        return 2

    print(
        f"DocAtlas live closure: model={MODEL}; reasoning={REASONING_EFFORT}; "
        "Task21=20x3; AgentDeveloper=11 tasks",
        flush=True,
    )

    task21_rc = _run(
        "Task 21 live tool choice",
        [
            sys.executable,
            "scripts/run_task21_openai_live.py",
            "--model",
            MODEL,
            "--output",
            str(TASK21_REPORT),
        ],
    )

    agent_rc = _run(
        "Agent Developer live benchmark",
        [
            sys.executable,
            "scripts/run_agent_developer_openai_benchmark.py",
            "--model",
            MODEL,
            "--min-pass-rate",
            "0.0",
            "--output",
            str(AGENT_REPORT),
        ],
    )

    verify_rc = 2
    if AGENT_REPORT.is_file():
        verify_rc = _run(
            "Seal and verify Agent Developer report",
            [
                sys.executable,
                "scripts/verify_agent_developer_model_report.py",
                str(AGENT_REPORT),
                "--seal",
                "--expected-model",
                MODEL,
                "--min-pass-rate",
                "0.0",
            ],
        )
    else:
        print("Agent Developer report was not produced; verifier skipped.")

    _print_summary()

    evidence_rc = _run(
        "Provider-free committed-evidence contract",
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/docs/test_tool_choice_eval.py",
            "tests/test_live_evaluation_evidence.py",
            "-q",
        ],
    )

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
