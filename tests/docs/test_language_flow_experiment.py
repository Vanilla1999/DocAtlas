"""Ordering mechanism guards plus the unchanged real frozen flow regression."""
from __future__ import annotations
from copy import deepcopy
from unittest.mock import patch
import pytest
from experiments.language_aware_context.flow_experiment import (
    prefer_audited_diversity, flow_experiment,
)
from experiments.language_aware_context.packing_experiment import prefer_original_baseline

H={'query-lookup-1','query-lookup-2'}
P=H|{'query-original','query-anchor-1'}
C={'query-host-rewrite-1','query-host-rewrite-2'}


def weak():
    return {'snippet':'topical', 'retrieval_query_matches': {'query-lookup-1': {
        'qualified':True, 'query_origin':'host_lookup','match_ratio':.6,
        'query_text':'documentation boundary accepts request'}}}


def audited(i=1):
    return {'snippet':'canonical witness','retrieval_query_matches': {
        f'query-host-rewrite-{i}': {'qualified':True, 'relation':'audited_rewrite',
            'query_origin':'canonical_intent', 'public_parent_query_id':f'query-lookup-{i}',
            'match_ratio':1.0, 'query_text':'contract API parameters'}}}


def test_full_audited_direction_precedes_partial_topical_match():
    values=[weak(),audited()]
    expected=values[1]
    prefer_audited_diversity(values,[],P,H,C)
    assert values[0] is expected


def test_unrepresented_audited_direction_not_hidden_by_attribution():
    selected=[audited(1)]
    selected[0]['retrieval_query_matches']['query-lookup-2']={'qualified':True,'match_ratio':.5}
    values=[weak(),audited(1),audited(2)]
    expected=values[-1]
    prefer_audited_diversity(values,selected,P,H,C)
    assert values[0] is expected


@pytest.mark.parametrize('change', [
    {'qualified':False}, {'admission_only':True}, {'match_ratio':.99},
    {'relation':'generated_hint'}, {'public_parent_query_id':'query-unregistered'},
    {'derived_from_query_id':'other'}, {'query_origin':'host_lookup'},
])
def test_unverified_partial_or_derived_trace_is_not_promoted(change):
    candidate=audited()
    candidate['retrieval_query_matches']['query-host-rewrite-1'].update(change)
    values=[weak(),candidate]
    expected=list(values)
    prefer_original_baseline(expected,[],P,H,C)
    prefer_audited_diversity(values,[],P,H,C)
    assert values==expected


def test_unregistered_canonical_id_is_not_promoted():
    values=[weak(),audited()]
    expected=list(values)
    prefer_original_baseline(expected,[],P,H,set())
    prefer_audited_diversity(values,[],P,H,set())
    assert values==expected


def test_direct_complete_leader_keeps_priority():
    lead=weak()
    lead['retrieval_query_matches']['query-lookup-1']['match_ratio']=1.0
    values=[lead,audited()]
    prefer_audited_diversity(values,[],P,H,C)
    assert values[0] is lead


@pytest.mark.parametrize('hosts',[set(),{'query-lookup-1'}])
def test_zero_single_host_behavior_identical_to_previous_experiment(hosts):
    values=[weak(),audited(),{'retrieval_query_matches':{'query-original':{'qualified':True}}}]
    expected=list(values)
    prefer_original_baseline(expected,[],P,hosts,C)
    prefer_audited_diversity(values,[],P,hosts,C)
    assert values==expected


def test_ordering_does_not_mutate_evidence_or_create_authority():
    values=[weak(),audited()]
    originals=list(values)
    before=deepcopy(originals)
    selected=[]
    prefer_audited_diversity(values,selected,P,H,C)
    assert originals==before and selected==[]
    assert {id(v) for v in values}=={id(v) for v in originals}
    assert all('answer_supported' not in v and 'edit_ready' not in v for v in values)


def test_patch_restores_on_exception():
    from docmancer.docs.application import _docs_context_projection_core as core
    original=core._prefer_missing_baseline_candidate
    with pytest.raises(RuntimeError):
        with flow_experiment():
            assert core._prefer_missing_baseline_candidate is prefer_audited_diversity
            raise RuntimeError('deliberate')
    assert core._prefer_missing_baseline_candidate is original


def test_real_frozen_flow_all_witnesses_without_changing_expected_labels():
    from tests.docs.test_context_projection_boundaries import (
        test_frozen_request_flow_prefers_project_context_module_witnesses,
    )
    # Same existing integration assertion, no weakened rubric or replacement payload.
    with flow_experiment():
        test_frozen_request_flow_prefers_project_context_module_witnesses()
