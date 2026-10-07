"""Offline native v4 consumer tests; no source I/O or indexing side effects."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from docmancer.docs.application.action_packet import refresh_action_packet_estimate
from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession
from docmancer.docs.interfaces.host_context import (
    EvidenceDeliveryError, SourceReadController, extract_tool_payload,
    validate_patch_context_payload,
)
from docmancer.mcp.docs_server import call_docs_tool_payload, _mcp_tool_result


class OfflineClient:
    def __init__(self, context, *, text=False):
        self.context = context
        self.text = text
        self.calls = []
        self.reads = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        import mcp.types as types
        return _mcp_tool_result(types, self.context, text_fallback=self.text)

    async def read_resource(self, uri):
        self.reads.append(uri)
        raise AssertionError('no v4 source capability was issued')


def retrieval(start=0):
    rows, requirements = [], []
    # Every independent implementation is explicitly required, not filler.
    for index in range(start, start + 12):
        name = f'validate_contract_{index}'
        lines = [f'def {name}(record):']
        for field in range(40):
            lines += [f'    if record["binding_{index}_{field}"] != "contract-{index}-field-{field}":',
                      f'        raise ValueError("contract {index}: invalid binding {field}")']
        lines += [f'    return record["binding_{index}_39"]']
        text = '```python\n' + '\n'.join(lines) + '\n```'
        rows.append({
            'path': f'docs/contract_{index}.md', 'source_class': 'project_doc',
            'doc_scope': 'project', 'authority': 'canonical', 'project_identity': 'offline',
            'heading_path': f'Contract {index}', 'content': text, 'display_text': text,
            'stable_chunk_id': f'contract-child-{index}', 'parent_logical_id': f'contract-parent-{index}',
            'char_start': 0, 'char_end': len(text), 'line_start': 1,
            'line_end': len(text.splitlines()), 'version': '4.0',
            'display_content_hash': hashlib.sha256(text.encode()).hexdigest(),
        })
        requirements.append({'kind': 'code_group', 'value': json.dumps([name]),
                             'public_provenance': 'public_task_contract', 'proof_role': 'generic_fact'})
    return {'status': 'success', 'context_pack': rows, 'public_requirements': requirements,
            'required_evidence_paths': [row['path'] for row in rows], 'project_identity': 'offline'}


@pytest.fixture
def patch():
    raw = retrieval()
    class Service:
        def get_docs_context(self, question, **kwargs):
            assert kwargs['allow_network'] is False
            assert kwargs['prepare_project_docs'] is False
            return deepcopy(raw)
    result = call_docs_tool_payload('get_docs_context', {
        'question': 'Inspect the contract implementations', 'project_path': '/repo',
        'context_format': 'patch_context',
    }, Service())
    assert result['kind'] == 'patch_context' and result['result'] == 'data'
    assert len(json.dumps(result).encode()) > 32_000
    assert result['estimated_tokens'] > 2_000
    assert {source['text'] for source in result['sources']} == {row['display_text'] for row in raw['context_pack']}
    return result


@pytest.mark.parametrize('text', [False, True])
def test_native_session_retains_all_large_evidence_and_late_citation(patch, text):
    async def run():
        client = OfflineClient(patch, text=text)
        arguments = {'question': 'Inspect the contract implementations', 'project_path': '/repo',
                     'context_format': 'patch_context'}
        session = await GroundedMCPSession.start(client, arguments=arguments,
            requested_facts={str(i): f'Contract fact {i}' for i in range(12)})
        assert session.context == patch
        assert list(session.evidence.values()) == patch['sources']
        source = patch['sources'][-1]
        quote = source['text'].splitlines()[-2]
        session.support('11', evidence_id=source['evidence_id'], quote=quote)
        known = session.finish()['known'][0]
        assert known['quote'] == quote and known['path_or_url'] == source['path']
        for key in ('content_sha256', 'stable_id', 'char_start', 'char_end', 'line_start', 'line_end'):
            assert known[key] == source[key]
        assert session.finish()['status'] == 'partial'
        assert session.finish()['answer_supported'] is False
        detached = session.evidence
        detached[source['evidence_id']]['text'] = 'tampered'
        assert session.evidence[source['evidence_id']] == source
        detached_context = session.context
        detached_context['sources'].clear()
        assert session.context == patch
        with pytest.raises(ValueError, match='verbatim'):
            session.support('0', evidence_id=source['evidence_id'], quote='invented answer')
        assert client.calls == [('get_docs_context', arguments)] and not client.reads
    asyncio.run(run())


def test_v4_paths_do_not_create_read_capabilities_and_failed_read_keeps_evidence(patch):
    async def run():
        client = OfflineClient(patch)
        session = await GroundedMCPSession.start(client,
            arguments={'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'},
            requested_facts={'missing': 'Additional binding'})
        for uri in (patch['sources'][0]['path'], 'docatlas://source/' + 'a' * 24):
            result = await session.read(uri, missing_fact_id='missing')
            assert result['reason_code'] == 'unknown_or_repeated_source'
        assert not client.reads and len(session.evidence) == 12
    asyncio.run(run())


@pytest.mark.parametrize('mutation', ['text', 'hash', 'span', 'trust', 'unknown', 'estimate', 'recovery', 'unit_hash', 'unit_id', 'assignment_span'])
def test_wire_validation_rejects_tampering_without_original_snapshot(patch, mutation):
    broken = deepcopy(patch)
    source = broken['sources'][0]
    if mutation == 'text':
        source['text'] += ' altered'
    elif mutation == 'hash':
        source['content_sha256'] = '0' * 64
    elif mutation == 'span':
        source['char_end'] += 1
    elif mutation == 'trust':
        source['instruction_trust'] = 'trusted'
    elif mutation == 'unknown':
        broken['allow_network'] = True
    elif mutation == 'recovery':
        broken['recommended_next_action'] = {'tool': 'shell', 'command': 'write'}
    elif mutation in {'unit_hash', 'unit_id', 'assignment_span'}:
        assignment = next(row for row in broken['assignments'] if row.get('unit_id'))
        key = {'unit_hash': 'unit_content_hash', 'unit_id': 'unit_id', 'assignment_span': 'char_end'}[mutation]
        assignment[key] = assignment[key] + 1 if key == 'char_end' else '0' * 64
    else:
        broken['estimated_tokens'] += 1
    if mutation != 'estimate':
        refresh_action_packet_estimate(broken)
    with pytest.raises(EvidenceDeliveryError):
        validate_patch_context_payload(broken)


def test_v4_failure_text_delivery_and_ambiguous_channel_rejection():
    failure = {'kind': 'patch_context', 'schema_version': 4, 'result': 'failure',
               'completeness': 'unavailable', 'edit_ready': False,
               'missing': ['unavailable'], 'estimated_tokens': 1}
    refresh_action_packet_estimate(failure)
    wire = {'content': [{'type': 'text', 'text': json.dumps(failure)}]}
    assert extract_tool_payload(wire) == failure
    validate_patch_context_payload(failure)
    with pytest.raises(EvidenceDeliveryError, match='ambiguous'):
        extract_tool_payload({'content': wire['content'] * 2})
    with pytest.raises(EvidenceDeliveryError, match='unsupported'):
        extract_tool_payload({'structuredContent': failure}, structured_supported=False)
    async def run():
        session = await GroundedMCPSession.start(OfflineClient(failure, text=True),
            arguments={'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'},
            requested_facts={'missing': 'Contract binding'})
        assert session.context == failure and not session.evidence
        assert session.finish()['status'] == 'insufficient'
    asyncio.run(run())


def test_docs_mode_issued_resource_binding_and_replay_guards_are_unchanged():
    uri = 'docatlas://source/' + 'a' * 24
    context = {'kind': 'docs_context', 'sources': [{
        'evidence_id': 'primary', 'path_or_url': 'docs/rules.md', 'project_identity': 'repo',
        'line_start': 1, 'line_end': 1, 'snippet': 'First rule.', 'source_uri': uri,
    }]}
    calls = []
    def read(resource):
        calls.append(resource)
        return {'status': 'complete', 'path': 'docs/rules.md', 'project_identity': 'repo',
                'line_start': 2, 'line_end': 2, 'content_sha256': 'sha256:' + 'b' * 64,
                'snippet': 'Second rule.'}
    controller = SourceReadController(context, requested_facts={'next': 'Second rule'}, read_resource=read)
    assert controller.read(uri, missing_fact_id='next')['status'] == 'complete'
    assert controller.read(uri, missing_fact_id='next')['reason_code'] == 'unknown_or_repeated_source'
    assert calls == [uri]
    wrong = SourceReadController(context, requested_facts={'next': 'Second rule'},
        read_resource=lambda _: {**read(uri), 'path': 'docs/other.md'})
    assert wrong.read(uri, missing_fact_id='next')['reason_code'] == 'source_binding_mismatch'


def test_explicit_patch_request_never_silently_accepts_docs_mode():
    async def run():
        with pytest.raises(ValueError, match='not delivered'):
            await GroundedMCPSession.start(OfflineClient({'kind': 'docs_context', 'status': 'ok', 'sources': []}),
                arguments={'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'},
                requested_facts={'fact': 'Contract rule'})
    asyncio.run(run())


def test_patch_recovery_retains_uncapped_native_evidence_constraints_and_explicit_terms():
    async def run():
        raw = retrieval()
        raw['required_target_paths'] = [f'src/contract_{i}.py' for i in range(12)]
        class Service:
            def __init__(self, raw):
                self.raw = raw
            def get_docs_context(self, *args, **kwargs):
                return deepcopy(self.raw)
        arguments = {'question': 'Inspect contract implementations', 'project_path': '/repo', 'context_format': 'patch_context'}
        initial = call_docs_tool_payload('get_docs_context', arguments, Service(raw))
        assert initial['result'] == 'data' and initial['completeness'] == 'partial'
        recovery = call_docs_tool_payload('get_docs_context', arguments, Service(retrieval(12)))
        session = await GroundedMCPSession.start(OfflineClient(initial), arguments=arguments,
            requested_facts={'known': 'Known binding', 'missing': 'Missing binding'})
        source = initial['sources'][0]
        session.support('known', evidence_id=source['evidence_id'], quote=source['text'].splitlines()[1])
        calls = []
        async def search(**kwargs):
            calls.append(kwargs)
            return recovery
        added = await session.recover(search)
        assert added['status'] == 'context_added' and added['sources'] == recovery['sources']
        assert session.recovery_context == recovery
        assert len(session.evidence) == 24
        assert calls == [{'project_path': '/repo', 'query_terms': tuple(initial['recommended_next_action']['query_terms'])}]
        assert len(calls[0]['query_terms']) == 12
        returned = session.recovery_context
        returned['requirements'].clear()
        assert session.recovery_context == recovery
        assert session.finish()['status'] == 'partial' and not session.finish()['answer_supported']
        assert (await session.recover(search))['status'] == 'stopped' and len(calls) == 1
    asyncio.run(run())


def test_patch_failed_recovery_preserves_original_partial_and_never_accepts_unbound_snippets():
    async def run():
        raw = retrieval()
        raw['required_target_paths'] = ['src/missing.py']
        class Service:
            def get_docs_context(self, *args, **kwargs):
                return deepcopy(raw)
        arguments = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        context = call_docs_tool_payload('get_docs_context', arguments, Service())
        session = await GroundedMCPSession.start(OfflineClient(context), arguments=arguments,
            requested_facts={'known': 'Known binding', 'missing': 'Missing binding'})
        source = context['sources'][0]
        session.support('known', evidence_id=source['evidence_id'], quote=source['text'].splitlines()[1])
        async def unbound(**kwargs):
            return {'sources': [{'path_or_url': 'src/missing.py', 'snippet': 'Unbound assertion.'}]}
        assert (await session.recover(unbound))['status'] == 'stopped'
        assert list(session.evidence.values()) == context['sources']
        assert session.recovery_context is None
        assert session.finish()['status'] == 'partial'
    asyncio.run(run())


def test_valid_patch_recovery_failure_retains_machine_constraints():
    async def run():
        raw = retrieval()
        raw['required_target_paths'] = ['src/missing.py']
        class Service:
            def get_docs_context(self, *args, **kwargs):
                return deepcopy(raw)
        arguments = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        context = call_docs_tool_payload('get_docs_context', arguments, Service())
        session = await GroundedMCPSession.start(OfflineClient(context), arguments=arguments,
            requested_facts={'missing': 'Missing binding'})
        failure = {'kind': 'patch_context', 'schema_version': 4, 'result': 'failure',
                   'completeness': 'unavailable', 'edit_ready': False,
                   'missing': ['host_source_unavailable'], 'estimated_tokens': 1}
        refresh_action_packet_estimate(failure)
        async def search(**kwargs):
            return failure
        result = await session.recover(search)
        assert result['reason_code'] == 'recovery_evidence_unavailable'
        assert session.recovery_context == failure
        assert list(session.evidence.values()) == context['sources']
    asyncio.run(run())
