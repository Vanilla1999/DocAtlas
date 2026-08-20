#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from docmancer.docs.tool_choice_eval import (
    OpenAICompatibleLowCostAdapter,
    _failure_report,
    _openai_completion,
    evaluate_tool_choice,
    installed_guidance,
    public_tool_schemas,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_API_BASE = "https://api.openai.com/v1"
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _retrying_completion(
    completion: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    max_attempts: int = 4,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    def complete(payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(max_attempts):
            try:
                return completion(payload)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in _RETRYABLE_STATUS_CODES or attempt + 1 >= max_attempts:
                    raise
                time.sleep(2.0 * (2**attempt))
        raise RuntimeError("unreachable retry state")

    return complete


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen Task 21 tool-choice evaluation through the OpenAI API"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "eval" / "results" / "task21_tool_choice_gate.json",
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    token = os.environ.get("OPENAI_API_KEY") or ""
    schemas: list[dict[str, Any]] | None = None
    try:
        if not token.strip():
            raise ValueError("OPENAI_API_KEY is required")
        guidance = installed_guidance()
        schemas = public_tool_schemas()
        raw_completion = _openai_completion(
            api_base=args.api_base,
            api_key=token,
            model=args.model,
        )
        adapter = OpenAICompatibleLowCostAdapter(
            model_version=args.model,
            completion=_retrying_completion(raw_completion),
        )
        report = evaluate_tool_choice(
            adapter,
            guidance=guidance,
            tool_schemas=schemas,
        )
    except Exception:
        report = _failure_report(
            model_version=args.model,
            reason="live evaluation failed",
            tool_schemas=schemas,
        )
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 2

    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = report["metrics"]
    print(
        "Task 21 live tool-choice: "
        f"first-tool={metrics['first_tool_accuracy']:.3f}; "
        f"unnecessary={metrics['unnecessary_prepare_or_status_rate']:.3f}; "
        f"legacy={metrics['legacy_tool_hallucination_rate']:.3f}; "
        f"copy={metrics['next_action_copy_accuracy']:.3f}; "
        f"retry={metrics['original_question_retry_rate']:.3f}; "
        f"passed={report['passed']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
