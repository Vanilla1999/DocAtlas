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


def evaluate_question_planning(adapter: Any, *, guidance: str, tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that a host does not batch independent questions into lookup_queries."""
    if not guidance.strip():
        raise ValueError("installed guidance must not be empty")
    if tool_schemas != public_tool_schemas():
        raise ValueError("tool_schemas must be the exact published schemas")

    results: list[dict[str, Any]] = []
    for probe in QUESTION_PLANNING_PROBES:
        scenario = ToolChoiceScenario(
            scenario_id=probe.scenario_id,
            prompt=probe.prompt,
            expected_first_tool="get_docs_context",
        )
        independent = set(probe.concrete_questions)
        for repeat in range(1, REPEATS + 1):
            response = dict(adapter.choose_tool(
                guidance=guidance,
                tool_schemas=tool_schemas,
                scenario=scenario,
            ) or {})
            arguments = response.get("arguments") or {}
            question = str(arguments.get("question") or "")
            raw_lookups = arguments.get("lookup_queries") or []
            lookups = [str(value) for value in raw_lookups] if isinstance(raw_lookups, list) else []
            other_questions = independent - {question}
            concrete_question = question in independent
            no_independent_batching = not any(lookup in other_questions for lookup in lookups)
            meta_request_not_used = question != probe.prompt
            passed = bool(
                response.get("tool") == "get_docs_context"
                and concrete_question
                and meta_request_not_used
                and no_independent_batching
            )
            results.append({
                "scenario_id": probe.scenario_id,
                "repeat": repeat,
                "tool": response.get("tool"),
                "question": question,
                "lookup_queries": lookups,
                "concrete_question": concrete_question,
                "meta_request_not_used": meta_request_not_used,
                "no_independent_batching": no_independent_batching,
                "passed": passed,
            })

    accuracy = sum(row["passed"] for row in results) / len(results)
    return {
        "schema_version": "docatlas-agent-question-planning-probe-v1",
        "adapter": {"name": adapter.name, "model_version": adapter.model_version},
        "probe_count": len(QUESTION_PLANNING_PROBES),
        "repeats": REPEATS,
        "threshold": THRESHOLD,
        "question_planning_accuracy": accuracy,
        "passed": accuracy >= THRESHOLD,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the opt-in live DocAtlas question-planning probe.")
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
            "schema_version": "docatlas-agent-question-planning-probe-v1",
            "adapter": {"name": MODEL_ADAPTER_NAME, "model_version": args.model},
            "probe_count": len(QUESTION_PLANNING_PROBES),
            "repeats": REPEATS,
            "threshold": THRESHOLD,
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
