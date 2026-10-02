"""Native snapshot guards without relevance or proof admission."""
from copy import deepcopy

import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.source_window_eligibility import source_window_eligibility
from docmancer.docs.domain.query_terms import documentation_query_terms
from tests.docs.test_read_context_admission_boundary import prepared, QUESTION


def check(candidate, question=QUESTION, identity=None):
    return source_window_eligibility(candidate, question=question,
        expected_project_identity=identity or candidate['project_identity'])


def test_source_eligibility_does_not_grant_qualification(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    decision = check(candidate)
    assert decision.eligible
    assert decision.span == tuple(candidate['char_span'])
    qualified = qualify_evidence(
        {'query_text': QUESTION, 'query_terms': list(documentation_query_terms(QUESTION))},
        query_id='query-original', visible_text=candidate['snippet'],
        candidate=candidate, expected_project_identity=candidate['project_identity'])
    assert not qualified.qualified
    assert qualified.reason == 'insufficient_visible_match'


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'freshness': 'stale'},
    {'index_freshness': 'dirty'}, {'risk_flags': ['unsafe']},
    {'instruction_risk_flags': ['injection']}, {'lifecycle_status': 'archived'},
    {'char_span': [0, 1]}, {'resolved_version': 'wrong'},
    {'generation_id': 'wrong'}, {'path': 'docs/other.md'},
    {'repository_identity': 'other'}, {'source_class': 'library_doc'},
])
def test_incoming_approval_cannot_bypass_guards(tmp_path, change):
    _, candidate, _ = prepared(tmp_path)
    identity = candidate['project_identity']
    candidate.update(change, qualified=True, context_eligible=True)
    assert not check(candidate, identity=identity).eligible


def test_snapshot_and_request_are_rechecked(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    changed = deepcopy(candidate)
    changed['_reference_evidence']['raw_document'] += ' changed'
    assert not check(changed).eligible
    assert not check(candidate, question=QUESTION + ' changed').eligible
    changed = deepcopy(candidate)
    changed['_reference_evidence']['source']['scope']['project_id'] = 'other'
    assert not check(changed).eligible


def test_unicode_window_uses_exact_offsets(tmp_path):
    _, candidate, _ = prepared(tmp_path, body='Пролог. storage retention behavior is documented.')
    raw = candidate['_reference_evidence']['raw_document']
    a, b = candidate['char_span']
    assert check(candidate).eligible
    assert raw[a:b] == candidate['snippet']
    assert raw.encode()[len(raw[:a].encode()):len(raw[:b].encode())].decode() == candidate['snippet']
    candidate['char_span'] = [len(raw[:a].encode()), len(raw[:b].encode())]
    assert not check(candidate).eligible
    body = 'storage retention behavior is documented.'
    _, repeated, _ = prepared(tmp_path / 'repeat', body=body + '\n\n' + body)
    evidence = repeated['_reference_evidence']
    start = evidence['raw_document'].rindex(body)
    assert evidence['char_start'] <= start < start + len(body) <= evidence['char_end']
    repeated.update(snippet=body, char_span=[start, start + len(body)])
    decision = check(repeated)
    assert decision.eligible
    assert decision.span == (start, start + len(body))
