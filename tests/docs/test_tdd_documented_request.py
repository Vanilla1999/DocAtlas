"""Validate a complete, user-readable MCP example against the real ToolSpec."""
import json
from pathlib import Path
import re

import jsonschema

from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface


def test_complete_quickstart_request_matches_runtime_schema():
    path = Path(__file__).resolve().parents[2] / "docs/mcp-quickstart-example.md"
    assert path.is_file(), "A complete machine-readable quickstart example is missing"
    blocks = re.findall(r"```json\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 1, "Keep exactly one executable request example"
    request = json.loads(blocks[0])
    assert set(request) == {"tool", "arguments"}
    assert request["tool"] == "get_docs_context"
    spec = next(s for s in build_docs_surface(DocsServerConfig()).tools if s.name == request["tool"])
    args = request["arguments"]
    jsonschema.validate(args, spec.input_schema)
    assert set(args) <= set(spec.input_schema["properties"])
    assert args["question"].strip() and args["project_path"] == "."
    assert args["scope"] == "all"
