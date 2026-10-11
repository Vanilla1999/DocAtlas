"""Explicit workflow representation and additive mutation schema contracts."""
from copy import deepcopy
from importlib.resources import files
import re

import jsonschema
import pytest

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import DocsServerConfig, MCP_RESOURCES, build_docs_surface






def mutation():
    return {'operation': 'sync_project_docs', 'confirm': True,
            'storage_path': '/repo/.docatlas/docatlas.db', 'catalog_sha256': 'a' * 64,
            'expected_generation_id': None,
            'documents': [{'path': 'docs/rules.md', 'content_sha256': 'b' * 64, 'catalog_entry_hash': 'sha256:' + 'c' * 64}]}












