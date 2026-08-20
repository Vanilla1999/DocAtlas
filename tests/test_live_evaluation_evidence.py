from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_agent_developer_openai_benchmark import _output_text
from scripts.run_task21_openai_live import _responses_input


TASK21_REPORT = Path("eval/results/task21_tool_choice_gate.json")
AGENT_REPORT = Path("eval/agent_developer_v1/results/model-benchmark.json")
EXPECTED_MODEL = "gpt-5.6-luna"


def test_task21_responses_input_preserves_function_history():
    items = _responses_input(
        "use docs tools",
        {
            "prompt": "Question",
            "messages": [
                {"role": "user", "content": "Question"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "context-1",
                            "type": "function",
                            "function": {
                                "name": "get_docs_context",
                                "arguments": '{"question":"Question"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "context-1",
                    "name": "get_docs_context",
                    "content": '{"status":"insufficient_evidence"}',
                },
            ],
        },
    )

    assert items[0] == {"role": "system", "content": "use docs tools"}
    assert items[1] == {"role": "user", "content": "Question"}
    assert items[2] == {
        "type": "function_call",
        "call_id": "context-1",
        "name": "get_docs_context",
        "arguments": '{"question":"Question"}',
    }
    assert items[3] == {
        "type": "function_call_output",
        "call_id": "context-1",
        "output": '{"status":"insufficient_evidence"}',
    }


def test_agent_responses_output_text_reads_only_message_text():
    response = {
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"action":"finish"}'},
                ],
            },
        ]
    }
    assert _output_text(response) == '{"action":"finish"}'


def test_task21_committed_live_report_is_complete_and_meets_frozen_thresholds():
    report = json.loads(TASK21_REPORT.read_text(encoding="utf-8"))
    model_version = str((report.get("adapter") or {}).get("model_version") or "")
    results = report.get("results") or []
    sentinel = (
        model_version == "not-run"
        and report.get("passed") is False
        and bool(results)
        and all(item.get("status") == "not_run" for item in results)
    )
    if sentinel:
        pytest.skip("Task 21 live evidence has not been recorded yet")

    assert report["passed"] is True
    assert model_version == EXPECTED_MODEL
    assert report["scenario_count"] == 20
    assert report["repeats"] == 3
    assert len(results) == 60
    assert all(item.get("status") != "not_run" for item in results)

    metrics = report["metrics"]
    thresholds = report["thresholds"]
    assert metrics["first_tool_accuracy"] >= thresholds["first_tool_accuracy"]
    assert metrics["unnecessary_prepare_or_status_rate"] <= thresholds["unnecessary_prepare_or_status_rate"]
    assert metrics["legacy_tool_hallucination_rate"] <= thresholds["legacy_tool_hallucination_rate"]
    assert metrics["next_action_copy_accuracy"] >= thresholds["next_action_copy_accuracy"]
    assert metrics["original_question_retry_rate"] >= thresholds["original_question_retry_rate"]


def test_agent_developer_committed_live_report_is_complete_and_safe():
    if not AGENT_REPORT.is_file():
        pytest.skip("Agent Developer live evidence has not been recorded yet")

    report = json.loads(AGENT_REPORT.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["protocol"] == "agent-developer-model-v1"
    assert report["provider_id"] == "openai-api"
    assert report["model"] == EXPECTED_MODEL
    assert report["task_count"] == 11
    assert report["executed_task_count"] == 11
    assert len(report["tasks"]) == 11
    assert report["infrastructure_errors"] == []
    assert report["false_supported"] == 0
    assert report["forbidden_source_contamination"] == 0
    assert 0.0 <= report["pass_rate"] <= 1.0
    assert 0.0 <= report["scope_accuracy"] <= 1.0
    assert 0.0 <= report["recovery_accuracy"] <= 1.0
    assert all(task.get("usage") for task in report["tasks"])
