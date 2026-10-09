"""Offline behavioral regressions for the real MCP v4 patch projection path."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from docmancer.docs.application import action_packet
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer,
    project_patch_context,
    project_insufficient,
    validate_model_visible_projection,
)
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.domain.project_doc_ranking import _found_window_retention_producer


class OfflineRetrieval:
    def __init__(self, result):
        self.result = result
        self.calls = []

    @_found_window_retention_producer
    def get_docs_context(self, question, *, retain_found_windows=False, _retention_ack=None, **kwargs):
        # This fixture supplies complete prepared windows, with no acquisition or
        # packing delegation. Acknowledge its deliberate retention behavior only.
        if retain_found_windows:
            kwargs['retain_found_windows'] = True
        self.calls.append((question, kwargs))
        result = deepcopy(self.result)
        if retain_found_windows:
            assert result == self.result
            assert _retention_ack is not None
        return result


def source(text, index=0):
    return {
        "path": f"docs/protocol_{index}.md", "source_class": "project_doc",
        "doc_scope": "project", "authority": "canonical",
        "heading_path": f"Protocol {index}", "project_identity": "offline-project",
        "content": text, "snippet": text, "display_text": text,
        "stable_chunk_id": f"protocol-child-{index}",
        "parent_logical_id": f"protocol-parent-{index}",
        "char_start": 0, "char_end": len(text),
        "line_start": 1, "line_end": len(text.splitlines()),
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "version": "4.0",
    }


@pytest.fixture
def necessary_evidence(tmp_path):
    # Twelve independently required protocol implementations, not padding or
    # interchangeable copies. Every window contains its own validation rules.
    fields = (
        "request_identity", "source_window", "content_digest", "scope_binding",
        "version_binding", "requirement_identity", "proof_role", "assignment_span",
        "destination_identity", "acceptance_condition", "preserved_target", "trust_boundary",
        "retrieval_identity", "module_identity", "parent_identity", "lifecycle_binding",
        "instruction_trust", "evidence_identity", "selection_identity", "request_identity_hash",
    )
    rows, requirements = [], []
    for index in range(12):
        name = f"validate_protocol_{index}"
        code = [f"def {name}(record):"]
        for position, field in enumerate(fields):
            code.append(
                f'    if record["{field}_{index}"] != "protocol-{index}-binding-{position}":'
            )
            code.append(f'        raise ValueError("invalid {field} for protocol {index}")')
        code.append(f'    return record["source_window_{index}"]')
        text = "```python\n" + "\n".join(code) + "\n```"
        rows.append(source(text, index))
        requirements.append({
            "kind": "code_group", "value": json.dumps([name]),
            "public_provenance": "public_task_contract", "proof_role": "generic_fact",
        })
    return {
        "status": "success", "context_pack": rows,
        "public_requirements": requirements, "project_identity": "offline-project",
        "required_evidence_paths": [row["path"] for row in rows],
    }


def build(result):
    return action_packet.build_action_packet(
        question="Inspect protocol implementations", context_pack=result["context_pack"],
        public_requirements=result.get("public_requirements", ()),
        required_evidence_paths=result.get("required_evidence_paths", ()),
        required_target_paths=result.get("required_target_paths", ()),
        project_identity=result.get("project_identity"),
    )


def refresh(packet):
    action_packet.refresh_action_packet_estimate(packet)


def test_imports_are_from_this_worktree(tmp_path):
    root = Path(__file__).resolve().parents[1]
    assert Path(action_packet.__file__).resolve().is_relative_to(root)


def test_real_mcp_preserves_unique_necessary_data_over_2000(necessary_evidence, tmp_path):
    service = OfflineRetrieval(necessary_evidence)
    result = handle_context_tool("get_docs_context", {
        "question": "Inspect protocol implementations", "tokens": 256,
        "context_format": "patch_context",
        "packet_tokens": 128, "allow_network": True,
    }, service)
    assert result["schema_version"] == 4 and result["kind"] == "patch_context"
    assert result["result"] == "data" and result["completeness"] == "complete"
    assert result["estimated_tokens"] > 2000
    assert result["edit_ready"] is False
    assert len(result["sources"]) == 12
    assert {row["text"] for row in result["sources"]} == {
        row["display_text"] for row in necessary_evidence["context_pack"]
    }
    assert len(result["assignments"]) >= 12
    for row in result["sources"]:
        assert row["content_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest()
        assert row["char_end"] == len(row["text"])
        assert row["instruction_trust"] == "untrusted_data"
    assert service.calls[0][1]["allow_network"] is False
    assert service.calls[0][1]["prepare_project_docs"] is False
    assert "context_format" not in service.calls[0][1]
    assert service.calls[0][1]['retain_found_windows'] is True
    expected = deepcopy(result)
    refresh(expected)
    assert result == expected


def test_partial_mcp_keeps_sources_requirements_and_unsliced_search_targets(necessary_evidence, tmp_path):
    target = "lib/" + "必要な対象_" * 70 + ".py"
    necessary_evidence["required_target_paths"] = [target]
    result = handle_context_tool("get_docs_context", {
        "question": "Inspect protocol implementations",
        "context_format": "patch_context",
    }, OfflineRetrieval(necessary_evidence))
    assert result["result"] == "data" and result["completeness"] == "partial"
    assert len(result["sources"]) == 12 and result["missing"]
    assert result["estimated_tokens"] > 2000 and result["edit_ready"] is False
    action = result["recommended_next_action"]
    assert action["query_terms"] == [target]
    assert action["suggested_doc_paths"] == [target]
    assert action["auto_execute"] is False
    assert result["source_search_status"] == "required"


def test_projector_keeps_partial_data_and_exact_contract(necessary_evidence, tmp_path):
    necessary_evidence["public_requirements"][-1] = {
        "kind": "exact_term", "value": "AbsentExplicitConstraint",
        "public_provenance": "public_task_contract",
    }
    packet = build(necessary_evidence)
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=iter(necessary_evidence["context_pack"]),
    )
    assert projection["result"] == "data" and projection["completeness"] == "partial"
    assert projection["sources"] == packet["sources"]
    assert projection["requirements"] == packet["requirements"]
    assert projection["missing"] == packet["missing"]
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    # A caller's old docs cap must not become a hidden patch limit.
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=1) == []


@pytest.mark.parametrize("change", ["hash", "span", "text", "trust"])
def test_projector_revalidates_hash_span_text_and_trust(necessary_evidence, tmp_path, change):
    packet = build(necessary_evidence)
    row = packet["sources"][0]
    if change == "hash":
        row["content_sha256"] = "0" * 64
    elif change == "span":
        row["char_end"] += 1
    elif change == "text":
        row["text"] += "\nforged visible constraint"
        row["content_sha256"] = hashlib.sha256(row["text"].encode()).hexdigest()
    else:
        row["instruction_trust"] = "scoped_agent_policy"
    refresh(packet)
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=necessary_evidence["context_pack"],
    )
    assert projection["result"] == "failure" and "sources" not in projection
    assert projection["edit_ready"] is False and snapshot == {}
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []


@pytest.mark.parametrize("change", ["raw_hash", "raw_span", "visible_span", "requirements"])
def test_final_validation_rejects_snapshot_or_visible_binding_changes(necessary_evidence, tmp_path, change):
    packet = build(necessary_evidence)
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=necessary_evidence["context_pack"],
    )
    if change == "raw_hash":
        snapshot["__action_packet__"]["evidence_items"][0]["display_content_hash"] = "0" * 64
    elif change == "raw_span":
        snapshot["__action_packet__"]["evidence_items"][0]["char_end"] += 1
    elif change == "visible_span":
        projection["sources"][0]["line_end"] += 1
    else:
        projection["requirements"] = [{"requirement_id": "forged", "kind": "exact_term", "value": "forged"}]
    refresh(projection)
    assert validate_model_visible_projection(projection, snapshot=snapshot)


@pytest.mark.parametrize("extra", [
    {"edit_ready": True}, {"checks": {"tests": ["execute shell"]}},
    {"investigation_allowed": True}, {"recommended_next_action": {"auto_execute": True}},
])
def test_final_patch_never_authorizes_or_ignores_unknown_fields(necessary_evidence, tmp_path, extra):
    projection, snapshot = project_patch_context(
        packet=build(necessary_evidence), evidence_items=necessary_evidence["context_pack"],
    )
    projection.update(extra)
    refresh(projection)
    assert validate_model_visible_projection(projection, snapshot=snapshot)


def test_mcp_delivery_block_is_v4_failure_without_sources(necessary_evidence, tmp_path):
    necessary_evidence["requires_confirmation"] = True
    result = handle_context_tool("get_docs_context", {
        "question": "Inspect protocol implementations",
        "context_format": "patch_context",
    }, OfflineRetrieval(necessary_evidence))
    assert result["schema_version"] == 4 and result["result"] == "failure"
    assert result["completeness"] == "unavailable" and result["missing"]
    assert "sources" not in result and result["edit_ready"] is False


def test_documents_remain_bounded_and_non_authorizing(tmp_path):
    # Historical node retained: output-size caps were removed; source binding
    # and non-authority guards remain. Every missing detail must survive.
    row = source("Protocol configuration: set `protocol_mode = strict`.")
    projection, snapshot = project_docs_answer(
        question="Protocol configuration", retrieval={"primary_snippet": row}, max_tokens=800,
    )
    assert projection["kind"] == "docs_answer"
    assert projection["sources"][0]["snippet"] == row["display_text"]
    assert projection["edit_ready"] is False
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=1) == []
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    missing = [f"missing-{i}:" + "detail" * 200 + f":required-tail-{i}" for i in range(8)]
    expected_missing = tuple(missing)
    failure = project_insufficient(
        kind="docs_answer", missing=missing,
        recommended_next_action=None, max_tokens=200,
    )
    assert tuple(failure["missing"]) == expected_missing
    assert tuple(missing) == expected_missing
    assert failure["estimated_tokens"] > 200
    assert failure["status"] == "insufficient_evidence"
    assert failure["answer_supported"] is failure["answer_available"] is failure["edit_ready"] is False
    assert not failure.get("sources")
    assert "recommended_next_action" not in failure
    expected = deepcopy(failure)
    refresh(expected)
    assert failure == expected
    assert validate_model_visible_projection(failure, snapshot={}, max_tokens=200) == []
    # Negatives start with the valid complete payload and change one guard.
    for key in ("answer_supported", "answer_available", "edit_ready"):
        forged = deepcopy(failure)
        forged[key] = True
        refresh(forged)
        assert validate_model_visible_projection(forged, snapshot={}, max_tokens=200)
    forged = deepcopy(projection)
    forged["sources"][0]["content_sha256"] = "0" * 64
    refresh(forged)
    assert validate_model_visible_projection(forged, snapshot=snapshot, max_tokens=1)


def test_public_caller_kind_and_mutation_do_not_change_docs_policy(tmp_path):
    service = OfflineRetrieval({"status": "success", "primary_snippet": source(
        "Protocol configuration: set `protocol_mode = strict`."
    )})
    result = handle_context_tool("get_docs_context", {
        "question": "Protocol configuration", "kind": "patch_context",
        "mutation_intent_contract": {"operation": "delete", "ready": True},
    }, service)
    assert result['kind'] == 'docs_answer'
    assert result["edit_ready"] is False
    assert "mutation_intent_contract" not in service.calls[0][1]
    default = handle_context_tool("get_docs_context", {"question": "Protocol configuration"}, service)
    nullable = handle_context_tool("get_docs_context", {
        "question": "Protocol configuration", "context_format": None,
    }, service)
    assert default == nullable
    before = len(service.calls)
    invalid = handle_context_tool("get_docs_context", {
        "question": "Protocol configuration", "context_format": "docs_answer",
    }, service)
    assert invalid["error"]["reason_code"] == "invalid_context_format"
    assert len(service.calls) == before


def test_docs_context_public_budget_is_unchanged(tmp_path):
    row = source("Protocol configuration: set `protocol_mode = strict`.")
    service = OfflineRetrieval({
        "status": "success", "mode_selected": "project", "primary_snippet": row,
        "context_pack": [row], "project_identity": "offline-project",
    })
    result = handle_context_tool("get_docs_context", {
        "question": "Protocol configuration", "project_path": str(tmp_path),
    }, service)
    assert result['kind'] == 'docs_context'
    assert result["edit_ready"] is False and result["answer_supported"] is False
    import jsonschema
    from docmancer.mcp._docs_server_schema import PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA
    jsonschema.validate(result, PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA)


def test_patch_order_is_deterministic(necessary_evidence, tmp_path):
    first = build(necessary_evidence)
    necessary_evidence["context_pack"].reverse()
    second = build(necessary_evidence)
    assert first == second
    first_projection, _ = project_patch_context(packet=first, evidence_items=necessary_evidence["context_pack"])
    second_projection, _ = project_patch_context(packet=second, evidence_items=necessary_evidence["context_pack"])
    assert first_projection == second_projection


def test_real_dispatch_and_both_terminal_transports_preserve_over_32000_bytes(necessary_evidence, tmp_path):
    import jsonschema
    import mcp.types as mcp_types
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, _mcp_tool_result
    from docmancer.mcp._docs_server_part01 import current_docs_surface
    from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload
    from docmancer.mcp._docs_server_schema import PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA

    service = OfflineRetrieval(necessary_evidence)
    surface = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})
    result = call_docs_tool_payload(
        "get_docs_context", {"question": "Inspect protocol implementations", "context_format": "patch_context"}, service,
        surface=surface,
    )
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert len(canonical.encode("utf-8")) > 32000
    assert result["estimated_tokens"] > 2000 and len(result["sources"]) == 12
    jsonschema.validate(result, PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA)
    tool = next(tool for tool in surface.tools if tool.name == "get_docs_context")
    jsonschema.validate(result, tool.output_schema)
    assert "context_format" in tool.input_schema["properties"]
    assert "context_format=patch_context" in tool.description
    assert compact_mcp_payload(result, max_bytes=1) is result
    structured = _mcp_tool_result(mcp_types, result, text_fallback=False)
    assert structured.structuredContent == result
    assert not structured.isError
    fallback = _mcp_tool_result(mcp_types, result, text_fallback=True)
    assert fallback.content[0].text == canonical
    assert json.loads(fallback.content[0].text) == result
    assert result["estimated_tokens"] == max(1, (len(canonical.encode("utf-8")) + 3) // 4)


def test_terminal_compaction_does_not_exempt_docs_or_forged_patch(tmp_path):
    from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload
    from tests.docs.test_docs_initial_delivery import large_context
    docs = large_context("docs_answer")
    assert compact_mcp_payload(docs) is docs
    assert 'return record["binding_3_99"]' in docs["sources"][-1]["snippet"]
    assert docs["answer_supported"] is docs["answer_available"] is docs["edit_ready"] is False
    forged = {**docs, "kind": "patch_context", "schema_version": 4, "edit_ready": True}
    assert compact_mcp_payload(forged)["reason_code"] == "transport_size_limit"


def test_explicit_mutation_constraints_and_request_plan_are_lossless(necessary_evidence, tmp_path):
    from docmancer.docs.domain.mutation_intent import MutationIntentContract, RequestedTarget
    from docmancer.docs.domain.patch_request_plan import PatchRequestPlan, PatchTarget, PatchClause

    target = "docs/" + "対象_" * 180 + ".md"
    destination = "docs/" + "移動先_" * 150 + ".md"
    acceptance = "Preserve " + ", ".join(f"protocol_{i}.scope_binding_{i}" for i in range(30))
    plan = PatchRequestPlan(
        operation="rename", mutation_targets=(PatchTarget(target, "path", 0, len(target), "mutate"),),
        destination=PatchTarget(destination, "path", 0, len(destination), "mutate", role="destination"),
        acceptance_conditions=(PatchClause("acceptance", acceptance, 0, len(acceptance)),),
        surface_id="explicit_offline_contract",
    )
    contract = MutationIntentContract(
        "rename", "docs", (RequestedTarget(target, "path", 0, len(target)),),
        destination=destination, acceptance_conditions=(acceptance,), request_plan=plan,
    )
    packet = action_packet.build_action_packet(
        question="Inspect protocol implementations", context_pack=necessary_evidence["context_pack"],
        public_requirements=necessary_evidence["public_requirements"], mutation_intent_contract=contract,
    )
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=necessary_evidence["context_pack"],
    )
    assert projection["result"] == "data" and projection["edit_ready"] is False
    assert projection["mutation_intent"] == packet["mutation_intent"]
    mutation = projection["mutation_intent"]
    assert mutation["requested_targets"][0]["value"] == target
    assert mutation["destination"] == destination
    assert mutation["acceptance_conditions"] == [acceptance]
    assert mutation["request_plan"]["mutation_targets"][0]["value"] == target
    assert mutation["request_plan"]["acceptance_conditions"][0]["text"] == acceptance
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []


def test_real_advertised_output_schema_accepts_partial_v4_without_missing_cap(necessary_evidence, tmp_path):
    import jsonschema
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, current_docs_surface

    necessary_evidence["context_pack"] = necessary_evidence["context_pack"][:5]
    surface = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})
    result = call_docs_tool_payload("get_docs_context", {
        "question": "Inspect protocol implementations", "context_format": "patch_context",
    }, OfflineRetrieval(necessary_evidence), surface=surface)
    assert result["result"] == "data" and result["completeness"] == "partial"
    assert len(result["missing"]) > 5 and "status" not in result
    tool = next(tool for tool in surface.tools if tool.name == "get_docs_context")
    jsonschema.validate(result, tool.to_tool_dict()["outputSchema"])
    forged = {**result, "edit_ready": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(forged, tool.output_schema)
    docs = call_docs_tool_payload("get_docs_context", {
        "question": "Protocol configuration",
    }, OfflineRetrieval({"status": "success", "primary_snippet": source(
        "Protocol configuration: set `protocol_mode = strict`."
    )}))
    assert docs['kind'] == 'docs_answer'
    jsonschema.validate(docs, tool.output_schema)


@pytest.mark.parametrize("module_path", [None, "docs"])
def test_catalog_scoped_authority_survives_projector_and_mcp(tmp_path, module_path):
    text = "Delivery evidence retains immutable source identity."
    # The catalog's missing local file makes its authority unverified. Rooted
    # retrieval correctly retains the useful quote as supporting, not canonical.
    (tmp_path / "docatlas.project-docs.yaml").write_text(json.dumps({
        "schema_version": 1, "documents": [{
            "path": "docs/guide.md", "role": "project_architecture", "scope": "project",
            "description": "Delivery data", "authority": "source_of_truth",
            "status": "active", "impact": "track",
        }],
    }), encoding="utf-8")
    row = source(text)
    row.update(path="docs/guide.md", stable_chunk_id="scope-child", parent_logical_id="scope-parent")
    packet = action_packet.build_action_packet(
        question="Delivery evidence", context_pack=[row], project_path=str(tmp_path),
        module_path=module_path, public_requirements=[text],
    )
    assert packet["result"] == "data" and packet["completeness"] == "complete"
    assert packet["sources"][0]["authority"] == "supporting"
    assert action_packet.validate_action_packet(
        packet, evidence_items=[row], project_path=str(tmp_path), module_path=module_path,
    ) == []
    assert action_packet.validate_action_packet(packet, evidence_items=[row])
    projection, snapshot = project_patch_context(
        packet=packet, evidence_items=[row], project_path=str(tmp_path), module_path=module_path,
    )
    assert projection["sources"] == packet["sources"] and projection["result"] == "data"
    assert snapshot["__action_packet__"]["project_path"] == str(tmp_path)
    assert snapshot["__action_packet__"]["module_path"] == module_path
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    result = handle_context_tool("get_docs_context", {
        "question": "Delivery evidence", "context_format": "patch_context",
        "project_path": str(tmp_path), "module_path": module_path,
    }, OfflineRetrieval({"status": "success", "context_pack": [row], "public_requirements": [text]}))
    assert result["result"] == "data" and result["sources"] == packet["sources"]
    assert result["edit_ready"] is False
    tampered = deepcopy(snapshot)
    tampered["__action_packet__"]["project_path"] = None
    assert validate_model_visible_projection(projection, snapshot=tampered)


def test_distinct_indexed_windows_keep_unique_public_ids_and_snapshot_bindings(tmp_path):
    text = "Delivery evidence retains immutable source identity."
    first = source(text)
    second = {**first, "stable_chunk_id": "second-indexed-window", "char_start": 500, "char_end": 500 + len(text)}
    rows = [first, second]
    packet = action_packet.build_action_packet(question="Delivery evidence", context_pack=rows, public_requirements=[text])
    assert packet["result"] == "data" and len(packet["sources"]) == 2
    ids = {row["evidence_id"] for row in packet["sources"]}
    assert len(ids) == 2
    projection, snapshot = project_patch_context(packet=packet, evidence_items=rows)
    assert set(snapshot) - {"__action_packet__"} == ids
    for row in projection["sources"]:
        bound = snapshot[row["evidence_id"]]
        assert bound["source"]["char_start"] == row["char_start"]
        assert bound["projected_source"] == row
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    result = handle_context_tool("get_docs_context", {
        "question": "Delivery evidence", "context_format": "patch_context",
    }, OfflineRetrieval({"status": "success", "context_pack": rows, "public_requirements": [text]}))
    assert result["sources"] == projection["sources"] and result["edit_ready"] is False
