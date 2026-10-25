"""Compare frozen real-MCP arms; source metrics are not answer-model metrics."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

OLD = ('fixed', 'adaptive-gap-b1-v1', 'mmr-budget-v1', 'facet-cover-v1', 'facet-guarded-v1')
MIDDLE = ('facet-cover-v2', 'facet-guarded-v2', 'facet-bundled-v1')
FINAL = ('facet-bundled-cover-v1',)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--head', required=True)
    p.add_argument('--run', type=int, required=True)
    args = p.parse_args()
    refs = {**{k: {'head': 'f4a885a49494bedb65154af48403a378b1b8d208', 'run_id': 40219786995} for k in OLD},
            **{k: {'head': '95c7bf4bedeefa98a565ec44c83b5df0aa7c526d', 'run_id': 40221157968} for k in MIDDLE},
            **{k: {'head': args.head, 'run_id': args.run} for k in FINAL}}
    policies = tuple(refs)
    summaries, rows, missing, pool_errors, frozen = {}, {}, [], [], None
    for suite in ('v40', 'new16', 'fresh8'):
        for policy, ref in refs.items():
            folder = args.artifacts / f'coverage-{suite}-{policy}-{ref["run_id"]}' / 'run'
            key = suite + '/' + policy
            if not (folder / 'SUMMARY.json').exists():
                missing.append(key)
                continue
            summary = read(folder / 'SUMMARY.json')
            assert summary['head'] == ref['head'], 'unexpected tested revision'
            hashes = read(folder / 'FREEZE.json')['files']
            if frozen is None:
                frozen = hashes
            assert hashes == frozen, 'corpus, questions or gold changed between arms'
            summaries[key] = summary
            assessment = read(folder / 'ASSESSMENTS.json')
            rows[key] = {r['case_id']: r for r in assessment}
            assert len(rows[key]) == len(assessment), 'duplicate case ID'
            for family in sorted({r['family'] for r in assessment}):
                good = [r for r in assessment if r['family'] == family and not r['runtime_error']]
                observations = read(folder / family / 'server.json')['observations']
                assert len(good) == len(observations)
                for row, obs in zip(good, observations, strict=True):
                    pool = read(folder / family / (row['case_id'] + '-pool.json'))
                    expected = {s['evidence_id'] for s in pool.get('sources', [])}
                    actual = {e for section in obs['ranked_sections'] for e in section['evidence_ids']}
                    assert actual == expected, 'scored candidates differ from baseline acquisition'
        if any(suite + '/' + policy not in rows for policy in policies):
            continue
        baseline = rows[suite + '/fixed']
        for policy in policies[1:]:
            candidates = rows[suite + '/' + policy]
            assert baseline.keys() == candidates.keys()
            for cid, base in baseline.items():
                candidate = candidates[cid]
                assert (base['question'], base['search_question']) == (candidate['question'], candidate['search_question'])
                if base['candidate_fingerprint'] != candidate['candidate_fingerprint']:
                    pool_errors.append({'suite': suite, 'case': cid, 'policy': policy})
    aggregates, losses = {}, {}
    for policy in policies:
        items = [r for k, group in rows.items() if k.endswith('/' + policy) for r in group.values()]
        aggregates[policy] = {
            'cases': len(items), 'complete_documented': sum(r['passed'] for r in items if r['answerability'] != 'unanswerable'),
            'documented_cases': sum(r['answerability'] != 'unanswerable' for r in items),
            'retained_facts': sum(c['covered'] for r in items for c in r['claims']),
            'required_facts': sum(len(r['claims']) for r in items),
            'strict_negatives_passed': sum(r['passed'] for r in items if r['answerability'] == 'unanswerable'),
            'model_visible_tokens': sum(r.get('tokens', 0) for r in items),
            'prepared_input_tokens': sum(r.get('prepared_input_tokens', 0) for r in items),
            'runtime_errors': sum(r['runtime_error'] for r in items),
            'integrity_errors': sum(not r['integrity'] for r in items),
            'seconds_total': sum(r['seconds'] for r in items)}
        losses[policy] = []
        for suite in ('v40', 'new16', 'fresh8'):
            if suite + '/' + policy not in rows:
                continue
            for reference in ('fixed', 'adaptive-gap-b1-v1'):
                for cid, base in rows.get(suite + '/' + reference, {}).items():
                    candidate = rows[suite + '/' + policy][cid]
                    old = {c['id'] for c in base['claims'] if c['covered']}
                    new = {c['id'] for c in candidate['claims'] if c['covered']}
                    negative_regression = base['answerability'] == 'unanswerable' and base['passed'] and not candidate['passed']
                    if old - new or negative_regression:
                        losses[policy].append({'suite': suite, 'case': cid, 'reference': reference,
                                               'lost_facts': sorted(old - new), 'negative_regression': negative_regression})
    eligible = [p for p in policies[2:] if not missing and not pool_errors and not losses[p]
                and aggregates[p]['cases'] == 64 and not aggregates[p]['runtime_errors'] and not aggregates[p]['integrity_errors']]
    best = min(eligible, key=lambda p: (-aggregates[p]['complete_documented'], -aggregates[p]['retained_facts'],
                                       aggregates[p]['model_visible_tokens'], aggregates[p]['seconds_total'])) if eligible else None
    result = {'head': args.head, 'policy_sources': refs, 'summaries': summaries, 'aggregate': aggregates,
              'fact_losses': losses, 'missing_arms': missing, 'candidate_pool_mismatches': pool_errors,
              'scored_candidate_identity_checked': True, 'identical_frozen_inputs': True,
              'eligible_new_policies': eligible, 'recommended_by_evidence_gate': best,
              'new_search_calls': 64, 'reused_search_calls': 512, 'total_stdio_search_calls': 576,
              'total_baseline_public_calls': 576, 'provider_usage': None, 'answer_generation_tested': False,
              'all_suites_are_known_regressions': True, 'default_promoted': False}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'PAIRED.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'summaries'}, ensure_ascii=False, indent=2))
    assert not missing and not pool_errors, 'incomplete or unmatched real-MCP experiment'
    assert eligible, 'no non-regressing replacement; do not promote'


if __name__ == '__main__':
    main()
