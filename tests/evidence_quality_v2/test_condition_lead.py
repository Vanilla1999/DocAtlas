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



