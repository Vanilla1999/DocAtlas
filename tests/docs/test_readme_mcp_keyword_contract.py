"""Validate documented MCP keyword arguments against the runtime surface."""
import ast
from pathlib import Path
import re

from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface


def test_readme_get_docs_context_uses_only_public_keyword_names():
    text = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    surface = build_docs_surface(DocsServerConfig())
    spec = next(s for s in surface.tools if s.name == "get_docs_context")
    allowed = set(spec.input_schema["properties"])
    examples = re.findall(r"`(get_docs_context\([^`\n]*\))`", text)
    assert examples, "No inline examples were checked"
    for code in examples:
        node = ast.parse(code, mode="eval").body
        assert isinstance(node, ast.Call)
        supplied = {k.arg for k in node.keywords if k.arg is not None}
        assert supplied <= allowed, f"Unsupported fields {supplied - allowed}: {code}"
