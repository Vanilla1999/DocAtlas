"""Regression for reviewed pilot boundaries; no model-quality PASS is implied."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from v2plan.next07_reader_experiment import model


class Host:
    """Deliberately a unit-test double, not DocAtlas source authorization."""
    def __init__(self):
        self.context = {'kind': 'docs_context', 'sources': []}
        self._evidence = {}
        self.read_attempts = 0
        self.reads = []

    def first_view(self, *, navigation):
        return {'initial_context': deepcopy(self.context), 'navigation': [],
                'available_section_reads': 2 if navigation else 0}

    def read_section(self, handle):
        self.read_attempts += 1
        return {'status': 'unavailable', 'reason': 'unknown_handle'}

    def citation_errors(self, citations):
        return ['quote_not_in_visible_evidence'] if citations else []


def call(name='submit_answer', arguments=None, call_id='call-1'):
    if arguments is None:
        arguments = {'status': 'unknown', 'answer': 'Not established.',
                     'citations': [], 'missing': 'A source.', 'question_for_user': ''}
    return {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': call_id, 'type': 'function',
        'function': {'name': name, 'arguments': json.dumps(arguments)}}]}


class Sequence:
    def __init__(self, messages):
        self.messages = list(messages)
        self.tools = []

    def complete(self, messages, tools):
        self.tools.append(deepcopy(tools))
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, {'provider': 'SCRIPTED_NOT_MODEL'}


@pytest.mark.parametrize('bad', [None, 'text', [], {'role': 'user', 'tool_calls': []},
    {'role': 'assistant', 'tool_calls': 'wrong'},
    {'role': 'assistant', 'tool_calls': {'0': {}}},
    {'role': 'assistant', 'tool_calls': [None]},
    {'role': 'assistant', 'tool_calls': [{'type': 'function', 'function': {}}]},
    {'role': 'assistant', 'tool_calls': [{'id': 'x', 'type': 'function', 'function': []}]},
])
def test_malformed_model_action_is_a_result_not_runner_crash(tmp_path, bad):
    host = Host()
    result = model.run_session(host, 'Question', arm='B', provider=Sequence([bad]), out=tmp_path)
    assert result['execution'] == 'INVALID_MODEL_ACTION'
    assert host.read_attempts == 0
    assert json.loads((tmp_path / 'result.json').read_text()) == result
    assert (tmp_path / 'transcript.json').exists()


def test_missing_id_cannot_trigger_source_read(tmp_path):
    bad = call('read_doc_section', {'handle': 'not-issued'})
    del bad['tool_calls'][0]['id']
    host = Host()
    result = model.run_session(host, 'Q', arm='B', provider=Sequence([bad]), out=tmp_path)
    assert result['execution'] == 'INVALID_MODEL_ACTION'
    assert host.read_attempts == 0


def test_reused_call_id_does_not_execute_second_read(tmp_path):
    first = call('read_doc_section', {'handle': 'x'})
    second = call('read_doc_section', {'handle': 'y'})
    host = Host()
    result = model.run_session(host, 'Q', arm='B', provider=Sequence([first, second]), out=tmp_path)
    assert result['execution'] == 'INVALID_MODEL_ACTION'
    assert host.read_attempts == 1
    assert json.loads((tmp_path / 'transcript.json').read_text())[0]['tool_result']['status'] == 'unavailable'


def test_exhausted_read_not_advertised_but_finish_still_possible(tmp_path):
    provider = Sequence([call('read_doc_section', {'handle': 'x'}, 'c1'),
                         call('read_doc_section', {'handle': 'y'}, 'c2'), call(call_id='c3')])
    result = model.run_session(Host(), 'Q', arm='B', provider=provider, out=tmp_path)
    assert result['execution'] == 'COMPLETE'
    assert [t['function']['name'] for t in provider.tools[2]] == ['submit_answer']
    assert result['read_attempts'] == 2


@pytest.mark.parametrize('reason', ['MODEL_OUTPUT_LIMIT', 'MODEL_REFUSAL_OR_INCOMPLETE'])
def test_model_termination_not_misreported_as_provider_outage(tmp_path, reason):
    exc = model.ModelTermination(reason, {'role': 'assistant', 'content': 'partial'},
                                 {'request_id': 'test-request', 'usage': {'total_tokens': 10}})
    result = model.run_session(Host(), 'Q', arm='B', provider=Sequence([exc]), out=tmp_path)
    assert result['execution'] == reason
    assert json.loads((tmp_path / 'transcript.json').read_text())[0]['provider']['request_id'] == 'test-request'


def test_empty_user_clarification_marked_not_silently_successful(tmp_path):
    final = call(arguments={'status': 'needs_user_data', 'answer': '', 'citations': [],
                            'missing': 'Deployment settings', 'question_for_user': ''})
    result = model.run_session(Host(), 'Q', arm='A', provider=Sequence([final]), out=tmp_path)
    assert result['finish_contract_errors'] == ['user_data_status_without_question']
    assert result['quality'] == 'PENDING_INDEPENDENT_REVIEW'


class HTTPResponse:
    def __init__(self, data):
        self.data = data
        self.headers = {'x-request-id': 'fake-test-request'}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, limit):
        return json.dumps(self.data).encode()[:limit]


def response(returned='reader-revision', finish='tool_calls'):
    return {'model': returned, 'choices': [{'finish_reason': finish, 'message': call()}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}}


def reader(monkeypatch, responses):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder-not-a-real-key')
    replies = iter(responses)
    monkeypatch.setattr(model.urllib.request, 'urlopen', lambda *_a, **_k: HTTPResponse(next(replies)))
    return model.OpenAIReader(model='explicit-reader')


def test_provider_returned_model_is_frozen_across_requests(monkeypatch):
    client = reader(monkeypatch, [response('rev-a'), response('rev-b')])
    client.complete([], [])
    with pytest.raises(model.ProviderError, match='model_changed'):
        client.complete([], [])


@pytest.mark.parametrize('body', [[], None, {'choices': [None]}, {'model': None, **{'choices': []}}])
def test_malformed_provider_payload_is_typed_failure(monkeypatch, body):
    client = reader(monkeypatch, [body])
    with pytest.raises(model.ProviderError):
        client.complete([], [])


def test_missing_model_identity_is_not_accepted(monkeypatch):
    client = reader(monkeypatch, [response(None)])
    with pytest.raises(model.ProviderError, match='identity_missing'):
        client.complete([], [])


def test_provider_length_keeps_identity_and_usage(monkeypatch):
    client = reader(monkeypatch, [response(finish='length')])
    with pytest.raises(model.ModelTermination) as caught:
        client.complete([], [])
    assert str(caught.value) == 'MODEL_OUTPUT_LIMIT'
    assert caught.value.usage['usage']['total_tokens'] == 12


def test_unselected_private_snapshot_row_is_not_marked_shown():
    from v2plan.test_next07_reader_experiment import setup
    from v2plan.next07_reader_experiment.host import SectionHost
    host, gateway, context, snapshot = setup()
    extra = deepcopy(snapshot['visible-1'])
    raw = gateway.data.decode()
    extra['source'].update(char_start=raw.index('##'), char_end=len(raw))
    extra['projected_source'] = {'evidence_id': 'never-delivered', 'snippet': raw[raw.index('##'):]}
    snapshot['never-delivered'] = extra
    revised = SectionHost(context, snapshot, root='/project', gateway=gateway)
    section = revised.navigation[0]['sections'][1]
    assert section['already_shown_in_full'] is False
    assert section['read_handle'] is not None
    assert 'never-delivered' not in revised._evidence


def test_initial_span_is_not_relocated_or_inflated():
    from v2plan.test_next07_reader_experiment import setup
    from v2plan.next07_reader_experiment.host import SectionHost
    _, gateway, context, snapshot = setup()
    snapshot['visible-1']['source']['char_end'] = len(gateway.data.decode())
    with pytest.raises(ValueError, match='public span is not exact'):
        SectionHost(context, snapshot, root='/project', gateway=gateway)


def test_whitespace_quote_is_not_citation_evidence():
    from v2plan.test_next07_reader_experiment import setup
    host, _, _, _ = setup()
    assert host.citation_errors([{'evidence_id': 'visible-1', 'quote': '\n'}])
