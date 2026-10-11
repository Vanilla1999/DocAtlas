"""Dynamic resource examples are literal, public-schema guidance, not actions."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import re

import jsonschema
import pytest

from docmancer.mcp.agent_workflow_contract import public_agent_contract
from docmancer.mcp.docs_server import (
    DocsServerConfig,
    MCP_RESOURCES,
    MCP_RESOURCE_TEMPLATES,
    build_docs_surface,
    read_docs_resource,
)


ORIGINAL = "Original вопрос: Alpha != Beta, exact version 1.2?"


def _example_arguments(text):
    examples = re.findall(r"`(get_docs_context\([^\n]*\))`", text)
    assert len(examples) == 1
    expression = ast.parse(examples[0], mode="eval").body
    assert isinstance(expression, ast.Call)
    assert isinstance(expression.func, ast.Name)
    assert expression.func.id == "get_docs_context"
    assert not expression.args
    arguments = {}
    for keyword in expression.keywords:
        assert keyword.arg is not None and keyword.arg not in arguments
        assert isinstance(keyword.value, ast.Constant)
        if keyword.arg == "question":
            assert keyword.value.value is Ellipsis
            arguments[keyword.arg] = ORIGINAL
        else:
            assert isinstance(keyword.value.value, str)
            arguments[keyword.arg] = keyword.value.value
    assert arguments["question"] == ORIGINAL
    return arguments











