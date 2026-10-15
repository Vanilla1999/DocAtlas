"""Delivered literal guidance with unchanged bounded MCP protocol surfaces."""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from docmancer.docs.domain.content_trust import annotate_context_pack, source_trust_dimensions
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import ProjectDocsResult
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
from tests.docs._scope_guidance_contract import (
    assert_public_context_guidance, assert_public_lifecycle_guidance,
)
from tests.docs.test_pr211_catalog_equivalence import (
    BASELINE_PATH, BASELINE_SHA256, _normalized_schema,
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



















