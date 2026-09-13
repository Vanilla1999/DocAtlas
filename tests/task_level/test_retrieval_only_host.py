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
