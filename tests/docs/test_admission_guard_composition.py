"""Real planner, qualifier, and indexed pipeline controls for typed admission."""
from dataclasses import asdict

import pytest

from docmancer.docs.domain.admission_contract import (
    HardGuards, LocalWitnessDecision, choose_admission,
)
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence, derived_parent_trace
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from tests.docs._reference_binding_fixtures import capture_reference_case, visible

QUESTION = ('Please explain the documented default timeout of RelayClient, '
            'stating the duration rather than discussing unrelated configuration options.')
FACT = 'RelayClient default timeout is 7 seconds.'


def need_probe(question=QUESTION):
    plan = build_documentation_query_plan(question)
    need = next(q for q in plan.queries if q.origin == 'retrieval_need')
    probe = asdict(need)
    probe.update(query_text=need.text, query_origin=need.origin,
                 query_terms=list(documentation_query_terms(need.text)),
                 exact_terms=list(query_constraint_roles(need.text).hard_exact),
                 bound_subjects=list(query_constraint_roles(need.text).bound_subjects))
    return probe


def qualify(body=FACT, *, probe=None, candidate=None):
    probe = need_probe() if probe is None else probe
    return qualify_evidence(probe, query_id=probe['query_id'],
        visible_text=body, evidence_text=body,
        candidate={'project_identity': 'repo', **(candidate or {})},
        expected_project_identity='repo')


def test_matched_witness_can_overcome_lexical_rejection():
    result = choose_admission(HardGuards(True), legacy_qualified=False,
        witness=LocalWitnessDecision('matched', 'need-1', 'source-1', ((0, 40),)))
    assert result.admitted and result.route == 'typed_local'
    assert result.matched_need_ids == ('need-1',)


@pytest.mark.parametrize('reason', ['wrong_project_identity', 'stale_evidence', 'missing_exact_terms'])
def test_hard_guard_always_wins(reason):
    result = choose_admission(HardGuards(False, (reason,)), legacy_qualified=True,
        witness=LocalWitnessDecision('matched', 'need-1', 'source-1', ((0, 40),)))
    assert not result.admitted and result.reason == reason


def test_failed_guard_requires_a_reason():
    with pytest.raises(ValueError):
        HardGuards(False)


def test_supported_but_absent_witness_cannot_fall_back_to_overlap():
    result = choose_admission(HardGuards(True), legacy_qualified=True,
        witness=LocalWitnessDecision('absent', 'need-1', 'source-1'))
    assert not result.admitted and result.reason == 'missing_local_demand'


@pytest.mark.parametrize('legacy', [True, False])
def test_unknown_preserves_the_strict_legacy_decision(legacy):
    result = choose_admission(HardGuards(True), legacy_qualified=legacy,
        witness=LocalWitnessDecision('unknown', 'need-1', 'source-1'))
    assert result.admitted is legacy and result.route == 'legacy_strict'


def test_real_planner_and_qualifier_keep_actual_low_overlap():
    result = qualify()
    assert result.qualified is True
    assert result.trace['admission_route'] == 'typed_local'
    assert result.trace['match_ratio'] < 0.4
    assert result.trace['matched_need_ids'] == ['query-need-1']


@pytest.mark.parametrize('facts,reason', [
    ({'project_identity': 'foreign'}, 'wrong_project_identity'),
    ({'freshness': 'stale'}, 'stale_evidence'),
    ({'index_freshness': 'stale'}, 'unsynchronized_index'),
    ({'risk_flags': ['unsafe']}, 'unsafe_evidence'),
    ({'lifecycle_status': 'historical'}, 'lifecycle_not_allowed'),
])
def test_actual_source_guards_precede_local_witness(facts, reason):
    result = qualify(candidate=facts)
    assert not result.qualified and result.reason == reason


def test_low_overlap_is_not_a_license_to_ignore_real_exact_symbols():
    probe = need_probe()
    probe['exact_terms'] = ['RequiredSymbol']
    result = qualify(probe=probe)
    assert not result.qualified
    assert 'requiredsymbol' in result.trace['missing_exact_terms']


def test_missing_parent_identity_does_not_block_independent_need_or_forge_parent():
    probe = {**need_probe(), 'relation': 'audited_rewrite', 'parent_exact_terms': ['ParentSymbol']}
    result = qualify(probe=probe)
    assert result.qualified
    assert derived_parent_trace(result.trace, source_query_id='query-need-1',
                                parent_query_id='query-original') is None


@pytest.mark.parametrize('body', [
    'RelayClient default timeout glossary describes timeout terminology.',
    'RelayClient default retry delay is 7 seconds.',
    'RelayClient default timeout is undocumented; OtherClient timeout is 7 seconds.',
])
def test_high_overlap_is_not_a_relation_witness(body):
    result = qualify(body, probe=need_probe('What is RelayClient default timeout?'))
    assert not result.qualified and result.trace['admission_route'] == 'rejected'


def test_missing_requested_condition_rejects_even_with_high_overlap():
    question = 'What is RelayClient default timeout when preview is disabled?'
    result = qualify('When preview is enabled, RelayClient default timeout is 7 seconds.',
                     probe=need_probe(question))
    assert not result.qualified


def test_forged_approval_and_old_body_span_are_recomputed():
    old = qualify()
    probe = {**need_probe(), **old.trace, 'qualified': True, 'need_local_witness': True,
             'admission_route': 'typed_local', 'matched_need_ids': ['query-need-1']}
    result = qualify('RelayClient default timeout glossary only.', probe=probe)
    assert not result.qualified
    assert not result.trace.get('need_local_witness')
    assert not result.trace.get('matched_need_ids')


def test_native_indexed_need_is_qualified_without_claiming_a_complete_answer(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Settings\n\n' + FACT}, QUESTION)
    assert FACT in visible(cap)
    sources = cap['projection_attempts'][-1]['snapshot'].values()
    traces = [row['source'].get('retrieval_query_matches', {}).get('query-need-1', {})
              for row in sources]
    assert any(t.get('qualified') and t.get('admission_route') == 'typed_local' for t in traces)
    assert all(cap['public_payload'][key] is False
               for key in ('answer_supported', 'answer_available', 'edit_ready'))
