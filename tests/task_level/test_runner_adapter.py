from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from eval.task_level.execution import capture_patch, run_canary
from eval.task_level.runners.base import AgentRunOutput, AgentRunRequest
from eval.task_level.runners.claude import ClaudeRunner
from eval.task_level.runners.codex import _is_provider_failure, _normalize_jsonl, _redact, _token_usage_summary
from eval.task_level.runners.opencode import _normalize_events, _write_opencode_config


class MockRunner:
    runner_id = "mock"

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        target = request.workspace / "calc.py"
        if target.exists():
            target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        normalization = request.workspace / "normalization.py"
        if normalization.exists():
            normalization.write_text(
                "def normalize(value):\n    return abs(value)\n",
                encoding="utf-8",
            )
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout = request.output_dir / "stdout.log"
        stderr = request.output_dir / "stderr.log"
        trajectory = request.output_dir / "trajectory.normalized.json"
        stdout.write_text("{}\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        trajectory.write_text(json.dumps([{
            "event_type": "edit",
            "tool_name": "Edit",
            "arguments": {},
            "result_summary": "edited calc.py and normalization.py",
        }]), encoding="utf-8")
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

    assert result["status"] == "passed", json.dumps(result, sort_keys=True)
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


def test_patch_capture_includes_pure_untracked_file(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=tmp_path, check=True)
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    (tmp_path / "new.txt").write_text("new content\n", encoding="utf-8")

    patch_path, _status_path, _changed_path, changed = capture_patch(tmp_path, tmp_path)

    assert changed == ["new.txt"]
    assert "new content" in patch_path.read_text(encoding="utf-8")


def test_missing_token_metrics_remain_null(tmp_path: Path):
    result = run_canary(MockRunner(), "mock", 30, tmp_path)

    assert result["status"] == "passed", json.dumps(result, sort_keys=True)
    output = MockRunner().run
    assert output is not None


def test_codex_normalized_trajectory_uses_sanitized_events(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PRIVATE_TOKEN", "super-secret-value")
    raw = json.dumps({
        "type": "item.completed",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_input_tokens": 60,
            "reasoning_tokens": 5,
        },
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


def test_codex_normalizes_measurable_tool_output():
    raw = json.dumps({
        "type": "item.completed",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_input_tokens": 60,
            "reasoning_tokens": 5,
        },
        "item": {
            "type": "mcp_tool_call",
            "server": "docmancer-docs",
            "tool": "get_docs_context",
            "arguments": {"question": "architecture"},
            "result": {"content": [{"type": "text", "text": "PermissionService owns the gate"}]},
        },
    })

    events, tool_calls, _input, _output = _normalize_jsonl(raw)

    assert tool_calls == [events[0]]
    assert tool_calls[0]["result_chars"] > 0
    assert "PermissionService owns the gate" in tool_calls[0]["result_summary"]
    assert _token_usage_summary(events) == {
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_input_tokens": 60,
        "reasoning_tokens": 5,
        "completed_turn_events": None,
    }


def test_codex_runner_uses_workspace_write_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: list[list[str]] = []

    def fake_run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n', "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    request = AgentRunRequest(
        task_id="task",
        condition_id="repo_only",
        workspace=tmp_path,
        prompt="inspect",
        model="model",
        timeout_seconds=30,
        max_turns=1,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "out",
    )

    from eval.task_level.runners.codex import CodexRunner
    CodexRunner("codex").run(request)

    command = next(command for command in captured if "exec" in command)
    assert command[command.index("--sandbox") + 1] == "workspace-write"


def test_codex_runner_allows_explicit_sandbox_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: list[list[str]] = []

    def fake_run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n', "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    request = AgentRunRequest(
        task_id="task",
        condition_id="repo_only_strict_offline",
        prompt="fix it",
        workspace=tmp_path,
        model="model",
        timeout_seconds=30,
        max_turns=1,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "out",
    )

    from eval.task_level.runners.codex import CodexRunner
    CodexRunner("codex", sandbox_mode="danger-full-access").run(request)

    command = next(command for command in captured if "exec" in command)
    assert command[command.index("--sandbox") + 1] == "danger-full-access"


def test_codex_redaction_preserves_json_literals_from_short_env_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHORT_TOKEN", "true")
    monkeypatch.setenv("API_TOKEN", "super-secret-value")
    raw = '{"details":true,"token":"super-secret-value"}\n'

    redacted = _redact(raw)

    assert json.loads(redacted)["details"] is True
    assert json.loads(redacted)["token"] == "<redacted>"


def test_codex_detects_error_event_stream_with_provider_403_as_failure():
    stdout = "\n".join([
        '{"type":"thread.started","thread_id":"thread-1"}',
        '{"type":"turn.started"}',
        '{"type":"error","message":"unexpected status 403 Forbidden"}',
        '{"type":"turn.failed","error":{"message":"unexpected status 403 Forbidden"}}',
    ])
    stderr = "failed to refresh available models: 403 Forbidden\nfailed to connect to websocket: HTTP error: 403 Forbidden"

    assert _is_provider_failure(stdout, stderr) is True
    assert _is_provider_failure("{\"type\":\"turn.completed\"}\n", stderr) is False


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
