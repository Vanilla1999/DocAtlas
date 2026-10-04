"""Pure tests for diagnostic accounting, not a native corpus replay."""
import importlib.util
from pathlib import Path
import sys
import pytest

# Runner imports real project execution modules only in main/capture_arm.
path = Path(__file__).with_name('next07_diagnostic_scope.py')
spec = importlib.util.spec_from_file_location('scope_diagnostics_under_test', path)
diag = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = diag
spec.loader.exec_module(diag)


SCHEMA = {'type': 'object', 'required': ['question'], 'properties': {
    'question': {'type': 'string'}, 'project_path': {'type': 'string'},
    'scope': {'enum': ['project', 'all', 'module', None]}, 'module_path': {'type': 'string'}}}


def test_public_preflight_rejects_internal_module_parameter():
    assert diag.validate_request({'question': 'q', 'module': 'legacy'}, SCHEMA)
    assert not diag.validate_request({'question': 'q', 'scope': 'module', 'module_path': 'packages/one'}, SCHEMA)


@pytest.mark.parametrize('bad', [{}, {'pairs': [['a', 'x'], ['a', 'x']]},
    {'pairs': [['a', 'x']], 'count': 49}, {'pairs': [['a']]}, {'pairs': [[1, 'x']]}])
def test_ledger_never_invents_missing_ids(bad):
    with pytest.raises(ValueError):
        diag.ledger_pairs(bad)


def record(status='supported', valid=True, audit=None):
    return {'call_attempted': True, 'valid_execution': valid, 'audit_errors': audit or [],
        'assessment': {'claims': {'required': {'status': status}}, 'optional_claims': {}, 'review_queue': []} if valid else None}


def test_eighty_case_loop_does_not_stop_on_invalid_or_quality_failure():
    cases = [{'id': str(i), 'project_group': 'g'} for i in range(80)]
    calls, saved = [], []
    def measure(case, arm):
        calls.append((case['id'], arm))
        return record('missing' if arm == 'C' else 'supported', valid=case['id'] != '2')
    rows = diag.paired_cases(cases, measure, saved.append)
    assert len(calls) == 160 and len(rows) == len(saved) == 80
    result = diag.summarize(rows, [case['id'] for case in cases])
    assert result['valid_pairs'] == 79
    assert result['candidate_verdict'] == 'REJECTED_N10_UNCHANGED'
    assert ('2', 'required') not in result['fresh_assessor_only']['lost_recognized_support']


def test_quality_rejection_does_not_prevent_diagnostic_completion():
    rows = [{'case_id': 'a', 'N': record(), 'C': record('missing')}]
    result = diag.summarize(rows, ['a'], {('a', 'required')})
    assert result['diagnostic_status'] == 'CORPUS_DIAGNOSTICS_COMPLETE'
    assert result['candidate_verdict'] == 'REJECTED_N10_UNCHANGED'
    assert result['historical_49']['lost'] == [('a', 'required')]


@pytest.mark.parametrize('bad', [record(valid=False), record(audit=['line mismatch']), record('needs_review')])
def test_historical_unknown_is_not_lost(bad):
    result = diag.summarize([{'case_id': 'a', 'N': record(), 'C': bad}], ['a', 'b'],
                            {('a', 'required'), ('b', 'required')})
    assert result['historical_49']['UNKNOWN'] == [('a', 'required'), ('b', 'required')]
    assert not result['historical_49']['lost']


def test_integrity_is_not_hidden_by_assessor_match():
    result = diag.summarize([{'case_id': 'a', 'N': record(), 'C': record(audit=['damage'])}], ['a'])
    assert result['fresh_assessor_only']['retained'] == [('a', 'required')]
    assert not result['fresh_source_valid_retained']
    assert result['audit_failure_case_ids']['C'] == ['a']


def test_duplicate_corpus_ids_rejected():
    row = {'case_id': 'a', 'N': record(), 'C': record()}
    with pytest.raises(ValueError):
        diag.summarize([row, row], ['a'])
