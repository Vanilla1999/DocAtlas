from docmancer.docs.tool_choice_eval import (
    REPEATS,
    SCENARIOS,
    evaluate_tool_choice,
    installed_guidance,
    main,
    public_tool_schemas,
)
import json
from pathlib import Path


class _Adapter:
    name = "openai-compatible-low-cost"
    model_version = "test"

    def choose_tool(self, *, guidance, tool_schemas, scenario):
        if scenario.expected_retry_question is not None and scenario.messages and any(
            message.get("name") == "prepare_docs" for message in scenario.messages
        ):
            return {"tool": "get_docs_context", "arguments": {"question": scenario.expected_retry_question}}
        return {"tool": scenario.expected_first_tool, "arguments": scenario.expected_next_action}


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

    fabricated = [dict(tool) for tool in public_tool_schemas()]
    fabricated[0] = {**fabricated[0], "description": "fabricated"}
    with pytest.raises(ValueError, match="published schemas"):
        evaluate_tool_choice(_Adapter(), guidance="contract", tool_schemas=fabricated)


def test_public_tool_schemas_are_the_published_mcp_surface():
    from docmancer.mcp.docs_server import PUBLIC_TOOL_NAMES, TOOLS

    assert public_tool_schemas() == [
        tool for tool in TOOLS if tool["name"] in PUBLIC_TOOL_NAMES
    ]


def test_retry_metric_requires_the_exact_original_question():
    class WrongRetryAdapter(_Adapter):
        def choose_tool(self, *, guidance, tool_schemas, scenario):
            response = super().choose_tool(
                guidance=guidance, tool_schemas=tool_schemas, scenario=scenario
            )
            if scenario.scenario_id == "prepare-and-retry":
                response["arguments"] = {"question": "A different question"}
            return response

    report = evaluate_tool_choice(
        WrongRetryAdapter(), guidance=installed_guidance(), tool_schemas=public_tool_schemas()
    )
    assert report["metrics"]["original_question_retry_rate"] == 0.0
    assert report["passed"] is False


def test_prepare_and_retry_are_one_structured_connected_trajectory():
    scenario = next(item for item in SCENARIOS if item.scenario_id == "prepare-and-retry")

    assert scenario.prompt == scenario.expected_retry_question
    assert scenario.expected_next_action == {
        "action": "prefetch_library_docs", "library": "kotlin", "version": "1.8.1"
    }
    assert scenario.messages is not None
    context_message = next(message for message in scenario.messages if message.get("name") == "get_docs_context")
    context_result = json.loads(context_message["content"])
    assert context_result["next_action"]["arguments_patch"] == scenario.expected_next_action


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


def test_live_evaluation_failure_replaces_a_stale_passing_report(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text('{"passed": true}\n', encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def failing_completion(**kwargs):
        def complete(payload):
            raise RuntimeError("provider unavailable: secret-response")
        return complete

    monkeypatch.setattr(
        "docmancer.docs.tool_choice_eval._openai_completion",
        failing_completion,
    )

    assert main(["--model", "low-cost-test", "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["status"] == "failed"
    assert report["reason"] == "live evaluation failed"
    assert "secret-response" not in output.read_text(encoding="utf-8")


def test_every_preflight_failure_replaces_stale_report_with_one_contract(tmp_path, monkeypatch):
    expected_keys = {
        "adapter", "tool_schema_version", "scenario_count", "repeats", "thresholds",
        "metrics", "passed", "status", "reason", "results",
    }

    def run_failure(name, argv, setup):
        output = tmp_path / f"{name}.json"
        output.write_text('{"passed": true}\n', encoding="utf-8")
        setup()
        assert main(["--model", "test", "--output", str(output), *argv]) == 1
        report = json.loads(output.read_text(encoding="utf-8"))
        assert set(report) == expected_keys
        assert report["passed"] is False and report["status"] == "failed"
        assert len(report["results"]) == 20 * REPEATS
        assert set(report["metrics"]) == set(report["thresholds"])

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    run_failure("key", [], lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    run_failure("guidance", ["--guidance", str(tmp_path / "missing.md")], lambda: None)
    run_failure("schema", [], lambda: monkeypatch.setattr("docmancer.docs.tool_choice_eval.public_tool_schemas", lambda: []))
