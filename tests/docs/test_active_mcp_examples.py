"""Maintained examples must use the actual public MCP keyword contract."""
import ast
from pathlib import Path
import re

import pytest
from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface

ROOT = Path(__file__).resolve().parents[2]
FILES = ('README.md', 'SKILL.md', 'docs/project-docs-demo.md', 'docs/project-docs-mcp-workflow.md')


@pytest.mark.parametrize('path', FILES)
def test_active_get_docs_context_keywords_match_runtime(path):
    spec = next(s for s in build_docs_surface(DocsServerConfig()).tools if s.name == 'get_docs_context')
    allowed = set(spec.input_schema['properties'])
    matches = list(re.finditer(r'get_docs_context\(([^()\n]*)\)', (ROOT / path).read_text()))
    assert matches, f'No examples checked in {path}'
    for match in matches:
        try:
            call = ast.parse(match.group(), mode='eval').body
        except SyntaxError:
            pytest.fail(f'{path}: example is not a valid call: {match.group()}')
        supplied = {arg.arg for arg in call.keywords if arg.arg is not None}
        assert supplied <= allowed, f'{path}: invalid fields {supplied - allowed}: {match.group()}'


def test_module_examples_keep_explicit_module_scope():
    text = (ROOT / 'docs/project-docs-mcp-workflow.md').read_text()
    calls = [m.group() for m in re.finditer(r'get_docs_context\(([^()\n]*)\)', text) if 'module_path=' in m.group()]
    assert calls
    for call in calls:
        assert 'scope="module"' in call


def test_multiline_module_example_also_uses_the_public_schema():
    spec = next(s for s in build_docs_surface(DocsServerConfig()).tools if s.name == 'get_docs_context')
    text = (ROOT / 'docs/project-docs-mcp-workflow.md').read_text()
    examples = re.findall(r'get_docs_context\(\n[^)]*\)', text)
    assert examples, 'Multiline documentation calls were not checked'
    for example in examples:
        call = ast.parse(example, mode='eval').body
        supplied = {arg.arg for arg in call.keywords if arg.arg is not None}
        assert supplied <= set(spec.input_schema['properties']), example
