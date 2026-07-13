from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import AgentRunOutput, AgentRunRequest, RunnerCapabilities


class CodexRunner:
    runner_id = "codex"

    def __init__(self, executable: str = "codex", *, sandbox_mode: str = "workspace-write") -> None:
        if sandbox_mode not in {"workspace-write", "danger-full-access"}:
            raise ValueError(f"Unsupported Codex sandbox mode: {sandbox_mode}")
        self.executable = executable
        self.sandbox_mode = sandbox_mode

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
            shell_network_isolation=found,
            token_usage=found,
            independent_process=found,
            verified=False,
            verification_notes=[
                "CLI capability detection is not causal verification; runner canary must pass before causal pilot execution.",
                "Uses `codex exec --json --ephemeral` for fresh non-interactive sessions.",
                "Uses per-run CODEX_HOME with copied auth material and generated MCP config.",
                "Uses Codex exec with explicit workspace-write isolation; policy and trajectory audits remain defense in depth.",
                "Codex JSONL result events expose concrete input/output token usage in observed canary and pilot runs.",
                "Codex exec does not expose a hard max-turn or cumulative-token flag; the harness records declared budget overruns and controls attempts with one ephemeral process plus a timeout.",
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
        env["CODEX_HOME"] = str(_prepare_codex_home(request))
        env["PATH"] = f"{_prepare_blocked_network_tools(request)}{os.pathsep}{env.get('PATH', '')}"

        command = [
            self.executable,
            "exec",
            "--json",
            "--ephemeral",
            "--model",
            request.model,
            "--sandbox",
            self.sandbox_mode,
            "--cd",
            str(request.workspace),
            request.prompt,
        ]

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
        sanitized_stdout = _redact(stdout)
        sanitized_stderr = _redact(stderr)
        stdout_path.write_text(sanitized_stdout, encoding="utf-8")
        stderr_path.write_text(sanitized_stderr, encoding="utf-8")
        events_path.write_text(sanitized_stdout, encoding="utf-8")
        normalized, tool_calls, input_tokens, output_tokens = _normalize_jsonl(sanitized_stdout)
        normalized_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
        (request.output_dir / "sanitization_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "task-trace-sanitizer-1",
                    "stdout_changed": sanitized_stdout != stdout,
                    "stderr_changed": sanitized_stderr != stderr,
                    "normalized_from_sanitized_events": True,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        if _is_provider_failure(stdout, stderr):
            raise RuntimeError("Codex provider unavailable: terminal provider failure event")

        return AgentRunOutput(
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=wall,
            raw_stdout_path=str(stdout_path),
            raw_stderr_path=str(stderr_path),
            trajectory_path=str(normalized_path),
            patch_path=None,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=request.model,
            runner_version=self._version(),
            notes=notes,
        )


def _is_provider_failure(stdout: str, stderr: str) -> bool:
    event_types: set[str] = set()
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("type"), str):
            event_types.add(payload["type"])
    if "turn.completed" in event_types:
        return False
    lowered = f"{stdout}\n{stderr}".lower()
    provider_marker = any(
        marker in lowered
        for marker in (
            "403 forbidden",
            "failed to connect to websocket",
            "failed to refresh available models",
            "transport channel closed",
        )
    )
    return provider_marker and (not stdout.strip() or "turn.failed" in event_types)


def _prepare_codex_home(request: AgentRunRequest) -> Path:
    codex_home = request.output_dir / "env" / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    source_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    auth = source_home / "auth.json"
    if auth.exists():
        shutil.copy2(auth, codex_home / "auth.json")
    config = _codex_config(request)
    (codex_home / "config.toml").write_text(config, encoding="utf-8")
    return codex_home


def _prepare_blocked_network_tools(request: AgentRunRequest) -> Path:
    bin_dir = request.output_dir / "env" / "blocked_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = "#!/bin/sh\nprintf '%s\n' 'blocked by benchmark network policy' >&2\nexit 126\n"
    for name in ("curl", "wget"):
        target = bin_dir / name
        target.write_text(script, encoding="utf-8")
        target.chmod(0o755)
    return bin_dir


def _codex_config(request: AgentRunRequest) -> str:
    project = str(request.workspace).replace('"', '\\"')
    lines = [
        f'model = "{request.model}"',
        "model_reasoning_effort = \"medium\"",
        "",
        f'[projects."{project}"]',
        'trust_level = "trusted"',
        "",
    ]
    if request.condition_id in {"docatlas_snippet_first", "docatlas_tool_optional", "docatlas_tool_recommended", "docatlas_context_injected", "docatlas_tool_required_once", "docatlas_tool_visibility_canary"}:
        lines.extend([
            "[mcp_servers.docmancer-docs]",
            'command = "uv"',
            f'args = ["run", "--project", "{Path(__file__).resolve().parents[3]}", "doc-atlas", "mcp", "docs-serve"]',
            "",
        ])
    return "\n".join(lines)


def _normalize_jsonl(stdout: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int | None, int | None]:
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
        raw_type = str(raw.get("type") or raw.get("event") or raw.get("msg", {}).get("type") or "assistant")
        message = raw.get("msg") if isinstance(raw.get("msg"), dict) else raw
        item = message.get("item") if isinstance(message.get("item"), dict) else message
        item_type = str(item.get("type") or "")
        tool_name = str(message.get("tool_name") or message.get("name") or message.get("tool") or "")
        if not tool_name and item_type == "command_execution":
            tool_name = "Bash"
        elif not tool_name and item_type == "file_change":
            tool_name = "Edit"
        elif not tool_name and item_type == "mcp_tool_call":
            tool_name = str(item.get("tool") or "mcp_tool_call")
        result_text = _tool_result_text(item, message)
        content = result_text[:4000] if result_text else json.dumps(message, sort_keys=True)[:500]
        event_type = "tool_call" if tool_name or "tool" in raw_type.lower() or "exec" in raw_type.lower() else "assistant"
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        if isinstance(usage.get("input_tokens"), int):
            input_tokens = usage["input_tokens"]
        if isinstance(usage.get("output_tokens"), int):
            output_tokens = usage["output_tokens"]
        normalized_event = {
            "sequence": sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "tool_name": tool_name,
            "arguments": _event_arguments(item, message),
            "result_summary": content,
            "result_chars": len(result_text),
            "result_truncated": len(result_text) > len(content),
            "source": "codex_jsonl",
            "source_event_type": raw_type,
            "tokens": usage or None,
        }
        events.append(normalized_event)
        if event_type == "tool_call":
            # Downstream accounting must consume the sanitized normalized event,
            # not the provider-specific raw envelope.
            tool_calls.append(normalized_event)
    return events, tool_calls, input_tokens, output_tokens


def _tool_result_text(item: dict[str, Any], message: dict[str, Any]) -> str:
    for container in (item, message):
        for field in ("result", "output", "aggregated_output", "content"):
            value = container.get(field)
            if value in (None, ""):
                continue
            if isinstance(value, str):
                return value
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return ""


def _event_arguments(item: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    if isinstance(message.get("arguments"), dict):
        return message["arguments"]
    if item.get("type") == "command_execution":
        return {"command": item.get("command", "")}
    if item.get("type") == "file_change":
        return {"changes": item.get("changes", [])}
    if item.get("type") == "mcp_tool_call":
        return {"server": item.get("server", ""), "tool": item.get("tool", ""), "arguments": item.get("arguments", {})}
    return {}


def _redact(text: str) -> str:
    redacted = text
    for key, value in os.environ.items():
        if any(marker in key.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and value:
            redacted = redacted.replace(value, "<redacted>")
    redacted = re.sub(r"/(?:home|tmp)/[^\s\"']+", "<path>", redacted)
    redacted = re.sub(r"https?://[^/@\s:]+:[^/@\s]+@", "https://<redacted>@", redacted)
    return redacted
