"""Read-only paired review of fixed-path benchmark captures and test logs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
from statistics import median


def read(path):
    return json.loads(path.read_text())


def tests(path):
    text = path.read_text()
    failed = sorted(set(re.findall(r'^FAILED (\S+)', text, re.M)))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'terminal_summary': text.splitlines()[-1], 'failed_nodes': failed,
            'failed_by_module': dict(Counter(n.split('::')[0] for n in failed))}


def compact(row):
    return {'id': row['id'], 'project': row['project'], 'answerability': row['answerability'],
            'sufficiency': row.get('assessment', {}).get('context_sufficiency'),
            'required_supported': row.get('assessment', {}).get('required_supported'),
            'required_count': row.get('assessment', {}).get('required_count'),
            'claim_statuses': {k: v['status'] for k, v in row.get('assessment', {}).get('claims', {}).items()},
            'admission_tokens': row.get('admission_tokens'), 'source_count': row.get('source_count'),
            'answer_supported': row.get('answer_supported'), 'edit_ready': row.get('edit_ready'),
            'validation_errors': row.get('validation_errors', []), 'error': row.get('error'),
            'first_observed_loss': row.get('stage_assessment', {}).get('first_observed_loss', {}),
            'stage_required_supported': {k: v['required_supported'] for k, v in
                row.get('stage_assessment', {}).get('stages', {}).items()},
            'incomplete_stage_observations': [k for k, v in
                row.get('stage_assessment', {}).get('stages', {}).items() if not v['complete']]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--coarse', type=Path, required=True)
    parser.add_argument('--no-boosts', type=Path, required=True)
    parser.add_argument('--baseline-no-boosts', type=Path)
    parser.add_argument('--baseline-tests', type=Path, required=True)
    parser.add_argument('--candidate-tests', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = {'baseline': args.baseline, 'candidate': args.candidate,
              'coarse': args.coarse, 'no-boosts': args.no_boosts}
    if args.baseline_no_boosts:
        inputs['baseline-no-boosts'] = args.baseline_no_boosts
    data = {name: read(path / 'rows.json') for name, path in inputs.items()}
    baseline = {r['id']: r for r in data['baseline'] if r['arm'] == 'native'}
    comparisons = {}
    for name, rows in data.items():
        for arm in sorted({r['arm'] for r in rows}):
            subset = [r for r in rows if r['arm'] == arm]
            wins, losses, facts_lost, facts_gained = [], [], [], []
            delta_by_project = defaultdict(list)
            for row in subset:
                old = baseline[row['id']]
                if row.get('error') or old.get('error'):
                    continue
                a, b = old['assessment'], row['assessment']
                delta = int(b['context_sufficiency'] == 'sufficient') - int(a['context_sufficiency'] == 'sufficient')
                if row['answerability'] == 'within_budget':
                    delta_by_project[row['project']].append(delta)
                    if delta > 0: wins.append(row['id'])
                    if delta < 0: losses.append(row['id'])
                for claim, status in a['claims'].items():
                    if status['status'] == 'supported' and b['claims'][claim]['status'] != 'supported':
                        facts_lost.append({'id': row['id'], 'claim': claim, 'old': status['status'],
                                           'new': b['claims'][claim]['status']})
                    if status['status'] != 'supported' and b['claims'][claim]['status'] == 'supported':
                        facts_gained.append({'id': row['id'], 'claim': claim})
            project_means = [sum(v) / len(v) for v in delta_by_project.values()]
            rng = random.Random(20261002)
            draws = sorted(sum(rng.choices(project_means, k=len(project_means))) / len(project_means)
                           for _ in range(10000)) if project_means else []
            valid = [r for r in subset if 'error' not in r]
            costs = sorted(r['admission_tokens'] for r in valid)
            elapsed = sorted(r['seconds'] for r in valid)
            comparisons[name + '/' + arm] = {
                'cases': len(subset), 'positive_sufficient': sum(r['answerability'] == 'within_budget'
                    and r['assessment']['context_sufficiency'] == 'sufficient' for r in valid),
                'sufficiency_counts': dict(Counter(r['assessment']['context_sufficiency'] for r in valid)),
                'errors': [r for r in subset if 'error' in r], 'wins': wins, 'losses': losses,
                'facts_gained': facts_gained, 'facts_lost': facts_lost,
                'project_cluster_bootstrap_95': [draws[250], draws[9749]] if draws else None,
                'cost_p50_p95': [median(costs), costs[int(.95 * (len(costs) - 1))]] if costs else None,
                'latency_p50_p95_single_pass': [median(elapsed), elapsed[int(.95 * (len(elapsed) - 1))]] if elapsed else None,
                'budget_violations': [r['id'] for r in valid if r['admission_tokens'] > 800 or r['source_count'] > 3],
                'validation_errors': [r['id'] for r in valid if r['validation_errors']],
                'rows': [compact(r) for r in subset],
            }
    base_tests, candidate_tests = tests(args.baseline_tests), tests(args.candidate_tests)
    result = {'schema_version': 1, 'baseline_head': '2ffb84fe',
              'inputs': {name: {'path': str(path), 'rows_sha256': hashlib.sha256((path / 'rows.json').read_bytes()).hexdigest()}
                         for name, path in inputs.items()},
              'comparisons': comparisons,
              'tests': {'baseline': base_tests, 'candidate': candidate_tests,
                        'new_failures': sorted(set(candidate_tests['failed_nodes']) - set(base_tests['failed_nodes'])),
                        'resolved_failures': sorted(set(base_tests['failed_nodes']) - set(candidate_tests['failed_nodes']))},
              'limitations': ['Exposed corpus, eight correlated project groups; bootstrap is diagnostic, not acceptance proof.',
                              'No independently adjudicated semantic precision or LLM reader outputs.',
                              'Coarse index is UNVALIDATED and used only in an external experimental store.',
                              'Single-pass latency with concurrent experiments is not a performance benchmark.',
                              'needs_review is never counted as sufficient; no formatting equivalence overrides added.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: {field: v[field] for field in ('cases', 'positive_sufficient', 'wins', 'losses', 'facts_lost')}
                      for k, v in comparisons.items()}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
