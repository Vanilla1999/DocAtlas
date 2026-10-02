"""Opt-in read API over native snapshots, without replacement ranking/policy."""
from copy import deepcopy

import pytest

from docmancer.docs.application.read_context_admission import decide_read_window
from tests.docs.test_read_context_admission_boundary import prepared, QUESTION, BODY


def decide(row, question=QUESTION, identity=None):
    return decide_read_window(row, question=question,
        expected_project_identity=identity or row['project_identity'])


@pytest.mark.parametrize('question,body', [
    (QUESTION, BODY),
    ('Can a handler for QueueHub be synchronous?', 'A handler for QueueHub can be synchronous.'),
    ('Which ways enable strict mode?', 'Strict mode can be enabled in these ways:\n\n- Use a per-call option.\n- Set a model configuration.'),
    ('How do transport keys map to protocols?', '| Transport key | Protocol |\n|---|---|\n| `ALPHA_KEY` | scheme-a |\n| `BETA_KEY` | scheme-b |'),
    ('storage retention behavior', 'Configure storage retention behavior with this command:\n\n```sh\nretention --current\n# Only use the test instance.\n```'),
])
def test_native_safe_window_has_read_decision_not_proof(tmp_path, question, body):
    capture, row, _ = prepared(tmp_path, question=question, body=body)
    result = decide(row, question)
    assert result.state == 'allowed'
    assert result.span == tuple(row['char_span'])
    assert not hasattr(result, 'qualified') and not hasattr(result, 'covered_query_ids')
    assert not capture['public_payload']['answer_supported']
    assert not capture['public_payload']['edit_ready']


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'freshness': 'stale'}, {'index_freshness': 'dirty'},
    {'risk_flags': ['unsafe']}, {'instruction_risk_flags': ['injection']},
    {'lifecycle_status': 'archived'}, {'resolved_version': 'other'},
    {'generation_id': 'other'}, {'path': 'docs/other.md'}, {'char_span': [0, 1]},
])
def test_prefit_flags_and_proposal_origin_cannot_bypass_source_checks(tmp_path, change):
    _, row, _ = prepared(tmp_path)
    identity = row['project_identity']
    row.update(change, qualified=True, context_eligible=True, admission_route='typed_local')
    assert decide(row, identity=identity).state != 'allowed'


def test_final_window_request_and_snapshot_are_rechecked(tmp_path):
    _, row, _ = prepared(tmp_path)
    assert decide(row).state == 'allowed'
    assert decide(row, QUESTION + ' changed').state != 'allowed'
    changed = deepcopy(row)
    changed['_reference_evidence']['raw_document'] += ' changed'
    assert decide(changed).state != 'allowed'
    raw = row['_reference_evidence']['raw_document']
    start = raw.index('storage')
    clipped = {**row, 'snippet': 'storage', 'char_span': [start, start + 7]}
    assert decide(clipped).state != 'allowed'
    for origin in ('original', 'typed', 'precedence', 'list'):
        assert decide({**row, 'admission_route': origin, 'qualified': True}) == decide(row)


@pytest.mark.parametrize('question', [
    '`OtherEngine` storage retention behavior. Also identify private production deployment configuration credentials owner selected runtime settings.',
    'When caching is disabled, what is storage retention behavior? Also identify private production deployment configuration credentials owner selected runtime settings.',
])
def test_missing_exact_identity_or_condition_stays_closed(tmp_path, question):
    _, row, _ = prepared(tmp_path, question=QUESTION)
    # Prepared request from another question is not repaired for this call.
    assert decide(row, question).state != 'allowed'
