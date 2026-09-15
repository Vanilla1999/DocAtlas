"""Host compatibility with the actual retrieval-only public projection."""
from copy import deepcopy

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import _refresh_estimate
from eval.task_level.one_call_agent_loop import FakeLoopAdapter, LoopCapabilities, OneCallAgentLoop, validate_docatlas_result
from docmancer.docs.interfaces.host_context import (
    EvidenceDeliveryError, SourceReadController, extract_tool_payload,
)


@pytest.fixture
def context():
    payload, _ = project_docs_context(retrieval={
        "context_pack": [{
            "source_class": "project_doc", "path": "docs/jobs.md",
            "heading_path": "Polling", "content": "Poll the job until its status is terminal.",
            "project_identity": "git:example/project", "authority": "source_of_truth",
            "doc_scope": "project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "retrieval_query_ids": ["query-original"],
            "retrieval_query_matches": {"query-original": {
                "qualified": True, "mode": "and", "query_text": "job polling",
            }},
        }],
        "documentation_query_plan": {
            "query_ids": ["query-original"], "required_query_ids": [],
            "queries": [{"query_id": "query-original", "text": "job polling",
                         "origin": "original", "coverage_required": False}],
        },
    })
    assert payload["kind"] == "docs_context"
    return payload


def test_host_retains_retrieval_only_context_and_can_finish_without_extra_reads(context):
    adapter = FakeLoopAdapter([{"type": "docatlas"}, {"type": "finish"}], docatlas_result=context)
    outcome = OneCallAgentLoop(adapter).run(objective="How do I poll the job?")
    assert outcome.status == "success"
    retained = [b["value"] for b in adapter.model_inputs[-1]["history"]["blocks"]]
    assert context in retained
    assert outcome.counts["action_attempts"] == 0


@pytest.mark.parametrize("field,value", [
    ("answer_supported", True), ("answer_available", True), ("edit_ready", True),
    ("answer_policy", "generate"), ("sources", []),
])
def test_host_rejects_forged_retrieval_only_contract(context, field, value):
    payload = deepcopy(context)
    payload[field] = value
    _refresh_estimate(payload)
    assert validate_docatlas_result(payload)


@pytest.mark.parametrize("action", [{"type": "edit"}, {"type": "shell", "command": "rm docs/jobs.md"}])
def test_context_acceptance_does_not_authorize_edit(context, action):
    adapter = FakeLoopAdapter([{"type": "docatlas"}, action], docatlas_result=context)
    outcome = OneCallAgentLoop(adapter).run(objective="Change polling")
    assert outcome.reason_code == "retrieval_only_does_not_authorize_edit"
    assert outcome.counts["action_attempts"] == 0


@pytest.mark.parametrize('fallback', [False, True])
def test_real_mcp_delivery_preserves_factual_payload_once(context, fallback):
    import mcp.types as types
    from docmancer.mcp.docs_server import _mcp_tool_result
    wire = _mcp_tool_result(types, context, text_fallback=fallback)
    assert extract_tool_payload(wire, structured_supported=not fallback) == context
    if fallback:
        assert wire.structuredContent is None
    else:
        assert context['sources'][0]['snippet'] not in wire.content[0].text


def test_text_only_host_diagnoses_unsupported_channel(context):
    import mcp.types as types
    from docmancer.mcp.docs_server import _mcp_tool_result
    wire = _mcp_tool_result(types, context, text_fallback=False)
    with pytest.raises(EvidenceDeliveryError, match='DOCATLAS_MCP_TEXT_FALLBACK'):
        extract_tool_payload(wire, structured_supported=False)


def controller_fixture(context, callback):
    source = context['sources'][0]
    source.update(source_uri='docatlas://source/' + 'a' * 24, line_end=2)
    return SourceReadController(context, requested_facts={'polling': 'When does polling stop?'}, read_resource=callback)


def test_link_and_false_flags_never_trigger_read(context):
    calls = []
    controller = controller_fixture(context, lambda uri: calls.append(uri))
    assert context['answer_available'] is False
    assert calls == []
    controller.mark_supported('polling')
    assert controller.read(context['sources'][0]['source_uri'], missing_fact_id='polling')['reason_code'] == 'no_concrete_missing_fact'
    assert calls == []


def test_host_only_reads_returned_locators_and_stops_at_two(context):
    calls = []
    source = context['sources'][0]
    def read(uri):
        calls.append(uri)
        line = 2 + len(calls)
        return dict(status='truncated', path=source['path_or_url'],
                    project_identity=source['project_identity'], content_sha256='sha256:' + 'f' * 64,
                    line_start=line, line_end=line, snippet=f'Polling condition {line}.',
                    continuation='docatlas://source/' + str(len(calls)) * 24)
    controller = controller_fixture(context, read)
    assert controller.read('https://example.com/whole-file', missing_fact_id='polling')['status'] == 'stopped'
    assert calls == []
    first = controller.read(source['source_uri'], missing_fact_id='polling')
    assert controller.read(source['source_uri'], missing_fact_id='polling')['status'] == 'stopped'
    second = controller.read(first['continuation'], missing_fact_id='polling')
    assert controller.read(second['continuation'], missing_fact_id='polling')['reason_code'] == 'read_budget_exhausted'
    assert len(calls) == 2
    assert len(controller.results) == 2
    assert controller.extra_tokens <= 1200


def test_new_locator_does_not_make_repeated_text_progress(context):
    source = context['sources'][0]
    def read(uri):
        return dict(status='complete', path=source['path_or_url'],
                    project_identity=source['project_identity'], content_sha256='sha256:' + 'f' * 64,
                    line_start=3, line_end=3, snippet=source['snippet'], continuation=None)
    controller = controller_fixture(context, read)
    result = controller.read(source['source_uri'], missing_fact_id='polling')
    assert result['reason_code'] == 'no_new_source_text'
    assert not controller.results


def test_host_loop_retains_initial_facts_and_requested_continuation(context):
    source = context['sources'][0]
    uri = 'docatlas://source/' + 'a' * 24
    source.update(source_uri=uri, line_end=2)
    _refresh_estimate(context)
    read = dict(status='complete', path=source['path_or_url'],
                project_identity=source['project_identity'], content_sha256='sha256:' + 'f' * 64,
                line_start=3, line_end=3, snippet='Retry after terminal completion.', continuation=None)
    adapter = FakeLoopAdapter([
        {'type': 'docatlas', 'requested_facts': {'retry': 'When may I retry?'}},
        {'type': 'source_read', 'uri': uri, 'missing_fact_id': 'retry'},
        {'type': 'finish'},
    ], docatlas_result=context, source_reads=[read],
        capabilities=LoopCapabilities(source_continuations=True))
    outcome = OneCallAgentLoop(adapter).run(objective='Explain job polling and retries.')
    assert outcome.status == 'success'
    assert outcome.counts['source_read_attempts'] == 1
    blocks = {block['kind']: block['value'] for block in adapter.model_inputs[-1]['history']['blocks']}
    assert blocks['docatlas_result'] == context
    assert blocks['source_reads'] == [read]
    assert blocks['requested_facts'] == {'retry': 'When may I retry?'}


@pytest.mark.parametrize('initial_overlap', [False, True])
def test_distinct_locators_cannot_repeat_source_lines(context, initial_overlap):
    source = context['sources'][0]
    first_uri, second_uri = ('docatlas://source/' + char * 24 for char in 'ab')
    source.update(source_uri=first_uri, line_start=1, line_end=1)
    other = {**source, 'source_uri': second_uri, 'line_start': 3 if initial_overlap else 5,
             'line_end': 3 if initial_overlap else 5, 'snippet': 'Another cited fact.'}
    context['sources'].append(other)
    def read(uri):
        start, end = (2, 4) if uri == first_uri else (6, 7)
        return dict(status='complete', path=source['path_or_url'],
                    project_identity=source['project_identity'], content_sha256='sha256:' + 'f' * 64,
                    line_start=start, line_end=end,
                    snippet='\n'.join(f'Fact at line {line}.' for line in range(start, end + 1)),
                    continuation=None)
    controller = SourceReadController(context, requested_facts={'remaining': 'What remains?'}, read_resource=read)
    result = controller.read(first_uri, missing_fact_id='remaining')
    if initial_overlap:
        assert result['reason_code'] == 'repeated_source_span'
        assert controller.results == []
    else:
        assert result['status'] == 'complete'
        assert controller.read(second_uri, missing_fact_id='remaining')['status'] == 'complete'


def test_distinct_continuation_chains_cannot_overlap(context):
    source = context['sources'][0]
    first_uri, second_uri = ('docatlas://source/' + char * 24 for char in 'ab')
    source.update(source_uri=first_uri, line_start=1, line_end=1)
    # The second seed has no complete range, as permitted for legacy citations.
    context['sources'].append({**source, 'source_uri': second_uri, 'line_start': None, 'line_end': 3})
    def read(uri):
        start = 2 if uri == first_uri else 4
        return dict(status='complete', path=source['path_or_url'],
                    project_identity=source['project_identity'], content_sha256='sha256:' + 'f' * 64,
                    line_start=start, line_end=start + 2, snippet=f'Lines {start} through {start + 2}.',
                    continuation=None)
    controller = SourceReadController(context, requested_facts={'remaining': 'What remains?'}, read_resource=read)
    assert controller.read(first_uri, missing_fact_id='remaining')['status'] == 'complete'
    assert controller.read(second_uri, missing_fact_id='remaining')['reason_code'] == 'repeated_source_span'
    assert len(controller.results) == 1


def _registered_range_context(context):
    value = deepcopy(context)
    source = value['sources'][0]
    source.update(line_start=162, line_end=168)
    uri = 'docatlas://source/' + 'b' * 24
    value['read_next'] = [{
        'source_uri': uri,
        'path': source['path_or_url'],
        'project_identity': source['project_identity'],
        'snapshot_sha256': 'sha256:' + 'f' * 64,
        'line_start': 156,
        'line_end': 172,
        'reason': 'inspect_source_context',
    }]
    _refresh_estimate(value)
    return value, uri


def _registered_range_result(context, *, start=156, end=172, continuation=None):
    source = context['sources'][0]
    return dict(
        status='truncated' if continuation else 'complete',
        path=source['path_or_url'], project_identity=source['project_identity'],
        content_sha256='sha256:' + 'f' * 64,
        line_start=start, line_end=end,
        snippet='\n'.join(f'Range line {line}.' for line in range(start, end + 1)),
        continuation=continuation,
    )


def test_registered_backward_target_accepted_sync_and_async(context):
    import asyncio
    ranged, uri = _registered_range_context(context)
    result = _registered_range_result(ranged)
    sync_calls = []
    sync_controller = SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=lambda value: sync_calls.append(value) or result,
    )
    accepted = sync_controller.read(uri, missing_fact_id='rule')
    assert accepted['line_start'] == 156
    assert accepted['line_end'] == 172
    assert sync_calls == [uri]

    async_calls = []
    async def aread(value):
        async_calls.append(value)
        return result
    async_controller = SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=aread,
    )
    accepted = asyncio.run(async_controller.aread(uri, missing_fact_id='rule'))
    assert accepted['status'] == 'complete'
    assert async_calls == [uri]


def test_arbitrary_backward_uri_is_rejected_before_callback(context):
    ranged, _ = _registered_range_context(context)
    calls = []
    controller = SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=lambda value: calls.append(value),
    )
    result = controller.read('docatlas://source/' + 'c' * 24, missing_fact_id='rule')
    assert result['reason_code'] == 'unknown_or_repeated_source'
    assert calls == []


def test_fully_seen_registered_range_is_not_progress(context):
    ranged, uri = _registered_range_context(context)
    source = ranged['sources'][0]
    ranged['read_next'][0].update(line_start=162, line_end=168)
    _refresh_estimate(ranged)
    result = _registered_range_result(ranged, start=162, end=168)
    controller = SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=lambda value: result,
    )
    stopped = controller.read(uri, missing_fact_id='rule')
    assert stopped['reason_code'] == 'repeated_source_span'
    assert controller.results == []
    assert source['line_start'] == 162 and source['line_end'] == 168


def test_quality_or_registered_link_alone_never_triggers_read(context):
    ranged, _ = _registered_range_context(context)
    ranged['context_quality'] = {'status': 'partial', 'reasons': ['requested_part_missing']}
    calls = []
    SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=lambda value: calls.append(value),
    )
    assert calls == []


def test_completed_fact_and_third_attempt_stop_before_io_for_registered_ranges(context):
    ranged, uri = _registered_range_context(context)
    calls = []
    completed = SourceReadController(
        ranged, requested_facts={'rule': 'What rule appears above the quote?'},
        read_resource=lambda value: calls.append(value),
    )
    completed.mark_supported('rule')
    assert completed.read(uri, missing_fact_id='rule')['reason_code'] == 'no_concrete_missing_fact'
    assert calls == []

    # One registered range can legitimately page twice. A continuation returned
    # by the second page is known, but the global two-read budget blocks its I/O.
    ranged['read_next'][0]['line_end'] = 199
    _refresh_estimate(ranged)
    continuation_1 = 'docatlas://source/' + 'd' * 24
    continuation_2 = 'docatlas://source/' + 'e' * 24

    def read(value):
        calls.append(value)
        if value == uri:
            return _registered_range_result(
                ranged, start=156, end=170, continuation=continuation_1,
            )
        if value == continuation_1:
            return _registered_range_result(
                ranged, start=171, end=185, continuation=continuation_2,
            )
        pytest.fail('third range read reached I/O')

    controller = SourceReadController(
        ranged, requested_facts={'other': 'What follows?'}, read_resource=read,
    )
    first = controller.read(uri, missing_fact_id='other')
    assert first['continuation'] == continuation_1
    second = controller.read(continuation_1, missing_fact_id='other')
    assert second['continuation'] == continuation_2
    assert controller.read(continuation_2, missing_fact_id='other')['reason_code'] == 'read_budget_exhausted'
    assert calls == [uri, continuation_1]


def test_unavailable_context_can_offer_only_an_authorized_recovery_target(context):
    ranged, uri = _registered_range_context(context)
    target = deepcopy(ranged['read_next'][0])
    unavailable = {
        'status': 'insufficient_evidence', 'kind': 'docs_context',
        'sources': [], 'context_quality': {'status': 'unavailable', 'reasons': ['source_unavailable']},
        'read_next': [target], 'answer_supported': False, 'answer_available': False,
        'answer_policy': 'cite_only', 'edit_ready': False, 'estimated_tokens': 0,
    }
    _refresh_estimate(unavailable)
    calls = []
    controller = SourceReadController(
        unavailable, requested_facts={'rule': 'What rule is missing?'},
        read_resource=lambda value: calls.append(value) or {
            'status': 'complete', 'path': target['path'],
            'project_identity': target['project_identity'],
            'content_sha256': target['snapshot_sha256'],
            'line_start': target['line_start'], 'line_end': target['line_end'],
            'snippet': 'Recovered bounded source range.', 'continuation': None,
        },
    )
    assert controller.read(uri, missing_fact_id='rule')['status'] == 'complete'
    assert calls == [uri]

    calls.clear()
    unavailable['read_next'] = []
    _refresh_estimate(unavailable)
    controller = SourceReadController(
        unavailable, requested_facts={'rule': 'What rule is missing?'},
        read_resource=lambda value: calls.append(value),
    )
    assert controller.read(uri, missing_fact_id='rule')['reason_code'] == 'unknown_or_repeated_source'
    assert calls == []
