from __future__ import annotations

import subprocess
from pathlib import Path

from eval.task_level.sandbox_execution import DockerCommandSandbox, SandboxCommandResult


def test_verify_reports_empty_canary_output_as_failed(
    tmp_path: Path,
    monkeypatch,
):
    sandbox = DockerCommandSandbox("evaluator:test")
    runtime_root = tmp_path / "docker-visible-runtime"
    monkeypatch.setenv("TASK33C_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "sha256:image\n", ""
        ),
    )
    observed_workspaces: list[Path] = []

    def fake_run(command, workspace, **kwargs):
        observed_workspaces.append(workspace)
        return SandboxCommandResult(
            command=("python",),
            returncode=125,
            stdout="",
            stderr="docker boundary rejected the canary",
            wall_time_seconds=0.1,
            boundary={},
        )

    monkeypatch.setattr(sandbox, "_run", fake_run)

    result = sandbox.verify()

    assert result["status"] == "failed"
    assert observed_workspaces[0].parent == runtime_root
    assert result["reason"] == (
        "canary:ValueError:canary produced no JSON output; "
        "returncode=125; stderr=docker boundary rejected the canary"
    )
