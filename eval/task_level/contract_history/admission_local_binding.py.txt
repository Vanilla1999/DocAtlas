"""A local default witness must bind the requested subject and property."""
import pytest

from docmancer.docs.application.retrieval_need_support import retrieval_need_local_witness


def default_need(subject='RelayClient', attribute='timeout'):
    return {'query_id': 'need-default', 'query_origin': 'retrieval_need',
            'text': f'What is the default {attribute} of {subject}?',
            'need_subject': subject, 'need_relation': 'default'}


@pytest.mark.parametrize('subject,value', [('RelayClient', 7), ('QueueDriver', 19)])
def test_direct_default_statement_is_a_witness(subject, value):
    assert retrieval_need_local_witness(default_need(subject),
        f'{subject} default timeout is {value} seconds.') is True


@pytest.mark.parametrize('body', [
    'RelayClient handles requests.\n\nOtherClient default timeout is 7 seconds.',
    'RelayClient has no default timeout.\n\nOtherClient default timeout is 7 seconds.',
    'RelayClient default retry delay is 7 seconds.',
    'RelayClient default timeout is undocumented.\n\nOtherClient timeout is 7 seconds.',
])
def test_default_does_not_borrow_subject_property_or_value(body):
    assert retrieval_need_local_witness(default_need(), body) is False


@pytest.mark.parametrize('body', [
    'RelayClient default retry count is 7.',
    'RelayClient default delay is 7 seconds.',
])
def test_compound_property_cannot_be_replaced_by_partial_word_match(body):
    assert retrieval_need_local_witness(default_need(attribute='retry delay'), body) is False


def test_compound_property_is_supported_when_fully_present():
    assert retrieval_need_local_witness(default_need(attribute='retry delay'),
        'RelayClient default retry delay is 7 seconds.') is True


def test_unrelated_source_title_cannot_lend_subject_to_another_api():
    assert retrieval_need_local_witness(default_need(),
        'OtherClient default timeout is 7 seconds.',
        source={'title': 'RelayClient', 'authority': 'source_of_truth'}) is False


def test_whole_page_membership_is_not_a_local_subject_binding():
    body = '# RelayClient\n\n## OtherClient\n\nOtherClient default timeout is 7 seconds.'
    assert retrieval_need_local_witness(default_need(), body,
        source={'title': 'RelayClient', 'authority': 'source_of_truth'}) is False


@pytest.mark.parametrize('body', [
    'RelayClient default timeout is undocumented; OtherClient default timeout is 7 seconds.',
    'RelayClient default timeout is undocumented. RelayClient retry delay is 7 seconds.',
    '# RelayClient\n\nOtherClient default timeout is 7 seconds.',
    'RelayClient handles requests. The OtherClient default timeout is 7 seconds.',
    'RelayClient default timeout glossary lists 7 seconds as an example.',
    'RelayClient enforces timeouts, but OtherClient uses delays. The default behavior is to wait 7 seconds.',
])
def test_default_requires_an_assignment_for_the_same_local_subject(body):
    assert retrieval_need_local_witness(default_need(), body) is False


@pytest.mark.parametrize('body', [
    '# RelayClient\n\nThe default timeout is 7 seconds.',
    'RelayClient default timeout is 7 seconds.',
    'The default timeout of RelayClient is 7 seconds.',
    "RelayClient's default timeout is 7 seconds.",
])
def test_default_local_layout_controls(body):
    assert retrieval_need_local_witness(default_need(), body) is True


@pytest.mark.parametrize('body', [
    'RelayClient default timeout is undocumented (the retry delay is 7 seconds).',
    'RelayClient default timeout is not 7 seconds.',
    'RelayClient default timeout is 7 attempts before waiting 19 seconds.',
    'RelayClient default timeout is 7 seconds when preview is enabled.',
])
def test_default_value_does_not_borrow_another_predicate_or_condition(body):
    assert retrieval_need_local_witness(default_need(), body) is False


@pytest.mark.parametrize('state,expected', [('disabled', True), ('not enabled', True), ('enabled', False)])
def test_conditional_default_requires_the_requested_state(state, expected):
    query = default_need()
    query['text'] = 'What is the default timeout of RelayClient when preview is disabled?'
    body = f'When preview is {state}, RelayClient default timeout is 7 seconds.'
    assert retrieval_need_local_witness(query, body) is expected


def test_compound_property_with_behavior_suffix_is_not_silently_shortened():
    assert retrieval_need_local_witness(default_need(attribute='cache behavior'),
        'RelayClient default cache is 7.') is False


@pytest.mark.parametrize('stance', ['is careful to enforce', 'is configured to use', 'is designed to enforce'])
def test_explicit_anaphora_handles_infinitive_stance_and_soft_wrapping(stance):
    body = (f'RelayClient {stance} timeouts everywhere by default.\n\n'
            'The default behavior is to raise `WaitExpired` after 19 seconds of\n'
            'network inactivity.')
    assert retrieval_need_local_witness(default_need(attribute='timeout behavior'), body) is True


@pytest.mark.parametrize('intro', [
    'RelayClient is not configured to enforce timeouts everywhere by default.',
    'OtherClient is configured to enforce timeouts everywhere by default.',
    'RelayClient is configured to enforce retries everywhere by default.',
])
def test_anaphoric_default_cannot_change_polarity_owner_or_property(intro):
    body = intro + '\n\nThe default behavior is to raise `WaitExpired` after 19 seconds.'
    assert retrieval_need_local_witness(default_need(attribute='timeout behavior'), body) is False


@pytest.mark.parametrize('answer', [
    'The default behavior is that OtherClient expires after 7 seconds.',
    'The default behavior is to retry after 7 seconds.',
    'The default behavior is to raise `WaitExpired` after 7 seconds when preview is enabled.',
    'The default behavior is to raise `WaitExpired` after 7 seconds except during startup.',
    'The default behavior is to raise `WaitExpired` after 7 seconds of retry delay.',
])
def test_anaphoric_default_cannot_borrow_another_answer_subject_property_or_condition(answer):
    body = 'RelayClient enforces timeouts everywhere.\n\n' + answer
    assert retrieval_need_local_witness(default_need(), body) is False


def test_recognized_condition_does_not_hide_unsupported_constraint_tail():
    query = default_need()
    query['text'] = 'What is the default timeout of RelayClient when preview is disabled except during startup?'
    assert retrieval_need_local_witness(query,
        'When preview is disabled, RelayClient default timeout is 7 seconds.') is not True


@pytest.mark.parametrize('action', ['raise a `WaitExpired`', 'throw an `OperationExpired`'])
def test_anaphoric_timeout_action_preserves_indefinite_article(action):
    body = ('RelayClient enforces timeouts everywhere.\n\n'
            f'The default behavior is to {action} after 19 seconds of\nnetwork inactivity.')
    assert retrieval_need_local_witness(default_need(attribute='timeout behavior'), body) is True
