from __future__ import annotations

from docmancer.docs.agent_question_planning_eval import (
    QUESTION_PLANNING_PROBES,
    evaluate_question_planning,
)
from docmancer.docs.tool_choice_eval import installed_guidance, public_tool_schemas


def _probe_for(scenario):
    return next(
        item for item in QUESTION_PLANNING_PROBES
        if item.scenario_id == scenario.scenario_id
    )


def _prior_context_calls(scenario) -> int:
    return sum(
        1 for message in (scenario.messages or ())
        if message.get("role") == "tool" and message.get("name") == "get_docs_context"
    )


class _GoodAdapter:
    name = "openai-compatible-low-cost"
    model_version = "test-good"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        probe = _probe_for(scenario)
        prior = _prior_context_calls(scenario)
        if prior >= len(probe.concrete_questions):
            return {"tool": None}
        return {
            "tool": "get_docs_context",
            "arguments": {
                "question": probe.concrete_questions[prior],
                "lookup_queries": ["same question retrieval clarification"],
            },
        }


class _StopsAfterFirstAdapter:
    name = "openai-compatible-low-cost"
    model_version = "test-stops-early"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        probe = _probe_for(scenario)
        if _prior_context_calls(scenario):
            return {"tool": None}
        return {
            "tool": "get_docs_context",
            "arguments": {"question": probe.concrete_questions[0]},
        }


class _BadBatchingAdapter:
    name = "openai-compatible-low-cost"
    model_version = "test-bad"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        probe = _probe_for(scenario)
        if _prior_context_calls(scenario):
            return {"tool": None}
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

    assert report["trajectory_accuracy"] == 1.0
    assert report["question_planning_accuracy"] == 1.0
    assert report["passed"] is True
    assert all(row["all_questions_covered"] for row in report["results"])
    assert all(row["one_call_per_question"] for row in report["results"])
    assert all(
        row["context_call_count"] == row["expected_question_count"]
        for row in report["results"]
    )
    assert all(row["terminated_after_questions"] for row in report["results"])

    truncated = evaluate_question_planning(
        _StopsAfterFirstAdapter(),
        guidance=installed_guidance(),
        tool_schemas=public_tool_schemas(),
    )
    assert truncated["trajectory_accuracy"] == 0.0
    assert truncated["passed"] is False
    assert all(not row["all_questions_covered"] for row in truncated["results"])


def test_question_planning_probe_rejects_meta_question_batching() -> None:
    report = evaluate_question_planning(
        _BadBatchingAdapter(),
        guidance=installed_guidance(),
        tool_schemas=public_tool_schemas(),
    )

    assert report["trajectory_accuracy"] == 0.0
    assert report["question_planning_accuracy"] == 0.0
    assert report["passed"] is False
    assert all(not row["meta_request_not_used"] for row in report["results"])
    assert all(not row["no_independent_batching"] for row in report["results"])
    assert all(not row["all_questions_covered"] for row in report["results"])


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
