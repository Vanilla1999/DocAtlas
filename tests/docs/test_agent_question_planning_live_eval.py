from __future__ import annotations

from docmancer.docs.agent_question_planning_eval import (
    QUESTION_PLANNING_PROBES,
    evaluate_question_planning,
)
from docmancer.docs.tool_choice_eval import installed_guidance, public_tool_schemas


class _GoodAdapter:
    name = "openai-compatible-low-cost"
    model_version = "test-good"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        probe = next(item for item in QUESTION_PLANNING_PROBES if item.scenario_id == scenario.scenario_id)
        return {
            "tool": "get_docs_context",
            "arguments": {
                "question": probe.concrete_questions[0],
                "lookup_queries": ["same question retrieval clarification"],
            },
        }


class _BadBatchingAdapter:
    name = "openai-compatible-low-cost"
    model_version = "test-bad"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        probe = next(item for item in QUESTION_PLANNING_PROBES if item.scenario_id == scenario.scenario_id)
        return {
            "tool": "get_docs_context",
            "arguments": {
                "question": scenario.prompt,
                "lookup_queries": list(probe.concrete_questions),
            },
        }


def test_question_planning_probe_accepts_one_question_per_call() -> None:
    report = evaluate_question_planning(
        _GoodAdapter(),
        guidance=installed_guidance(),
        tool_schemas=public_tool_schemas(),
    )

    assert report["question_planning_accuracy"] == 1.0
    assert report["passed"] is True
    assert all(row["concrete_question"] for row in report["results"])
    assert all(row["no_independent_batching"] for row in report["results"])


def test_question_planning_probe_rejects_meta_question_batching() -> None:
    report = evaluate_question_planning(
        _BadBatchingAdapter(),
        guidance=installed_guidance(),
        tool_schemas=public_tool_schemas(),
    )

    assert report["question_planning_accuracy"] == 0.0
    assert report["passed"] is False
    assert all(not row["meta_request_not_used"] for row in report["results"])
    assert all(not row["no_independent_batching"] for row in report["results"])


def test_question_planning_probe_uses_real_public_tool_schemas() -> None:
    fabricated = [dict(tool) for tool in public_tool_schemas()]
    fabricated[0] = {**fabricated[0], "description": "fake"}

    try:
        evaluate_question_planning(
            _GoodAdapter(), guidance=installed_guidance(), tool_schemas=fabricated
        )
    except ValueError as exc:
        assert "exact published schemas" in str(exc)
    else:
        raise AssertionError("fabricated schemas must be rejected")
