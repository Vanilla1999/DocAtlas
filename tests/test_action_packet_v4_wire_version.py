"""Current v4 version carriage and documented nullable MCP routing."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

import jsonschema
import pytest

from docmancer.docs.application.action_packet import (
    ACTION_PACKET_OUTPUT_SCHEMA, build_action_packet, refresh_action_packet_estimate,
    serialize_action_packet, validate_action_packet,
)
from docmancer.docs.application.evidence_selection import (
    build_requirements, patch_selection_config, select_evidence,
)
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
)
from docmancer.docs.interfaces.host_context import (
    EvidenceDeliveryError, validate_patch_context_payload,
)
from docmancer.mcp.agent_workflow_contract import runtime_public_tool_dicts
from docmancer.mcp.docs_server import call_docs_tool_payload

pytestmark = pytest.mark.behavioral
TEXT = "Cache configuration remains enabled for version 2.0."


def window(version="2.0"):
    return {
        "path": "docs/cache.md", "source_class": "library_doc",
        "content": TEXT, "snippet": TEXT, "display_text": TEXT,
        "stable_chunk_id": "cache-child", "parent_logical_id": "cache-parent",
        "display_content_hash": hashlib.sha256(TEXT.encode()).hexdigest(),
        "version_binding": "exact_snapshot", "resolved_version": version,
        "char_start": 0, "char_end": len(TEXT), "line_start": 1, "line_end": 1,
        "authority": "supporting",
    }


def packet_for(item):
    return build_action_packet(
        question="reference", context_pack=[item], exact_version="2.0",
        public_requirements=[{"kind": "required_fact", "value": TEXT,
                              "proof_role": "dependency_fact"}],
    )


def test_exact_library_roundtrip_preserves_canonical_assignment_and_window():
    item = window()
    packet = json.loads(serialize_action_packet(packet_for(item)))
    assert packet["completeness"] == "complete" and packet["edit_ready"] is False
    source = packet["sources"][0]
    assert source["resolved_version"] == "2.0"
    assert source["version_binding"] == "exact_snapshot"
    assert source["text"] == TEXT and source["content_sha256"] == item["display_content_hash"]
    for key in ("char_start", "char_end", "line_start", "line_end"):
        assert source[key] == item[key]
    requirements = build_requirements(
        "reference", exact_version="2.0", profile="generic", representation_bounded=False,
        public_requirements=[{"kind": "required_fact", "value": TEXT, "proof_role": "dependency_fact"}],
    )
    decision = select_evidence(
        [{**item, "_packet_authority": "supporting"}], question="reference",
        config=patch_selection_config(), requirements=requirements,
    )
    canonical = [{key: value for key, value in asdict(row).items()
                  if value is not None and value != ()} for row in decision.assignments]
    assert packet["assignments"] == canonical
    assert validate_action_packet(packet, evidence_items=[item], requirements=requirements) == []
    assert validate_action_packet(packet) == []
    projection, snapshot = project_patch_context(packet=packet, evidence_items=[item])
    assert projection["sources"] == packet["sources"]
    assert projection["assignments"] == packet["assignments"]
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    validate_patch_context_payload(json.loads(serialize_action_packet(projection)))


@pytest.mark.parametrize("attack", ["contradictory", "missing", "binding", "text", "qualifiers"])
def test_bound_and_visible_version_witnesses_reject_tampering(attack):
    item = window()
    packet = packet_for(item)
    projection, snapshot = project_patch_context(packet=packet, evidence_items=[item])
    changed = deepcopy(packet)
    if attack == "contradictory":
        changed["sources"][0]["resolved_version"] = "3.0"
    elif attack == "missing":
        del changed["sources"][0]["resolved_version"]
    elif attack == "binding":
        changed["sources"][0]["version_binding"] = "latest"
    elif attack == "text":
        changed["sources"][0]["text"] = TEXT.replace("enabled", "blocked")
        changed["sources"][0]["content_sha256"] = hashlib.sha256(changed["sources"][0]["text"].encode()).hexdigest()
    else:
        changed["assignments"][-1]["qualifiers"] = ["conditional"]
    refresh_action_packet_estimate(changed)
    assert validate_action_packet(changed, evidence_items=[item])
    assert validate_action_packet(changed)
    changed_projection = {**changed, "kind": "patch_context"}
    refresh_action_packet_estimate(changed_projection)
    assert validate_model_visible_projection(changed_projection, snapshot=snapshot)
    # Unit-less version/scope claims remain unverified at the host boundary.
    if attack not in {"contradictory", "missing"}:
        with pytest.raises(EvidenceDeliveryError):
            validate_patch_context_payload(changed_projection)
    else:
        validate_patch_context_payload(changed_projection)
    assert projection["edit_ready"] is False


@pytest.mark.parametrize("actual", [None, "3.0"])
def test_request_never_synthesizes_actual_version_or_exact_assignment(actual):
    item = window(actual)
    packet = packet_for(item)
    assert packet["result"] == "failure"
    assert "exact_version:2.0" in packet["missing"]
    assert not packet.get("assignments")
    assert validate_action_packet(packet, evidence_items=[item]) == []


def test_unversioned_project_packet_keeps_optional_field_abi():
    item = window()
    del item["resolved_version"]
    item.update(source_class="project_doc", doc_scope="project", version_binding="not_applicable")
    packet = build_action_packet(question="reference", context_pack=[item], public_requirements=[TEXT])
    assert packet["completeness"] == "complete"
    assert "resolved_version" not in packet["sources"][0]
    source_schema = ACTION_PACKET_OUTPUT_SCHEMA["properties"]["sources"]["items"]
    assert "resolved_version" not in source_schema["required"]
    assert source_schema["additionalProperties"] is False
    assert validate_action_packet(packet, evidence_items=[item]) == []
    assert validate_action_packet(packet) == []


def test_runtime_public_schema_and_mcp_validation_preserve_null_docs_route():
    from docmancer.mcp.docs_server import current_docs_surface

    class Service:
        def __init__(self):
            self.calls = []

        def get_docs_context(self, question, **kwargs):
            self.calls.append((question, kwargs))
            return {"status": "success", "context_pack": []}

    schema = next(tool["inputSchema"] for tool in runtime_public_tool_dicts()
                  if tool["name"] == "get_docs_context")
    service = Service()
    omitted = {"question": "Patch code before editing"}
    null = {**omitted, "context_format": None}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(null, schema)
    rejected = call_docs_tool_payload("get_docs_context", null, service)
    assert rejected["error"]["reason_code"] == "validation_error" and not service.calls
    advanced = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})
    advanced_schema = next(spec.input_schema for spec in advanced.tools if spec.name == "get_docs_context")
    jsonschema.validate(null, advanced_schema)
    left = call_docs_tool_payload("get_docs_context", omitted, service)
    right = call_docs_tool_payload("get_docs_context", null, service, surface=advanced)
    assert left == right and left["kind"] != "patch_context"
    assert len(service.calls) == 2 and service.calls[0] == service.calls[1]
    for arguments in ({**omitted, "context_format": "docs_answer"},
                      {**omitted, "question": None}):
        for checked_schema, surface in ((schema, None), (advanced_schema, advanced)):
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(arguments, checked_schema)
            result = call_docs_tool_payload("get_docs_context", arguments, service, surface=surface)
            assert result["error"]["reason_code"] == "validation_error"
    result = call_docs_tool_payload("get_docs_context", {**null, "allow_edit": True}, service, surface=advanced)
    assert result["error"]["reason_code"] == "validation_error"
    assert len(service.calls) == 2
    for name in ("prepare_docs", "docs_status"):
        other_schema = next(tool["inputSchema"] for tool in runtime_public_tool_dicts()
                            if tool["name"] == name)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"action": None}, other_schema)
        result = call_docs_tool_payload(name, {"action": None}, service)
        assert result["error"]["reason_code"] == "validation_error"
