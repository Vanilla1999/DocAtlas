#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from eval.agent_developer_v1.model_benchmark import action_schema, run_benchmark
from eval.task_level.github_models import GitHubModelsClient, OPENAI_API_PROVIDER


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gpt-5.4-mini"


class OpenAIAPIPlanner:
    provider_id = OPENAI_API_PROVIDER.provider_id

    def __init__(self, token: str, *, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._client = GitHubModelsClient(token, provider=OPENAI_API_PROVIDER)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the model-backed Agent Developer benchmark through the OpenAI API"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "eval" / "agent_developer_v1" / "results" / "model-benchmark.json",
    )
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    token = os.environ.get("OPENAI_API_KEY") or ""
    if not token.strip():
        print("Agent Developer OpenAI benchmark: missing OPENAI_API_KEY")
        return 2

    planner = OpenAIAPIPlanner(token, model=args.model)
    report = run_benchmark(planner, task_ids=set(args.tasks) if args.tasks else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Agent Developer OpenAI benchmark: {report['passed_tasks']}/{report['task_count']} "
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
