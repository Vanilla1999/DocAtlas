"""Known development regression and ordering controls; not independent quality."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import pytest

from experiments.language_aware_context.packing_experiment import (
    packing_experiment, prefer_original_baseline,
)
from docmancer.docs.application.context_candidate_ranking import (
    _prefer_missing_baseline_candidate as baseline_preference,
)


def candidate(*query_ids: str) -> dict:
    return {'retrieval_query_matches': {q: {'qualified': True} for q in query_ids}}


def test_single_lookup_does_not_promote_optional_anchor():
    strongest = candidate('query-lookup-1')
    incidental = candidate('query-anchor-1', 'query-lookup-1')
    values = [strongest, incidental]
    prefer_original_baseline(values, [],
        {'query-original', 'query-anchor-1', 'query-lookup-1'}, {'query-lookup-1'}, set())
    assert values[0] is strongest


def test_actual_original_evidence_is_still_protected():
    strongest = candidate('query-lookup-1')
    original = candidate('query-original')
    values = [strongest, original]
    prefer_original_baseline(values, [],
        {'query-original', 'query-anchor-1', 'query-lookup-1'}, {'query-lookup-1'}, set())
    assert values[0] is original


@pytest.mark.parametrize('hosts', [set(), {'query-lookup-1', 'query-lookup-2'}])
@pytest.mark.parametrize('already_selected', [False, True])
def test_zero_and_multiple_lookups_are_exactly_unchanged(hosts, already_selected):
    values = [candidate('query-hint-1'), candidate('query-anchor-1'),
              candidate('query-original'), candidate(*sorted(hosts))]
    selected = [candidate(*sorted(hosts))] if already_selected else []
    public = {'query-original', 'query-anchor-1'} | hosts
    expected = list(values)
    baseline_preference(expected, selected, public, hosts, {'query-intent-1'})
    prefer_original_baseline(values, selected, public, hosts, {'query-intent-1'})
    assert all(a is b for a, b in zip(values, expected, strict=True))


def test_canonical_fallback_is_not_disabled():
    values = [candidate('query-hint-1'), candidate('query-intent-1')]
    target = values[1]
    prefer_original_baseline(values, [], {'query-original', 'query-lookup-1'},
                             {'query-lookup-1'}, {'query-intent-1'})
    assert values[0] is target


def test_adapter_only_reorders_existing_objects():
    values = [candidate('query-lookup-1'), candidate('query-original')]
    selected = [candidate('query-anchor-1')]
    originals = list(values)
    before = deepcopy((values, selected))
    public = {'query-original', 'query-anchor-1', 'query-lookup-1'}
    public_before = public.copy()
    prefer_original_baseline(values, selected, public, {'query-lookup-1'}, set())
    assert {id(v) for v in values} == {id(v) for v in originals}
    assert originals == before[0] and selected == before[1] and public == public_before


def test_admission_only_original_is_not_promoted():
    values = [candidate('query-lookup-1'), candidate('query-original')]
    strongest = values[0]
    values[1]['retrieval_query_matches']['query-original']['admission_only'] = True
    prefer_original_baseline(values, [], {'query-original', 'query-lookup-1'},
                             {'query-lookup-1'}, set())
    assert values[0] is strongest


def test_patch_restores_on_error_and_nested_exit():
    from docmancer.docs.application import _docs_context_projection_core as core
    previous = core._prefer_missing_baseline_candidate
    with pytest.raises(RuntimeError, match='deliberate'):
        with packing_experiment():
            with packing_experiment():
                assert core._prefer_missing_baseline_candidate is prefer_original_baseline
            assert core._prefer_missing_baseline_candidate is prefer_original_baseline
            raise RuntimeError('deliberate')
    assert core._prefer_missing_baseline_candidate is previous


def test_real_handler_retains_complete_client_example_with_lookup():
    # The corpus and claim are the pre-existing viewed development case. Gold
    # clauses are evaluated after real execution and never passed to the adapter.
    from experiments.language_aware_context.baseline_probe import run
    from experiments.language_aware_context.ci_diagnostic import TASKS, CLAIMS, claim_check
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'eval/evidence_quality_v2/source-manifest.json').read_text())
    task_id, project, question, lookup = next(t for t in TASKS if t[0] == 'httpx-disable-client')
    spec = {'schema_version': 1, 'sources': [
        {'path': row['path'], 'sha256': row['sha256']}
        for row in manifest['sources'] if row['project'] == project]}
    with packing_experiment():
        result = run(root / 'eval/evidence_quality_v2/sources' / project,
                     spec, {'question': question, 'lookup_queries': [lookup]})
    assert result['status'] == 'EXECUTED' and result['audit_errors'] == []
    assert 0 < result['budget_tokens'] <= 800
    assert result['payload'].get('answer_supported') is not True
    assert result['payload'].get('edit_ready') is not True
    assert len(result['payload'].get('sources', [])) <= 3
    assert claim_check(result, *CLAIMS[task_id])['status'] == 'COMPLETE'
