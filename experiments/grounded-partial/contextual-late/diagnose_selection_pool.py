"""Post-hoc loss localization, NOT another selector or attainable budget score.

Observe the exact bindable qualified pool passed to retain_extend, return the
unchanged baseline, and only afterward evaluate literal witness availability.
Unbounded unions may exceed 800 tokens / three sources and overlap. They must
never be presented as model-visible packets, feasible scores or promotion.
No policy tuning, inference, hidden questions, or production modifications.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
from unittest.mock import patch

import run_selection as runner
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import _docs_source
from eval.evidence_quality_v2.run import load_protocol, registry_for
from eval.evidence_quality_v2.semantic import assess_context


def union_sources(sources):
    """Unique literal spans with independent diagnostic identities, no packing."""
    unique = {}
    for original in sources:
        source = deepcopy(original)
        identity = (source.get('path_or_url'), source.get('line_start'),
                    source.get('line_end'), source.get('snippet'))
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        source['evidence_id'] = 'diag-' + key
        unique[key] = source
    # Strip runtime-private fields with the ordinary serializer. The result is
    # an unbounded diagnostic union, not an admitted or truthful coverage claim.
    return _payload(list(unique.values()), query_plan={'queries': [], 'broad_context_only': True})['sources']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    _, cases, manifest = load_protocol()
    cases = {c['id']: c for c in cases}
    pools = []

    def observe_pool(baseline, candidates, **kwargs):
        pools.append({'question': kwargs['question'], 'baseline': deepcopy(baseline),
                      'candidates': deepcopy(candidates)})
        return deepcopy(baseline)

    spec = importlib.util.spec_from_file_location('pool_factorial_evaluator', runner.HERE.parent / 'research-suite/evaluate.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    with patch.object(runner, 'retain_extend', observe_pool):
        rows, observations = runner.execute_lane(evaluator, args.output / 'unchanged-replay', False)
    prior = {(r['id'], r['variant']): r for r in json.loads(lzma.decompress((runner.HERE / 'results/raw-results.json.xz').read_bytes()))}
    pool_iterator = iter(pools)
    diagnostics = []
    for row, observation in zip(rows, observations):
        case = cases[row['id']]
        key = row['id'], row['variant']
        assert runner.spans(row['replay']) == runner.spans(prior[key]['replay']), key
        assert row['replay_assessment'] == prior[key]['replay_assessment'], key
        assert not row['replay_errors'], key
        if observation['base'].get('sources'):
            pool = next(pool_iterator)
            assert pool['question'] == observation['question'], key
            assert len(pool['candidates']) == observation['qualified_variants'], key
            assert [(x['source']['path_or_url'], x['source']['snippet']) for x in pool['baseline']] == runner.spans(observation['base']), key
        else:
            # If this assumption ever changes, stop rather than omit evidence.
            assert observation['qualified_variants'] == 0, key
            pool = {'baseline': [], 'candidates': []}
        raw_sources = []
        for raw in observation['input']['context_pack']:
            source = _docs_source(raw, display_snippet=raw['content'])
            source.update(project_identity=raw['project_identity'], authority=raw['authority'],
                          scope=raw['doc_scope'], line_start=raw['line_start'], line_end=raw['line_end'])
            raw_sources.append(source)
        qualified = [item['source'] for item in pool['candidates']]
        for source in qualified:
            assert any(source['path_or_url'] == raw['path'] and source['snippet'] in raw['content']
                       for raw in observation['input']['context_pack']), key
        sets = {'raw_top20_union': union_sources(raw_sources),
                'qualified_variant_union': union_sources(qualified),
                'qualified_plus_final_expansion_union': union_sources([*qualified, *row['replay'].get('sources', [])])}
        assessments = {name: assess_context(case, {'sources': sources}, registry_for(case['project_group'], manifest))
                       for name, sources in sets.items()}
        diagnostics.append({'id': row['id'], 'retrieval': row['variant'],
                            'question': case['question'], 'answerability': case['answerability'],
                            'input_sha256': observation['input_sha256'],
                            'qualified_variants': len(qualified),
                            'final_assessment': row['replay_assessment'],
                            'union_assessments': assessments, 'unbounded_diagnostic_sources': sets})
    assert next(pool_iterator, None) is None
    assert len(diagnostics) == 320
    sufficient = lambda assessment: assessment['context_sufficiency'] == 'sufficient'
    summary = {}
    for name in sorted({d['retrieval'] for d in diagnostics}):
        positives = [d for d in diagnostics if d['retrieval'] == name and d['answerability'] == 'within_budget']
        final = {d['id'] for d in positives if sufficient(d['final_assessment'])}
        raw = {d['id'] for d in positives if sufficient(d['union_assessments']['raw_top20_union'])}
        available = {d['id'] for d in positives if sufficient(d['union_assessments']['qualified_plus_final_expansion_union'])}
        summary[name] = {'raw_top20_literal_available': len(raw),
                         'qualified_and_expanded_literal_available': len(available),
                         'final_sufficient': len(final),
                         'raw_available_qualified_unconfirmed': sorted(raw - available),
                         'qualified_available_final_unconfirmed': sorted(available - final),
                         'raw_top20_unconfirmed': sorted({d['id'] for d in positives} - raw)}
        assert final <= available, name
    validation = {'rows': 320, 'historical_controls_reproduced': 320,
                  'nonempty_pools_observed': len(pools), 'diagnostic_only': True,
                  'union_is_unbounded_not_an_800_token_result': True,
                  'selection_policy_changed': False, 'holdout_opened': False,
                  'answer_model_run': False, 'original_replay_audit_errors': 0}
    runner.save(args.output / 'summary.json', summary)
    runner.save(args.output / 'validation.json', validation)
    runner.save(args.output / 'questions.json', diagnostics)
    (args.output / 'raw-results.json.xz').write_bytes(lzma.compress(json.dumps(diagnostics, ensure_ascii=False).encode()))
    print('POOL_DIAGNOSTIC_BEGIN', flush=True)
    print(json.dumps({'summary': summary, 'validation': validation}, ensure_ascii=False, indent=2), flush=True)
    print('POOL_DIAGNOSTIC_END', flush=True)


if __name__ == '__main__':
    main()
