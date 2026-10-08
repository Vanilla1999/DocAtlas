"""Offline native v4 consumer tests; no source I/O or indexing side effects."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from docmancer.docs.application.action_packet import refresh_action_packet_estimate
from docmancer.docs.domain.project_doc_ranking import _found_window_retention_producer
from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession
from docmancer.docs.interfaces.host_context import (
    EvidenceDeliveryError, SourceReadController, extract_tool_payload,
    validate_patch_context_payload,
)
from docmancer.mcp.docs_server import call_docs_tool_payload, current_docs_surface, _mcp_tool_result


ADVANCED_SURFACE = current_docs_surface({'DOCATLAS_MCP_ADVANCED_TOOLS': '1'})


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


def prepared_fixture_context(raw, *, retain_found_windows=False, _retention_ack=None):
    """Deliver all prepared fixture windows; no acquisition/delegation or packing."""
    result = deepcopy(raw)
    if retain_found_windows:
        assert result == raw  # Keep text, hashes, spans and explicit obligations.
        assert _retention_ack is not None
    return result


@pytest.fixture
def patch():
    raw = retrieval()
    class Service:
        @_found_window_retention_producer
        def get_docs_context(self, question, *, retain_found_windows=False, _retention_ack=None, **kwargs):
            assert kwargs['allow_network'] is False
            assert kwargs['prepare_project_docs'] is False
            return prepared_fixture_context(raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
    result = call_docs_tool_payload('get_docs_context', {
        'question': 'Inspect the contract implementations', 'project_path': '/repo',
        'context_format': 'patch_context',
    }, Service(), surface=ADVANCED_SURFACE)
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


@pytest.mark.parametrize('mutation', ['text', 'hash', 'span', 'trust', 'unknown', 'estimate', 'recovery', 'unit_hash', 'unit_id', 'assignment_span', 'unit_kind_rehash'])
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
    elif mutation == 'unit_kind_rehash':
        assignment = next(row for row in broken['assignments'] if row.get('unit_id'))
        source = next(row for row in broken['sources'] if row['stable_id'] == assignment['evidence_id'])
        start, end = assignment['unit_char_start'], assignment['unit_char_end']
        witness = source['text'][start:end]
        assignment['unit_kind'] = 'invented_kind'
        assignment['unit_id'] = 'unit-' + hashlib.sha256(f'invented_kind\0{start}\0{end}\0{witness}'.encode()).hexdigest()[:20]
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
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(self.raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        arguments = {'question': 'Inspect contract implementations', 'project_path': '/repo', 'context_format': 'patch_context'}
        initial = call_docs_tool_payload('get_docs_context', arguments, Service(raw), surface=ADVANCED_SURFACE)
        assert initial['result'] == 'data' and initial['completeness'] == 'partial'
        recovery = call_docs_tool_payload('get_docs_context', arguments, Service(retrieval(12)), surface=ADVANCED_SURFACE)
        session = await GroundedMCPSession.start(OfflineClient(initial), arguments=arguments,
            requested_facts={'known': 'Known binding', 'missing': 'Missing binding'})
        source = initial['sources'][0]
        session.support('known', evidence_id=source['evidence_id'], quote=source['text'].splitlines()[1])
        calls = []
        async def search(**kwargs):
            calls.append(kwargs)
            return recovery
        def verify(*, bindings, context):
            # Host-owned fixture provenance, separate from returned data labels.
            return bindings == {'project_path': '/repo'} and context == recovery
        added = await session.recover(search, verify_bindings=verify)
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


@pytest.mark.parametrize('structured', [[], ['packet'], 'packet', 1, False])
def test_malformed_nonnull_structured_channel_never_falls_back(patch, structured):
    with pytest.raises(EvidenceDeliveryError, match='malformed_structured'):
        extract_tool_payload({'structuredContent': structured,
                              'content': [{'type': 'text', 'text': json.dumps(patch)}]})


@pytest.mark.parametrize('structured', [True, False])
def test_error_tool_result_never_delivers_evidence(patch, structured):
    result = {'isError': True, 'content': [{'type': 'text', 'text': json.dumps(patch)}]}
    if structured:
        result['structuredContent'] = patch
    with pytest.raises(EvidenceDeliveryError, match='error_tool_result'):
        extract_tool_payload(result)


def test_structured_delivery_rejects_conflicting_and_multiple_evidence_channels(patch):
    other = deepcopy(patch)
    other['sources'][0]['text'] += 'different packet'
    bare_packet = deepcopy(patch)
    bare_packet.pop('kind')
    for alternate in (other, bare_packet, {'status': 'ok', 'kind': 'docs_context', 'sources': []}):
        with pytest.raises(EvidenceDeliveryError, match='conflicting'):
            extract_tool_payload({'structuredContent': patch,
                                  'content': [{'type': 'text', 'text': json.dumps(alternate)}]})
    text = {'type': 'text', 'text': json.dumps(patch)}
    with pytest.raises(EvidenceDeliveryError, match='ambiguous'):
        extract_tool_payload({'structuredContent': patch, 'content': [text, text]})


def test_identical_dual_delivery_allows_only_canonical_equality_and_ignores_prose(patch):
    assert extract_tool_payload({'structuredContent': patch,
        'content': [{'type': 'text', 'text': 'Structured DocAtlas result attached in structuredContent.'}]}) == patch
    assert extract_tool_payload({'structuredContent': patch,
        'content': [{'type': 'text', 'text': json.dumps(patch, sort_keys=True)}]}) == patch
    alternate = deepcopy(patch)
    alternate['estimated_tokens'] = float(alternate['estimated_tokens'])
    with pytest.raises(EvidenceDeliveryError, match='conflicting'):
        extract_tool_payload({'structuredContent': patch,
            'content': [{'type': 'text', 'text': json.dumps(alternate)}]})


def test_visible_requirement_value_must_match_canonical_witness_not_only_hash(patch):
    from docmancer.docs.application.action_packet import validate_action_packet
    original_core = deepcopy(patch)
    original_core.pop('kind')
    refresh_action_packet_estimate(original_core)
    assert validate_action_packet(original_core, evidence_items=retrieval()['context_pack'], project_path='/repo') == []
    broken = deepcopy(patch)
    requirement = next(row for row in broken['requirements'] if row['kind'] == 'code_group')
    requirement['value'] = json.dumps(['definitely_absent_review_symbol'])
    refresh_action_packet_estimate(broken)
    broken_core = deepcopy(broken)
    broken_core.pop('kind')
    refresh_action_packet_estimate(broken_core)
    assert 'assignment witness binding is invalid' in validate_action_packet(
        broken_core, evidence_items=retrieval()['context_pack'], project_path='/repo')
    with pytest.raises(EvidenceDeliveryError, match='canonical visible witness binding'):
        validate_patch_context_payload(broken)


@pytest.mark.parametrize('change', ['source_line_end', 'source_line_start', 'assignment_line_end', 'assignment_char_end'])
def test_source_newline_endpoints_and_assignment_containment_fail_closed(patch, change):
    broken = deepcopy(patch)
    if change.startswith('source'):
        broken['sources'][0][change.removeprefix('source_')] += 100
    else:
        assignment = next(row for row in broken['assignments'] if row.get('unit_id'))
        assignment[change.removeprefix('assignment_')] += 100_000
    refresh_action_packet_estimate(broken)
    with pytest.raises(EvidenceDeliveryError):
        validate_patch_context_payload(broken)


def test_newline_endpoint_convention_handles_trailing_newline_and_unknown_absolute_position():
    from docmancer.docs.application.action_packet import build_action_packet
    from docmancer.docs.application.model_visible_projection import project_patch_context
    for positioned in (True, False):
        row = retrieval()['context_pack'][0]
        text = row['content'] + '\n'
        row.update(content=text, display_text=text, char_end=len(text),
                   display_content_hash=hashlib.sha256(text.encode()).hexdigest())
        if positioned:
            row.update(line_start=17, line_end=17 + text.count('\n'))
        else:
            row.pop('line_start')
            row.pop('line_end')
        packet = build_action_packet(question='Read contract setting', context_pack=[row])
        context, _ = project_patch_context(packet=packet, evidence_items=[row])
        validate_patch_context_payload(context)
        assert context['sources'][0]['text'].endswith('\n')


@pytest.mark.parametrize('kind', ['version', 'module', 'project_scope', 'unknown_version', 'project_identity'])
def test_recovery_rejects_visible_binding_contradictions_and_preserves_partial(patch, kind):
    async def run():
        initial_raw = retrieval()
        initial_raw['required_target_paths'] = ['src/missing.py']
        recovery_raw = retrieval(12)
        class Service:
            def __init__(self, raw):
                self.raw = raw
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(self.raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        request = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        initial = call_docs_tool_payload('get_docs_context', request, Service(initial_raw), surface=ADVANCED_SURFACE)
        recovery = call_docs_tool_payload('get_docs_context', request, Service(recovery_raw), surface=ADVANCED_SURFACE)
        if kind in {'version', 'unknown_version'}:
            request['version'] = '4.0'
            for source in recovery['sources']:
                source['version_binding'] = '99.0' if kind == 'version' else 'exact_version'
        elif kind == 'module':
            request.update(module_path='packages/orders', scope='module')
            for source in recovery['sources']:
                source['scope'] = 'packages/other'
        elif kind == 'project_identity':
            request['project_identity'] = 'offline'
            for requirement in recovery['requirements']:
                if requirement['kind'] == 'project_identity':
                    requirement['value'] = 'different-project'
        else:
            request['scope'] = 'project'
            for source in recovery['sources']:
                source['scope'] = 'packages/other'
        refresh_action_packet_estimate(recovery)
        validate_patch_context_payload(recovery)
        session = await GroundedMCPSession.start(OfflineClient(initial), arguments=request,
            requested_facts={'known': 'Known binding', 'missing': 'Missing binding'})
        source = initial['sources'][0]
        session.support('known', evidence_id=source['evidence_id'], quote=source['text'].splitlines()[1])
        calls, verifications = [], []
        async def search(**kwargs):
            calls.append(kwargs)
            return recovery
        def verify(**kwargs):
            verifications.append(kwargs)
            return True  # Even a permissive host callback cannot override contradictions.
        denied = await session.recover(search, verify_bindings=verify)
        assert denied['status'] == 'stopped'
        assert 'binding' in denied['reason_code'] or 'scope' in denied['reason_code']
        assert not verifications
        assert calls[0]['project_path'] == '/repo'
        for key in ('version', 'module_path', 'scope', 'project_identity'):
            if key in request:
                assert calls[0][key] == request[key]
        assert session.finish()['status'] == 'partial'
        assert list(session.evidence.values()) == initial['sources'] and session.recovery_context is None
    asyncio.run(run())


@pytest.mark.parametrize('verification', [None, False, 1])
def test_unverifiable_recovery_origin_never_becomes_matching_evidence(verification):
    async def run():
        initial_raw = retrieval()
        initial_raw['required_target_paths'] = ['src/missing.py']
        class Service:
            def __init__(self, raw):
                self.raw = raw
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(self.raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        request = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        initial = call_docs_tool_payload('get_docs_context', request, Service(initial_raw), surface=ADVANCED_SURFACE)
        recovery = call_docs_tool_payload('get_docs_context', request, Service(retrieval(12)), surface=ADVANCED_SURFACE)
        session = await GroundedMCPSession.start(OfflineClient(initial), arguments=request,
            requested_facts={'known': 'Known binding', 'missing': 'Missing binding'})
        source = initial['sources'][0]
        session.support('known', evidence_id=source['evidence_id'], quote=source['text'].splitlines()[1])
        async def search(**kwargs):
            return recovery
        verifier = None if verification is None else lambda **kwargs: verification
        denied = await session.recover(search, verify_bindings=verifier)
        assert denied['reason_code'] == 'unverified_recovery_request_bindings'
        assert session.finish()['status'] == 'partial'
        assert list(session.evidence.values()) == initial['sources']
    asyncio.run(run())


def test_recovery_forwards_all_explicit_bindings_but_never_permission_flags(patch):
    async def run():
        initial_raw = retrieval()
        initial_raw['required_target_paths'] = ['src/missing.py']
        class Service:
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(initial_raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        basic = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        context = call_docs_tool_payload('get_docs_context', basic, Service(), surface=ADVANCED_SURFACE)
        bindings = {'project_path': '/repo', 'library': 'sample', 'libraries': ['sample', 'second'],
            'ecosystem': 'python', 'version': '4.0', 'source_type': 'api', 'docs_url': 'https://example.invalid/docs',
            'module': 'orders', 'module_path': 'packages/orders', 'scope': 'module', 'mode': 'mixed',
            'allow_latest_fallback': False, 'project_identity': 'offline', 'module_id': 'orders-id'}
        request = {**basic, **bindings, 'allow_network': True, 'force_refresh': True, 'prepare_project_docs': True}
        session = await GroundedMCPSession.start(OfflineClient(context), arguments=request,
            requested_facts={'missing': 'Missing binding'})
        detached = session.arguments
        detached['scope'] = 'all'
        detached['libraries'].append('inferred')
        calls = []
        async def search(**kwargs):
            calls.append(kwargs)
            return patch
        denied = await session.recover(search)
        assert denied['status'] == 'stopped'
        assert calls == [{**bindings, 'query_terms': tuple(context['recommended_next_action']['query_terms'])}]
        assert session.arguments == request and not session.recovery_context
    asyncio.run(run())


def test_async_host_binding_verifier_cannot_mutate_retained_response_or_request():
    async def run():
        initial_raw = retrieval()
        initial_raw['required_target_paths'] = ['src/missing.py']
        class Service:
            def __init__(self, raw):
                self.raw = raw
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(self.raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        basic = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        initial = call_docs_tool_payload('get_docs_context', basic, Service(initial_raw), surface=ADVANCED_SURFACE)
        recovery = call_docs_tool_payload('get_docs_context', basic, Service(retrieval(12)), surface=ADVANCED_SURFACE)
        expected_recovery = deepcopy(recovery)
        request = {**basic, 'version': '4.0', 'scope': 'project', 'libraries': ['sample']}
        session = await GroundedMCPSession.start(OfflineClient(initial), arguments=request,
            requested_facts={'missing': 'Missing binding'})
        async def search(**kwargs):
            assert kwargs['version'] == '4.0' and kwargs['scope'] == 'project'
            kwargs['libraries'].append('altered-by-search')
            return recovery
        async def verify(*, bindings, context):
            # The offline host fixture independently owns /repo provenance.
            assert bindings == {'project_path': '/repo', 'version': '4.0', 'scope': 'project', 'libraries': ['sample']}
            assert context == expected_recovery
            bindings['scope'] = 'all'
            context['sources'][0]['text'] = 'tampered'
            recovery['sources'][0]['version_binding'] = '99.0'
            refresh_action_packet_estimate(recovery)
            return True
        assert (await session.recover(search, verify_bindings=verify))['status'] == 'context_added'
        assert session.arguments == request
        assert session.recovery_context == expected_recovery
        assert len(session.evidence) == 24
    asyncio.run(run())


def test_patch_failed_recovery_preserves_original_partial_and_never_accepts_unbound_snippets():
    async def run():
        raw = retrieval()
        raw['required_target_paths'] = ['src/missing.py']
        class Service:
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        arguments = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        context = call_docs_tool_payload('get_docs_context', arguments, Service(), surface=ADVANCED_SURFACE)
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
            @_found_window_retention_producer
            def get_docs_context(self, *args, retain_found_windows=False, _retention_ack=None, **kwargs):
                return prepared_fixture_context(raw, retain_found_windows=retain_found_windows, _retention_ack=_retention_ack)
        arguments = {'question': 'Inspect contracts', 'project_path': '/repo', 'context_format': 'patch_context'}
        context = call_docs_tool_payload('get_docs_context', arguments, Service(), surface=ADVANCED_SURFACE)
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
