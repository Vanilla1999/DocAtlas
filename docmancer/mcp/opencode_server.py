"""Native OpenCode boundary; exact public retrieval plus bounded readable pages.

The normalizer in OpenCode 2.1.2 does not retain MCP _meta. This path therefore
requires no client-side private ledger: continuation is checked by this server,
and reuses the original public handler's source and scope checks on every read.
"""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
import json
import os
import sys

from .native_delivery import META_KEY, NativeDelivery


async def run(service) -> None:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
    from ._docs_server_part01 import (
        call_docs_tool_payload, current_tools, read_docs_resource, _mcp_tool_result,
    )
    from ._docs_server_shared import MCP_RESOURCES, MCP_RESOURCE_TEMPLATES
    from docmancer.docs.application.section_compression import observe_section_compression
    from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer

    delivery = NativeDelivery()
    server = Server("docatlas-docs")

    @server.list_tools()
    async def list_tools():
        result = []
        for spec in current_tools():
            if spec["name"] == "get_docs_context":
                spec["inputSchema"]["properties"]["continuation"] = {
                    "type": "string", "maxLength": 1024,
                    "description": "Opaque next-page cursor. Repeat the original arguments; only request for a concrete missing fact.",
                }
                spec.pop("outputSchema", None)
                spec["description"] += " Returns bounded original evidence with paths and lines; a partial page does not prove absence."
            result.append(types.Tool(**spec))
        return result

    @server.list_resources()
    async def list_resources():
        return [types.Resource(uri=r["uri"], name=r["name"], description=r["description"],
                               mimeType=r["mimeType"]) for r in MCP_RESOURCES]

    @server.list_resource_templates()
    async def list_templates():
        return [types.ResourceTemplate(uriTemplate=r["uriTemplate"], name=r["name"],
                    description=r["description"], mimeType=r["mimeType"]) for r in MCP_RESOURCE_TEMPLATES]

    @server.read_resource()
    async def read_resource(uri):
        value = await asyncio.to_thread(read_docs_resource, str(uri), service)
        if value is None:
            raise ValueError("unknown_source_reference")
        return value["text"]

    def failure(code):
        # Do not leak arbitrary exception text, paths, source bytes or credentials.
        return types.CallToolResult(isError=True, content=[types.TextContent(type="text",
            text=f"DocAtlas could not deliver evidence: {code}. No answer-completeness claim; retry only after resolving this condition.")])

    def invoke(name, arguments):
        try:
            prepared = delivery.prepare(arguments) if name == "get_docs_context" else None
        except (ValueError, TypeError):
            return failure("invalid_or_expired_continuation")
        request = prepared.arguments if prepared else arguments
        stages = []

        def observed(receipt):
            stages.append({"acquired_occurrences": len(receipt.get("complete_candidates", [])),
                           "admitted_rows": len(receipt.get("pool", [])),
                           "excluded_occurrences": len(receipt.get("excluded", [])),
                           "policy": (receipt.get("selection") or {}).get("mode")})

        trace_enabled = os.environ.get("DOCATLAS_NATIVE_TRACE") == "1"
        observer = experimental_selection_observer(observed) if trace_enabled else nullcontext()
        with observe_section_compression() as section_trace, observer:
            packet = call_docs_tool_payload(name, request, service)
            try:
                rendered = delivery.render(packet, prepared, section_trace=section_trace) if prepared else None
            except (ValueError, TypeError, KeyError) as exc:
                reason = str(exc)
                allowed = {"continuation_source_changed", "continuation_source_unavailable",
                           "native_source_exceeds_page_budget", "native_output_limit", "continuation_out_of_range"}
                return failure(reason if reason in allowed else "native_evidence_validation_failed")
        if rendered is not None:
            text, receipt = rendered
            receipt["retrieval_trace_enabled"] = trace_enabled
            receipt["retrieval_stages"] = stages
            receipt["section_selection"] = [{k: t.get(k) for k in (
                "selection_policy", "candidate_rows", "candidate_sections", "selected_rows", "selected_sections")}
                for t in section_trace]
            # This meta is DIAGNOSTIC only. Visible evidence and continuations
            # work after OpenCode drops it. No full source packet goes to _meta.
            if os.environ.get("DOCATLAS_NATIVE_TRACE") == "1":
                print(json.dumps({META_KEY: receipt}, ensure_ascii=False), file=sys.stderr, flush=True)
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                        _meta={META_KEY: receipt})
        result = _mcp_tool_result(types, packet, text_fallback=True)
        text = "\n".join(x.text for x in result.content if x.type == "text")
        if name == "get_docs_context" and (len(text.encode()) > delivery.max_bytes or len(text.splitlines()) > delivery.max_lines):
            return failure("native_non_document_output_limit")
        return result

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        return await asyncio.to_thread(invoke, name, arguments)

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
