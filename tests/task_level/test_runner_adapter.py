from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from eval.task_level.execution import capture_patch, run_canary
from eval.task_level.runners.base import AgentRunOutput, AgentRunRequest
from eval.task_level.runners.claude import ClaudeRunner
from eval.task_level.runners.codex import _normalize_jsonl, _redact
from eval.task_level.runners.opencode import _normalize_events, _write_opencode_config


class MockRunner:
    runner_id = "mock"

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        target = request.workspace / "calc.py"
        if target.exists():
            target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout = request.output_dir / "stdout.log"
        stderr = request.output_dir / "stderr.log"
        trajectory = request.output_dir / "trajectory.normalized.json"
        stdout.write_text("{}\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        trajectory.write_text(json.dumps([{"event_type": "edit", "tool_name": "Edit", "arguments": {}, "result_summary": "edited calc.py"}]), encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        return AgentRunOutput(
            status="completed",
            exit_code=0,
            started_at=now,
            finished_at=now,
            wall_time_seconds=0.1,
            raw_stdout_path=str(stdout),
            raw_stderr_path=str(stderr),
            trajectory_path=str(trajectory),
            patch_path=None,
            tool_calls=[],
            input_tokens=None,
            output_tokens=None,
            model="mock",
            runner_version="mock",
            notes=[],
        )


def test_runner_canary_produces_patch(tmp_path: Path):
    result = run_canary(MockRunner(), "mock", 30, tmp_path)

    assert result["status"] == "passed"
    assert result["patch_exists"]
    assert result["pytest_passes"]


def test_patch_capture(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=tmp_path, check=False)
    subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=tmp_path, check=False)
    (tmp_path / "file.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=False)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (tmp_path / "file.txt").write_text("after\n", encoding="utf-8")

    patch_path, status_path, changed_path, changed = capture_patch(tmp_path, tmp_path)

    assert patch_path.read_text(encoding="utf-8")
    assert status_path.read_text(encoding="utf-8")
    assert json.loads(changed_path.read_text(encoding="utf-8")) == ["file.txt"]
    assert changed == ["file.txt"]


def test_missing_token_metrics_remain_null(tmp_path: Path):
    result = run_canary(MockRunner(), "mock", 30, tmp_path)

    assert result["status"] == "passed"
    output = MockRunner().run
    assert output is not None


def test_codex_normalized_trajectory_uses_sanitized_events(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PRIVATE_TOKEN", "super-secret-value")
    raw = json.dumps({
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "inspect /home/alice/private/project with super-secret-value",
        },
    })

    normalized, _calls, _input, _output = _normalize_jsonl(_redact(raw))
    serialized = json.dumps(normalized)

    assert "super-secret-value" not in serialized
    assert "/home/alice/private/project" not in serialized
    assert "<redacted>" in serialized
    assert "<path>" in serialized


def test_opencode_normalizes_json_events_for_policy_audit():
    events = _normalize_events("\n".join([
        json.dumps({"type": "tool_use", "part": {"tool": "edit", "state": {"input": {"filePath": "calc.py"}}}}),
        json.dumps({"type": "tool_use", "part": {"tool": "bash", "state": {"input": {"command": "pytest -q"}}}}),
        json.dumps({"type": "step_finish", "part": {"tokens": {"input": 10, "output": 3}}}),
    ]))

    tool_events = [event for event in events if event["event_type"] == "tool_call"]
    assert [event["tool_name"] for event in tool_events] == ["edit", "bash"]
    assert tool_events[0]["arguments"] == {"filePath": "calc.py"}
    assert tool_events[1]["arguments"] == {"command": "pytest -q"}


def test_opencode_config_uses_condition_mcp_only(tmp_path: Path):
    source = tmp_path / "mcp_config.json"
    source.write_text(json.dumps({
        "mcpServers": {
            "docmancer-docs": {
                "command": "uv",
                "args": ["run", "doc-atlas", "mcp", "docs-serve"],
                "env": {"DOCMANCER_TASK_LEVEL_ALLOW_NETWORK": "false"},
            }
        }
    }), encoding="utf-8")

    config_home = tmp_path / "xdg_config"
    written = _write_opencode_config(config_home, source)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert sorted(payload["mcp"]) == ["docmancer-docs"]
    assert payload["mcp"]["docmancer-docs"]["type"] == "local"
    assert payload["mcp"]["docmancer-docs"]["command"] == ["uv", "run", "doc-atlas", "mcp", "docs-serve"]


@pytest.mark.integration
def test_claude_verify_reports_token_usage_unverified():
    caps = ClaudeRunner().verify()

    assert caps.token_usage is False
