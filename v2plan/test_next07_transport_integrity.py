"""Lossless terminal transport contracts; native tests use actual handler/SDK.

No N10, retrieval tuning or semantic admission changes. Tests labelled unit do
not attest source eligibility. The native round trip uses current source checks.
"""
from copy import deepcopy
import asyncio
import json

import pytest

from docmancer.docs.domain.read_delivery_limits import (
    COMPACT_READ_LIMITS, ReadDeliveryLimits, current_read_delivery_limits,
    use_read_delivery_limits,
)
from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload, json_bytes


def large_output(kind='docs_context', status='ok'):
    return {'kind': kind, 'status': status, 'estimated_tokens': 12345,
        'sources': [{'evidence_id': f'ev-{i}', 'path_or_url': f'{i}.md',
                     'line_start': 1, 'line_end': 90, 'content_sha256': 'bound-hash',
                     'snippet': '# Owner\r\n\r\n' + 'Exact original 😀 material. ' * 160
                         + '\r\nOnly when preview is disabled.\r\n'} for i in range(12)]}


@pytest.mark.parametrize('kind', ['docs_context', 'docs_answer', 'patch_context'])
@pytest.mark.parametrize('status', ['ok', 'truncated', 'insufficient_evidence'])
def test_unit_finite_limit_is_whole_failure_never_shortened_evidence(kind, status):
    payload = large_output(kind, status); before = deepcopy(payload)
    assert json_bytes(payload) > 32000
    result = compact_mcp_payload(payload)
    assert result['status'] == 'failed'
    assert result['reason_code'] == 'transport_size_limit'
    assert not any(key in result for key in ('sources', 'answer', 'answer_supported', 'edit_ready', 'decision_hash'))
    assert json_bytes(result) <= 32000
    assert payload == before
    assert compact_mcp_payload(result) == result


@pytest.mark.parametrize('status', ['ok', 'truncated', 'insufficient_evidence'])
def test_unit_compact_preserves_entire_payload_and_is_idempotent(status):
    payload = large_output(status=status); before = deepcopy(payload)
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        result = compact_mcp_payload(payload, tool='get_docs_context')
        result = compact_mcp_payload(result)
        assert result == before
        assert json.dumps(result, ensure_ascii=False) == json.dumps(before, ensure_ascii=False)
    assert current_read_delivery_limits() is None


@pytest.mark.parametrize('kind', ['docs_answer', 'patch_context', 'other'])
def test_unit_read_policy_does_not_uncap_other_outputs(kind):
    payload = large_output(kind)
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        result = compact_mcp_payload(payload)
    assert json_bytes(result) <= 32000
    assert result != payload


def test_unit_source_fields_cannot_choose_policy():
    payload = large_output()
    payload.update(max_transport_bytes=None, compact_read=True,
                   delivery_limits={'max_tokens': None, 'max_transport_bytes': None})
    for row in payload['sources']:
        row.update(validated=True, transport_policy='unlimited')
    assert current_read_delivery_limits() is None
    assert compact_mcp_payload(payload)['reason_code'] == 'transport_size_limit'


@pytest.mark.parametrize('modifier', [{'page': 2, 'page_size': 1}, {'include_sections': ['status']}])
def test_unit_transport_does_not_reselect_a_projection(modifier):
    payload = large_output()
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert compact_mcp_payload(payload, **modifier) == payload


def test_unit_explicit_finite_limit_overrides_unlimited_caller_policy():
    payload = large_output()
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert compact_mcp_payload(payload, max_bytes=32000)['status'] == 'failed'
        assert compact_mcp_payload(payload, max_bytes=json_bytes(payload)) == payload


def test_unit_policy_can_express_real_finite_transport_limit():
    payload = large_output()
    assert ReadDeliveryLimits().max_transport_bytes == 32000
    assert COMPACT_READ_LIMITS.max_transport_bytes is None
    with use_read_delivery_limits(ReadDeliveryLimits(max_transport_bytes=500)):
        result = compact_mcp_payload(payload)
        assert result['reason_code'] == 'transport_size_limit'
        assert json_bytes(result) <= 500


@pytest.mark.parametrize('bad', [0, -1, True, 1.5, '32000'])
def test_unit_invalid_transport_limit_rejected(bad):
    with pytest.raises(ValueError):
        ReadDeliveryLimits(max_transport_bytes=bad)
    with pytest.raises(ValueError):
        compact_mcp_payload(large_output(), max_bytes=bad)


def test_unit_impossibly_tiny_limit_does_not_return_oversized_error():
    with pytest.raises(ValueError, match='minimal error'):
        compact_mcp_payload(large_output(), max_bytes=1)


def test_unit_byte_boundary_uses_utf8_not_token_estimate():
    payload = {'kind': 'docs_context', 'status': 'ok', 'blob': '😀' * 10000, 'estimated_tokens': 1}
    size = json_bytes(payload)
    assert compact_mcp_payload(payload, max_bytes=size) == payload
    assert compact_mcp_payload(payload, max_bytes=size-1)['status'] == 'failed'


def test_unit_generic_administrative_compaction_unchanged():
    payload = {'status': 'success', 'tool': 'get_project_context', 'context_pack': [
        {'path': f'{i}.md', 'content': 'x' * 40000} for i in range(4)]}
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        result = compact_mcp_payload(payload, max_bytes=12000, page=1, page_size=2)
    assert json_bytes(result) <= 12000
    assert result['mcp_compaction']['truncated'] is True
    assert result['mcp_compaction']['next_page'] == 2
    assert result['context_pack'][0]['content_omitted'] is True


def test_unit_policy_is_restored_after_exception_and_thread_transfer():
    async def scenario():
        with use_read_delivery_limits(COMPACT_READ_LIMITS):
            result = await asyncio.to_thread(compact_mcp_payload, large_output())
            assert result == large_output()
        assert current_read_delivery_limits() is None
        with pytest.raises(RuntimeError):
            with use_read_delivery_limits(COMPACT_READ_LIMITS):
                raise RuntimeError('restore')
    asyncio.run(scenario())
    assert current_read_delivery_limits() is None


def bound_large_packet():
    """Projection/transport unit fixture, not a forged read-eligibility fixture."""
    from docmancer.docs.application._docs_context_payload import _payload
    from docmancer.docs.application.model_visible_projection import _docs_source, _snapshot_entry
    sources, snapshot = [], {}
    for i in range(12):
        text = large_output()['sources'][i]['snippet']
        row = {'path': f'{i}.md', 'title': 'Owner', 'content': text, 'snippet': text}
        source = _docs_source(row, display_snippet=text, max_snippet_chars=None)
        source.update(snippet=text, project_identity='project-A', authority='source_of_truth',
                      scope='project', line_start=1, line_end=len(text.splitlines()))
        sources.append(source)
        snapshot[source['evidence_id']] = _snapshot_entry(row, source)
    return _payload(sources), snapshot


@pytest.mark.parametrize('text_fallback', [False, True])
def test_sdk_double_boundary_preserves_validated_packet(text_fallback):
    import mcp.types as mcp_types
    from docmancer.mcp.docs_server import _mcp_tool_result
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    payload, snapshot = bound_large_packet()
    assert json_bytes(payload) > 32000
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
        first = compact_mcp_payload(payload, tool='get_docs_context')
        result = _mcp_tool_result(mcp_types, first, text_fallback=text_fallback)
        final = json.loads(result.content[0].text) if text_fallback else json.loads(
            result.model_dump_json())['structuredContent']
        assert final == payload
        assert validate_model_visible_projection(final, snapshot=snapshot, max_tokens=800) == []


def test_sdk_lost_policy_fails_explicitly_instead_of_corrupting_citations():
    import mcp.types as mcp_types
    from docmancer.mcp.docs_server import _mcp_tool_result
    payload, _ = bound_large_packet()
    result = _mcp_tool_result(mcp_types, payload, text_fallback=False)
    assert result.isError is True
    assert result.structuredContent['reason_code'] == 'transport_size_limit'
    assert 'sources' not in result.structuredContent


def test_sdk_transport_does_not_certify_tampered_source():
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection, _refresh_estimate
    payload, snapshot = bound_large_packet()
    payload['sources'][0]['snippet'] = 'invented'
    _refresh_estimate(payload)
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        transported = compact_mcp_payload(payload)
        assert validate_model_visible_projection(transported, snapshot=snapshot, max_tokens=800)


@pytest.mark.parametrize('text_fallback', [False, True])
def test_native_large_owner_through_handler_and_sdk(tmp_path, text_fallback):
    import mcp.types as mcp_types
    from docmancer.mcp.docs_server import _mcp_tool_result
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.project_context_quality.capture_public_context import capture_public_call
    from eval.evidence_quality_v2.audit import audit_payload
    from v2plan.next07_grounded_public import installed

    root = (tmp_path / 'corpus').resolve()
    tail = 'This retention behavior applies only while storage is enabled.\n'
    raw = '# Storage\n\n' + ''.join(
        f'Storage retention behavior record {i} documents the original storage rules. '
        + 'Storage retains the original record and its declared restrictions. ' * 5 + '\n\n'
        for i in range(100)) + tail
    assert len(raw.encode()) > 32000
    write_project(root, {'guide.md': raw})
    trace = {}
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        request = {'project_path': str(root), 'scope': 'project', 'question': 'What is storage retention behavior?'}
        with installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
            capture = capture_public_call(service, request)
            payload = capture['public_payload']
            assert payload['status'] == 'ok', payload
            assert json_bytes(payload) > 32000
            assert len(payload['sources']) == 1
            assert payload['sources'][0]['snippet'] == raw
            result = _mcp_tool_result(mcp_types, payload, text_fallback=text_fallback)
            final = json.loads(result.content[0].text) if text_fallback else json.loads(
                result.model_dump_json())['structuredContent']
            assert final == payload
            assert final['sources'][0]['snippet'].endswith(tail)
        assert trace['restored'] and not trace.get('exceptions')
        assert trace.get('handler_validation')
        assert not any(record['errors'] for record in trace['handler_validation'])
        assert not audit_payload(final, trace['final_snapshot'], root, delivery_limits=COMPACT_READ_LIMITS)
