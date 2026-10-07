"""New offline evaluator smoke cases; not historical quality acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_action_packet_v4_public import necessary_evidence, OfflineRetrieval
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool


@pytest.fixture
def case(necessary_evidence):
    return {
        "case_id": "offline-v4-protocols", "result_kind": "patch_context",
        "question": "Inspect protocol implementations", "maximum_visible_tokens": 128,
        "expected_status": "data", "candidates": necessary_evidence["context_pack"],
        "required_facts": necessary_evidence["public_requirements"],
        "required_evidence_paths": necessary_evidence["required_evidence_paths"],
        "project_identity": necessary_evidence["project_identity"],
    }


def test_evidence_evaluator_retains_data_and_reports_historical_ceiling(case, tmp_path):
    from eval.evidence_selection_quality import evaluate_case, _evaluate_projection_only

    result = evaluate_case(case)
    assert result["status"] == "data" and result["completeness"] == "complete"
    assert result["errors"] == [] and result["checks"]["deterministic"]
    assert result["projected_tokens"] > 2000
    assert result["checks"]["token_ceiling"] is False and result["passed"] is False
    _, projection = _evaluate_projection_only(case)
    assert len(projection["sources"]) == 12 and projection["edit_ready"] is False


def test_historical_status_expectation_is_explicitly_unsupported(case, tmp_path):
    from eval.evidence_selection_quality import evaluate_case

    case["expected_status"] = "ok"
    result = evaluate_case(case)
    assert result["status"] == "data" and not result["checks"]["expected_status"]
    assert result["unsupported_evaluation_requirements"] == ["legacy_packet_status"]


def test_answer_quality_projection_uses_v4_without_producer_budget(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection, _run_integrity_mutation_gate

    projection, snapshot, errors = _task42_projection(case)
    assert errors == [] and projection["estimated_tokens"] > 2000
    assert projection["result"] == "data" and len(projection["sources"]) == 12
    assert snapshot["__action_packet__"]["packet"]["schema_version"] == 4
    integrity = _run_integrity_mutation_gate({"patch_context": (projection, snapshot, 128)})
    assert integrity["checks"]["patch_context"]["passed"] is True
    assert integrity["checks"]["docs_answer"]["passed"] is False


def test_answer_quality_docs_budget_is_unchanged(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection

    case.update(result_kind="docs_answer", maximum_visible_tokens=800)
    projection, _, errors = _task42_projection(case)
    assert errors == [] and projection["kind"] == "docs_answer"
    assert projection["estimated_tokens"] <= 800 and projection["edit_ready"] is False


def test_runner_observations_accept_flat_read_only_v4_and_reject_permission(necessary_evidence, tmp_path):
    from eval.task_level.runners.codex import _required_once_retrieval_metadata as codex_metadata
    from eval.task_level._github_models_part01 import _required_once_retrieval_metadata as hosted_metadata

    objective = "Inspect protocol implementations"
    projection = handle_context_tool("get_docs_context", {
        "question": objective, "context_format": "patch_context",
    }, OfflineRetrieval(necessary_evidence))
    assert projection["edit_ready"] is False
    event = {"arguments": {"question": objective, "context_format": "patch_context"},
             "result": {"structuredContent": projection}}
    assert codex_metadata(event, task_objective=objective)["retrieval_succeeded"] is True
    request = SimpleNamespace(task_objective=objective)
    action = {"query": objective, "tool": "get_docs_context"}
    assert hosted_metadata(request, action, json.dumps(projection))["retrieval_succeeded"] is True
    forged = {**projection, "edit_ready": True}
    event["result"]["structuredContent"] = forged
    assert codex_metadata(event, task_objective=objective)["retrieval_succeeded"] is False
    assert hosted_metadata(request, action, json.dumps(forged))["retrieval_succeeded"] is False


def test_isolated_evidence_checks_read_visible_v4_sources(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.task_level.isolated_delivery import missing_packet_evidence_categories, missing_packet_evidence_paths

    projection, _, errors = _task42_projection(case)
    assert errors == []
    evidence = tuple(case["candidates"])
    assert missing_packet_evidence_categories(projection, evidence, ("project_docs",)) == []
    assert missing_packet_evidence_paths(projection, evidence, tuple(case["required_evidence_paths"])) == []
    assert missing_packet_evidence_paths(projection, evidence, ("docs/absent.md",)) == ["docs/absent.md"]


def test_direct_task_evaluation_ceiling_rejects_without_runtime_compaction(case, tmp_path):
    from eval.task_level._execution_part03 import build_bounded_direct_packet
    from eval.task_level.isolated_delivery import HostEvidenceSnapshot, IsolatedDeliveryError, TASK33_QUERY_DERIVATION

    task = SimpleNamespace(issue_text=case["question"], test_command="pytest offline_protocols", task_id="offline-v4")
    evidence = HostEvidenceSnapshot(
        query="protocol implementations", objective_sha256=hashlib.sha256(task.issue_text.encode()).hexdigest(),
        query_derivation=TASK33_QUERY_DERIVATION, evidence_items=tuple(case["candidates"]),
        trust_contract={}, retrieval_issues=(), evidence_categories=("project_docs",),
        project_revision="offline-head", index_revision="offline-index", response_status="success",
        raw_retrieval_tokens=9000, retrieval_wall_time_seconds=0,
    )
    with pytest.raises(IsolatedDeliveryError, match="historical_evaluation_packet_token_ceiling_exceeded"):
        build_bounded_direct_packet(task, tmp_path, tmp_path / "evaluation", evidence)
    assert not (tmp_path / "evaluation" / "action_packet.json").exists()


def test_eval_source_imports_are_from_worktree(tmp_path):
    import eval.evidence_selection_quality as module
    assert Path(module.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1])


def test_workflow_evaluation_requirements_fail_closed_without_v4_policy_fields(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection, _evaluate_measured_case

    projection, snapshot, errors = _task42_projection(case)
    contract = {
        "contract_id": "offline-forbidden-workflow", "source_ref": "offline:v4", "taxonomy": "patch_context",
        "result_kind": "patch_context", "expected_status": "ok", "maximum_visible_tokens": 1500,
        "required_patch_fields": {"checks": ["pytest"]}, "required_public_commands": ["pytest"],
        "required_answer_facts": [], "acceptable_evidence": [], "forbidden_claims": [],
        "forbidden_versions": [], "exact_identifiers": [],
    }
    result = _evaluate_measured_case(contract, {
        "projection": projection, "snapshot": snapshot, "validation_errors": errors,
    })
    assert result["passed"] is False
    assert "workflow_commands_from_document_data" in result["unsupported_evaluation_requirements"]
    assert "checks" in result["unsupported_evaluation_requirements"]
    assert "checks" not in projection and projection["edit_ready"] is False
    assert len(result["source_manifest"]) == 12
