#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from docmancer.docs.tool_choice_eval import (
    OpenAICompatibleLowCostAdapter,
    _failure_report,
    evaluate_tool_choice,
    installed_guidance,
    public_tool_schemas,
)
from scripts.opencode_chat_support import (
    DEFAULT_OPENCODE_MODEL,
    OPENCODE_VARIANT,
    REPORT_MODEL,
    OpenCodeJSONClient,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _decision_schema(tool_names: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "tool": {
                "anyOf": [
                    {"type": "string", "enum": tool_names},
                    {"type": "null"},
                ]
            },
            "arguments": {"type": "object"},
        },
        "required": ["tool", "arguments"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen Task 21 through the authenticated OpenCode chat provider"
    )
    parser.add_argument("--opencode-model", default=DEFAULT_OPENCODE_MODEL)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "eval" / "results" / "task21_tool_choice_gate.json",
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    schemas: list[dict[str, Any]] | None = None
    try:
        guidance = installed_guidance()
        schemas = public_tool_schemas()
        client = OpenCodeJSONClient(model_id=args.opencode_model)
        decision_schema = _decision_schema([str(tool["name"]) for tool in schemas])

        def complete(payload: dict[str, Any]) -> dict[str, Any]:
            messages = [
                {
                    "role": "system",
                    "content": str(payload["guidance"]),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "scenario": payload["scenario"],
                            "public_tools": payload["tools"],
                            "instruction": (
                                "Choose the first public DocAtlas tool call for this scenario. "
                                "If no DocAtlas tool should be called, return tool=null and arguments={}."
                            ),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ]
            decision, _usage = client.complete_json(
                messages=messages,
                schema=decision_schema,
                purpose="Task 21 frozen tool-choice decision",
            )
            return decision

        adapter = OpenAICompatibleLowCostAdapter(
            model_version=REPORT_MODEL,
            completion=complete,
        )
        report = evaluate_tool_choice(
            adapter,
            guidance=guidance,
            tool_schemas=schemas,
        )
        report["provider_id"] = "opencode-chat"
        report["reasoning_effort"] = OPENCODE_VARIANT
        report["opencode_model_id"] = args.opencode_model
    except Exception as exc:
        report = _failure_report(
            model_version=REPORT_MODEL,
            reason="live evaluation failed",
            tool_schemas=schemas,
        )
        report["provider_id"] = "opencode-chat"
        report["reasoning_effort"] = OPENCODE_VARIANT
        report["opencode_model_id"] = args.opencode_model
        report["provider_error"] = {
            "provider": "opencode-chat",
            "error_type": exc.__class__.__name__,
            "detail": str(exc)[:500],
        }
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "Task 21 OpenCode provider error: "
            + json.dumps(report["provider_error"], sort_keys=True)
        )
        return 2

    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = report["metrics"]
    print(
        "Task 21 OpenCode chat: "
        f"model={REPORT_MODEL}; variant={OPENCODE_VARIANT}; "
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
