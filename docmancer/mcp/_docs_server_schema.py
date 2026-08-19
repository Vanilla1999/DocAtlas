"""`doc-atlas mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, cast

import jsonschema

from docmancer.core.storage_topology import StorageTopologyResolver
from docmancer.docs.application.action_packet import ACTION_PACKET_OUTPUT_SCHEMA
from docmancer.docs.domain.project_path_validation import validate_project_path
from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload, debug_errors_enabled
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.context_tools import (
    BOUNDED_STRUCTURED_CONTENT_MARKER,
    context_tools,
    handle_context_tool,
)
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool, library_tools
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, prefetch_tools
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools

ToolHandler = Callable[[str, dict[str, Any], LibraryDocsService], dict[str, Any] | None]


@dataclass(frozen=True)
class DocsServerConfig:
    expose_legacy: bool = False
    expose_admin: bool = False
    expose_advanced: bool = False
    text_fallback: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "DocsServerConfig":
        return cls(
            expose_legacy=env.get("DOCMANCER_MCP_LEGACY_TOOLS") == "1",
            expose_admin=env.get("DOCMANCER_MCP_ADMIN_TOOLS") == "1",
            expose_advanced=env.get("DOCMANCER_MCP_ADVANCED_TOOLS") == "1",
            text_fallback=env.get("DOCATLAS_MCP_TEXT_FALLBACK") == "1",
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    output_schema: dict[str, Any] | None = None
    validation_schema: dict[str, Any] | None = None

    def to_tool_dict(self) -> dict[str, Any]:
        result = {"name": self.name, "description": self.description, "inputSchema": copy.deepcopy(self.input_schema)}
        if self.output_schema is not None:
            result["outputSchema"] = copy.deepcopy(self.output_schema)
        return result


@dataclass(frozen=True)
class DocsMcpSurface:
    tools: tuple[ToolSpec, ...]
    handlers: Mapping[str, ToolHandler]


DOCS_TARGET_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "library": {"type": "string", "minLength": 1},
        "ecosystem": {"type": ["string", "null"]},
        "version": {"type": ["string", "null"]},
        "source_type": {"type": ["string", "null"]},
        "docs_url": {"type": ["string", "null"]},
        "docs_url_template": {"type": ["string", "null"]},
        "seed_urls": {"type": ["array", "null"], "items": {"type": "string"}},
        "allowed_domains": {"type": ["array", "null"], "items": {"type": "string"}},
        "path_prefixes": {"type": ["array", "null"], "items": {"type": "string"}},
        "max_pages": {"type": ["integer", "null"], "minimum": 1, "maximum": 500},
        "browser": {"type": ["boolean", "null"]},
        "doc_format": {"type": ["string", "null"]},
        "warnings": {"type": ["array", "null"], "items": {"type": "string"}},
        "source_manifest": {"type": ["object", "null"]},
    },
    "required": ["library"],
    "additionalProperties": False,
}


GET_DOCS_CONTEXT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["tool"],
    "properties": {
        "tool": {"const": "get_docs_context"},
        "delivery_strategy": {"enum": ["bounded_direct"]},
        "action_packet": ACTION_PACKET_OUTPUT_SCHEMA,
        "document_content_policy": {"type": "object"},
        "recommended_next_action": {"type": "object"},
    },
    "additionalProperties": True,
    "allOf": [{
        "if": {
            "required": ["delivery_strategy"],
            "properties": {"delivery_strategy": {"const": "bounded_direct"}},
        },
        "then": {"required": ["action_packet", "document_content_policy"]},
    }],
}


PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status"],
    "properties": {
        # The advertised tool defaults to the canonical bounded projection,
        # but explicitly requested compatibility output keeps the underlying
        # unified-context lifecycle status.  MCP clients validate both shapes
        # against this one output schema before returning the tool result.
        "status": {"enum": [
            "ok", "truncated", "insufficient_evidence", "failed",
            "success", "partial_success", "confirmation_required",
            "not_found", "invalid_request",
        ]},
        "kind": {"enum": ["docs_answer", "patch_context"]},
        "estimated_tokens": {"type": "integer"},
        "reason_code": {"type": "string"},
        "operational_reason_code": {"type": "string"},
        "module_candidates": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["module_path"],
                "properties": {
                    "module_path": {
                        "type": "string",
                        "maxLength": 240,
                    },
                    "module_name": {"type": "string"},
                    "module_type": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "missing": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "recommended_next_action": {"type": "object"},
    },
}

__all__=[n for n in globals() if not n.startswith('__')]
