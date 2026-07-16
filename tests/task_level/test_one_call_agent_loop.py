from __future__ import annotations

import json
from pathlib import Path

import pytest

from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from eval.task_level.one_call_agent_loop import (
    FakeLoopAdapter,
    HistoryBlock,
    LoopBudgetProfile,
    LoopCapabilities,
    OneCallAgentLoop,
    ToolExecution,
    ToolOutputLimitError,
    capture_tool_execution,
    compact_retained_history,
    estimated_loop_tokens,
    validate_docatlas_result,
)


PATCH_CONTEXT = {
    "status": "ok",
    "kind": "patch_context",
    "objective": "Implement the bounded change.",
    "sources": [{"evidence_id": "ev-1", "content_sha256": "0" * 64}],
    "targets": {"likely_files": [], "symbols": []},
    "invariants": [],
    "forbidden_changes": [],
    "implementation_guidance": [],
    "checks": {"compile": [], "tests": [], "semantic_checks": []},
    "uncertainties": [],
    "omitted_counts": {},
    "estimated_tokens": 0,
}
for _ in range(3):
    PATCH_CONTEXT["estimated_tokens"] = estimate_projection_tokens(PATCH_CONTEXT)


def test_successful_one_call_patch_loop_disables_docatlas_and_retains_minimum(tmp_path):
    adapter = FakeLoopAdapter(
        [
            {"type": "docatlas", "arguments": {"question": "Implement change"}},
            {"type": "edit"},
            {"type": "shell", "command": "uv run pytest tests/test_feature.py"},
            {"type": "finish"},
        ],
        docatlas_result=PATCH_CONTEXT,
        executions=[
            ToolExecution(result=["edited"], exit_code=0, diff="diff --git a/a.py b/a.py\n+fixed\n"),
            ToolExecution(stdout=["1 passed\n"], exit_code=0),
        ],
        usage={"input_tokens": 1200, "output_tokens": 80},
    )
    audit_path = tmp_path / "loop_audit.json"

    outcome = OneCallAgentLoop(adapter).run(
        objective="Implement change", task_id="task-1", audit_path=audit_path,
    )

    assert outcome.status == "success"
    assert outcome.docatlas_state == "accepted"
    assert outcome.capability_verified is True
    assert outcome.counts["docatlas_calls"] == 1
    assert outcome.counts["test_invocations"] == 1
    assert adapter.docatlas_enabled_events == [True, False]
    assert adapter.action_output_limits == [
        LoopBudgetProfile().max_tool_output_bytes_per_call,
        LoopBudgetProfile().max_tool_output_bytes_per_call,
    ]
    assert [tool["name"] for tool in adapter.model_inputs[1]["tools"]] == ["edit", "shell", "finish"]
    final_blocks = {block["kind"] for block in adapter.model_inputs[-1]["history"]["blocks"]}
    assert {"objective", "docatlas_result", "action_state", "current_diff"}.issubset(final_blocks)
    assert any(row["reason"] == "successful_tool_output_summarized" for row in outcome.audit["omitted_blocks"])
    assert json.loads(audit_path.read_text())["provider_usage"] == {"input_tokens": 1200, "output_tokens": 80}


def test_insufficient_evidence_stops_before_edit():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}],
        docatlas_result={"status": "insufficient_evidence", "kind": "patch_context", "missing": ["docs"]},
        executions=[ToolExecution(diff="must not happen")],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "incomplete"
    assert outcome.reason_code == "insufficient_evidence"
    assert outcome.docatlas_state == "insufficient"
    assert len(adapter.executions) == 1


def test_second_docatlas_call_is_rejected_after_acceptance():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "docatlas"}],
        docatlas_result=PATCH_CONTEXT,
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "incomplete"
    assert outcome.reason_code == "second_docatlas_call_rejected"
    assert outcome.counts["docatlas_calls"] == 1


def test_thirteenth_model_request_is_hard_rejected_under_v1_profile():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, *({"type": "shell", "command": "true"} for _ in range(20))],
        docatlas_result=PATCH_CONTEXT,
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "model_request_limit"
    assert outcome.counts["model_requests"] == 12


def test_only_one_repair_pass_is_allowed():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "repair"}, {"type": "repair"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(exit_code=0), ToolExecution(exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "repair_pass_limit"
    assert outcome.counts["action_attempts"] == 2
    assert outcome.counts["repair_passes"] == 1


def test_third_test_invocation_is_rejected_before_execution():
    adapter = FakeLoopAdapter(
        [
            {"type": "docatlas"},
            {"type": "shell", "command": "pytest a.py"},
            {"type": "shell", "command": "python -m pytest b.py"},
            {"type": "shell", "command": "uv run pytest c.py"},
        ],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(exit_code=0), ToolExecution(exit_code=0), ToolExecution(exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "test_invocation_limit"
    assert outcome.counts["test_invocations"] == 2
    assert len(adapter.executions) == 1


def test_streaming_capture_bounds_oversized_stdout_stderr_and_result():
    captured = capture_tool_execution(
        ToolExecution(
            stdout=("o" * 10_000 for _ in range(10)),
            stderr=("e" * 10_000 for _ in range(10)),
            result=("r" * 10_000 for _ in range(10)),
        ),
        max_bytes=3_000,
    )

    assert captured["capture_bytes"] <= 3_000
    assert all(captured[name]["captured_bytes"] <= 1_000 for name in ("stdout", "stderr", "result"))
    assert all(captured[name]["truncated"] for name in ("stdout", "stderr", "result"))


def test_repeated_failed_shell_fingerprint_uses_task34_normalization():
    adapter = FakeLoopAdapter(
        [
            {"type": "docatlas"},
            {"type": "shell", "command": "/bin/bash -lc 'pytest tests/a.py'"},
            {"type": "shell", "command": "pytest tests/a.py"},
            {"type": "finish"},
        ],
        docatlas_result=PATCH_CONTEXT,
        executions=[
            ToolExecution(stderr=["first failure"], exit_code=1),
            ToolExecution(stderr=["second failure"], exit_code=1),
        ],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.counts["failed_shell_calls"] == 2
    assert outcome.counts["retried_command_count"] == 1
    assert any(row["reason"] == "superseded_failure" for row in outcome.audit["omitted_blocks"])
    final_blocks = {block["kind"] for block in adapter.model_inputs[-1]["history"]["blocks"]}
    assert "latest_failure" in final_blocks


def test_compaction_is_deterministic_and_hashes_whole_omitted_blocks():
    blocks = [
        HistoryBlock("objective", "objective", "keep", required=True),
        HistoryBlock("old-search", "tool_output", "secret search output " * 200, priority=300),
        HistoryBlock("success-log", "tool_output", "all tests passed " * 200, priority=200),
    ]

    first, first_omitted = compact_retained_history(blocks, max_tokens=40)
    second, second_omitted = compact_retained_history(reversed(blocks), max_tokens=40)

    assert first is not None and second is not None
    assert first_omitted == second_omitted
    assert {row["block_id"] for row in first_omitted} == {"old-search", "success-log"}
    assert all(len(row["sha256"]) == 64 and row["reason"] == "request_input_budget" for row in first_omitted)


def test_required_input_over_budget_is_typed_exhaustion_before_provider_request():
    adapter = FakeLoopAdapter([{"type": "docatlas"}], docatlas_result=PATCH_CONTEXT)
    profile = LoopBudgetProfile(max_serialized_input_tokens_per_request=40)

    outcome = OneCallAgentLoop(adapter, profile=profile).run(objective="x" * 10_000)

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "serialized_input_limit"
    assert adapter.model_inputs == []


def test_sanitized_audit_excludes_secrets_and_missing_usage_is_none(tmp_path):
    secret = "ZG39vJnp40smLXXd76"
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "finish"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(stdout=[secret], diff=f"+token={secret}", exit_code=0)],
    )
    audit_path = tmp_path / "audit.json"

    outcome = OneCallAgentLoop(adapter).run(objective=f"Do work with {secret}", audit_path=audit_path)
    serialized = audit_path.read_text()

    assert outcome.status == "success"
    assert secret not in serialized
    assert outcome.audit["provider_usage"] is None


def test_generic_unverified_client_is_never_labelled_verified():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "finish"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(exit_code=0, diff="+change")],
        capabilities=LoopCapabilities(one_docatlas_call_enforced=True),
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "success"
    assert outcome.capability_verified is False
    assert outcome.audit["capabilities"]["verified"] is False


def test_every_serialized_fake_request_meets_profile_ceiling():
    profile = LoopBudgetProfile(max_serialized_input_tokens_per_request=500)
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "finish"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(diff="+small", exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter, profile=profile).run(objective="Small change")

    assert outcome.status == "success"
    assert all(estimated_loop_tokens(request) <= 500 for request in adapter.model_inputs)


def test_large_diff_is_retained_as_bounded_summary_and_hash():
    large_diff = "".join(f"+line {index} {'x' * 200}\n" for index in range(1_000))
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "finish"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(diff=large_diff, exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")
    diff_block = next(
        block["value"] for block in adapter.model_inputs[-1]["history"]["blocks"]
        if block["kind"] == "current_diff"
    )

    assert outcome.status == "success"
    assert diff_block["truncated"] is True
    assert diff_block["original_bytes"] == len(large_diff.encode())
    assert len(diff_block["sha256"]) == 64
    assert len(diff_block["text"].encode()) <= LoopBudgetProfile().max_tool_output_bytes_per_call // 2
    assert any(row["reason"] == "diff_summarized" for row in outcome.audit["omitted_blocks"])


def test_frozen_task33_protocol_is_not_modified():
    protocol = json.loads((
        Path(__file__).resolve().parents[2]
        / "eval" / "task_level" / "task33c_protocol_v1.lock.json"
    ).read_text())

    assert protocol["agent_turn_limit"] == 24
    assert protocol["provider_request_budget"] == 113


def test_unvalidated_or_raw_docatlas_payload_is_rejected():
    payload = {**PATCH_CONTEXT, "context_pack": [{"content": "raw"}]}
    payload["estimated_tokens"] = estimate_projection_tokens(payload)
    adapter = FakeLoopAdapter([{"type": "docatlas"}], docatlas_result=payload)

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "failed"
    assert outcome.reason_code == "invalid_docatlas_result"
    assert "forbidden model-visible fields" in " ".join(validate_docatlas_result(payload))


def test_repeated_edit_names_cannot_bypass_repair_budget():
    adapter = FakeLoopAdapter(
        [{"type": "docatlas"}, {"type": "edit"}, {"type": "edit"}, {"type": "edit"}],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(exit_code=0), ToolExecution(exit_code=0), ToolExecution(exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "repair_pass_limit"
    assert outcome.counts["action_attempts"] == 2
    assert outcome.counts["repair_passes"] == 1


def test_bash_aliases_are_normalized_before_test_budgeting():
    adapter = FakeLoopAdapter(
        [
            {"type": "docatlas"},
            {"type": "Bash", "command": "pytest a.py"},
            {"type": "command_execution", "command": "pytest b.py"},
            {"type": "Bash", "command": "pytest c.py"},
        ],
        docatlas_result=PATCH_CONTEXT,
        executions=[ToolExecution(exit_code=0), ToolExecution(exit_code=0), ToolExecution(exit_code=0)],
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "test_invocation_limit"
    assert outcome.counts["test_invocations"] == 2


def test_dynamic_tool_capability_requires_host_observed_catalog_removal():
    class LyingAdapter(FakeLoopAdapter):
        def tool_catalog(self, *, docatlas_enabled):
            return [{"name": "get_docs_context"}, {"name": "edit"}, {"name": "finish"}]

        def set_docatlas_enabled(self, enabled):
            return None

    adapter = LyingAdapter(
        [{"type": "docatlas"}, {"type": "finish"}], docatlas_result=PATCH_CONTEXT,
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "failed"
    assert outcome.reason_code == "dynamic_tool_exposure_violation"
    assert outcome.capability_verified is False


def test_capture_budget_is_global_for_tiny_profiles():
    captured = capture_tool_execution(
        ToolExecution(stdout=["a"], stderr=["b"], result=["c"], diff="d"), max_bytes=1,
    )

    assert captured["capture_bytes"] == 1


def test_stream_ending_exactly_at_channel_boundary_is_not_truncated():
    captured = capture_tool_execution(
        ToolExecution(stdout=["a"], stderr=["b"], result=["c"], diff="d"), max_bytes=4,
    )

    assert captured["capture_bytes"] == 4
    assert captured["truncated"] is False


def test_adapter_output_refusal_becomes_typed_budget_exhaustion():
    class RefusingAdapter(FakeLoopAdapter):
        def execute_action(self, action, *, max_output_bytes):
            raise ToolOutputLimitError(f"refused output above {max_output_bytes}")

    adapter = RefusingAdapter(
        [{"type": "docatlas"}, {"type": "edit"}], docatlas_result=PATCH_CONTEXT,
    )

    outcome = OneCallAgentLoop(adapter).run(objective="Change code")

    assert outcome.status == "budget_exhausted"
    assert outcome.reason_code == "action_output_limit"
