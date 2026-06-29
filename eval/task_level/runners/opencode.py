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


class OpenCodeRunner:
    runner_id = "opencode"

    def __init__(self, executable: str = "opencode") -> None:
        self.executable = executable

    def _version(self) -> str:
        if not shutil.which(self.executable):
            return "not found"
        return subprocess.run([self.executable, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()

    def verify(self) -> RunnerCapabilities:
        version = self._version()
        found = version != "not found"
        auth = _auth_available(self.executable) if found else False
        return RunnerCapabilities(
            runner_id=self.runner_id,
            version=version,
            structured_trajectory=found,
            patch_capture=found,
            tool_isolation=found,
            mcp_isolation=found,
            shell_network_isolation=False,
            token_usage=found,
            independent_process=found,
            verified=found and auth,
            verification_notes=[
                "Uses `opencode run --format json` in a fresh non-interactive process.",
                "Writes a per-run XDG_CONFIG_HOME/opencode/opencode.json from the condition MCP config so repo-only has no MCP servers and DocAtlas conditions expose only docmancer-docs.",
                "Uses post-run normalized trajectory audit for tool/network policy; hard shell network isolation is not provided by OpenCode CLI help.",
                "Uses the user's OpenCode credentials from XDG_DATA_HOME because isolated HOME would otherwise remove auth; this is auth reuse, not workspace/context reuse.",
            ],
        )

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = request.output_dir / "stdout.log"
        stderr_path = request.output_dir / "stderr.log"
        events_path = request.output_dir / "events.jsonl"
        normalized_path = request.output_dir / "trajectory.normalized.json"
        config_home = Path(request.environment.get("XDG_CONFIG_HOME", str(request.output_dir / "env" / "xdg_config")))
        config_path = _write_opencode_config(config_home, request.mcp_config_path)

        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        env = os.environ.copy()
        env.update(request.environment)
        env["XDG_CONFIG_HOME"] = str(config_home)
        env.setdefault("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))

        command = [
            self.executable,
            "run",
            "--pure",
            "--format",
            "json",
            "--dir",
            str(request.workspace),
            "--model",
            _normalize_model(request.model),
            "--title",
            f"task-level-{request.task_id}-{request.condition_id}",
            request.prompt,
        ]

        notes = [f"opencode_config={config_path}"]
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
            status = "completed" if completed.returncode == 0 and '"type":"error"' not in completed.stdout else "runner_failed"
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
        normalized = _normalize_events(stdout)
        normalized_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
        input_tokens, output_tokens = _last_token_usage(normalized)

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
            tool_calls=[event for event in normalized if event.get("event_type") == "tool_call"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=_normalize_model(request.model),
            runner_version=self._version(),
            notes=notes,
        )


def _auth_available(executable: str) -> bool:
    completed = subprocess.run([executable, "auth", "list"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.returncode == 0 and "credential" in completed.stdout.lower()


def _normalize_model(model: str) -> str:
    aliases = {
        "sonnet": "openrouter/anthropic/claude-sonnet-4",
        "claude-sonnet": "openrouter/anthropic/claude-sonnet-4",
    }
    return aliases.get(model, model)


def _write_opencode_config(config_home: Path, mcp_config_path: Path | None) -> Path:
    opencode_dir = config_home / "opencode"
    opencode_dir.mkdir(parents=True, exist_ok=True)
    target = opencode_dir / "opencode.json"
    payload: dict[str, Any] = {"$schema": "https://opencode.ai/config.json", "mcp": {}}
    if mcp_config_path is not None and mcp_config_path.exists():
        source = json.loads(mcp_config_path.read_text(encoding="utf-8"))
        servers = source.get("mcpServers", {}) if isinstance(source.get("mcpServers"), dict) else {}
        for name, server in servers.items():
            if not isinstance(server, dict):
                continue
            command = server.get("command")
            args = server.get("args", [])
            if command:
                payload["mcp"][name] = {
                    "type": "local",
                    "command": [str(command), *[str(arg) for arg in args]],
                    "enabled": True,
                }
                if isinstance(server.get("env"), dict):
                    payload["mcp"][name]["environment"] = {str(k): str(v) for k, v in server["env"].items()}
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _normalize_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    sequence = 0
    for line in stdout.splitlines():
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        raw_type = str(raw.get("type") or "")
        part = raw.get("part") if isinstance(raw.get("part"), dict) else {}
        if raw_type == "tool_use" or part.get("type") == "tool":
            sequence += 1
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            arguments = state.get("input") if isinstance(state.get("input"), dict) else {}
            events.append({
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "tool_call",
                "tool_name": str(part.get("tool") or raw.get("tool") or ""),
                "arguments": arguments,
                "result_summary": str(state.get("output") or "")[:500],
                "source": "opencode_json",
                "tokens": None,
            })
        elif raw_type in {"text", "error", "step_finish"}:
            sequence += 1
            tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else None
            events.append({
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": raw_type,
                "tool_name": "",
                "arguments": {},
                "result_summary": str(part.get("text") or raw.get("error") or raw_type)[:500],
                "source": "opencode_json",
                "tokens": tokens,
            })
    return events


def _last_token_usage(events: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    input_tokens = None
    output_tokens = None
    for event in events:
        tokens = event.get("tokens") if isinstance(event.get("tokens"), dict) else None
        if not tokens:
            continue
        if isinstance(tokens.get("input"), int):
            input_tokens = tokens["input"]
        if isinstance(tokens.get("output"), int):
            output_tokens = tokens["output"]
    return input_tokens, output_tokens


def _redact(text: str) -> str:
    redacted = text
    for key, value in os.environ.items():
        if any(marker in key.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted
