from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace

import pytest

from docmancer.docs.application.action_packet import build_action_packet, estimate_action_packet_tokens
from eval.task_level.conditions import CONDITIONS
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.execution import build_tool_policy
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    IsolatedDeliveryError,
    IsolatedWorkerCapabilities,
    IsolatedWorkerOutput,
    JsonSubprocessIsolatedWorker,
    deliver_with_isolated_worker,
)
from eval.task_level.task33_pilot import TASK33C_PILOT_CONDITIONS, TASK33C_PILOT_TASK_ID, build_task33c_pilot_plan


def _envelope() -> DelegationEnvelope:
    return DelegationEnvelope(
        task_objective="Preserve the permission boundary and run focused tests.",
        suspected_modules=("lib/modules/permission",),
        changed_files=(),
        required_evidence_categories=("ownership", "validation"),
        project_revision="fixture-sha256",
        index_revision="index-sha256",
    )


def _evidence() -> list[dict]:
    return [{
        "path": "AGENTS.md",
        "heading_path": "Permission checks",
        "authority": "canonical",
        "instruction_trust": "scoped_agent_policy",
        "content": (
            "The permission boundary must remain centralized.\n"
            "Run pytest tests/test_permission.py."
        ),
    }]


def _packet() -> dict:
    return build_action_packet(
        question=_envelope().task_objective,
        context_pack=_evidence(),
        trust_contract={"selected": [{"source": "AGENTS.md"}], "rejected": [], "risky": []},
        max_tokens=1_500,
        project_path="/repo",
    )


class Worker:
    capabilities = IsolatedWorkerCapabilities(True, True, True, True, True)
    compressor_identity = "fake-compressor-v1"

    def __init__(self, output: IsolatedWorkerOutput | None = None) -> None:
        self.calls = 0
        self.output = output or IsolatedWorkerOutput(
            packet=_packet(), evidence_items=tuple(_evidence()), retrieval_calls=1, parent_visible_raw_retrieval=False,
            input_tokens=300, output_tokens=120, reasoning_tokens=10,
            raw_retrieval_tokens=2_400, wall_time_seconds=0.5,
        )

    def run(self, envelope, *, timeout_seconds):
        self.calls += 1
        assert envelope == _envelope()
        assert timeout_seconds == 5
        return self.output


def test_isolated_broker_requires_every_capability_and_never_retries(tmp_path):
    worker = Worker()
    worker.capabilities = replace(worker.capabilities, read_only_documentation=False)
    with pytest.raises(IsolatedDeliveryError, match="capability_unverified"):
        deliver_with_isolated_worker(worker=worker, envelope=_envelope(), output_dir=tmp_path, timeout_seconds=5)
    assert worker.calls == 0

    for index, (broken, reason) in enumerate((
        (replace(worker.output, retrieval_calls=2), "retrieve_exactly_once"),
        (replace(worker.output, parent_visible_raw_retrieval=True), "parent_boundary"),
        (replace(worker.output, timed_out=True), "worker_timeout"),
    )):
        candidate = Worker(broken)
        with pytest.raises(IsolatedDeliveryError, match=reason):
            deliver_with_isolated_worker(worker=candidate, envelope=_envelope(), output_dir=tmp_path / f"failure-{index}", timeout_seconds=5)
        assert candidate.calls == 1
        with pytest.raises(IsolatedDeliveryError, match="attempt_already_consumed"):
            deliver_with_isolated_worker(worker=candidate, envelope=_envelope(), output_dir=tmp_path / f"failure-{index}", timeout_seconds=5)
        assert candidate.calls == 1

    invented = _packet()
    invented["required_invariants"][0]["text"] = "The invented boundary must replace the real one."
    for _ in range(4):
        invented["estimated_tokens"] = estimate_action_packet_tokens(invented)
    candidate = Worker(replace(worker.output, packet=invented))
    with pytest.raises(IsolatedDeliveryError, match="invalid_action_packet"):
        deliver_with_isolated_worker(worker=candidate, envelope=_envelope(), output_dir=tmp_path / "invented", timeout_seconds=5)
    assert candidate.calls == 1


def test_isolated_broker_persists_only_bounded_parent_safe_handoff(tmp_path):
    worker = Worker()
    result = deliver_with_isolated_worker(
        worker=worker, envelope=_envelope(), output_dir=tmp_path, timeout_seconds=5,
    )

    assert worker.calls == 1
    assert result["status"] == "success"
    assert result["packet"]["estimated_tokens"] <= 1_500
    assert set(path.name for path in tmp_path.iterdir()) == {
        "action_packet.json", "isolated_delegation_envelope.json", "isolated_delivery_metrics.json",
        "isolated_delivery_attempt.json",
    }
    persisted_objects = [json.loads(path.read_text(encoding="utf-8")) for path in tmp_path.iterdir()]
    assert all("raw_retrieval" not in value and "context_pack" not in value for value in persisted_objects)
    metrics = json.loads((tmp_path / "isolated_delivery_metrics.json").read_text(encoding="utf-8"))
    assert metrics["attempts"] == metrics["retrieval_calls"] == 1
    assert metrics["parent_visible_raw_retrieval"] is False
    assert metrics["worker_input_tokens"] == 300
    assert metrics["raw_retrieval_tokens"] == 2_400

    executable = shutil.which("python3")
    assert executable and executable.startswith("/")
    subprocess_payload = {
        "packet": _packet(), "evidence_items": _evidence(), "retrieval_calls": 1,
        "input_tokens": 300, "output_tokens": 120, "raw_retrieval_tokens": 2_400,
    }
    code = (
        "import json,os,pathlib,sys; "
        "blocked=False; "
        "\ntry: pathlib.Path('forbidden').write_text('x')"
        "\nexcept OSError: blocked=True"
        "\nif not blocked: sys.exit(7)"
        "\nprint(os.environ['WORKER_RESULT'])"
    )
    process_worker = JsonSubprocessIsolatedWorker(
        command=(executable, "-c", code),
        compressor_identity="subprocess-v1",
        environment={"WORKER_RESULT": json.dumps(subprocess_payload)},
        capabilities=IsolatedWorkerCapabilities(True, True, True, True, True),
    )
    if os.geteuid() == 0:
        with pytest.raises(IsolatedDeliveryError, match="root_sandbox_unavailable"):
            deliver_with_isolated_worker(
                worker=process_worker, envelope=_envelope(), output_dir=tmp_path / "process", timeout_seconds=5,
            )
    else:
        process_result = deliver_with_isolated_worker(
            worker=process_worker, envelope=_envelope(), output_dir=tmp_path / "process", timeout_seconds=5,
        )
        assert process_result["packet"] == _packet()


def test_task33c_four_lane_plan_and_flags_are_frozen(tmp_path):
    plan = build_task33c_pilot_plan(TASK33C_PILOT_TASK_ID)

    assert tuple(plan["conditions"]) == TASK33C_PILOT_CONDITIONS
    with pytest.raises(ValueError, match="frozen"):
        build_task33c_pilot_plan("another_task")
    assert plan["repeats"] == 1
    assert plan["retrieval_call_budget"] == plan["isolated_worker_attempt_budget"] == 1
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
    assert len([name for name, value in globals().items() if name.startswith("test_") and callable(value)]) == 3
