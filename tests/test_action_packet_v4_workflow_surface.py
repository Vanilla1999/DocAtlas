"""Explicit workflow representation and additive mutation schema contracts."""
from copy import deepcopy
from importlib.resources import files
import re

import jsonschema
import pytest

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import DocsServerConfig, MCP_RESOURCES, build_docs_surface


def test_coding_policy_examples_resources_and_template_explicitly_select_v4():
    contract = public_agent_contract()
    policy = contract['workflow']['first_call']
    assert policy['coding_context_format'] is None
    assert policy['documentation_context_format'] is None
    assert policy['context_format_inferred_from_prose'] is False
    assert policy['skill_read_required'] is False
    assert contract['workflow']['advanced_patch'] == {
        'default_available': False,
        'startup_setting': 'DOCATLAS_MCP_ADVANCED_TOOLS=1',
        'context_format': 'patch_context',
        'patch_evidence_representation_cap': None,
        'authorizes_edit': False,
    }
    examples = {row['id']: row for row in contract['examples']}
    assert 'context_format' not in examples['coding-first-call']['arguments']
    assert 'context_format' not in examples['repository-first-call']['arguments']
    tools = {tool['name']: tool for tool in runtime_public_tool_dicts()}
    assert set(tools) == {'get_docs_context', 'prepare_docs', 'docs_status'}
    for example in contract['examples']:
        jsonschema.validate(example['arguments'], tools[example['tool']]['inputSchema'])
    default = tools['get_docs_context']
    assert 'context_format' not in default['inputSchema']['properties']
    assert default['inputSchema']['additionalProperties'] is False
    assert default['outputSchema']['properties']['kind']['enum'] == ['docs_answer', 'docs_context']
    advanced = next(spec for spec in build_docs_surface(DocsServerConfig(expose_advanced=True)).tools
                    if spec.name == 'get_docs_context')
    for value in (None, 'patch_context'):
        arguments = {**examples['coding-first-call']['arguments'], 'context_format': value}
        jsonschema.validate(arguments, advanced.input_schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(arguments, default['inputSchema'])
    assert advanced.validation_schema == advanced.input_schema
    assert advanced.output_schema['oneOf'][0] == default['outputSchema']
    assert advanced.output_schema['oneOf'][1]['properties']['kind']['const'] == 'patch_context'
    for uri in ('docmancer://agent/quickstart', 'docmancer://workflow/project-docs', 'docmancer://agent/tool-selection'):
        text = next(row['text'] for row in MCP_RESOURCES if row['uri'] == uri)
        assert 'DOCATLAS_MCP_ADVANCED_TOOLS=1' in text
        assert 'default' in text and 'patch' in text
        assert 'explicit' in text and 'startup' in text
        assert 'advertised schema' in text and 'automatically' in text
    template = files('docmancer.templates').joinpath('agent_contract.md').read_text()
    for name in ('patch.md', 'troubleshooting.md'):
        assert f'(docatlas-references/{name})' in template
    patch = files('docmancer.templates').joinpath('references/patch.md').read_text()
    troubleshooting = files('docmancer.templates').joinpath('references/troubleshooting.md').read_text()
    assert 'context_format="patch_context"' in patch
    assert 'DOCATLAS_MCP_ADVANCED_TOOLS=1' in patch
    assert 'Do not change host configuration automatically' in patch
    assert 'actual advertised' in patch
    assert 'no internal evidence representation cap' in patch
    assert 'separate explicit target and authorization' in patch
    assert 'attribution, not source-read capabilities' in troubleshooting
    assert 'never construct one' in troubleshooting
    assert 'consent, network and I/O budgets' in troubleshooting


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
            'storage_path': '/repo/.docatlas/docatlas.db', 'catalog_sha256': 'a' * 64,
            'expected_generation_id': None,
            'documents': [{'path': 'docs/rules.md', 'content_sha256': 'b' * 64, 'catalog_entry_hash': 'sha256:' + 'c' * 64}]}


def test_prepare_mutation_schema_is_additive_nullable_and_strict():
    tools = {tool['name']: tool for tool in runtime_public_tool_dicts()}
    schema = tools['prepare_docs']['inputSchema']
    for value in (None, mutation(), {**mutation(), 'expected_generation_id': 'gen-' + 'd' * 32}):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)
    jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo'}, schema)
    description = schema['properties']['mutation']['description']
    assert re.search(r'\bomitted/null\b[^.;]*\bno writes\b', description, re.I)
    assert 'Confirmed lexical member upserts only' in description
    assert 'No deletion/vector/artifact writes' in description
    guide = files('docmancer.templates').joinpath('references/prepare.md').read_text()
    assert 'without an explicit mutation contract is read-only' in guide
    assert 'explicit target and separate host authorization' in guide
    assert 'do not synthesize consent, broaden scope or redirect storage' in guide
    unknown_document = mutation()
    unknown_document['documents'][0]['allow_delete'] = True
    for arguments in (
        {'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': unknown_document},
        {'action': 'clear_index', 'scope': 'project-local', 'project_path': '/repo', 'mutation': mutation()},
        {'action': 'clear_index', 'scope': 'project-local', 'project_path': '/repo', 'mutation': None},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(arguments, schema)


@pytest.mark.parametrize('field,value', [
    ('operation', 'delete'), ('confirm', False), ('confirm', 1), ('storage_path', ''),
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


@pytest.mark.parametrize('member_hash', ['c' * 64, 'sha256:' + 'C' * 64, 'sha256:' + 'c' * 63, 'sha256:' + 'c' * 65, 'sha256:' + 'c' * 64 + '\n'])
def test_prepare_mutation_schema_requires_prefixed_exact_member_hash(member_hash):
    schema = next(tool['inputSchema'] for tool in runtime_public_tool_dicts() if tool['name'] == 'prepare_docs')
    value = mutation()
    value['documents'][0]['catalog_entry_hash'] = member_hash
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)


@pytest.mark.parametrize('generation', ['', 'generation-1', 'd' * 32, 'gen-' + 'D' * 32, 'gen-' + 'd' * 31, 'gen-' + 'd' * 33, 'gen-' + 'd' * 32 + '\n', False])
def test_prepare_mutation_schema_requires_null_or_exact_generation_id(generation):
    schema = next(tool['inputSchema'] for tool in runtime_public_tool_dicts() if tool['name'] == 'prepare_docs')
    value = {**mutation(), 'expected_generation_id': generation}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value}, schema)


@pytest.mark.parametrize('extra', ['unexpected', 'with_vectors', 'changed_paths', 'deleted_paths', 'renamed_paths', 'plan_digest', 'dry_run', 'async', 'confirm', 'library'])
def test_prepare_sync_schema_rejects_all_extra_top_level_fields(extra):
    schema = next(tool['inputSchema'] for tool in runtime_public_tool_dicts() if tool['name'] == 'prepare_docs')
    for value in (None, mutation()):
        arguments = {'action': 'sync_project_docs', 'project_path': '/repo', 'mutation': value, extra: False}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(arguments, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'action': 'sync_project_docs', 'project_path': '/repo', extra: False}, schema)


def test_prepare_storage_schema_leaves_platform_and_exact_existing_store_to_runtime():
    tools = {tool['name']: tool for tool in runtime_public_tool_dicts()}
    schema = tools['prepare_docs']['inputSchema']
    value = {**mutation(), 'storage_path': r'C:\repo\.docatlas\docatlas.db'}
    jsonschema.validate({'action': 'sync_project_docs', 'project_path': r'C:\repo', 'mutation': value}, schema)
    storage = schema['properties']['mutation']['properties']['storage_path']
    assert 'pattern' not in storage
    description = schema['properties']['mutation']['description']
    assert re.search(r'\bnull generation\b[^.]*\bonly\b[^.]*\babsent[- ]store\b', description, re.I)
    assert 'POSIX no-follow reads' in description
    assert re.search(r'\b(?:unsupported platforms|reads or) fail closed\b', description)
    assert 'Exact absolute host-selected private DB outside project' in storage['description']
    assert re.search(
        r'(?:Caller/project configuration cannot redirect it|no caller/project redirects)',
        storage['description'],
    )
    guide = files('docmancer.templates').joinpath('references/prepare.md').read_text()
    # Relocated security handoff is required, even while the skill fix is pending.
    guide = ' '.join(guide.split())
    for retained in (
        'exact host-selected private SQLite store outside the project',
        'project configuration and caller paths cannot redirect it',
        'explicit null generation initializes only an absent store',
        'unexpected existing databases are refused',
        'lexical upserts only: no deletion, vector or artifact writes',
        'POSIX descriptor-relative no-follow checks',
        'unsupported platforms fail closed',
        'trusted OS isolation and the current UID',
        'not protection against a hostile process running as that same UID',
    ):
        assert retained in guide, retained
