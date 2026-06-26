from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import AgentRunOutput, AgentRunRequest, RunnerCapabilities


class ClaudeRunner:
    runner_id = "claude"

    def __init__(self, executable: str = "claude") -> None:
        self.executable = executable

    def _version(self) -> str:
        if not shutil.which(self.executable):
            return "not found"
        completed = subprocess.run([self.executable, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        return completed.stdout.strip()

    def verify(self) -> RunnerCapabilities:
        version = self._version()
        found = version != "not found"
        return RunnerCapabilities(
            runner_id=self.runner_id,
            version=version,
            structured_trajectory=found,
            patch_capture=found,
            tool_isolation=found,
            mcp_isolation=found,
            shell_network_isolation=False,
            token_usage=False,
            independent_process=found,
            verified=False,
            verification_notes=[
                "CLI capability detection is not causal verification; runner canary must pass before causal pilot execution.",
                "Uses `claude -p --output-format stream-json --no-session-persistence --bare` for fresh non-interactive process.",
                "Uses `--strict-mcp-config` and condition-specific MCP config files.",
                "Uses `--tools`/`--allowedTools` plus post-run trajectory audit for tool policy.",
                "Hard shell network isolation is not provided by Claude CLI help; network_enforcement=policy_and_trajectory_audit.",
                "Token usage is not treated as verified unless stream events include concrete usage fields from an authenticated run.",
            ],
        )

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = request.output_dir / "stdout.log"
        stderr_path = request.output_dir / "stderr.log"
        events_path = request.output_dir / "events.jsonl"
        normalized_path = request.output_dir / "trajectory.normalized.json"
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()

        env = os.environ.copy()
        env.update(request.environment)
        env.setdefault("CLAUDE_CODE_SIMPLE", "1")

        command = [
            self.executable,
            "-p",
            request.prompt,
            "--bare",
            "--no-session-persistence",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            request.model,
            "--tools",
            "Read,Grep,Glob,Edit,MultiEdit,Write,Bash",
            "--allowedTools",
            "Read,Grep,Glob,Edit,MultiEdit,Write,Bash(git *),Bash(pytest *),Bash(python *),Bash(python3 *),Bash(uv *),Bash(ls *),Bash(pwd)",
            "--disallowedTools",
            "WebFetch,WebSearch,Bash(curl *),Bash(wget *),Bash(python -c *requests*),Bash(python3 -c *requests*)",
        ]
        if request.mcp_config_path is not None:
            command.extend(["--mcp-config", str(request.mcp_config_path), "--strict-mcp-config"])
        else:
            command.extend(["--mcp-config", "{}", "--strict-mcp-config"])

        notes: list[str] = []
        exit_code: int | None = None
        stdout = ""
        stderr = ""
        try:
            completed = subprocess.run(
                command,
                cwd=request.workspace,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=request.timeout_seconds,
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            status = "completed" if completed.returncode == 0 else "runner_failed"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            status = "timeout"
            notes.append(f"Timed out after {request.timeout_seconds}s")

        finished_at = datetime.now(timezone.utc).isoformat()
        wall = round(time.monotonic() - started, 4)
        stdout_path.write_text(_redact(stdout), encoding="utf-8")
        stderr_path.write_text(_redact(stderr), encoding="utf-8")
        events_path.write_text(_redact(stdout), encoding="utf-8")
        normalized, tool_calls, input_tokens, output_tokens = _normalize_stream(stdout)
        normalized_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")

        return AgentRunOutput(
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=wall,
            raw_stdout_path=str(stdout_path),
            raw_stderr_path=str(stderr_path),
            trajectory_path=str(normalized_path) if normalized else str(events_path),
            patch_path=None,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=request.model,
            runner_version=self._version(),
            notes=notes,
        )


def _normalize_stream(stdout: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int | None, int | None]:
    events: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    sequence = 0
    for line in stdout.splitlines():
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        sequence += 1
        raw_type = str(raw.get("type") or raw.get("event") or "assistant")
        tool_name = str(raw.get("name") or raw.get("tool_name") or "")
        if "tool" in raw_type or tool_name:
            event_type = "tool_call"
            tool_calls.append(raw)
        else:
            event_type = "assistant"
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        if isinstance(usage.get("input_tokens"), int):
            input_tokens = usage["input_tokens"]
        if isinstance(usage.get("output_tokens"), int):
            output_tokens = usage["output_tokens"]
        events.append({
            "sequence": sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "tool_name": tool_name,
            "arguments": raw.get("input") if isinstance(raw.get("input"), dict) else {},
            "result_summary": str(raw.get("result") or raw.get("content") or raw_type)[:500],
            "source": "claude_stream_json",
            "tokens": usage or None,
        })
    return events, tool_calls, input_tokens, output_tokens


def _redact(text: str) -> str:
    redacted = text
    for key, value in os.environ.items():
        if any(marker in key.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted
