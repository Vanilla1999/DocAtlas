"""Terminal envelope integrity. Large envelopes are controlled producer fixtures.

These tests exercise real transport/SDK functions, not retrieval authorization.
The finite default and ordinary administrative compaction remain unchanged.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from docmancer.docs.interfaces.mcp.output_contract import (
    DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES, compact_mcp_payload, json_bytes,
)


def projection(kind="docs_context", ending="\r\n", large=True):
    text = "# Guide" + ending + ("Original exact material. 😀" + ending) * (1400 if large else 2)
    text += "Only when the operation expires; not when it is cancelled." + ending
    return {"kind": kind, "status": "ok", "answer_supported": False,
            "answer_available": False, "edit_ready": False, "estimated_tokens": 1,
            "sources": [{"evidence_id": "fixture-1", "path_or_url": "guide.md",
                         "snippet": text, "content_sha256": "fixture-bound-hash",
                         "line_start": 1, "line_end": len(text.splitlines())}]}


@pytest.mark.parametrize("kind", ["docs_context", "docs_answer", "patch_context"])
@pytest.mark.parametrize("status", ["ok", "truncated", "insufficient_evidence"])
def test_large_canonical_envelope_is_whole_failure(kind, status):
    item = projection(kind)
    item["status"] = status
    before = deepcopy(item)
    assert json_bytes(item) > DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES
    result = compact_mcp_payload(item)
    assert result == {"status": "failed", "reason_code": "transport_size_limit",
                      "message": "MCP payload exceeded the transport size limit."}
    assert json_bytes(result) <= DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES
    assert compact_mcp_payload(result) == result
    assert item == before


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
@pytest.mark.parametrize("kind", ["docs_context", "docs_answer", "patch_context"])
def test_admitted_small_envelope_is_not_rewritten(kind, ending):
    item = projection(kind, ending, large=False)
    before = json.dumps(item, ensure_ascii=False)
    result = compact_mcp_payload(item)
    assert result is item
    assert json.dumps(result, ensure_ascii=False) == before


def test_explicit_finite_caller_limit_and_utf8_boundary():
    item = projection()
    size = json_bytes(item)
    assert compact_mcp_payload(item, max_bytes=size) is item
    assert compact_mcp_payload(item, max_bytes=size - 1)["status"] == "failed"
    assert DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES == 32_000


@pytest.mark.parametrize("options", [{"page": 2, "page_size": 1},
                                     {"include_sections": ["status"]}])
def test_pagination_cannot_rewrite_a_finalized_envelope(options):
    assert compact_mcp_payload(projection(), **options)["reason_code"] == "transport_size_limit"


def test_source_fields_cannot_select_an_unlimited_policy():
    item = projection()
    item.update(compact_read=True, max_transport_bytes=None,
                delivery_limits={"max_transport_bytes": None})
    assert compact_mcp_payload(item)["reason_code"] == "transport_size_limit"


def test_impossibly_tiny_limit_does_not_emit_oversized_success_or_error():
    with pytest.raises(ValueError, match="minimal error payload"):
        compact_mcp_payload(projection(), max_bytes=1)


def test_existing_administrative_compaction_remains_available():
    item = {"status": "success", "context_pack": [
        {"path": f"{i}.md", "content": "x" * 40000} for i in range(4)]}
    result = compact_mcp_payload(item, max_bytes=12000, page=1, page_size=2)
    assert json_bytes(result) <= 12000
    assert result["mcp_compaction"]["truncated"] is True
    assert result["mcp_compaction"]["next_page"] == 2
    assert result["context_pack"][0]["content_omitted"] is True


@pytest.mark.parametrize("text_fallback", [False, True])
@pytest.mark.parametrize("large", [False, True])
def test_dispatcher_and_sdk_use_the_same_terminal_contract(text_fallback, large):
    import mcp.types as mcp_types
    from docmancer.mcp.docs_server import call_docs_tool_payload, _mcp_tool_result

    item = projection(large=large)
    before = deepcopy(item)
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    # Explicit producer seam. No production tool registration is changed.
    surface = SimpleNamespace(
        handlers={"fixture": lambda name, args, service: item},
        tools=[SimpleNamespace(name="fixture", input_schema=schema, validation_schema=None)],
    )
    first = call_docs_tool_payload("fixture", {}, object(), surface=surface)
    delivered = _mcp_tool_result(mcp_types, first, text_fallback=text_fallback)
    final = json.loads(delivered.content[0].text) if text_fallback else delivered.structuredContent
    assert item == before
    if large:
        assert delivered.isError is True
        assert final["reason_code"] == "transport_size_limit" and "sources" not in final
    else:
        assert not delivered.isError
        assert final == before
