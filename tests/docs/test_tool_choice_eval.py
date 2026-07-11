from docmancer.docs.tool_choice_eval import (
    REPEATS,
    SCENARIOS,
    evaluate_tool_choice,
    installed_guidance,
    public_tool_schemas,
)
import json
from pathlib import Path


class _Adapter:
    name = "openai-compatible-low-cost"
    model_version = "test"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        return {
            "tool": scenario.expected_first_tool,
            "arguments": (
                {"question": scenario.expected_retry_question}
                if scenario.expected_retry_question is not None
                else scenario.expected_next_action
            ),
        }


def test_tool_choice_evaluation_has_frozen_20_scenarios_and_three_repeats():
    assert len(SCENARIOS) == 20
    report = evaluate_tool_choice(
        _Adapter(), guidance=installed_guidance(), tool_schemas=public_tool_schemas()
    )
    assert len(report["results"]) == len(SCENARIOS) * REPEATS
    assert report["metrics"]["first_tool_accuracy"] == 1.0
    assert report["metrics"]["legacy_tool_hallucination_rate"] == 0.0
    assert report["passed"] is True
    assert report["tool_schema_version"].startswith("sha256:")


def test_tool_choice_evaluation_rejects_fake_or_empty_schemas():
    import pytest

    with pytest.raises(ValueError, match="actual three public"):
        evaluate_tool_choice(_Adapter(), guidance="contract", tool_schemas=[])


def test_retry_metric_requires_the_exact_original_question():
    class WrongRetryAdapter(_Adapter):
        def choose_tool(self, *, guidance, tool_schemas, scenario):
            response = super().choose_tool(
                guidance=guidance, tool_schemas=tool_schemas, scenario=scenario
            )
            if scenario.scenario_id == "retry-question":
                response["arguments"] = {"question": "A different question"}
            return response

    report = evaluate_tool_choice(
        WrongRetryAdapter(), guidance=installed_guidance(), tool_schemas=public_tool_schemas()
    )
    assert report["metrics"]["original_question_retry_rate"] == 0.0
    assert report["passed"] is False


def test_implementation_fact_scenarios_do_not_expect_a_docs_tool():
    scenario = next(item for item in SCENARIOS if item.scenario_id == "project-code-boundary")
    assert scenario.expected_first_tool is None


def test_committed_live_report_is_explicit_and_matches_frozen_scenarios():
    report_path = Path("eval/results/task21_tool_choice_gate.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["tool_schema_version"].startswith("sha256:")
    assert {item["scenario_id"] for item in report["results"]} == {
        scenario.scenario_id for scenario in SCENARIOS
    }
