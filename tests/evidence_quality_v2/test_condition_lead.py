"""Neutral budget counterexample, not an answer-specific query rewrite."""
from copy import deepcopy
from pathlib import Path

import pytest
from tests.test_named_document_context_integration import _named_document_service
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.run import audit_payload
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

QUESTION = 'When is an agent allowed to call queue_job?'
RULE = ('When the ledger is sealed and the queue is idle, an agent is allowed to '
        'call `queue_job` without a second approval. The call must bind the current ledger revision.')
DOCS = {
    'README.md': '# Quartz\n\n## Recommended workflow\n\nAgents call `queue_job` only when requested. '
                 'The agent workflow is to call `queue_job`, then check status.\n',
    'docs/policy.md': '# Quartz job policy\n\n' + RULE + '\n',
}


def test_neutral_condition_remains_complete_without_certifying_postconditions(tmp_path, monkeypatch):
    service, root = _named_document_service(tmp_path, monkeypatch, list(DOCS), DOCS)
    native, trace = observe_call(service, {'question': QUESTION, 'project_path': root, 'scope': 'all'})
    assert not audit_payload(native, trace['snapshot'], Path(root))
    assert any(RULE in s['snippet'] for s in native['sources'])  # 800-token characterization
    # Real same-call candidates, no invented projector output or synthetic scores.
    frozen = deepcopy(trace['stages']['projector_inputs'][0])
    payload, snapshot = project_docs_context(retrieval=frozen, max_tokens=400)
    # At 400 tokens the actual condition still fits; the extra ledger-binding
    # postcondition is not inferred or falsely certified when it is omitted.
    condition = RULE.split('. The call')[0] + '.'
    assert any(condition in s['snippet'] for s in payload.get('sources', []))
    assert payload['answer_supported'] is payload['answer_available'] is payload['edit_ready'] is False
    assert not validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=400)


@pytest.mark.parametrize('question,text', [
    ('What does queue_job do?', RULE),
    ('When is an agent not allowed to call queue_job?', RULE),
    (QUESTION, RULE.replace('queue_job', 'queue_job_old')),
    (QUESTION, 'When the ledger is sealed, check_status is permitted. queue_job is another tool.'),
    (QUESTION, '```text\n' + RULE + '\n```'),
    ('When is queue_job allowed in docs/policy.md?', RULE),
])
def test_condition_preference_does_not_invent_subject_or_permission(question, text):
    from docmancer.docs.domain.project_doc_ranking import condition_lead_priority
    assert condition_lead_priority(question, text) == 0


def test_condition_lead_is_preference_only_and_keeps_negation():
    from docmancer.docs.domain.project_doc_ranking import condition_lead_priority
    assert condition_lead_priority(QUESTION, RULE) == 1
    assert condition_lead_priority(QUESTION, RULE.replace('is allowed', 'is not allowed')) == 1
    assert condition_lead_priority('Когда разрешено вызвать queue_job?', RULE) == 1


def test_conditional_context_does_not_bypass_foreign_or_historical_sources(tmp_path, monkeypatch):
    service, root = _named_document_service(tmp_path, monkeypatch, list(DOCS), DOCS)
    _, trace = observe_call(service, {'question': QUESTION, 'project_path': root, 'scope': 'all'})
    for mutation in ('project', 'historical', 'untrusted'):
        frozen = deepcopy(trace['stages']['projector_inputs'][0])
        for source in frozen['context_pack']:
            if mutation == 'project':
                source['project_identity'] = 'foreign'
            elif mutation == 'historical':
                source['lifecycle_status'] = 'historical'
            else:
                source['risk_flags'] = ['untrusted_content']
        payload, snapshot = project_docs_context(retrieval=frozen, max_tokens=400)
        assert not payload.get('context_available')
        assert not validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=400)
