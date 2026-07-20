from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from eval.task_level import task33_local
from eval.task_level.execution import _runner_id_from_version


def test_openai_api_runner_identity_is_not_aliased_to_claude():
    assert _runner_id_from_version("openai-api-controlled-agent-v1-bounded-context") == "openai-api"


def test_local_preflight_requires_key_without_persisting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        task33_local.main(["--preflight-output", str(tmp_path / "preflight")])

    assert not (tmp_path / "preflight").exists()


def test_local_preflight_gates_causal_run_on_all_three_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "preflight"
    calls = {name: 0 for name in ("image", "prewarm", "provider", "docker", "retrieval", "runner")}

    def called(name: str, result=None):
        def invoke(*args, **kwargs):
            calls[name] += 1
            return result
        return invoke

    monkeypatch.setenv("OPENAI_API_KEY", "secret-not-for-artifacts")
    monkeypatch.setattr(
        task33_local,
        "_build_image",
        called("image", {"status": "verified", "image_id": "verified-image"}),
    )
    monkeypatch.setattr(task33_local, "_prewarm_fixture_dependencies", called("prewarm"))
    monkeypatch.setattr(
        task33_local,
        "run_openai_api_capability_probe",
        called("provider", {"status": "verified", "provider": "openai-api"}),
    )
    monkeypatch.setattr(
        task33_local.DockerCommandSandbox,
        "verify",
        called("docker", {"status": "verified", "image": "verified-image"}),
    )
    monkeypatch.setattr(
        task33_local,
        "_probe_retrieval",
        called("retrieval", {"status": "verified", "retrieval_calls": 1}),
    )
    monkeypatch.setattr(
        task33_local.subprocess,
        "run",
        called("runner", subprocess.CompletedProcess([], 0)),
    )

    assert task33_local.main(["--preflight-output", str(output)]) == 0

    summary = json.loads((output / "preflight-summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "verified"
    assert summary["run_causal_pilot_requested"] is False
    assert "secret-not-for-artifacts" not in json.dumps(summary)
    assert calls == {
        "image": 1,
        "prewarm": 1,
        "provider": 1,
        "docker": 1,
        "retrieval": 1,
        "runner": 0,
    }

    calls.update({name: 0 for name in calls})
    causal_output = tmp_path / "causal-preflight"
    assert task33_local.main([
        "--run-causal-pilot",
        "--preflight-output",
        str(causal_output),
    ]) == 3
    causal_summary = json.loads(
        (causal_output / "preflight-summary.json").read_text(encoding="utf-8")
    )
    assert causal_summary["status"] == "unsupported"
    assert causal_summary["checks"]["resource_budget"] == {
        "status": "unsupported",
        "reason": (
            "Task 33 causal execution requires a runner with a proven "
            "hard cumulative input budget"
        ),
        "provider_input_token_limit": 7_000,
        "max_input_tokens": 120_000,
    }
    assert calls == {name: 0 for name in calls}


def test_local_preflight_returns_inconclusive_when_retrieval_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "preflight"
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setattr(
        task33_local,
        "_build_image",
        lambda image, base: {"status": "verified"},
    )
    monkeypatch.setattr(task33_local, "_prewarm_fixture_dependencies", lambda output: None)
    monkeypatch.setattr(
        task33_local,
        "run_openai_api_capability_probe",
        lambda *args, **kwargs: {"status": "verified"},
    )
    monkeypatch.setattr(
        task33_local.DockerCommandSandbox,
        "verify",
        lambda self: {"status": "verified"},
    )
    monkeypatch.setattr(
        task33_local,
        "_probe_retrieval",
        lambda output: {"status": "failed", "missing_required_paths": ["docs/offline-sync.md"]},
    )

    assert task33_local.main(["--preflight-output", str(output)]) == 3
    summary = json.loads((output / "preflight-summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "inconclusive"
