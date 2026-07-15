from __future__ import annotations

import json
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
    monkeypatch.setenv("OPENAI_API_KEY", "secret-not-for-artifacts")
    monkeypatch.setattr(
        task33_local,
        "_build_image",
        lambda image, base: {"status": "verified", "image_id": image + base},
    )
    monkeypatch.setattr(task33_local, "_prewarm_fixture_dependencies", lambda output: None)
    monkeypatch.setattr(
        task33_local,
        "run_openai_api_capability_probe",
        lambda *args, **kwargs: {"status": "verified", "provider": "openai-api"},
    )
    monkeypatch.setattr(
        task33_local.DockerCommandSandbox,
        "verify",
        lambda self: {"status": "verified", "image": self.image},
    )
    monkeypatch.setattr(
        task33_local,
        "_probe_retrieval",
        lambda output: {"status": "verified", "retrieval_calls": 1},
    )

    assert task33_local.main(["--preflight-output", str(output)]) == 0

    summary = json.loads((output / "preflight-summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "verified"
    assert summary["run_causal_pilot_requested"] is False
    assert "secret-not-for-artifacts" not in json.dumps(summary)


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
