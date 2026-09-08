"""Opt-in live probe for host-side get_docs_context question planning."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docmancer.docs.tool_choice_eval import (
    MODEL_ADAPTER_NAME,
    OpenAICompatibleLowCostAdapter,
    ToolChoiceScenario,
    _openai_completion,
    installed_guidance,
    public_tool_schemas,
)

REPEATS = 3
THRESHOLD = 1.0


@dataclass(frozen=True)
class QuestionPlanningProbe:
    scenario_id: str
    prompt: str
    concrete_questions: tuple[str, ...]


QUESTION_PLANNING_PROBES = (
    QuestionPlanningProbe(
        "multi-question-evaluation",
        "Evaluate DocAtlas by asking these questions through its MCP and assess the results: "
        "What problem does DocAtlas solve? How is the project architecture organized? "
        "How do I install it locally and verify it works?",
        (
            "What problem does DocAtlas solve?",
            "How is the project architecture organized?",
            "How do I install it locally and verify it works?",
        ),
    ),
    QuestionPlanningProbe(
        "ru-multi-question-evaluation",
        "Проверь DocAtlas через MCP на этих вопросах и оцени ответы: "
        "Какую проблему решает DocAtlas? Как устроена архитектура проекта? "
        "Как проверить актуальность индекса?",
        (
            "Какую проблему решает DocAtlas?",
            "Как устроена архитектура проекта?",
            "Как проверить актуальность индекса?",
        ),
    ),
)


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _append_synthetic_result(
    messages: list[dict[str, Any]], *, turn: int, tool: str, arguments: dict[str, Any]
) -> None:
    call_id = f"planning-{turn}"
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {
                "name": tool,
                "arguments": json.dumps(arguments, ensure_ascii=False, sort_keys=True),
            },
        }],
    })
    if tool == "get_docs_context":
        content = {
            "answer_available": True,
            "query_coverage": "full",
            "question": arguments.get("question"),
            "sources": [{"path": "synthetic-probe.md"}],
        }
    else:
        content = {"status": "synthetic", "tool": tool}
    messages.append({
        "role": "tool",
        "tool_call_id": call_id,
        "name": tool,
        "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
    })


def evaluate_question_planning(
    adapter: Any, *, guidance: str, tool_schemas: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check the full multi-call trajectory for independent documentation questions."""
    if not guidance.strip():
        raise ValueError("installed guidance must not be empty")
    if tool_schemas != public_tool_schemas():
        raise ValueError("tool_schemas must be the exact published schemas")

    results: list[dict[str, Any]] = []
    for probe in QUESTION_PLANNING_PROBES:
        expected = list(probe.concrete_questions)
        expected_normalized = {_normalize(question) for question in expected}
        for repeat in range(1, REPEATS + 1):
            messages: list[dict[str, Any]] = [{"role": "user", "content": probe.prompt}]
            calls: list[dict[str, Any]] = []
            terminated = False

            for turn in range(1, len(expected) + 2):
                scenario = ToolChoiceScenario(
                    scenario_id=probe.scenario_id,
                    prompt=probe.prompt,
                    expected_first_tool="get_docs_context",
                    messages=tuple(messages),
                )
                response = dict(adapter.choose_tool(
                    guidance=guidance,
                    tool_schemas=tool_schemas,
                    scenario=scenario,
                ) or {})
                tool = response.get("tool")
                if not tool:
                    terminated = True
                    break

                arguments = response.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                question = str(arguments.get("question") or "")
                raw_lookups = arguments.get("lookup_queries") or []
                lookups = [str(value) for value in raw_lookups] if isinstance(raw_lookups, list) else []
                calls.append({
                    "turn": turn,
                    "tool": tool,
                    "question": question,
                    "lookup_queries": lookups,
                })
                _append_synthetic_result(
                    messages, turn=turn, tool=str(tool), arguments=arguments
                )
                if len(calls) > len(expected):
                    break

            context_calls = [call for call in calls if call["tool"] == "get_docs_context"]
            context_questions = [call["question"] for call in context_calls]
            normalized_questions = [_normalize(question) for question in context_questions]
            all_questions_covered = (
                len(context_questions) == len(expected)
                and set(normalized_questions) == expected_normalized
            )
            one_call_per_question = (
                all_questions_covered
                and len(normalized_questions) == len(set(normalized_questions))
            )
            only_context_calls = (
                len(calls) == len(expected)
                and all(call["tool"] == "get_docs_context" for call in calls)
            )
            meta_request_not_used = all(
                _normalize(call["question"]) != _normalize(probe.prompt)
                for call in context_calls
            )
            no_independent_batching = True
            for call in context_calls:
                own = _normalize(call["question"])
                other_questions = expected_normalized - {own}
                if any(_normalize(lookup) in other_questions for lookup in call["lookup_queries"]):
                    no_independent_batching = False
                    break
            terminated_after_questions = terminated and len(calls) == len(expected)
            passed = bool(
                all_questions_covered
                and one_call_per_question
                and only_context_calls
                and meta_request_not_used
                and no_independent_batching
                and terminated_after_questions
            )
            results.append({
                "scenario_id": probe.scenario_id,
                "repeat": repeat,
                "expected_question_count": len(expected),
                "context_call_count": len(context_calls),
                "calls": calls,
                "all_questions_covered": all_questions_covered,
                "one_call_per_question": one_call_per_question,
                "only_context_calls": only_context_calls,
                "meta_request_not_used": meta_request_not_used,
                "no_independent_batching": no_independent_batching,
                "terminated_after_questions": terminated_after_questions,
                "passed": passed,
            })

    accuracy = sum(row["passed"] for row in results) / len(results)
    return {
        "schema_version": "docatlas-agent-question-planning-trajectory-v1",
        "adapter": {"name": adapter.name, "model_version": adapter.model_version},
        "probe_count": len(QUESTION_PLANNING_PROBES),
        "repeats": REPEATS,
        "threshold": THRESHOLD,
        "trajectory_accuracy": accuracy,
        "question_planning_accuracy": accuracy,
        "passed": accuracy >= THRESHOLD,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the opt-in live DocAtlas question-planning trajectory probe.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-base", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        adapter = OpenAICompatibleLowCostAdapter(
            model_version=args.model,
            completion=_openai_completion(
                api_base=args.api_base,
                api_key=api_key,
                model=args.model,
            ),
        )
        report = evaluate_question_planning(
            adapter,
            guidance=installed_guidance(),
            tool_schemas=public_tool_schemas(),
        )
    except Exception:
        report = {
            "schema_version": "docatlas-agent-question-planning-trajectory-v1",
            "adapter": {"name": MODEL_ADAPTER_NAME, "model_version": args.model},
            "probe_count": len(QUESTION_PLANNING_PROBES),
            "repeats": REPEATS,
            "threshold": THRESHOLD,
            "trajectory_accuracy": 0.0,
            "question_planning_accuracy": 0.0,
            "passed": False,
            "status": "failed",
            "reason": "live evaluation failed",
            "results": [],
        }
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1

    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
