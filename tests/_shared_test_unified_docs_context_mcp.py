from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any, cast

import jsonschema

from docmancer.docs.interfaces.mcp.context_tools import context_tools, handle_context_tool
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application.model_visible_projection import canonical_projection_bytes, decode_support_envelope
from docmancer.docs.models import DocsChunk, DocsResult, LibraryInfo
from docmancer.docs.interfaces.mcp.project_tools import MCP_COMPACT_OUTPUT_MAX_BYTES
from docmancer.docs.models import UnifiedDocsContextResult
from docmancer.mcp.docs_server import TOOLS, call_docs_tool_payload
