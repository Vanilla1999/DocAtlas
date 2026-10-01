"""Use actual indexed source preparation, never injected ownership approvals."""
from dataclasses import replace
import json
import pytest

from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.domain.evidence_set_validation import validate_evidence_set
from tests.docs._reference_binding_fixtures import capture_reference_case


@pytest.fixture
def indexed(tmp_path,monkeypatch):
    observed=[];actual=SourceReferenceContext.prepare
    def record(self,*args,**kwargs):
        result=actual(self,*args,**kwargs)
        if result:observed.append((self,result))
        return result
    monkeypatch.setattr(SourceReferenceContext,'prepare',record)
    cap=capture_reference_case(tmp_path,{'Guide.md':'# OrbitResolver\n\n'
        'OrbitResolver selects the first index.\n\n'
        'This rule prevents dependency confusion.\n'},
        'How does OrbitResolver choose candidate versions and why?')
    assert observed
    return cap,observed


def test_real_prepared_source_exposes_structural_sets_without_answer_approval(indexed):
    cap,observed=indexed
    context=observed[-1][0]
    sets=getattr(context,'dependency_sets',{})
    assert sets
    assert any(edge.kind=='cause' for bundle in sets.values() for edge in bundle.edges)
    for bundle in sets.values():
        assert validate_evidence_set(bundle,context.need_contracts,context.dependency_sources)==()
    wire=json.dumps(cap['public_payload'])
    assert all(key not in wire for key in ('_evidence_sets','raw_document','proposed_need_ids','dependency_sources'))
    assert all(cap['public_payload'][key] is False for key in ('answer_supported','answer_available','edit_ready'))


def test_preparation_ignores_forged_candidate_scope_and_records_a_reason(indexed):
    from docmancer.docs.application.source_dependency_preparation import prepare_dependency_sets
    _,observed=indexed;context,rows=observed[-1]
    row=rows[0].model_copy(deep=True)
    row.metadata['_reference_evidence']['source']['scope']['snapshot_id']='forged-snapshot'
    sets=prepare_dependency_sets(context,[row],context.need_contracts)
    assert not sets
    assert 'source_identity_mismatch' in context.dependency_rejections[str(row.source)]


def test_preparation_reuses_raw_snapshot_without_another_store_read(indexed,monkeypatch):
    from docmancer.docs.application.source_dependency_preparation import prepare_dependency_sets
    _,observed=indexed;context,rows=observed[-1]
    def forbidden(*args,**kwargs):raise AssertionError('dependency preparation reread source')
    monkeypatch.setattr(context.store,'_connect',forbidden)
    monkeypatch.setattr('builtins.open',forbidden)
    sets=prepare_dependency_sets(context,rows,context.need_contracts)
    assert sets


def test_invalid_replay_clears_previously_valid_window_proposal(indexed):
    from docmancer.docs.application.source_dependency_preparation import prepare_dependency_sets
    _,observed=indexed;context,rows=observed[-1];row=rows[0].model_copy(deep=True)
    evidence=row.metadata['_reference_evidence']
    window=(str(row.source),evidence['char_start'],evidence['char_end'])
    assert context.dependency_windows.get(window)
    evidence['source']['scope']['snapshot_id']='foreign'
    assert not prepare_dependency_sets(context,[row],context.need_contracts)
    assert not context.dependency_windows.get(window)
