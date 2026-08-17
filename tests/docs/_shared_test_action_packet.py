from __future__ import annotations

import json
import hashlib
import math

import jsonschema
import pytest

from docmancer.cli.commands import _get_template_content
from docmancer.docs.domain.mutation_intent import (
    build_mutation_intent, evaluate_mutation_readiness, resolve_mutation_targets,
)
from docmancer.docs.application.action_packet import (
    ACTION_PACKET_OUTPUT_SCHEMA,
    build_action_packet,
    estimate_action_packet_tokens,
    validate_action_packet,
)
















from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.domain.content_trust import annotate_context_pack
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.models import ProjectContextResult
from docmancer.mcp.docs_server import MCP_RESOURCES, TOOLS, _json_text, _mcp_tool_result, call_docs_tool_payload
