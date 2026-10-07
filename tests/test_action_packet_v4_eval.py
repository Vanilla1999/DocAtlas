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
    assert result["required_covered"] == 0


def test_projection_gate_validates_actual_v4_and_keeps_historical_limits(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.answer_quality_gate import evaluate_projection_contract

    projection, snapshot, _ = _task42_projection(case)
    contract = {
        "contract_id": "offline-visible-data", "source_ref": "offline:v4",
        "result_kind": "patch_context", "expected_status": "data", "maximum_visible_tokens": 50000,
        "required_patch_fields": {"sources": ["validate_protocol_0"]},
        "required_public_commands": [], "exact_identifiers": [],
        "acceptable_evidence": case["required_evidence_paths"],
    }
    assert evaluate_projection_contract(projection, snapshot, contract)["passed"] is True
    contract["maximum_visible_tokens"] = 1500
    result = evaluate_projection_contract(projection, snapshot, contract)
    assert result["passed"] is False and "projection:token_budget_or_estimate" in result["errors"]
    assert len(projection["sources"]) == 12


def test_actionability_measures_sources_but_never_grants_normative_claims(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.task_level.evaluators.actionability import _load_projection, _projection_metrics

    projection, snapshot, _ = _task42_projection(case)
    path, snapshot_path = tmp_path / "projection.json", tmp_path / "snapshot.json"
    path.write_text(json.dumps(projection), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    loaded, reason = _load_projection(path, snapshot_path)
    assert loaded is None and "historical_evaluation_projection_token_ceiling_exceeded" in reason
    metrics = _projection_metrics(projection, [SimpleNamespace(expected_files=[case["candidates"][0]["path"]])])
    assert metrics["source_coverage"] == 1.0 and metrics["citation_fidelity"] == 1.0
    assert metrics["requirement_recall"] == metrics["critical_invariant_recall"] == metrics["behavioral_scope_coverage"] == 0


def test_delivery_metrics_and_source_manifest_read_v4(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.task_level._execution_part01 import action_packet_project_doc_metrics, _persist_delivery_prompt_sources, _bounded_direct_projection_errors
    from eval.task_level.evaluators.docatlas_utilization import _used_sources

    projection, _, _ = _task42_projection(case)
    paths = case["required_evidence_paths"]
    metrics = action_packet_project_doc_metrics(SimpleNamespace(expected_project_docs=paths), projection)
    assert metrics["action_packet_project_doc_coverage"] == 1.0
    _persist_delivery_prompt_sources(tmp_path, projection)
    assert len(json.loads((tmp_path / "delivery_prompt_sources.json").read_text())) == 12
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(projection), encoding="utf-8")
    assert _used_sources(tmp_path / "absent.json", paths[0], packet_path) == [paths[0]]
    assert "unsupported_evaluation_requirement:workflow_checks_from_patch_context" in _bounded_direct_projection_errors(projection, [])


def test_real_provider_tool_dispatch_uses_explicit_read_only_format(necessary_evidence, tmp_path, monkeypatch):
    import time
    import docmancer.docs.service as service_module
    from eval.task_level._github_models_part02 import _execute_agent_tool

    service = OfflineRetrieval(necessary_evidence)
    monkeypatch.setattr(service_module, "LibraryDocsService", lambda: service)
    request = SimpleNamespace(workspace=tmp_path, environment={}, condition_id="docatlas_tool_required_once")
    result = _execute_agent_tool(request, {"tool": "get_docs_context", "query": "Inspect protocol implementations"},
                                 sandbox=None, deadline=time.monotonic() + 30)
    packet = json.loads(result)
    assert packet["kind"] == "patch_context" and packet["result"] == "data"
    assert packet["edit_ready"] is False and len(packet["sources"]) == 12
    assert result == json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert "context_format" not in service.calls[0][1]


def test_one_call_loop_cannot_unlock_edit_or_shell_from_patch_data(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.task_level._one_call_agent_loop_core import FakeLoopAdapter, OneCallAgentLoop, validate_docatlas_result

    small = {**case, "candidates": case["candidates"][:1], "required_facts": case["required_facts"][:1],
             "required_evidence_paths": case["required_evidence_paths"][:1]}
    projection, _, _ = _task42_projection(small)
    assert validate_docatlas_result(projection) == []
    adapter = FakeLoopAdapter([
        {"type": "docatlas", "arguments": {"context_format": "patch_context"}},
        {"type": "shell", "command": "must-not-execute"},
    ], docatlas_result=projection)
    result = OneCallAgentLoop(adapter).run(objective=case["question"])
    assert result.docatlas_state == "accepted"
    assert result.reason_code == "retrieval_only_does_not_authorize_edit"
    assert adapter.action_output_limits == []


def test_policy_audit_checks_v4_read_only_retrieval_metadata(tmp_path):
    from eval.task_level.evaluators.policy import audit_trajectory

    event = {"sequence": 1, "tool_name": "get_docs_context", "arguments": {
        "context_format": "patch_context", "question_matches_task_objective": True,
        "retrieval_succeeded": True, "action_packet_result": "data", "action_packet_completeness": "complete",
    }}
    path = tmp_path / "trajectory.json"
    path.write_text(json.dumps([event]), encoding="utf-8")
    assert audit_trajectory("docatlas_tool_required_once", path).clean is True
    event["arguments"]["action_packet_completeness"] = "partial"
    path.write_text(json.dumps([event]), encoding="utf-8")
    assert "required_docatlas_action_packet_invalid" in audit_trajectory("docatlas_tool_required_once", path).violations


def test_provider_composer_keeps_old_oversized_patch_and_embedded_constraints(case, tmp_path):
    from eval.answer_quality_runner import _task42_projection
    from eval.task_level._github_models_part01 import _bounded_runner_messages

    projection, _, _ = _task42_projection(case)
    content = "Observed tool output:\n" + json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert len(content) > 32000
    protected = {"role": "user", "content": content}
    history = [protected] + [{"role": "user", "content": "ordinary history " * 500} for _ in range(8)]
    messages, metrics = _bounded_runner_messages(
        [{"role": "system", "content": "offline"}], history, [], token_limit=7000,
    )
    assert protected in messages
    assert metrics["protected_patch_data_exceeds_input_budget"] is True
    assert metrics["input_token_limit"] == 7000
    assert metrics["clipped_messages"] == []
    retained = json.loads(next(row["content"] for row in messages if row == protected).split("\n", 1)[1])
    assert retained == projection
    for row in retained["sources"]:
        assert hashlib.sha256(row["text"].encode()).hexdigest() == row["content_sha256"]
    # A patch embedded alongside explicit instructions protects that entire message.
    base = {"role": "user", "content": "Explicit target: lib/example.py; do not change policy.\n" + content}
    composed, _ = _bounded_runner_messages([base], [], [], token_limit=7000)
    assert composed == [base]
    from docmancer.docs.application.action_packet import refresh_action_packet_estimate
    packet = {key: value for key, value in projection.items()
              if key not in {"kind", "recommended_next_action", "source_search_status"}}
    refresh_action_packet_estimate(packet)
    packet_message = {"role": "user", "content": json.dumps(packet)}
    composed, _ = _bounded_runner_messages([], [packet_message] + history[1:], [], token_limit=7000)
    assert packet_message in composed
    docs, docs_metrics = _bounded_runner_messages(
        [{"role": "system", "content": "offline"}], history[1:], [], token_limit=7000,
    )
    assert docs_metrics["estimated_input_tokens"] <= 7000
    assert docs_metrics["protected_patch_data_exceeds_input_budget"] is False


def test_mocked_provider_request_keeps_full_v4_after_history_selection(necessary_evidence, tmp_path, monkeypatch):
    import docmancer.docs.service as service_module
    import eval.task_level._github_models_part02 as runner_module
    from eval.task_level.runners.base import AgentRunRequest

    service = OfflineRetrieval(necessary_evidence)
    monkeypatch.setattr(service_module, "LibraryDocsService", lambda: service)
    monkeypatch.setattr(runner_module, "_absolute_deadline_supported", lambda: True)
    calls = []
    expected = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete_json(self, **kwargs):
            messages = deepcopy(kwargs["messages"])
            calls.append(messages)
            if len(calls) > 1:
                packet_message = next(row for row in messages if row["content"].startswith("Observed tool output:\n{"))
                if not expected:
                    expected.append(packet_message)
                assert packet_message == expected[0]
                packet = json.loads(packet_message["content"].split("\n", 1)[1])
                assert packet["result"] == "data" and len(packet["sources"]) == 12
                assert len(packet_message["content"]) > 32000
                assert packet["edit_ready"] is False
            action = ({"tool": "get_docs_context", "query": "Inspect protocol implementations"} if len(calls) == 1
                      else {"tool": "finish", "summary": "offline composer smoke"} if len(calls) == 7
                      else {"tool": "list_files"})
            completion = SimpleNamespace(model="offline", request_id="offline", request_ids={},
                                         raw_usage={"prompt_tokens": 1, "completion_tokens": 1},
                                         request_payload_sha256="offline", estimated_input_tokens=1)
            return action, completion

    monkeypatch.setattr(runner_module, "GitHubModelsClient", MockClient)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "example.py").write_text("value = 1\n", encoding="utf-8")
    request = AgentRunRequest(
        task_id="offline", condition_id="docatlas_tool_optional", workspace=workspace,
        prompt="Inspect protocol implementations", model="offline", timeout_seconds=30, max_turns=7,
        environment={}, mcp_config_path=None, tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "output", allowed_write_paths=("example.py",),
    )
    sandbox = SimpleNamespace(verify=lambda: {"status": "verified"})
    result = runner_module.GitHubModelsRunner("offline-placeholder", sandbox=sandbox).run(request)
    assert result.status == "completed" and len(calls) == 7
    assert expected[0] in calls[-1]  # Survives both the old six-message selection and byte slice.


def test_delivery_report_uses_v4_result_and_completeness(tmp_path):
    from eval.task_level.report import write_report
    from eval.task_level._execution_shared import BOUNDED_DIRECT_EXECUTION_POLICY

    result = {"task_id": "offline", "condition_id": "docatlas_bounded_direct", "repeat": 1,
              "status": "condition_setup_failed", "metrics": {
                  "action_packet_result": "data", "action_packet_completeness": "partial",
              }}
    text = write_report(tmp_path, {}, [result]).read_text()
    assert "packet_result | packet_completeness" in text
    assert "| docatlas_bounded_direct | data | partial |" in text
    assert "packet_status" not in text
    assert "UNSUPPORTED: workflow_checks_from_patch_context" in BOUNDED_DIRECT_EXECUTION_POLICY
    assert "cannot run from v4 patch evidence alone" in BOUNDED_DIRECT_EXECUTION_POLICY


def test_required_once_injected_arguments_reach_current_public_dispatch(necessary_evidence, tmp_path):
    import ast
    import re
    import jsonschema
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, current_docs_surface
    from eval.task_level import _execution_part04
    from eval.task_level.conditions import CONDITIONS, TOOL_REQUIRED_ONCE_INSTRUCTION
    from eval.task_level.runners.codex import _required_once_retrieval_metadata

    # Execute only the actual active injection statement, not a historical pilot run.
    tree = ast.parse(Path(_execution_part04.__file__).read_text(encoding="utf-8"))
    injections = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Attribute)
                  and node.test.attr == "require_docatlas_call_before_edit"]
    assert len(injections) == 1
    question = "Inspect protocol implementations"
    namespace = {"prompt": question, "condition_id": "docatlas_tool_required_once",
                 "CONDITIONS": CONDITIONS, "TOOL_REQUIRED_ONCE_INSTRUCTION": TOOL_REQUIRED_ONCE_INSTRUCTION}
    exec(compile(ast.Module(body=injections, type_ignores=[]), "<offline-prompt-injection>", "exec"), namespace)
    prompt = namespace["prompt"]
    assert prompt.startswith(question + "\n")
    assert "`get_docs_context` exactly once" in prompt
    arguments = {key: json.loads(value) for key, value in re.findall(r'^- (\w+)=("[^"\n]*")$', prompt, re.MULTILINE)}
    assert arguments["question"] == "<original task objective>"
    arguments["question"] = question
    assert arguments["project_path"] == "."

    surface = current_docs_surface(env={})
    tool = next(tool for tool in surface.tools if tool.name == "get_docs_context")
    service = OfflineRetrieval(necessary_evidence)
    result = call_docs_tool_payload("get_docs_context", arguments, service, surface=surface)
    assert len(service.calls) == 1
    jsonschema.validate(arguments, tool.input_schema)
    jsonschema.validate(result, tool.output_schema)
    assert result["kind"] == "patch_context" and result["result"] == "data"
    assert result["completeness"] == "complete" and result["edit_ready"] is False
    assert len(result["sources"]) == 12
    metadata = _required_once_retrieval_metadata(
        {"arguments": arguments, "result": {"structuredContent": result}}, task_objective=question,
    )
    assert metadata["question_matches_task_objective"] is True
    assert metadata["context_format"] == "patch_context"
    assert metadata["retrieval_succeeded"] is True
