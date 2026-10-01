"""Semantic guards for the development probe's reporting, not a retrieval test."""
import pytest
from experiments.language_aware_context.ci_diagnostic import claim_check

PATH = 'docs/advanced/timeouts.md'
CLAUSES = ('default behavior', 'TimeoutException', '5 seconds', 'network inactivity')
TEXT = 'The default behavior is to raise a `TimeoutException` after 5 seconds of\nnetwork inactivity.'


def result(sources=()):
    return {'status': 'EXECUTED', 'audit_errors': [], 'budget_tokens': 700,
            'payload': {'sources': list(sources)}}


def source(text=TEXT, path=PATH):
    return {'path_or_url': path, 'snippet': text}


def test_complete_rule_must_be_in_one_audited_quote():
    assert claim_check(result([source()]), PATH, CLAUSES)['status'] == 'COMPLETE'


def test_separate_quotes_do_not_prove_a_relationship():
    packet = result([source('default behavior TimeoutException'),
                     source('5 seconds network inactivity')])
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'PARTIAL'


def test_wrong_source_is_not_a_witness():
    packet = result([source(path='docs/other.md')])
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'ABSENT'


def test_empty_packet_is_a_real_miss_not_an_execution_error():
    assert claim_check(result(), PATH, CLAUSES)['status'] == 'ABSENT'


@pytest.mark.parametrize('patch', [
    {'status': 'BLOCKED_IMPORT'}, {'status': 'HANDLER_FAILED'},
    {'status': 'AUDIT_FAILED'}, {'audit_errors': ['noncanonical evidence']},
    {'audit_errors': None}, {'budget_tokens': None}, {'budget_tokens': 801},
    {'budget_tokens': True}, {'budget_tokens': -1},
])
def test_invalid_execution_is_not_quality_evidence(patch):
    packet = result([source()]); packet.update(patch)
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'NOT_EVALUABLE'


@pytest.mark.parametrize('clauses', [(), ('',), ('fact', None), ('fact', 'fact')])
def test_empty_or_invalid_labels_are_rejected(clauses):
    with pytest.raises(ValueError):
        claim_check(result([source()]), PATH, clauses)


def test_keyword_alone_is_not_a_full_fact():
    packet = result([source('Use TimeoutException when configuring the client.')])
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'PARTIAL'


def test_valid_terminal_packet_without_sources_is_a_miss():
    packet = result()
    packet['payload'] = {'context_available': False}
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'ABSENT'


@pytest.mark.parametrize('payload', [None, [], 'broken'])
def test_invalid_payload_is_not_evaluable(payload):
    packet = result()
    packet['payload'] = payload
    assert claim_check(packet, PATH, CLAUSES)['status'] == 'NOT_EVALUABLE'
