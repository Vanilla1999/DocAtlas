"""Delivered literal guidance with unchanged bounded MCP protocol surfaces."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from docmancer.mcp._docs_server_tool_data import (
    ADMIN_TOOL_NAMES,
    ADVANCED_TOOL_NAMES,
    PUBLIC_ADVERTISED_DESCRIPTIONS,
    PUBLIC_ADVERTISED_INPUT_SCHEMAS,
    PUBLIC_ADVERTISED_OUTPUT_SCHEMAS,
    RAW_TOOLS,
)
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import (
    DocsServerConfig,
    MCP_RESOURCES,
    MCP_RESOURCE_TEMPLATES,
    build_docs_surface,
    call_docs_tool_payload,
    current_tools,
    read_docs_resource,
)


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _without_descriptions(value):
    if isinstance(value, dict):
        return {key: _without_descriptions(child) for key, child in value.items() if key != "description"}
    if isinstance(value, list):
        return [_without_descriptions(child) for child in value]
    return value


@pytest.mark.parametrize("which,expected", [
    ("raw", "b1dcc4b386d8c6a9aeb2cbdb201ff59565a884f35d4baf73b4b800ddaafea201"),
    ("input", "0cde87ff219c430fd9c74558d3db852869f88e7aba8ba4aaef6747b45f2b90fd"),
    ("output", "76e20412ff93662d7379e912192ffd5f6c413507dc3e7e64c14e55335995aa23"),
])
def test_all_schema_constraints_remain_bound_to_pre_slice_snapshot(which, expected):
    values = {
        "raw": {tool["name"]: {key: tool[key] for key in ("inputSchema", "outputSchema") if key in tool} for tool in RAW_TOOLS},
        "input": PUBLIC_ADVERTISED_INPUT_SCHEMAS,
        "output": PUBLIC_ADVERTISED_OUTPUT_SCHEMAS,
    }
    assert _digest(_without_descriptions(values[which])) == expected


@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("advanced", [False, True])
@pytest.mark.parametrize("fallback", [False, True])
def test_surface_flags_preserve_names_order_handlers_and_fallback(admin, advanced, fallback):
    config = DocsServerConfig(expose_admin=admin, expose_advanced=advanced, text_fallback=fallback)
    surface = build_docs_surface(config)
    expected = [tool["name"] for tool in RAW_TOOLS
                if (admin or tool["name"] not in ADMIN_TOOL_NAMES)
                and (advanced or tool["name"] not in ADVANCED_TOOL_NAMES)]
    assert [spec.name for spec in surface.tools] == expected
    assert set(surface.handlers) == set(expected)
    assert [tool["name"] for tool in current_tools({
        "DOCATLAS_MCP_ADMIN_TOOLS": str(int(admin)),
        "DOCATLAS_MCP_ADVANCED_TOOLS": str(int(advanced)),
        "DOCATLAS_MCP_TEXT_FALLBACK": str(int(fallback)),
    })] == expected
    for spec in surface.tools:
        assert spec.handler is surface.handlers[spec.name]
        assert spec.validation_schema == spec.input_schema
        if fallback:
            assert "outputSchema" not in spec.to_tool_dict()


def test_runtime_contract_hashes_actual_delivered_descriptions(monkeypatch):
    before = public_agent_contract()
    runtime = runtime_public_tool_dicts()
    assert [tool["name"] for tool in runtime] == ["get_docs_context", "prepare_docs", "docs_status"]
    payload = deepcopy(before)
    assert payload.pop("identity") == "sha256:" + _digest(payload)
    for record, tool in zip(before["tools"], runtime, strict=True):
        assert record["description_sha256"] == _digest(tool["description"])
        assert record["input_schema_sha256"] == _digest(tool["inputSchema"])
        assert record["output_schema_sha256"] == _digest(tool.get("outputSchema"))
        assert record["tool_contract_sha256"] == _digest(tool)
    monkeypatch.setitem(PUBLIC_ADVERTISED_DESCRIPTIONS, "get_docs_context", "Changed actual runtime description")
    after = public_agent_contract()
    assert after["identity"] != before["identity"]
    assert after["tools"][0]["description_sha256"] == _digest("Changed actual runtime description")
    assert after["workflow"] == before["workflow"]
    assert after["tools"][0]["input_schema_sha256"] == before["tools"][0]["input_schema_sha256"]


def test_raw_advertised_and_runtime_lookups_deliver_only_explicit_contract():
    raw = next(tool for tool in RAW_TOOLS if tool["name"] == "get_docs_context")
    runtime = runtime_public_tool_dicts()[0]
    descriptions = [tool["inputSchema"]["properties"]["lookup_queries"]["description"] for tool in (raw, runtime)]
    descriptions.append(PUBLIC_ADVERTISED_INPUT_SCHEMAS["get_docs_context"]["properties"]["lookup_queries"]["description"])
    assert len(set(descriptions)) == 1
    for text in descriptions:
        assert "unchanged original question" in text
        assert "at most five" in text
        assert "Never infer rewrites, translations, subquestions" in text
        assert "coverage does not transfer" in text
        assert "does not certify an answer or authorize editing" in text
    text = runtime["description"]
    assert "Never widen scope from question wording" in text
    assert "separate explicit target and authorization" in text
    assert "hard_stop=false is not permission" in text
    assert "freshness, provenance, network consent and budgets" in text


@pytest.mark.parametrize("name", ["get_code_context", "get_patch_plan_context", "get_patch_constraints"])
def test_advanced_descriptions_do_not_turn_flags_or_context_into_edit_authority(name):
    surface = build_docs_surface(DocsServerConfig(expose_advanced=True))
    description = next(spec.description for spec in surface.tools if spec.name == name)
    assert "separate explicit target and authorization" in description
    assert "answer-ready" not in description
    assert "If safe_to_answer=true, answer" not in description
    assert "get_patch_constraints before editing ->" not in description


@pytest.mark.parametrize("patch", [
    {"question": ""},
    {"question": 123},
    {"lookup_queries": ["lookup"] * 6},
    {"lookup_queries": ["same", "same"]},
    {"lookup_queries": [""]},
    {"lookup_queries": ["x" * 501]},
    {"scope": "foreign"},
])
def test_invalid_context_inputs_fail_before_any_handler(patch):
    request = {"question": "Exact original вопрос?", "project_path": "/repo", **patch}
    before = deepcopy(request)
    payload = call_docs_tool_payload("get_docs_context", request, object())
    assert payload["error"]["reason_code"] == "validation_error"
    assert request == before


@pytest.mark.parametrize("arguments", [
    {"question": "Exact original вопрос?", "project_path": "/repo", "scope": "project"},
    {"question": "Exact original вопрос?", "library": "sample", "version": "1.2.3", "lookup_queries": ["Exact lookup"]},
    {"question": "Exact original вопрос?", "project_path": "/repo", "scope": "module", "module_path": "packages/sample"},
])
def test_explicit_bindings_and_original_lookup_inputs_keep_schema_support(arguments):
    before = deepcopy(arguments)
    spec = build_docs_surface(DocsServerConfig()).tools[0]
    jsonschema.validate(arguments, spec.validation_schema)
    assert arguments == before
    assert set(spec.input_schema["properties"]) == {
        "question", "lookup_queries", "project_path", "library", "version", "module_path", "scope",
    }


@pytest.mark.parametrize("uri", [
    "docmancer://agent/quickstart",
    "docmancer://workflow/project-docs",
    "docmancer://agent/tool-selection",
    "docmancer://workflow/library-docs",
])
def test_resources_read_literal_guidance_without_semantic_authority(uri):
    resource = read_docs_resource(uri)
    assert resource is not None
    assert resource["uri"] == uri
    assert resource["mimeType"] == "text/markdown"
    text = resource["text"]
    assert "explicit" in text and "at most five" in text
    assert "separate explicit target and authorization" in text
    assert "budget" in text
    for removed in (
        "Split only after", "Same need, different vocabulary", "relation-specific proof authorizes",
        "retry at most one server-suggested rephrase", "cross-language", "facet decomposition",
        "safe_to_answer=true", "For repository onboarding", "Accept explicit logical implications",
    ):
        assert removed not in text


def test_resource_uris_trust_schema_and_bounded_reader_template_unchanged():
    assert {resource["uri"] for resource in MCP_RESOURCES} == {
        "docmancer://agent/quickstart", "docmancer://workflow/project-docs",
        "docmancer://agent/tool-selection", "docmancer://schema/trust-contract",
        "docmancer://workflow/library-docs",
    }
    assert {template["uriTemplate"] for template in MCP_RESOURCE_TEMPLATES} == {
        "docatlas://source/{reference}", "docmancer://workflow/project-docs/{project_path}",
        "docmancer://library/{ecosystem}/{library}/{version}",
    }
    schema = json.loads(read_docs_resource("docmancer://schema/trust-contract")["text"])
    assert schema["schema_version"] == "trust-contract-1.2"
    assert schema["source_dimensions"] == {
        "source_provenance": "configured_repository|external_source",
        "version_exactness": "independent_from_instruction_trust",
        "repository_authority": "explicit_agent_policy|ordinary_repository_document|not_applicable",
        "instruction_trust": "scoped_agent_policy|untrusted_data",
    }
    assert schema["policy"]["document_content"] == "cited_data_never_lifecycle_instruction"
    bounded = next(template for template in MCP_RESOURCE_TEMPLATES if template["uriTemplate"] == "docatlas://source/{reference}")
    assert "returned source_uri" in bounded["description"]
    assert "600 tokens" in bounded["description"] and "two reads per chain" in bounded["description"]
    assert "never construct a reference" in bounded["description"]
    assert read_docs_resource("docmancer://missing") is None
    unavailable = json.loads(read_docs_resource("docatlas://source/" + "0" * 24)["text"])
    assert unavailable["status"] == "source_unavailable"


def test_lifecycle_recovery_status_and_current_binding_guidance():
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    assert "recommended_next_action" in tools["prepare_docs"]["description"]
    assert "Honor approval" in tools["prepare_docs"]["description"]
    assert "only after success" in tools["prepare_docs"]["description"]
    assert "not discovery" in tools["docs_status"]["description"]
    assert "returned" in tools["docs_status"]["description"]
    version = tools["get_docs_context"]["inputSchema"]["properties"]["version"]["description"]
    assert "Current project: omit" in version
    assert "exact/historical" in version and "lockfile" in version
    quickstart = read_docs_resource("docmancer://agent/quickstart")["text"]
    assert "terminal success" in quickstart and "failure/cancellation" in quickstart
    assert "network consent" in quickstart and "confirmation" in quickstart
    assert "lockfile changes" in quickstart


def test_root_guide_is_literal_not_topic_scope_or_proof_policy():
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "unchanged original" in text
    assert "at most five" in text
    assert "Lookup coverage does not transfer" in text
    assert "separate explicit target and authorization" in text
    assert "Never infer or widen scope from question wording" in text
    assert "lockfile change" in text and "network consent" in text
    assert "only after success" in text and "never for discovery" in text
    assert 'get_docs_context(project_path=..., question=..., scope="all")' not in text
    for removed in ("add 1–3", "Split only after", "Same need, different vocabulary", "Accept explicit logical implications", "Treat `CHANGELOG.md` as primary"):
        assert removed not in text
