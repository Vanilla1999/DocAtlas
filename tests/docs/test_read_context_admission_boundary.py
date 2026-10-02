"""Read-context locality is not semantic qualification or edit permission."""
from copy import deepcopy

import pytest

from docmancer.docs.application.read_context_admission import (
    iter_read_context_variants, read_context_admission, project_read_context_fallback,
)
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from tests.docs._reference_binding_fixtures import capture_reference_case


QUESTION = ('storage retention behavior. Also identify private production deployment '
            'configuration credentials owner selected runtime settings.')
BODY = 'storage retention behavior is documented in this current guide.'


def prepared(tmp_path, question=QUESTION, body=BODY):
    capture = capture_reference_case(tmp_path, {'docs/guide.md': '# Guide\n\n' + body + '\n'}, question)
    candidate = capture['projection_attempts'][0]['before_projection']['context_pack'][0]
    evidence = candidate['_reference_evidence']
    candidate = {**candidate, 'snippet': evidence['text'],
                 'char_span': [evidence['char_start'], evidence['char_end']]}
    plan = capture['projection_attempts'][0]['before_projection']['documentation_query_plan']
    return capture, candidate, plan


def test_original_partial_query_retains_read_context_without_coverage(tmp_path):
    capture, candidate, plan = prepared(tmp_path)
    payload = capture['public_payload']
    assert payload['sources']
    assert not payload['answer_supported']
    assert not payload['edit_ready']
    assert all(q['origin'] == 'original' for q in plan['queries'])
    result = project_read_context_fallback([candidate], query_plan=plan,
        expected_project_identity=candidate['project_identity'], max_tokens=800, diagnostics={})
    assert result is not None
    delivered, _ = result
    assert all(not row.get('retrieval_query_ids') for row in delivered['sources'])
    assert docs_context_budget_tokens(delivered) <= 800


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'freshness': 'stale'}, {'index_freshness': 'dirty'},
    {'risk_flags': ['unsafe']}, {'instruction_risk_flags': ['injection']},
    {'lifecycle_status': 'archived'}, {'char_span': [0, 1]},
])
def test_topic_context_cannot_bypass_source_guards(tmp_path, change):
    _, candidate, _ = prepared(tmp_path)
    identity = candidate['project_identity']
    candidate.update(change)
    assert not read_context_admission(candidate, question=QUESTION,
                                     expected_project_identity=identity).allowed


def test_snapshot_and_question_binding_are_recomputed(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    changed = deepcopy(candidate)
    changed['_reference_evidence']['raw_document'] += ' changed'
    assert not read_context_admission(changed, question=QUESTION,
        expected_project_identity=candidate['project_identity']).allowed
    assert not read_context_admission(candidate, question=QUESTION + ' other scope',
        expected_project_identity=candidate['project_identity']).allowed


def test_clipped_topic_and_tiny_budget_cannot_reuse_approval(tmp_path):
    _, candidate, plan = prepared(tmp_path)
    start = candidate['_reference_evidence']['char_start']
    clipped = {**candidate, 'snippet': 'storage', 'char_span': [start, start + 7]}
    assert not read_context_admission(clipped, question=QUESTION,
        expected_project_identity=candidate['project_identity']).allowed
    assert not list(iter_read_context_variants([candidate], query_plan=plan,
        expected_project_identity=candidate['project_identity'], max_tokens=1, diagnostics={}))


@pytest.mark.parametrize('body', [
    '# storage retention behavior\n\nUnrelated network details.',
    'storage retention behavior\n==========================\n\nstorage is documented. retention is documented. behavior is documented.',
    'storage retention details are documented.',
    'storage is documented. retention is documented. behavior is documented.',
    'storage behavior retention is documented.',
    'storage retention behavior?',
    'storage retention behavior.',
])
def test_local_topic_witness_rejects_heading_echo_and_scattered_terms(tmp_path, body):
    # Use a valid prepared source for the negative bytes, not an invented DTO.
    capture = capture_reference_case(tmp_path, {'docs/guide.md': '# Guide\n\n' + body + '\n'}, QUESTION)
    # Negative candidates may be correctly removed before context_pack. The
    # public boundary still must remain empty; this is the primary assertion.
    assert not capture['public_payload'].get('sources')


def test_unicode_original_topic_is_not_translated(tmp_path):
    question = 'αποθήκευση διατήρηση συμπεριφορά. Also identify private production deployment configuration credentials owner selected runtime settings.'
    body = 'αποθήκευση διατήρηση συμπεριφορά περιγράφονται στον τρέχοντα οδηγό.'
    capture, _, plan = prepared(tmp_path, question, body)
    assert plan['original_question'] == question
    assert capture['public_payload']['sources']
    assert not capture['public_payload']['answer_supported']
    assert not capture['public_payload']['edit_ready']


@pytest.mark.parametrize('field,value', [
    ('canonical_path', 'docs/other.md'), ('content_sha256', '0' * 64),
    ('document_id', 'other'),
])
def test_prepared_source_identity_cannot_be_forged(tmp_path, field, value):
    _, candidate, _ = prepared(tmp_path)
    candidate = deepcopy(candidate)
    candidate['_reference_evidence']['source'][field] = value
    assert not read_context_admission(candidate, question=QUESTION,
        expected_project_identity=candidate['project_identity']).allowed


@pytest.mark.parametrize('question', [
    '`OtherEngine` storage retention behavior. Also identify private production deployment configuration credentials owner selected runtime settings.',
    'When caching is disabled, what is storage retention behavior? Also identify private production deployment configuration credentials owner selected runtime settings.',
])
def test_added_identity_or_condition_does_not_preserve_context(tmp_path, question):
    capture = capture_reference_case(tmp_path, {'docs/guide.md': '# Guide\n\n' + BODY + '\n'}, question)
    assert not capture['public_payload'].get('sources')
    assert not capture['public_payload']['answer_supported']
    assert not capture['public_payload']['edit_ready']
