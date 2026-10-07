"""Explicit workflow representation and additive mutation schema contracts."""
from copy import deepcopy
from importlib.resources import files

import jsonschema
import pytest

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import MCP_RESOURCES


def test_coding_policy_examples_resources_and_template_explicitly_select_v4():
    contract = public_agent_contract()
    policy = contract['workflow']['first_call']
    assert policy['coding_context_format'] == 'patch_context'
    assert policy['documentation_context_format'] is None
    assert policy['context_format_inferred_from_prose'] is False
    assert policy['patch_evidence_representation_cap'] is None
    examples = {row['id']: row for row in contract['examples']}
    assert examples['coding-first-call']['arguments']['context_format'] == 'patch_context'
    assert 'context_format' not in examples['repository-first-call']['arguments']
    tools = {tool['name']: tool for tool in runtime_public_tool_dicts()}
    assert set(tools) == {'get_docs_context', 'prepare_docs', 'docs_status'}
    for example in contract['examples']:
        jsonschema.validate(example['arguments'], tools[example['tool']]['inputSchema'])
    assert 'explicitly pass context_format=patch_context' in tools['get_docs_context']['description']
    for uri in ('docmancer://agent/quickstart', 'docmancer://workflow/project-docs', 'docmancer://agent/tool-selection'):
        text = next(row['text'] for row in MCP_RESOURCES if row['uri'] == uri)
        assert 'context_format="patch_context"' in text
        assert 'Omitted/null' in text
    template = files('docmancer.templates').joinpath('agent_contract.md').read_text()
    assert 'context_format="patch_context"' in template
    assert 'attribution, not source-read capabilities' in template
    assert 'no internal representation cap' in template


def test_omitted_null_and_prose_never_change_docs_routing():
    class Service:
        def get_docs_context(self, question, **kwargs):
            return {'status': 'success', 'context_pack': []}
    omitted = handle_context_tool('get_docs_context', {'question': 'Patch code before editing'}, Service())
    null = handle_context_tool('get_docs_context', {'question': 'Patch code before editing', 'context_format': None}, Service())
    assert null == omitted and omitted['kind'] != 'patch_context'
    invalid = handle_context_tool('get_docs_context', {'question': 'Patch code', 'context_format': 'docs_answer'}, Service())
    assert invalid['error']['reason_code'] == 'invalid_context_format'


def mutation():
    return {'operation': 'sync_project_docs', 'confirm': True,
            'storage_path': '/repo/.docatlas/docs.sqlite', 'catalog_sha256': 'a' * 64,
            'expected_generation_id': None,
            'documents': [{'path': 'docs/rules.md', 'content_sha256': 'b' * 64, 'catalog_entry_hash': 'c' * 64}]}


def test_prepare_mutation_schema_is_additive_nullable_and_strict():
    tools = {tool['name']: tool for tool in runtime_public_tool_dicts()}
    schema = tools['prepare_docs']['inputSchema']
    for value in (None, mutation(), {**mutation(), 'expected_generation_id': 'generation-1'}):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)
    jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo'}, schema)
    assert 'omission/null supplies no mutation permission' in schema['properties']['mutation']['description']
    assert 'No deletion, vector or artifact writes' in tools['prepare_docs']['description']
    unknown_document = mutation()
    unknown_document['documents'][0]['allow_delete'] = True
    for arguments in (
        {'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': unknown_document},
        {'action': 'clear_index', 'scope': 'project-local', 'project_path': '/repo', 'mutation': mutation()},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(arguments, schema)


@pytest.mark.parametrize('field,value', [
    ('operation', 'delete'), ('confirm', False), ('confirm', 1), ('storage_path', 'docs.sqlite'),
    ('catalog_sha256', 'A' * 64), ('documents', []), ('unexpected', True),
])
def test_prepare_mutation_schema_rejects_invalid_or_unknown_contract_fields(field, value):
    schema = next(tool['inputSchema'] for tool in runtime_public_tool_dicts() if tool['name'] == 'prepare_docs')
    value = {**mutation(), field: value}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)


@pytest.mark.parametrize('path', ['/outside.md', '../outside.md', 'docs/../outside.md', './docs/a.md', 'docs\\a.md', 'https://source/a'])
def test_prepare_mutation_schema_rejects_nonliteral_member_paths(path):
    schema = next(tool['inputSchema'] for tool in runtime_public_tool_dicts() if tool['name'] == 'prepare_docs')
    value = deepcopy(mutation())
    value['documents'][0]['path'] = path
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)
