from __future__ import annotations

import shutil
import subprocess

from .base import AgentRunOutput, AgentRunRequest, RunnerCapabilities


class OpenCodeRunner:
    runner_id = "opencode"

    def verify(self) -> RunnerCapabilities:
        if not shutil.which("opencode"):
            version = "not found"
        else:
            version = subprocess.run(["opencode", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()
        found = version != "not found"
        return RunnerCapabilities(
            runner_id=self.runner_id,
            version=version,
            structured_trajectory=found,
            patch_capture=found,
            tool_isolation=False,
            mcp_isolation=False,
            shell_network_isolation=False,
            token_usage=False,
            independent_process=found,
            verified=False,
            verification_notes=["opencode run supports --format json, but help output did not expose strict per-run MCP/tool isolation flags for this pilot."],
        )

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        raise NotImplementedError("OpenCode adapter is intentionally unsupported for causal pilot runs until strict tool isolation is verified.")
