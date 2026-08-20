#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.agent_developer_v1.model_benchmark import action_schema, run_benchmark
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
            # The provider returned normally but the model failed the structured
            # response contract even after the bounded format-repair attempt.
            # That is model-quality evidence, not an infrastructure outage. Return
            # a deliberately invalid action so the existing benchmark scorer marks
            # this task failed and continues with the remaining public tasks.
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
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    planner = OpenCodeChatPlanner(model_id=args.opencode_model)
    report = run_benchmark(
        planner,
        task_ids=set(args.tasks) if args.tasks else None,
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
