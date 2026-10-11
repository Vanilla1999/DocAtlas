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

import eval.task_level._isolated_delivery_part02 as isolated_delivery_part02

from docmancer.docs.application.action_packet import (
    build_action_packet,
    estimate_action_packet_tokens,
    refresh_action_packet_estimate,
    validate_action_packet,
)
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from eval.task_level.conditions import CONDITIONS, TOOL_REQUIRED_ONCE_INSTRUCTION
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
    TASK33C_AGENT_TURN_LIMIT,
    TASK33C_PILOT_CONDITIONS,
    TASK33C_PILOT_TASK_ID,
    TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    TASK33C_REQUIRED_EVIDENCE_PATHS,
    TASK33C_REQUIRED_TARGET_PATHS,
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
    items = evidence if evidence is not None else _evidence()
    # The fixture requests each authored source sentence explicitly. The
    # selector must not derive behavioral obligations from the objective.
    content_literals = tuple(items[0]["content"].splitlines())
    assert content_literals and all(content_literals)
    packet = build_action_packet(
        question=_envelope().task_objective,
        context_pack=items,
        trust_contract={"selected": [{"source": "AGENTS.md"}], "rejected": [], "risky": []},
        project_path="/repo",
        public_requirements=content_literals,
    )
    assert validate_action_packet(packet, evidence_items=items, project_path="/repo") == []
    assert packet["result"] == "data" and packet["completeness"] == "complete"
    assert len(packet["sources"]) == len(items) == 1
    source = packet["sources"][0]
    assert source["path"] == items[0]["path"] and source["text"] == items[0]["content"]
    assert source["content_sha256"] == hashlib.sha256(items[0]["content"].encode()).hexdigest()
    assert source["instruction_trust"] == "untrusted_data" and packet["edit_ready"] is False
    assert "task_interpretation" not in packet and "mutation_intent" not in packet
    requirements = {row["requirement_id"]: row for row in packet["requirements"]}
    assert {row["value"] for row in requirements.values()} == set(content_literals)
    assert all(row["kind"] == "required_fact" and row["mandatory"] is True
               and row["public_provenance"] == "public_task_contract" for row in requirements.values())
    assert len(packet["assignments"]) == len(requirements) == len(content_literals)
    for assignment in packet["assignments"]:
        literal = requirements[assignment["requirement_id"]]["value"]
        assert assignment["evidence_id"] == source["stable_id"] and assignment["path"] == source["path"]
        assert assignment["proof_role"] == "generic_fact" and assignment["unit_id"]
        assert source["text"][assignment["unit_char_start"]:assignment["unit_char_end"]] == literal
        assert assignment["unit_content_hash"] == hashlib.sha256(literal.encode()).hexdigest()
    assert "missing" not in packet
    assert packet["estimated_tokens"] == estimate_action_packet_tokens(packet)
    return packet


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






def test_isolated_broker_persists_recomputable_evidence_and_bounded_handoff(tmp_path):
    worker = Worker()
    result = _deliver(worker, tmp_path)

    assert worker.calls == 1
    assert result["result"] == _packet()["result"] == "data"
    assert result["completeness"] == _packet()["completeness"] == "complete"
    assert result["packet"]["estimated_tokens"] <= 1_500
    assert result["packet"]["edit_ready"] is False
    assert result["projection"]["sources"] == result["packet"]["sources"]
    assert result["projection"]["edit_ready"] is False
    assert set(path.name for path in tmp_path.iterdir()) == {
        "action_packet.json",
        "context_sources.json",
        "host_evidence_manifest.json",
        "host_evidence_snapshot.json",
        "isolated_delegation_envelope.json",
        "isolated_delivery_attempt.json",
        "isolated_delivery_metrics.json",
        "model_visible_evidence_snapshot.json",
        "model_visible_patch_context.json",
        "worker_usage_proof.json",
    }
    manifest = json.loads((tmp_path / "host_evidence_manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((tmp_path / "host_evidence_snapshot.json").read_text(encoding="utf-8"))
    metrics = json.loads((tmp_path / "isolated_delivery_metrics.json").read_text(encoding="utf-8"))
    projection_snapshot = json.loads((tmp_path / "model_visible_evidence_snapshot.json").read_text(encoding="utf-8"))
    projection = json.loads((tmp_path / "model_visible_patch_context.json").read_text(encoding="utf-8"))
    assert projection == result["projection"]
    assert validate_model_visible_projection(projection, snapshot=projection_snapshot) == []
    assert projection["sources"][0]["text"] == _evidence()[0]["content"]
    assert metrics["result"] == result["result"] and metrics["completeness"] == result["completeness"]
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
    assert all("DOCATLAS_HOME" not in part for part in command)
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



