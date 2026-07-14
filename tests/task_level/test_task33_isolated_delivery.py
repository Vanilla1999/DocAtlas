from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from docmancer.docs.application.action_packet import build_action_packet, estimate_action_packet_tokens
from eval.task_level.conditions import CONDITIONS
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.execution import build_tool_policy
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorkerCapabilities,
    IsolatedWorkerOutput,
    JsonSubprocessIsolatedWorker,
    TASK33_QUERY_DERIVATION,
    WorkerUsage,
    _communicate_bounded,
    derive_task33_retrieval_query,
    deliver_with_isolated_worker,
)
from eval.task_level.task33_pilot import (
    TASK33C_PILOT_CONDITIONS,
    TASK33C_PILOT_TASK_ID,
    build_task33c_pilot_plan,
    evaluate_task33c_pilot_completeness,
)


def _envelope() -> DelegationEnvelope:
    return DelegationEnvelope(
        task_objective="Preserve the permission boundary and run focused tests.",
        suspected_modules=("lib/modules/permission",),
        changed_files=(),
        required_evidence_categories=("project_docs",),
        project_revision="fixture-sha256",
        index_revision="index-sha256",
    )


def _evidence() -> list[dict]:
    return [{
        "path": "AGENTS.md",
        "heading_path": "Permission checks",
        "authority": "canonical",
        "source_class": "project_doc",
        "instruction_trust": "scoped_agent_policy",
        "content": (
            "The permission boundary must remain centralized.\n"
            "Run pytest tests/test_permission.py."
        ),
    }]


def _snapshot() -> HostEvidenceSnapshot:
    return HostEvidenceSnapshot(
        query=derive_task33_retrieval_query(_envelope().task_objective),
        objective_sha256=hashlib.sha256(_envelope().task_objective.encode("utf-8")).hexdigest(),
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=tuple(_evidence()),
        trust_contract={"selected": [{"source": "AGENTS.md"}], "rejected": [], "risky": []},
        retrieval_issues=(),
        evidence_categories=("project_docs",),
        project_revision=_envelope().project_revision,
        index_revision=_envelope().index_revision,
        response_status="success",
        raw_retrieval_tokens=2_400,
        retrieval_wall_time_seconds=0.25,
    )


def _packet(*, evidence: list[dict] | None = None) -> dict:
    return build_action_packet(
        question=_envelope().task_objective,
        context_pack=evidence or _evidence(),
        trust_contract={"selected": [{"source": "AGENTS.md"}], "rejected": [], "risky": []},
        max_tokens=1_500,
        project_path="/repo",
    )


def _usage() -> WorkerUsage:
    return WorkerUsage(
        provider="test-provider",
        model="test-model",
        request_id="request-1",
        input_tokens=300,
        output_tokens=120,
        reasoning_tokens=10,
        proof={
            "schema_version": 1,
            "provider": "test-provider",
            "model": "test-model",
            "request_id": "request-1",
            "input_tokens": 300,
            "output_tokens": 120,
            "reasoning_tokens": 10,
        },
    )


class Worker:
    capabilities = IsolatedWorkerCapabilities(True, True, True, True, True, True, True, True)
    compressor_identity = "fake-compressor-v1"
    command_fingerprint = "sha256:fake-command"
    sandbox_identity = "fake-sandbox-v1"
    capability_evidence = {"schema_version": 1, "status": "verified", "checks": {"fake": True}}
    usage_verifier_identity = "fake-host-provider-verifier-v1"

    def __init__(self, output: IsolatedWorkerOutput | None = None) -> None:
        self.calls = 0
        self.output = output or IsolatedWorkerOutput(
            packet=_packet(),
            usage=_usage(),
            wall_time_seconds=0.5,
        )

    def run(self, envelope, evidence, *, timeout_seconds):
        self.calls += 1
        assert envelope == _envelope()
        assert evidence == _snapshot()
        assert timeout_seconds == 5
        return self.output


def _deliver(worker: Worker, output_dir: Path) -> dict:
    return deliver_with_isolated_worker(
        worker=worker,
        envelope=_envelope(),
        evidence=_snapshot(),
        output_dir=output_dir,
        timeout_seconds=5,
    )


def test_isolated_broker_requires_verified_boundary_and_never_retries(tmp_path):
    worker = Worker()
    worker.capabilities = replace(worker.capabilities, read_only_documentation=False)
    with pytest.raises(IsolatedDeliveryError, match="capability_unverified"):
        _deliver(worker, tmp_path)
    assert worker.calls == 0

    candidate = Worker(replace(worker.output, wall_time_seconds=6))
    with pytest.raises(IsolatedDeliveryError, match="worker_timeout"):
        _deliver(candidate, tmp_path / "timeout")
    assert candidate.calls == 1
    with pytest.raises(IsolatedDeliveryError, match="attempt_already_consumed"):
        _deliver(candidate, tmp_path / "timeout")
    assert candidate.calls == 1


def test_host_owns_retrieval_evidence_objective_and_usage_contract(tmp_path):
    with pytest.raises(IsolatedDeliveryError, match="retrieve_exactly_once"):
        replace(_snapshot(), retrieval_calls=True).validate(_envelope())
    with pytest.raises(IsolatedDeliveryError, match="retrieve_exactly_once"):
        replace(_snapshot(), retrieval_calls=1.0).validate(_envelope())
    with pytest.raises(IsolatedDeliveryError, match="revision_mismatch"):
        replace(_snapshot(), index_revision="invented-index").validate(_envelope())
    with pytest.raises(IsolatedDeliveryError, match="query_derivation_mismatch"):
        replace(_snapshot(), query="invented evaluator query").validate(_envelope())
    with pytest.raises(IsolatedDeliveryError, match="objective_fingerprint_mismatch"):
        replace(_snapshot(), objective_sha256="0" * 64).validate(_envelope())
    with pytest.raises(IsolatedDeliveryError, match="invalid_worker_usage_input_tokens"):
        WorkerUsage.from_json({
            "provider": "provider", "model": "model", "request_id": "id",
            "input_tokens": True, "output_tokens": 1, "reasoning_tokens": None,
            "proof": {"schema_version": 1},
        })

    different_evidence = [{
        **_evidence()[0],
        "content": "The invented boundary must replace the real one.",
    }]
    candidate = Worker(replace(Worker().output, packet=_packet(evidence=different_evidence)))
    with pytest.raises(IsolatedDeliveryError, match="invalid_action_packet"):
        _deliver(candidate, tmp_path / "invented-evidence")

    wrong_objective = _packet()
    wrong_objective["task_interpretation"]["objective"] = "Completely different task"
    wrong_objective["estimated_tokens"] = estimate_action_packet_tokens(wrong_objective)
    candidate = Worker(replace(Worker().output, packet=wrong_objective))
    with pytest.raises(IsolatedDeliveryError, match="objective_mismatch"):
        _deliver(candidate, tmp_path / "wrong-objective")

    class MutatingWorker(Worker):
        def run(self, envelope, evidence, *, timeout_seconds):
            output = super().run(envelope, evidence, timeout_seconds=timeout_seconds)
            evidence.evidence_items[0]["content"] = "mutated after host validation"
            return output

    with pytest.raises(IsolatedDeliveryError, match="host_evidence_mutated"):
        _deliver(MutatingWorker(), tmp_path / "mutated-host-evidence")


def test_isolated_broker_persists_recomputable_evidence_and_bounded_handoff(tmp_path):
    worker = Worker()
    result = _deliver(worker, tmp_path)

    assert worker.calls == 1
    assert result["status"] == _packet()["status"]
    assert result["packet"]["estimated_tokens"] <= 1_500
    assert set(path.name for path in tmp_path.iterdir()) == {
        "action_packet.json",
        "context_sources.json",
        "host_evidence_manifest.json",
        "host_evidence_snapshot.json",
        "isolated_delegation_envelope.json",
        "isolated_delivery_attempt.json",
        "isolated_delivery_metrics.json",
        "worker_usage_proof.json",
    }
    manifest = json.loads((tmp_path / "host_evidence_manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((tmp_path / "host_evidence_snapshot.json").read_text(encoding="utf-8"))
    metrics = json.loads((tmp_path / "isolated_delivery_metrics.json").read_text(encoding="utf-8"))
    assert manifest["evidence_fingerprint"] == metrics["evidence_fingerprint"] == _snapshot().fingerprint
    assert manifest["items"][0]["content_sha256"]
    assert snapshot["evidence_items"] == _evidence()
    assert metrics["attempts"] == metrics["retrieval_calls"] == 1
    assert metrics["parent_visible_raw_retrieval"] is False
    assert metrics["worker_input_tokens"] == 300
    assert metrics["usage_verifier_identity"] == "fake-host-provider-verifier-v1"
    assert metrics["worker_usage_proof_fingerprint"]
    assert metrics["raw_retrieval_tokens"] == 2_400
    assert "evidence_items" not in result and "trust_contract" not in result


def test_subprocess_worker_is_fail_closed_and_bounds_both_output_streams(tmp_path):
    worker = JsonSubprocessIsolatedWorker(
        command=("/usr/bin/python3", "-c", "pass"),
        compressor_identity="subprocess-v1",
        environment={},
        sandbox_executable=str(tmp_path / "missing-bwrap"),
    )
    assert not worker.capabilities.verified
    with pytest.raises(IsolatedDeliveryError, match="capability_unverified"):
        deliver_with_isolated_worker(
            worker=worker,
            envelope=_envelope(),
            evidence=_snapshot(),
            output_dir=tmp_path / "unavailable",
            timeout_seconds=5,
        )

    command = replace(worker, sandbox_executable="/usr/bin/bwrap")._sandbox_command(
        Path("/usr/bin/python3"), tmp_path,
    )
    for required in ("--unshare-all", "--die-with-parent", "--new-session", "--tmpfs", "--chdir"):
        assert required in command
    assert "/work" in command
    assert all("DOCMANCER_HOME" not in part for part in command)
    assert all(str(Path.cwd()) not in part for part in command)

    process = subprocess.Popen(
        [shutil.which("python3") or sys.executable, "-c", "import sys; sys.stderr.write('x' * 100000)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    with pytest.raises(IsolatedDeliveryError, match="stderr_too_large"):
        _communicate_bounded(
            process,
            b"{}",
            deadline=time.monotonic() + 3,
            max_stdout_bytes=100,
            max_stderr_bytes=1_000,
        )
    assert process.poll() is not None


def test_task33c_four_lane_plan_and_flags_are_frozen(tmp_path):
    plan = build_task33c_pilot_plan(TASK33C_PILOT_TASK_ID)

    objective = (
        "Browser and scan users see a permission gate conflict. Fix the permission gate so browser and scan agree."
    )
    assert derive_task33_retrieval_query(objective) == "browser scan permission gate"
    domain_objective = (
        "Browser and scan users can reach inconsistent permission outcomes after a partial "
        "permission result: one path can continue through an offline handoff while related "
        "paths do not agree on the shared gate. Fix the cross-module permission gate contract "
        "so browser, scan, and deferred sync decisions use the local permission architecture "
        "consistently."
    )
    assert derive_task33_retrieval_query(domain_objective) == (
        "browser scan permission gate offline sync"
    )
    assert tuple(plan["conditions"]) == TASK33C_PILOT_CONDITIONS
    with pytest.raises(ValueError, match="frozen"):
        build_task33c_pilot_plan("another_task")
    assert plan["repeats"] == 1
    assert plan["retrieval_call_budget"] == plan["isolated_worker_attempt_budget"] == 1
    assert plan["agent_turn_limit"] == 24
    assert plan["required_evidence_categories"] == ["project_docs"]
    assert plan["claims"]["may_claim_product_improvement"] is False
    direct = CONDITIONS["docatlas_bounded_direct"].tool_policy
    isolated = CONDITIONS["docatlas_bounded_subagent"].tool_policy
    assert direct.delivery_strategy == "bounded_direct" and not direct.isolated_worker_required
    assert isolated.delivery_strategy == "bounded_subagent" and isolated.isolated_worker_required
    assert not direct.allow_docatlas and not isolated.allow_docatlas
    _, mcp_path = build_tool_policy("docatlas_bounded_subagent", tmp_path)
    assert json.loads(mcp_path.read_text(encoding="utf-8")) == {"mcpServers": {}}
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(json.dumps([{
        "sequence": 1, "tool_name": "mcp", "arguments": {
            "server": "docmancer-docs", "tool": "get_docs_context",
        },
    }]), encoding="utf-8")
    audit = audit_trajectory("docatlas_bounded_subagent", trajectory)
    assert not audit.clean
    assert audit.violations == ["bounded delivery exposed a parent-visible DocAtlas tool call"]


def test_task33c_decision_gate_requires_complete_comparable_measurements():
    results = []
    for condition in TASK33C_PILOT_CONDITIONS:
        metrics = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_latency": 1.5,
            "time_to_first_edit": 0.5,
        }
        if condition in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
            metrics.update({
                "delivery_retrieval_calls": 1,
                "action_packet_status": "ok",
                "evidence_fingerprint": "shared-evidence",
                "action_packet_project_doc_coverage": 0.5,
            })
        if condition == "docatlas_bounded_subagent":
            metrics.update({
                "worker_input_tokens": 200,
                "worker_output_tokens": 80,
                "system_total_tokens": 430,
            })
        results.append({
            "task_id": TASK33C_PILOT_TASK_ID,
            "condition_id": condition,
            "repeat": 0,
            "status": "success",
            "metrics": metrics,
            "evaluation_execution": {
                "setup": {
                    "phase": "pre_runner",
                    "status": "success",
                    "returncode": 0,
                },
                "public_tests": {"status": "executed", "returncode": 1},
                "hidden_tests": {"status": "executed", "returncode": 1},
            },
            "evaluation_contract": {
                "status": "valid",
                "compile_gate": {"status": "not_applicable"},
            },
            "budget": {
                "max_turns_enforced_by_runner": True,
                "input_tokens_exceeded": False,
                "output_tokens_exceeded": False,
            },
        })

    complete = evaluate_task33c_pilot_completeness(results)
    assert complete["decision"] == "ENGINEERING_PILOT_COMPLETE"
    assert complete["complete"] is True
    results[-1]["metrics"]["worker_input_tokens"] = None
    incomplete = evaluate_task33c_pilot_completeness(results)
    assert incomplete["decision"] == "INCONCLUSIVE"
    assert "docatlas_bounded_subagent:missing_worker_input_tokens" in incomplete["errors"]
    results[-1]["metrics"]["worker_input_tokens"] = 200
    results[-1]["metrics"]["delivery_retrieval_calls"] = True
    incomplete = evaluate_task33c_pilot_completeness(results)
    assert "docatlas_bounded_subagent:invalid_retrieval_call_count" in incomplete["errors"]

    results[-1]["metrics"]["delivery_retrieval_calls"] = 1
    results[-1]["evaluation_execution"]["setup"]["status"] = "condition_setup_failed"
    incomplete = evaluate_task33c_pilot_completeness(results)
    assert "docatlas_bounded_subagent:setup_not_successful" in incomplete["errors"]
