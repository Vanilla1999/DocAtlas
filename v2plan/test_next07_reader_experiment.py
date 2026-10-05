"""Host-contract tests, not model-quality evidence. Native pilot is separate."""
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from v2plan.next07_reader_experiment.host import SectionHost, digest
from v2plan.next07_reader_experiment.model import run_session, ProviderError, OpenAIReader


class Gateway:
    def __init__(self, raw):
        self.data = raw.encode('utf-8')
        self.read_count = 0
        self.failure = None
    def authorize(self, reference):
        return self.failure
    def read_snapshot(self, reference):
        self.read_count += 1
        return self.data


def setup(raw='# Guide\n\nAn introduction.\n\n## Functions\n\nA function can be normal or asynchronous.\n', *, clock=lambda: 0):
    end = raw.index('##')
    public = {'evidence_id': 'visible-1', 'path_or_url': 'guide.md', 'snippet': raw[:end],
              'project_identity': 'project-1', 'line_start': 1, 'line_end': 4}
    source = {'path': 'guide.md', 'source_class': 'project_doc', 'project_identity': 'project-1',
        'authority': 'source_of_truth', 'doc_scope': 'project', 'line_end': 4,
        'char_start': 0, 'char_end': end, '_source_snapshot_sha256': digest(raw.encode('utf-8')),
        '_source_catalog_hash': 'sha256:' + 'c' * 64,
        '_reference_evidence': {'raw_document': raw}}
    context = {'kind': 'docs_context', 'sources': [public], 'answer_supported': False}
    snapshot = {'visible-1': {'source': source, 'projected_source': deepcopy(public)}}
    gateway = Gateway(raw)
    host = SectionHost(context, snapshot, root='/project', gateway=gateway, clock=clock)
    return host, gateway, context, snapshot


def handle(host):
    return next(s['read_handle'] for d in host.navigation for s in d['sections'] if s['read_handle'])


def test_navigation_does_not_hydrate_or_mutate_initial_packet():
    host, gateway, context, _ = setup()
    assert not gateway.read_count
    assert host.first_view(navigation=True)['initial_context'] == context
    assert host.first_view(navigation=False)['navigation'] == []
    assert host.navigation[0]['sections'][1]['title'] == 'Functions'
    assert host.navigation[0]['sections'][0]['already_shown_in_full']


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
@pytest.mark.parametrize('body', ['Text.', 'Δοκιμή 😀.'])
def test_reads_exact_bytes_and_scope(ending, body):
    raw = ('# Guide\n\nIntro.\n\n## Detail\n\n' + body + '\n\nOnly for the described condition.\n').replace('\n', ending)
    host, gateway, _, _ = setup(raw)
    result = host.read_section(handle(host))
    assert result['status'] == 'complete' and result['unit_complete'] is True
    assert result['source']['snippet'] == raw[raw.index('##'):]
    assert result['source']['snapshot_sha256'] == digest(gateway.data)
    assert result['answer_supported'] is False and result['applicability'] == 'not_assessed'


def test_unknown_handle_does_not_authorize_read():
    host, gateway, _, _ = setup()
    assert host.read_section('../../outside')['reason'] == 'unknown_handle'
    assert gateway.read_count == 0


def test_expiry_precedes_io():
    now = [0]
    host, gateway, _, _ = setup(clock=lambda: now[0])
    token = handle(host)
    now[0] = 10000
    assert host.read_section(token)['reason'] == 'expired_handle'
    assert gateway.read_count == 0


def test_catalog_revocation_precedes_io():
    host, gateway, _, _ = setup()
    gateway.failure = 'scope_changed'
    assert host.read_section(handle(host))['reason'] == 'source_no_longer_authorized'
    assert gateway.read_count == 0


def test_snapshot_change_returns_no_quote():
    host, gateway, _, _ = setup()
    gateway.data += b'\nCHANGED'
    response = host.read_section(handle(host))
    assert response['reason'] == 'source_changed' and 'source' not in response
    assert host.reads == []


def test_repetition_does_not_hydrate_again():
    host, gateway, _, _ = setup()
    token = handle(host)
    assert host.read_section(token)['status'] == 'complete'
    assert host.read_section(token)['reason'] == 'repeated_handle'
    assert host.read_section(token)['reason'] == 'read_budget_exhausted'
    assert gateway.read_count == 1


def test_guessed_session_handle_is_not_transferable():
    first, _, _, _ = setup()
    other, gateway, _, _ = setup()
    assert other.read_section(handle(first))['reason'] == 'unknown_handle'
    assert gateway.read_count == 0


def test_oversized_section_is_never_clipped():
    raw = '# Guide\n\nIntro.\n\n## Long\n\n' + 'A line with text.\n' * 70
    host, _, _, _ = setup(raw)
    entry = host.navigation[0]['sections'][1]
    assert entry['read_handle'] is None
    token = next(k for k, v in host._sections.items() if v.title == 'Long')
    response = host.read_section(token)
    assert response['reason'] == 'section_exceeds_read_budget'
    assert 'source' not in response and not host.reads


def test_late_condition_and_negation_are_delivered_together():
    raw = '# Guide\n\nIntro.\n\n## Behavior\n\nRaises E.\n\nOnly after expiration, not cancellation.\n'
    host, _, _, _ = setup(raw)
    response = host.read_section(handle(host))
    assert 'Only after expiration, not cancellation.' in response['source']['snippet']


def test_forged_initial_binding_fails_closed():
    _, gateway, context, snapshot = setup()
    context['sources'][0]['snippet'] = 'forged'
    with pytest.raises(ValueError, match='validated snapshot'):
        SectionHost(context, snapshot, root='/project', gateway=gateway)


def test_unread_citation_is_not_accepted():
    host, _, _, _ = setup()
    assert host.citation_errors([{'evidence_id': 'not-shown', 'quote': 'A function'}])
    result = host.read_section(handle(host))
    assert not host.citation_errors([{'evidence_id': result['source']['evidence_id'],
                                      'quote': result['source']['snippet']}])


class Scripted:
    """Mechanical reachability oracle, deliberately not a fake live model."""
    def __init__(self):
        self.messages = []
    def complete(self, messages, tools):
        self.messages.append(deepcopy(messages))
        first = json.loads(messages[3]['content'])
        if len(self.messages) == 1 and first['available_section_reads']:
            token = next(s['read_handle'] for d in first['navigation'] for s in d['sections'] if s['read_handle'])
            name, args = 'read_doc_section', {'handle': token}
        else:
            last = json.loads(messages[-1]['content']) if messages[-1]['role'] == 'tool' else {}
            source = last.get('source')
            name, args = 'submit_answer', {'status': 'answered' if source else 'unknown',
                'answer': 'Both forms.' if source else 'Unknown.', 'missing': '', 'question_for_user': '',
                'citations': [{'evidence_id': source['evidence_id'], 'quote': source['snippet']}] if source else []}
        return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call-' + str(len(self.messages)),
            'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}, {'provider': 'SCRIPTED_NOT_MODEL'}


def test_scripted_loop_validates_reachability_not_model_quality(tmp_path):
    host, _, context, snapshot = setup()
    snapshot['hidden-gold'] = {'rubric': 'SECRET_EXPECTED_ANSWER'}
    provider = Scripted()
    report = run_session(host, 'Can the function be asynchronous?', arm='B', provider=provider, out=tmp_path)
    assert report['execution'] == 'COMPLETE'
    assert report['successful_reads'] == 1
    assert report['quality'] == 'PENDING_INDEPENDENT_REVIEW'
    assert not report['citation_errors']
    assert 'SECRET_EXPECTED_ANSWER' not in json.dumps(provider.messages)
    assert host.context == context


def test_baseline_has_no_reader_tool(tmp_path):
    host, gateway, _, _ = setup()
    report = run_session(host, 'Question', arm='A', provider=Scripted(), out=tmp_path)
    assert report['execution'] == 'COMPLETE' and report['read_attempts'] == 0
    assert gateway.read_count == 0
    request = json.loads((tmp_path / 'request-0.json').read_text())
    assert [t['function']['name'] for t in request['tools']] == ['submit_answer']


def test_absent_provider_is_never_called_scripted_live(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ProviderError, match='credential'):
        OpenAIReader()
