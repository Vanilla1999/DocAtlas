from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
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
    envelope = _envelope()
    source_literal = "Keep permission checks centralized in lib/modules/permission/service.dart."

    def worker_output(evidence):
        packet = build_action_packet(
            question=envelope.task_objective,
            context_pack=evidence.evidence_items,
            trust_contract=evidence.trust_contract,
            required_evidence_paths=envelope.required_evidence_paths,
            required_target_paths=envelope.suspected_modules,
            # Path assignments establish identities only; this authored quote
            # supplies the separate visible-content witness.
            public_requirements=(source_literal,),
        )
        assert validate_action_packet(packet, evidence_items=evidence.evidence_items) == []
        assert packet["result"] == "data" and packet["edit_ready"] is False
        return IsolatedWorkerOutput(packet=packet, usage=usage, wall_time_seconds=0.5)

    evidence = _snapshot()
    assert evidence.evidence_items[0]["content"] == source_literal
    output = worker_output(evidence)
    assert output.packet["completeness"] == "partial"
    assert output.packet["missing"] == ["target_path:0:" + envelope.suspected_modules[0]]
    monkeypatch.setattr(CodexExploratoryWorker, "run", lambda *args, **kwargs: output)
    with pytest.raises(IsolatedDeliveryError, match="action_packet_missing_required_target_modules"):
        deliver_with_exploratory_worker(
            worker=CodexExploratoryWorker(model="gpt-test", temp_root=tmp_path),
            envelope=envelope,
            evidence=evidence,
            output_dir=tmp_path / "missing-target",
            timeout_seconds=30,
        )
    assert not (tmp_path / "missing-target" / "action_packet.json").exists()

    # An explicit host-selected code window supplies the target identity; the
    # documentation's mention of this filename does not establish that identity.
    target = envelope.suspected_modules[0]
    target_path = tmp_path / target
    target_path.parent.mkdir(parents=True)
    target_path.write_text("class PermissionService {}\n", encoding="utf-8")
    target_text = target_path.read_text(encoding="utf-8")
    target_evidence = {
        "path": target,
        "source_class": "project_file",
        "authority": "supporting",
        "content": target_text,
        "matched": True,
        "char_start": 0,
        "char_end": len(target_text),
        "line_start": 1,
        "line_end": 1,
    }
    evidence = replace(evidence, evidence_items=(*evidence.evidence_items, target_evidence))
    output = worker_output(evidence)

    result = deliver_with_exploratory_worker(
        worker=CodexExploratoryWorker(model="gpt-test", temp_root=tmp_path),
        envelope=envelope,
        evidence=evidence,
        output_dir=tmp_path / "exploratory",
        timeout_seconds=30,
    )

    metrics = json.loads(
        (tmp_path / "exploratory" / "isolated_delivery_metrics.json").read_text()
    )
    assert result["result"] == metrics["result"] == "data"
    assert result["completeness"] == metrics["completeness"] == "complete"
    assert result["packet"]["estimated_tokens"] <= envelope.token_budget
    assert result["packet"]["edit_ready"] is False
    projection = result["projection"]
    projection_snapshot = json.loads(
        (tmp_path / "exploratory" / "model_visible_evidence_snapshot.json").read_text()
    )
    assert validate_model_visible_projection(projection, snapshot=projection_snapshot) == []
    assert projection["sources"] == result["packet"]["sources"]
    assert projection["edit_ready"] is False
    expected = {item["path"]: item["content"] for item in evidence.evidence_items}
    assert len(projection["sources"]) == len(expected) == 2
    for source in projection["sources"]:
        assert source["text"] == expected[source["path"]]
        assert source["content_sha256"] == hashlib.sha256(source["text"].encode()).hexdigest()
        assert source["instruction_trust"] == "untrusted_data"
    selected_target = next(source for source in projection["sources"] if source["path"] == target)
    assert (selected_target["char_start"], selected_target["char_end"], selected_target["line_start"], selected_target["line_end"]) == (0, len(target_text), 1, 1)
    assert any(row["path"] == target and row["proof_role"] == "target_identity" for row in projection["assignments"])
    literal_requirement, = [row for row in projection["requirements"] if row["kind"] == "required_fact"]
    assert literal_requirement["value"] == source_literal and literal_requirement["mandatory"] is True
    assert literal_requirement["public_provenance"] == "public_task_contract"
    content_assignment, = [row for row in projection["assignments"]
                           if row["requirement_id"] == literal_requirement["requirement_id"]]
    doc_source = next(source for source in projection["sources"]
                      if source["path"] == envelope.required_evidence_paths[0])
    assert content_assignment["evidence_id"] == doc_source["stable_id"]
    assert content_assignment["path"] == doc_source["path"]
    assert content_assignment["proof_role"] == "generic_fact" and content_assignment["unit_id"]
    assert content_assignment["unit_content_hash"] == doc_source["content_sha256"]
    assert (content_assignment["unit_char_start"], content_assignment["unit_char_end"]) == (0, len(source_literal))
    assert "missing" not in projection
    assert metrics["evidence_fingerprint"] == evidence.fingerprint
    assert metrics["attempts"] == metrics["retrieval_calls"] == 1
    assert metrics["evidence_tier"] == "exploratory"
    assert metrics["causal_claim_allowed"] is False
    assert metrics["server_request_id_verified"] is False






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















