"""Offline streaming gzip trace checks and selected old-DEV paired summaries.

No inference or scoring is performed by this CLI. score_run in run_campaign is
an explicit, reusable independent offline scoring API for completed MCP runs.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from run_campaign import ARMS, BLIND, dev_cases, load, module, save, sha, validate_run

STAGES = ('raw_checked', 'post_prune', 'eligible')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in {'evidence_id', 'source_uri'}}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def inspect_trace(path, run, budget, expected_arm='B'):
    """Stream full events; retain compact checks/identities, never full snapshots.

    Recomputes canonical digests AND verifies normalization against raw evidence.
    Reuses step16's unambiguous question/project/chronology binding offline.
    step17 study traces are labeled 'step17_<selection mode>'; the caller passes
    the label it expects, so a wrong-arm reuse fails closed.
    """
    path = Path(path)
    events, errors = [], []
    scoring = []
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                    if event.get('arm') != expected_arm or event.get('portion') != 1:
                        raise ValueError('wrong arm or portion')
                    kind = event['event']
                    if kind == 'pool_manifest':
                        for field, raw in (('normalized_rows', 'raw_rows'), ('normalized_snapshots', 'raw_snapshots')):
                            if digest(event[field]) != event[field + '_sha256'] or normalized(event[raw]) != event[field]:
                                raise ValueError('canonical manifest/normalization mismatch')
                        if event['row_count'] != len(event['normalized_rows']):
                            raise ValueError('row count mismatch')
                        event['normalized_rows'] = [{k: row[k] for k in ('project_identity', 'path_or_url') if k in row}
                                                    for row in event['normalized_rows']]
                        for field in ('raw_rows', 'raw_snapshots', 'normalized_snapshots'):
                            event.pop(field)
                    elif kind == 'qwen_scoring':
                        receipt = event.get('actual_scorer_receipt')
                        if receipt is not None and digest(receipt) != event.get('actual_scorer_receipt_sha256'):
                            raise ValueError('actual scorer receipt hash mismatch')
                        scoring.append({k: event.get(k) for k in ('run_id', 'cache_hits', 'cache_misses', 'actual_scorer_receipt')})
                        event = {k: event[k] for k in ('run_id', 'original_question', 'budget', 'event')}
                    elif kind == 'qwen_failure':
                        errors.append(f'line {number}: qwen_failure')
                    else:
                        # Keep binding metadata, not decision row bodies.
                        event = {k: event[k] for k in ('run_id', 'original_question', 'budget', 'event')}
                    events.append(event)
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(f'line {number}: {exc}')
    except (OSError, EOFError) as exc:
        errors.append(f'trace unreadable: {exc}')
    paired = module('step17_paired_report', BLIND / 'step16-qwen-delivery' / 'paired_report.py')
    questions = {c['id']: c['question'] for c in dev_cases(run['selected_cases'])}
    bound, binding_errors = paired.bind(events, run, questions, budget)
    errors.extend(binding_errors)
    expected = {(c, cid) for c in run['corpora'] for cid in run['selected_cases']}
    if set(bound) != expected:
        errors.append('trace case universe incomplete/unexpected')
    stages = {}
    for identity in sorted(expected):
        group = bound.get(identity) or []
        stages['/'.join(identity)] = {}
        for stage in STAGES:
            matches = [e for e in group if e['event'] == 'pool_manifest' and e['stage'] == stage]
            if len(matches) != 1:
                errors.append(f'{identity}: expected exactly one {stage} manifest')
                continue
            stages['/'.join(identity)][stage] = {k: matches[0][k] for k in
                ('normalized_rows_sha256', 'normalized_snapshots_sha256', 'row_count')}
        if sum(e['event'] == 'qwen_scoring' for e in group) != 1:
            errors.append(f'{identity}: missing/duplicate scoring event')
    fresh = [e['actual_scorer_receipt'] for e in scoring if e['actual_scorer_receipt'] is not None]
    def total(field):
        values = [e.get(field) for e in scoring]
        return sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
    runtime = {'scoring_events': len(scoring), 'cache_hits': total('cache_hits'), 'cache_misses': total('cache_misses'),
               'fresh_receipts': len(fresh), 'cold_full_cost': None,
               'note': 'Only actual fresh receipts are summed; cache-origin cost excluded. Durations are not wall time.'}
    for field in ('model_forwards', 'model_pairs', 'model_input_tokens', 'model_loads',
                  'inference_seconds', 'total_seconds', 'asset_verification_seconds'):
        values = [r.get(field) for r in fresh]
        runtime[field] = sum(values) if all(isinstance(v, (int, float)) for v in values) else None
    return {'stages': stages, 'errors': errors, 'runtime': runtime}


def summarize_run(root, name, config):
    dest = root / name
    env = config['environments'][name]
    budget = int(env['DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS'])
    result = {'valid': False, 'errors': [], 'budget': budget}
    try:
        run = validate_run(dest, config['selected_cases'])
        marker = load(dest / 'COMPLETED.json')
        if marker.get('status') != 'COMPLETED' or marker['config'] != env:
            raise ValueError('invalid COMPLETED config')
        if any(sha(dest / p) != h for p, h in marker['artifacts'].items()):
            raise ValueError('COMPLETED artifact hash mismatch')
        if any(run['server_environment'].get(k) != v for k, v in env.items()):
            raise ValueError('actual server environment differs from declaration')
        if run['source_tree']['code_manifest_sha256'] != config['code_manifest_sha256'] or run['work_root'] != config['work_root']:
            raise ValueError('run code/store differs from declared campaign')
        score = load(dest / 'score.json')
        if score['questions_sha256'] != run['questions_sha256'] or score['scorer_sha256'] != sha(BLIND / 'score.py'):
            raise ValueError('score provenance mismatch')
        cases = score['cases']
        expected = {(c, cid) for c in ('L0', 'L2') for cid in config['selected_cases']}
        keys = [(c['corpus'], c['case_id']) for c in cases]
        if len(keys) != len(set(keys)) or set(keys) != expected or any(c['split'] != 'dev' for c in cases):
            raise ValueError('scored case universe incomplete/unexpected')
        if score['anomalies'] or any(c['anomalies'] for c in cases):
            raise ValueError('scorer anomalies')
        for c in cases:
            facts = c['facts']
            if len(facts) != c['facts_total'] or len({f['fact_id'] for f in facts}) != len(facts) or any(type(f['found']) is not bool for f in facts):
                raise ValueError('missing/duplicate fact verdicts')
            if any(type(c[k]) is not int or c[k] < 0 for k in ('o200k_tokens', 'utf8_bytes')):
                raise ValueError('missing actual wire metrics')
        expected_arm = f'step17_{name.rsplit("-", 1)[0] if name.rsplit("-", 1)[0] in ("control", "no_stop", "no_redundancy", "relative") else "control"}'
        trace = inspect_trace(root / f'{name}.jsonl.gz', run, budget, expected_arm=expected_arm)
        result.update(trace)
        result.update(cases=len(cases), complete_dev_cases=len(expected),
                      full_dev_universe=len(expected) == 2 * len(dev_cases()),
                      all_found=sum(c['all_found'] for c in cases),
                      facts_found=sum(c['facts_found'] for c in cases), facts_total=sum(c['facts_total'] for c in cases),
                      o200k_tokens=sum(c['o200k_tokens'] for c in cases), utf8_bytes=sum(c['utf8_bytes'] for c in cases),
                      over_budget=[list(k) for k, c in zip(keys, cases) if max(c['o200k_tokens'], (c['utf8_bytes'] + 3) // 4) > budget],
                      found=[list((c['corpus'], c['case_id'], f['fact_id'])) for c in cases for f in c['facts'] if f['found']],
                      fact_universe=[list((c['corpus'], c['case_id'], f['fact_id'])) for c in cases for f in c['facts']],
                      provenance={k: score[k] for k in ('questions_sha256', 'oracle_sha256', 'scorer_sha256')},
                      code_manifest_sha256=run['source_tree']['code_manifest_sha256'],
                      work_root=run['work_root'], wall_seconds=run['wall_seconds'],
                      offline_scoring_seconds=marker.get('offline_scoring_seconds'))
        result['valid'] = not result['errors'] and not result['over_budget']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['errors'].append(str(exc))
    return result


def summarize_campaign(root):
    root = Path(root).resolve()
    config = load(root / 'campaign.json')['config']
    variants = {f'{arm}-{budget}': summarize_run(root, f'{arm}-{budget}', config)
                for budget in config['budgets'] for arm in config['arms']}
    comparisons = {}
    for budget in config['budgets']:
        control = variants.get(f'control-{budget}', {})
        for arm in config['arms']:
            if arm == 'control':
                continue
            candidate = variants[f'{arm}-{budget}']
            required = ('raw_checked',) if arm in ('prune_off', 'prune_union') else STAGES
            checks = []
            for identity in sorted(set(control.get('stages', {})) | set(candidate.get('stages', {}))):
                for stage in required:
                    a = control.get('stages', {}).get(identity, {}).get(stage)
                    b = candidate.get('stages', {}).get(identity, {}).get(stage)
                    checks.append({'case': identity, 'stage': stage, 'equal': a is not None and a == b})
            valid = bool(control.get('valid') and candidate.get('valid') and checks and all(c['equal'] for c in checks)
                         and control.get('provenance') == candidate.get('provenance')
                         and control.get('code_manifest_sha256') == candidate.get('code_manifest_sha256')
                         and control.get('work_root') == candidate.get('work_root')
                         and sorted(control.get('fact_universe', [])) == sorted(candidate.get('fact_universe', [])))
            item = {'valid_paired_comparison': valid, 'required_equal_stages': list(required), 'stage_checks': checks,
                    'gains': None, 'losses': None, 'net_facts': None}
            if valid:
                before, after = set(map(tuple, control['found'])), set(map(tuple, candidate['found']))
                item.update(gains=[list(v) for v in sorted(after - before)], losses=[list(v) for v in sorted(before - after)],
                            net_facts=len(after) - len(before), complete_case_delta=candidate['all_found'] - control['all_found'])
            comparisons[f'{arm}-{budget}'] = item
    return {'schema_version': 1, 'scope': 'old selected DEV only; smoke is not full-dev completion',
            'variants': variants, 'comparisons': comparisons,
            'requested_runs_complete': bool(variants) and all(v['valid'] for v in variants.values()),
            'limitations': 'No observer acquisition claims; no fresh/holdout evaluation. Trace stages precede final wire. Independent span scorer is delivery authority.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('--out must be a new file; no existing evidence is overwritten')
    result = summarize_campaign(args.output_root)
    save(args.out, result)
    print(json.dumps({'requested_runs_complete': result['requested_runs_complete'], 'out': str(args.out)}))
    return 0 if result['requested_runs_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
