from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.application.action_packet import build_action_packet
from eval.task_level.execution import (
    _assert_task33_run_preconditions,
    _run_evaluation_command,
)
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorkerOutput,
    TASK33_QUERY_DERIVATION,
    WorkerUsage,
    deliver_with_exploratory_worker,
    deliver_with_isolated_worker,
    derive_task33_retrieval_query,
)
from eval.task_level.runner import load_tasks
from eval.task_level.runners.codex import CodexRunner
from eval.task_level import task33_codex_exploratory
from eval.task_level.task33_codex_exploratory import (
    CodexExploratoryWorker,
    _codex_failure_summary,
    summarize_exploratory_results,
)
from eval.task_level.task33_validation import load_protocol


def _envelope() -> DelegationEnvelope:
    objective = "Preserve permission permission architecture and offline sync boundaries."
    return DelegationEnvelope(
        task_objective=objective,
        suspected_modules=("lib/modules/permission/service.dart",),
        changed_files=(),
        required_evidence_categories=("project_docs",),
        required_evidence_paths=("docs/permission-architecture.md",),
        project_revision="fixture-revision",
        index_revision="index-revision",
    )


def _snapshot() -> HostEvidenceSnapshot:
    envelope = _envelope()
    evidence = ({
        "path": "docs/permission-architecture.md",
        "heading_path": "Permission boundary",
        "authority": "canonical",
        "source_class": "project_doc",
        "instruction_trust": "trusted_project_policy",
        "content": "Keep permission checks centralized in lib/modules/permission/service.dart.",
    },)
    return HostEvidenceSnapshot(
        query=derive_task33_retrieval_query(envelope.task_objective),
        objective_sha256=hashlib.sha256(envelope.task_objective.encode()).hexdigest(),
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=evidence,
        trust_contract={"selected": [], "rejected": [], "risky": []},
        retrieval_issues=(),
        evidence_categories=("project_docs",),
        project_revision=envelope.project_revision,
        index_revision=envelope.index_revision,
        response_status="success",
        raw_retrieval_tokens=100,
        retrieval_wall_time_seconds=0.1,
    )


def test_codex_exploratory_worker_uses_oauth_jsonl_without_claiming_verified_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    stdout = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "thread-123"}),
        json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": '{"selected_indices":[0]}'},
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 120,
                "cached_input_tokens": 20,
                "output_tokens": 15,
                "reasoning_output_tokens": 5,
            },
        }),
    ])
    captured: dict[str, object] = {}
    source_home = tmp_path / "source-codex-home"
    source_home.mkdir()
    (source_home / "auth.json").write_text('{"tokens": {}}')
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-forwarded")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-forwarded")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        assert (Path(kwargs["env"]["CODEX_HOME"]) / "auth.json").is_file()
        assert Path(kwargs["env"]["HOME"]).is_dir()
        schema_path = Path(command[command.index("--output-schema") + 1])
        schema = json.loads(schema_path.read_text())
        assert "uniqueItems" not in schema["properties"]["selected_indices"]
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(task33_codex_exploratory, "_run_bounded_codex", fake_run)
    worker = CodexExploratoryWorker(model="gpt-test", temp_root=tmp_path)

    output = worker.run(_envelope(), _snapshot(), timeout_seconds=30)

    assert worker.capabilities.verified is False
    assert worker.capability_evidence["status"] == "exploratory_unverified"
    assert "OPENAI_API_KEY" not in worker.capability_evidence
    assert output.packet["task_interpretation"]["objective"] == _envelope().task_objective
    assert output.usage.request_id == "client-thread:thread-123"
    assert output.usage.proof["request_id_kind"] == "client_thread_id"
    assert output.usage.input_tokens == 120
    assert output.usage.reasoning_tokens == 5
    assert output.usage.proof["server_request_id_verified"] is False
    command = captured["command"]
    assert "--ephemeral" in command
    assert "--skip-git-repo-check" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "danger-full-access" not in command
    assert captured["cwd"] != Path.cwd()
    env = captured["env"]
    assert "OPENAI_API_KEY" not in env
    assert "UNRELATED_SECRET" not in env


def test_codex_failure_summary_redacts_credentials_and_preserves_diagnostic():
    summary = _codex_failure_summary(
        "Authorization: Bearer secret...odel gpt-test is unavailable"
    )

    assert "secret-token" not in summary
    assert "Bearer <redacted>" in summary
    assert "gpt-test is unavailable" in summary


def test_unverified_codex_worker_requires_explicit_exploratory_delivery(tmp_path: Path):
    worker = CodexExploratoryWorker(model="gpt-test", temp_root=tmp_path)
    with pytest.raises(IsolatedDeliveryError, match="capability_unverified"):
        deliver_with_isolated_worker(
            worker=worker,
            envelope=_envelope(),
            evidence=_snapshot(),
            output_dir=tmp_path / "causal",
            timeout_seconds=30,
        )


def test_explicit_exploratory_delivery_is_persisted_as_non_causal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    usage = WorkerUsage(
        provider="codex-oauth",
        model="gpt-test",
        request_id="thread-123",
        input_tokens=120,
        output_tokens=15,
        reasoning_tokens=5,
        proof={
            "schema_version": 1,
            "provider": "codex-oauth",
            "model": "gpt-test",
            "request_id": "thread-123",
            "input_tokens": 120,
            "output_tokens": 15,
            "reasoning_tokens": 5,
            "server_request_id_verified": False,
            "provider_usage_verified": False,
        },
    )
    output = IsolatedWorkerOutput(
        packet=build_action_packet(
            question=_envelope().task_objective,
            context_pack=_snapshot().evidence_items,
            trust_contract=_snapshot().trust_contract,
            max_tokens=_envelope().token_budget,
        ),
        usage=usage,
        wall_time_seconds=0.5,
    )
    monkeypatch.setattr(CodexExploratoryWorker, "run", lambda *args, **kwargs: output)

    result = deliver_with_exploratory_worker(
        worker=CodexExploratoryWorker(model="gpt-test", temp_root=tmp_path),
        envelope=_envelope(),
        evidence=_snapshot(),
        output_dir=tmp_path / "exploratory",
        timeout_seconds=30,
    )

    metrics = json.loads(
        (tmp_path / "exploratory" / "isolated_delivery_metrics.json").read_text()
    )
    assert result["status"] == metrics["status"]
    assert metrics["evidence_tier"] == "exploratory"
    assert metrics["causal_claim_allowed"] is False
    assert metrics["server_request_id_verified"] is False


def test_task33_preconditions_allow_codex_only_for_explicit_exploratory_tier():
    task = next(task for task in load_tasks() if task.task_id == load_protocol()["task_id"])
    runner = CodexRunner(sandbox_mode="workspace-write")
    conditions = load_protocol()["conditions"]

    with pytest.raises(ValueError, match="proven hard turn limit"):
        _assert_task33_run_preconditions([task], runner)

    _assert_task33_run_preconditions(
        [task], runner, evidence_tier="exploratory", conditions=conditions, repeats=1
    )
    with pytest.raises(ValueError, match="exactly the frozen protocol cells"):
        _assert_task33_run_preconditions(
            [task], runner, evidence_tier="exploratory", conditions=conditions[:-1], repeats=1
        )


def test_host_exploratory_evaluator_runs_without_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(
        task33_codex_exploratory,
        "DockerCommandSandbox",
        lambda *args, **kwargs: pytest.fail("Docker must not be used"),
    )

    completed = _run_evaluation_command(
        SimpleNamespace(task_id=load_protocol()["task_id"]),
        "python3 -c 'print(42)'",
        workspace,
        output_dir,
        "public",
        30,
        evaluation_backend="host_exploratory",
    )

    boundary = json.loads((output_dir / "evaluator_execution_boundary.json").read_text())
    assert completed.returncode == 0
    assert completed.stdout.strip() == "42"
    assert boundary["status"] == "exploratory_unisolated"
    assert boundary["causal_claim_allowed"] is False


def test_host_evaluator_is_rejected_for_causal_task33():
    task = next(task for task in load_tasks() if task.task_id == load_protocol()["task_id"])
    runner = CodexRunner(sandbox_mode="workspace-write")

    with pytest.raises(ValueError, match="host evaluator requires exploratory evidence tier"):
        _assert_task33_run_preconditions(
            [task],
            runner,
            conditions=load_protocol()["conditions"],
            repeats=1,
            evaluation_backend="host_exploratory",
        )


def test_host_preflight_does_not_require_or_probe_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(task33_codex_exploratory, "RESULTS_ROOT", tmp_path)
    monkeypatch.setattr(
        task33_codex_exploratory.shutil,
        "which",
        lambda name: None if name == "docker" else f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_prewarm_fixture_dependencies",
        lambda output: output / "uv-cache",
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_probe_retrieval",
        lambda output: {"status": "verified"},
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_probe_codex_selector",
        lambda *args, **kwargs: {"status": "exploratory_verified"},
    )
    monkeypatch.setattr(
        task33_codex_exploratory.DockerCommandSandbox,
        "verify",
        lambda self: pytest.fail("Docker must not be probed"),
    )

    rc = task33_codex_exploratory.main(
        ["--host-exploratory", "--run-id", "host-preflight"]
    )

    summary = json.loads(
        (tmp_path / "host-preflight_preflight" / "preflight-summary.json").read_text()
    )
    assert rc == 0
    assert summary["checks"]["execution_backend"]["status"] == "exploratory_unisolated"
    assert "docker" not in summary["checks"]


def test_preflight_stops_before_codex_probe_when_docker_boundary_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(task33_codex_exploratory, "RESULTS_ROOT", tmp_path)
    monkeypatch.setattr(
        task33_codex_exploratory.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_build_image",
        lambda *args: {"status": "verified", "image_id": "sha256:test"},
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_prewarm_fixture_dependencies",
        lambda output: output / "uv-cache",
    )
    monkeypatch.setattr(
        task33_codex_exploratory.DockerCommandSandbox,
        "verify",
        lambda self: {"status": "failed", "reason": "no-new-privileges blocked"},
    )
    monkeypatch.setattr(
        task33_codex_exploratory,
        "_probe_codex_selector",
        lambda *args: pytest.fail("Codex probe must not run after failed Docker boundary"),
    )

    rc = task33_codex_exploratory.main(["--run-id", "blocked-docker"] )

    summary = json.loads(
        (tmp_path / "blocked-docker_preflight" / "preflight-summary.json").read_text()
    )
    assert rc == 3
    assert summary["checks"]["docker"]["status"] == "failed"
    assert "codex_oauth_selector" not in summary["checks"]


def test_exploratory_summary_reports_metrics_without_valid_verdict():
    conditions = load_protocol()["conditions"]
    results = [
        {
            "condition_id": condition,
            "status": "completed",
            "resolved": condition != "repo_only_strict_offline",
            "hidden_tests_passed": condition != "repo_only_strict_offline",
            "metrics": {
                "input_tokens": 100 + index,
                "cached_input_tokens": 80,
                "uncached_input_tokens": 20 + index,
                "output_tokens": 20,
                "total_latency": 1.0 + index,
                "time_to_first_edit": 0.5,
            },
            "budget": {
                "input_token_basis": "parent_provider_reported_input_including_cached",
                "indexing_provider_tokens_included": False,
            },
            "token_attribution": {
                "indexing": {
                    "status": "already_current",
                    "provider_input_tokens": 0,
                    "provider_output_tokens": 0,
                    "included_in_parent_budget": False,
                },
            },
        }
        for index, condition in enumerate(conditions)
    ]

    summary = summarize_exploratory_results(results)

    assert summary["status"] == "complete_exploratory"
    assert summary["verdict"] == "EXPLORATORY_NON_CAUSAL"
    assert summary["valid"] is False
    assert summary["conditions"]["repo_only_strict_offline"]["hidden_tests_passed"] is False
    assert summary["conditions"]["docatlas_bounded_direct"]["input_tokens"] == 102
    assert summary["conditions"]["docatlas_bounded_direct"]["cached_input_tokens"] == 80
    assert summary["conditions"]["docatlas_bounded_direct"]["uncached_input_tokens"] == 22
    assert summary["conditions"]["docatlas_bounded_direct"]["indexing_provider_tokens"] == 0
    assert summary["conditions"]["docatlas_bounded_direct"]["indexing_provider_tokens_included"] is False
    assert summary["conditions"]["docatlas_bounded_direct"]["time_to_first_edit"] is None
    assert (
        summary["conditions"]["docatlas_bounded_direct"]["time_to_first_edit_reason"]
        == "codex_jsonl_not_stream_timed"
    )


def test_exploratory_summary_is_inconclusive_when_indexing_attribution_is_missing():
    conditions = load_protocol()["conditions"]
    results = [
        {
            "condition_id": condition,
            "status": "completed",
            "metrics": {},
            "budget": {},
        }
        for condition in conditions
    ]

    summary = summarize_exploratory_results(results)

    assert summary["status"] == "inconclusive_exploratory"
    assert summary["verdict"] == "INCONCLUSIVE"
    assert summary["missing_indexing_attribution"] == conditions
    assert summary["conditions"][conditions[0]]["indexing_provider_tokens"] is None


def test_codex_exploratory_path_does_not_change_frozen_provider_profiles():
    assert set(load_protocol()["provider_profiles"]) == {"github-models", "openai-api"}