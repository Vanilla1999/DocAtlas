"""Diagnostic acceptance: real projector, same visible results, bounded decisions."""
from copy import deepcopy
import json
from unittest.mock import patch

from docmancer.docs.application import _docs_context_projection_core as core
from docmancer.docs.application.docs_context_projection import project_docs_context
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def test_every_selection_iteration_has_one_terminal_event():
    retrieval = _host_lookup_context_retrieval()
    payload, _ = project_docs_context(retrieval=retrieval)
    diag = retrieval['retrieval_diagnostics']['docs_context_projection']
    assert 'decision_trace' in diag, 'Executed selection decisions have no bounded event trace'
    trace = diag['decision_trace']
    assert trace['variant_attempts'] > 0
    events = [row for row in trace['events'] if row['stage'] == 'selection']
    assert len(events) + trace['selection_events_omitted'] == trace['variant_attempts']
    assert sum(trace['counts'].values()) == len(trace['events']) + trace['omitted_events']
    assert sum(row['reason'] == 'accepted' for row in events) == len(payload['sources'])
    assert any(row['reason'] == 'source_cap' for row in events)
    assert 'decision_trace' not in json.dumps(payload)


def test_trace_records_literal_rejection_not_missing_output_inference():
    retrieval = _host_lookup_context_retrieval()
    duplicate = deepcopy(retrieval['context_pack'][0])
    duplicate.update(path='docs/another-purpose.md', content='Project purpose documentation gives another focused explanation.')
    retrieval['context_pack'] = [retrieval['context_pack'][0], duplicate]
    project_docs_context(retrieval=retrieval)
    trace = retrieval['retrieval_diagnostics']['docs_context_projection'].get('decision_trace')
    assert trace is not None, 'No trace for executed rejection'
    assert trace['counts'].get('selection:no_new_direction', 0) > 0


def test_instrumentation_does_not_change_public_payload_or_snapshot():
    retrieval = _host_lookup_context_retrieval()
    assert hasattr(core, 'ProjectionDecisionTrace'), 'Trace seam absent'
    observed = project_docs_context(retrieval=deepcopy(retrieval))
    with patch.object(core.ProjectionDecisionTrace, 'record', return_value=None):
        unobserved = project_docs_context(retrieval=deepcopy(retrieval))
    assert observed == unobserved


def test_trace_is_bounded_and_does_not_copy_source_or_query_text():
    assert hasattr(core, 'ProjectionDecisionTrace'), 'Trace seam absent'
    diagnostics = {}
    trace = core.ProjectionDecisionTrace(diagnostics)
    secret = 'PRIVATE_DO_NOT_LOG_document_or_question'
    for i in range(1000):
        trace.record('selection', 'rejected', 'no_new_direction',
                     {'path': secret, 'content': secret, 'project_identity': secret, 'line_start': i},
                     {'evidence_id': secret, 'snippet': secret, 'line_start': i})
    public = diagnostics['decision_trace']
    assert len(public['events']) == 128
    assert public['omitted_events'] == 872
    assert public['selection_events_omitted'] == 872
    assert public['counts']['selection:no_new_direction'] == 1000
    assert secret not in json.dumps(public)
    assert public['events'][0]['candidate_key'] == public['events'][1]['candidate_key']
    assert public['events'][0]['variant_key'] != public['events'][1]['variant_key']


def test_tiny_packet_budget_has_explicit_budget_rejections():
    retrieval = _host_lookup_context_retrieval()
    project_docs_context(retrieval=retrieval, max_tokens=160)
    trace = retrieval['retrieval_diagnostics']['docs_context_projection'].get('decision_trace')
    assert trace is not None
    assert trace['counts'].get('selection:token_budget', 0) > 0
