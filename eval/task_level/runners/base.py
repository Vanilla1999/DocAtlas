from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RunnerCapabilities:
    runner_id: str
    version: str
    structured_trajectory: bool
    patch_capture: bool
    tool_isolation: bool
    mcp_isolation: bool
    shell_network_isolation: bool
    token_usage: bool
    independent_process: bool
    verified: bool
    hard_turn_limit: bool = False
    verification_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentRunRequest:
    task_id: str
    condition_id: str
    workspace: Path
    prompt: str
    model: str
    timeout_seconds: int
    max_turns: int
    environment: dict[str, str]
    mcp_config_path: Path | None
    tool_policy_path: Path
    output_dir: Path
    test_command: str | None = None
    allowed_write_paths: tuple[str, ...] = ()
    task_objective: str | None = None


@dataclass(frozen=True)
class AgentRunOutput:
    status: str
    exit_code: int | None
    started_at: str
    finished_at: str
    wall_time_seconds: float
    raw_stdout_path: str
    raw_stderr_path: str
    trajectory_path: str | None
    patch_path: str | None
    tool_calls: list[dict]
    input_tokens: int | None
    output_tokens: int | None
    model: str
    runner_version: str
    max_turns_enforced: bool = False
    token_usage: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class AgentRunner(Protocol):
    def verify(self) -> RunnerCapabilities:
        ...

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        ...
