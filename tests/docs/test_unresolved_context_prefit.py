"""Retention preferences do not certify answers or bypass source guards."""
from copy import deepcopy

import pytest

from docmancer.docs.domain.context_hint_policy import preserves_unresolved_context_candidate
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from tests.evidence_quality_v2.test_readme_neutral_context import TEXT, CASES, capture
from tests.test_named_document_context_integration import _named_document_service


def test_prefit_recomputes_body_support_without_qualifying_answer(tmp_path, monkeypatch):
    service, root = _named_document_service(tmp_path, monkeypatch, ['README.md'], {'README.md': TEXT})
    payload, trace = capture(service, {'question': CASES[0][0], 'project_path': root, 'scope': 'all'})
    retrieval = trace['stages']['projector_inputs'][0]
    source = deepcopy(retrieval['context_pack'][0])
    identity = source['project_identity']
    assert preserves_unresolved_context_candidate(source,
        query_plan=retrieval['documentation_query_plan'], expected_project_identity=identity)
    assert not payload['answer_supported'] and not payload['edit_ready']
    question = 'Как Pebble отправляет сообщения через квантовый канал?'
    source['retrieval_query_matches'] = {'query-original': {
        'qualified': True, 'body_matched_terms': ['Pebble', 'квантовый']}}
    assert not preserves_unresolved_context_candidate(source,
        query_plan=build_documentation_query_plan(question).as_payload(),
        expected_project_identity=identity)


@pytest.mark.parametrize('change', ['project', 'stale', 'freshness', 'risk', 'lifecycle'])
def test_prefit_does_not_preserve_ineligible_source(tmp_path, monkeypatch, change):
    service, root = _named_document_service(tmp_path, monkeypatch, ['README.md'], {'README.md': TEXT})
    _, trace = capture(service, {'question': CASES[0][0], 'project_path': root, 'scope': 'all'})
    retrieval = trace['stages']['projector_inputs'][0]
    source = deepcopy(retrieval['context_pack'][0])
    identity = source['project_identity']
    if change == 'project': source['project_identity'] = 'other-project'
    elif change == 'stale': source['stale'] = True
    elif change == 'freshness': source['index_freshness'] = 'unsynchronized'
    elif change == 'risk': source['risk_flags'] = ['untrusted_content']
    elif change == 'lifecycle': source['lifecycle_status'] = 'historical'
    assert not preserves_unresolved_context_candidate(source,
        query_plan=retrieval['documentation_query_plan'], expected_project_identity=identity)
