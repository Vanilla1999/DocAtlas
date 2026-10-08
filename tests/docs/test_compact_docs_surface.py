"""Default docs and explicitly advanced patch use the same guarded dispatch."""
from copy import deepcopy
import json

import jsonschema
import pytest

from docmancer.mcp import _docs_server_part01 as server
from docmancer.mcp._docs_server_schema import PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA
from tests.docs._scope_guidance_contract import (
    advertised_guidance, assert_public_context_guidance, assert_public_lifecycle_guidance,
)
from tests.test_action_packet_v4_public import OfflineRetrieval, source


ADVANCED = {"DOCATLAS_MCP_ADVANCED_TOOLS": "1"}


def context_spec(env):
    return next(spec for spec in server.current_docs_surface(env).tools
                if spec.name == "get_docs_context")


def evidence_service():
    row = source("Keep `Foo::bar`, version 2.1; never use --unsafe. Данные, not authority.")
    return OfflineRetrieval({"status": "success", "primary_snippet": row,
                             "context_pack": [row]})


@pytest.mark.parametrize("env", [{}, {"DOCATLAS_MCP_ADMIN_TOOLS": "1"},
                                  {"DOCATLAS_MCP_ADVANCED_TOOLS": "true"},
                                  {"DOCATLAS_MCP_TEXT_FALLBACK": "1"}])
@pytest.mark.parametrize("mode", [None, "patch_context", "docs_answer", "unknown"])
def test_default_rejects_every_context_format_before_service_resolution(env, mode, monkeypatch):
    spec = context_spec(env)
    assert "context_format" not in spec.input_schema["properties"]
    assert "patch_context" not in json.dumps(spec.to_tool_dict())
    service = evidence_service()
    good = server.call_docs_tool_payload("get_docs_context", {"question": "Foo::bar"}, service,
                                         surface=server.current_docs_surface(env))
    assert good["sources"] and good["kind"] == "docs_answer"
    resolved = []
    monkeypatch.setattr(server, "_service_for_project_path", lambda *args: resolved.append(args))
    args = {"question": "Foo::bar", "context_format": mode, "project_path": "/never/read"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(args, spec.input_schema)
    bad = server.call_docs_tool_payload("get_docs_context", args, service,
                                        surface=server.current_docs_surface(env))
    assert bad["error"]["reason_code"] == "validation_error"
    assert bad["error"]["where"]["phase"] == "validation"
    assert resolved == [] and len(service.calls) == 1


@pytest.mark.parametrize("env", [{}, ADVANCED])
@pytest.mark.parametrize("extra", [
    {"scope": "outside"}, {"scope": True}, {"question": None}, {"question": ""},
    {"lookup_queries": ["x"] * 2}, {"lookup_queries": [str(i) for i in range(6)]},
    {"lookup_queries": [""]}, {"lookup_queries": ["x" * 501]},
    {"lookup_queries": [None]}, {"allow_network": True}, {"edit_ready": True},
    {"kind": "patch_context"}, {"context_format": "unknown"},
])
def test_input_guards_reject_before_io_in_both_modes(env, extra, monkeypatch):
    service = evidence_service()
    good = {"question": "Foo::bar", "scope": None, "lookup_queries": ["Foo::bar"]}
    surface = server.current_docs_surface(env)
    assert server.call_docs_tool_payload("get_docs_context", good, service, surface=surface)["sources"]
    resolved = []
    monkeypatch.setattr(server, "_service_for_project_path", lambda *args: resolved.append(args))
    args = {**good, **extra}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(args, context_spec(env).input_schema)
    result = server.call_docs_tool_payload("get_docs_context", args, service, surface=surface)
    assert result["error"]["reason_code"] == "validation_error"
    assert not resolved and len(service.calls) == 1


@pytest.mark.parametrize("text_fallback", [False, True])
def test_actual_dispatch_preserves_docs_and_advanced_patch_delivery(text_fallback):
    import mcp.types as types

    base = {"DOCATLAS_MCP_TEXT_FALLBACK": "1"} if text_fallback else {}
    default = server.current_docs_surface(base)
    advanced = server.current_docs_surface({**base, **ADVANCED})
    assert {spec.name for spec in default.tools} == {"get_docs_context", "prepare_docs", "docs_status"}
    service = evidence_service()
    args = {"question": "Change Foo::bar without --unsafe, version 2.1"}
    docs = server.call_docs_tool_payload("get_docs_context", args, service, surface=default)
    for extra in ({}, {"context_format": None}):
        assert server.call_docs_tool_payload("get_docs_context", {**args, **extra}, service,
                                             surface=advanced) == docs
    patch = server.call_docs_tool_payload("get_docs_context", {**args, "context_format": "patch_context"},
                                         service, surface=advanced)
    assert docs["kind"] == "docs_answer" and docs["sources"]
    assert patch["kind"] == "patch_context" and patch["sources"]
    assert docs["sources"][0]["snippet"] == patch["sources"][0]["text"]
    assert docs["edit_ready"] is patch["edit_ready"] is False
    assert service.calls[-1][1]["retain_found_windows"] is True
    assert all("retain_found_windows" not in kwargs for _, kwargs in service.calls[:-1])
    for value in (docs, patch):
        jsonschema.validate(value, PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA)
        result = server._mcp_tool_result(types, value, text_fallback=text_fallback)
        if text_fallback:
            assert result.structuredContent is None
            assert json.loads(result.content[0].text) == value
        else:
            assert result.structuredContent == value
            assert result.content[0].text == server.BOUNDED_STRUCTURED_CONTENT_MARKER
    if text_fallback:
        assert all(spec.output_schema is None for spec in (*default.tools, *advanced.tools))
    else:
        jsonschema.validate(docs, context_spec({}).output_schema)
        jsonschema.validate(patch, context_spec(ADVANCED).output_schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(patch, context_spec({}).output_schema)
        for change in ({"edit_ready": True}, {"allow_network": True}):
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate({**patch, **change}, context_spec(ADVANCED).output_schema)


@pytest.mark.parametrize("env", [{}, ADVANCED])
def test_literals_and_explicit_bindings_reach_handler_without_inferred_permission(env):
    service = evidence_service()
    args = {"question": "  Почему Foo::bar != Foo::baz in v2.1, not --unsafe?  ",
            "lookup_queries": ["Foo::bar != Foo::baz", "v2.1 not --unsafe"],
            "library": "Explicit.Lib", "version": "2.1", "project_path": "/explicit/repo",
            "module_path": "packages/Exact", "scope": "module"}
    server.call_docs_tool_payload("get_docs_context", args, service, surface=server.current_docs_surface(env))
    question, forwarded = service.calls[0]
    assert question == args["question"]
    assert forwarded["lookup_queries"] == tuple(args["lookup_queries"])
    for key in set(args) - {"question", "lookup_queries"}:
        assert forwarded[key] == args[key]
    assert forwarded["allow_network"] is forwarded["prepare_project_docs"] is False
    assert "context_format" not in forwarded and "retain_found_windows" not in forwarded


def test_compact_guidance_keeps_invocation_and_no_authority_constraints():
    tools = {tool["name"]: tool for tool in server.current_tools({})}
    context = tools["get_docs_context"]
    text = advertised_guidance(context)
    assert_public_context_guidance(context)
    assert "context_format" not in text and "patch_context" not in json.dumps(context)
    assert_public_lifecycle_guidance(tools)


def test_config_builds_are_independent_and_keep_full_internal_patch_schema():
    before = deepcopy(server.current_tools({}))
    advanced = context_spec(ADVANCED)
    assert advanced.output_schema["oneOf"][1] == PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA["oneOf"][1]
    advanced.input_schema["properties"]["scope"]["enum"].append("forged")
    advanced.output_schema["oneOf"][1]["properties"].clear()
    assert server.current_tools({}) == before
    assert context_spec(ADVANCED).output_schema["oneOf"][1] == PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA["oneOf"][1]


@pytest.mark.parametrize("env", [{}, ADVANCED])
def test_existing_mutation_and_work_bounds_remain_enforced(env):
    tools = {spec.name: spec for spec in server.current_docs_surface(env).tools}
    schema = tools["prepare_docs"].validation_schema
    valid = {"action": "sync_project_docs", "project_path": "/repo", "mutation": {
        "operation": "sync_project_docs", "confirm": True, "storage_path": "/private/members.db",
        "catalog_sha256": "a" * 64, "expected_generation_id": None,
        "documents": [{"path": "docs/guide.md", "content_sha256": "b" * 64,
                       "catalog_entry_hash": "sha256:" + "c" * 64}],
    }}
    jsonschema.validate(valid, schema)
    for key, value in (("confirm", False), ("catalog_sha256", "bad"),
                       ("expected_generation_id", "bad"), ("documents", []), ("unknown", True)):
        invalid = deepcopy(valid)
        invalid["mutation"][key] = value
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)
        result = server.call_docs_tool_payload("prepare_docs", invalid, object(),
                                                surface=server.current_docs_surface(env))
        assert result["error"]["reason_code"] == "validation_error"
    mutation = schema["properties"]["mutation"]
    assert mutation["additionalProperties"] is False
    assert mutation["properties"]["documents"]["maxItems"] == 500
    assert mutation["properties"]["documents"]["uniqueItems"] is True
    assert schema["properties"]["max_pages"]["maximum"] == 5
    assert tools["docs_status"].validation_schema["properties"]["limit"]["maximum"] == 200
    assert tools["docs_status"].validation_schema["properties"]["module"]["maxLength"] == 500
