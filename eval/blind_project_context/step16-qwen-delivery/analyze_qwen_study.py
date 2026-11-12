"""Aggregate persisted Qwen study artifacts without running scoring or inference.

Score metrics are authoritative; parsed payload JSON is not a wire-size fallback.
Missing artifacts/observer evidence remain explicit unknowns, never successes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics
import tempfile
from datetime import datetime, timezone
import paired_report as paired

HERE = Path(__file__).resolve().parent
BLIND = HERE.parent
RUNS = Path('/home/viadmin/.local/share/docatlas-eval/step16')
VARIANTS = {f'{arm}-{budget}': f'{arm}@{budget}'
            for arm in ('A', 'B') for budget in (12000, 6000, 3000, 1500)}
RULE = 'max(o200k_tokens, ceil(UTF-8 bytes / 4)) <= 12000'


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None  # A running campaign may not have atomically completed this file.


def key(case: dict) -> tuple[str, str]:
    return case['corpus'], case['case_id']


def indexed(cases: list[dict]) -> dict:
    result = {key(case): case for case in cases}
    if len(result) != len(cases):
        raise ValueError('duplicate corpus/case identity')
    return result


def load_run(name: str, root: Path = RUNS) -> dict:
    out = root / name
    path = out.with_suffix('.jsonl')
    events, errors = paired.trace(path)
    return {'dir': out, 'score': read_json(out / 'score.json'),
            'run': read_json(out / 'run.json'), 'trace': path,
            'events': events, 'trace_errors': errors}


def payload_or_empty(case: dict, out: Path) -> dict:
    path = out / 'payloads' / case['corpus'] / f"{case['case_id']}.json"
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return {}


def acquisition_known(case: dict, record: dict, score: dict, run: dict) -> bool:
    events = [e for e in record.get('observer_events', []) if e.get('event') == 'acquisition']
    return bool(score.get('candidate_ranks') and run.get('observer')
                and run.get('observer_oracle_sha256') == score.get('oracle_sha256')
                and events and all(isinstance(e.get('fact_ranks'), dict) for e in events)
                and case.get('lost') is not None)


def fact_stage(case: dict, fact: dict, known: bool = False) -> str:
    if fact.get('found'):
        return 'delivered'
    if not known or fact.get('in_candidates') is None:
        return 'unknown'
    return 'lost_after_acquisition' if fact['in_candidates'] else 'not_acquired'


def continuation(payload: dict, record: dict) -> dict:
    more = payload.get('more_context') or {}
    offered = (isinstance(more.get('continuation_token'), str) and bool(more['continuation_token'])
               and type(more.get('next_portion')) is int and more['next_portion'] > 1)
    return {'offered': offered if payload else None,
            'next_portion': more.get('next_portion'), 'remaining_rows': more.get('remaining_rows'),
            'requested_by_client': bool(record.get('portions')) if record else None}


def q6_diagnostic(payload: dict) -> dict:
    # Inspect only actually delivered source text, never path/metadata strings.
    # Complete-rule evidence requires all three parts within one delivered row.
    texts = []
    columns = payload.get('source_columns') or []
    for row in payload.get('sources') or []:
        if isinstance(row, list) and 'text' in columns and len(row) > columns.index('text'):
            text = row[columns.index('text')]
        elif isinstance(row, dict):
            text = row.get('snippet') or row.get('text')
        else:
            text = None
        if isinstance(text, str):
            texts.append(' '.join(text.split()))
    parts = [(RULE in text, 'compact output' in text, 'canonical fallback' in text) for text in texts]
    return {'available': bool(payload), 'source_text_rows': len(texts),
            'rule_present': any(p[0] for p in parts) if payload else None,
            'condition_compact_present': any(p[1] for p in parts) if payload else None,
            'condition_canonical_present': any(p[2] for p in parts) if payload else None,
            'complete_rule_in_one_source_row': any(all(p) for p in parts) if payload else None,
            'note': 'Positive literal source-row diagnostic only, separate from budget compliance and sealed facts.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-root', type=Path, default=RUNS / 'paired-campaign')
    parser.add_argument('--output-dir', type=Path, help='Temporary review output; defaults to a fresh /tmp directory')
    parser.add_argument('--variant-path', action='append', default=[], metavar='A-1500=/path/to/run', help='Explicit smoke/paired artifact override; never mixes legacy defaults')
    parser.add_argument('--pool-path', action='append', default=[], metavar='1500=/path/to/pools.json')
    parser.add_argument('--initial-smoke-trace', action='append', type=Path, default=[])
    parser.add_argument('--variants', nargs='+', choices=list(VARIANTS), default=list(VARIANTS))
    args = parser.parse_args()
    baseline = read_json(BLIND / 'baseline' / 'score.json')
    expected = indexed(baseline['cases'])
    universe = {(c['corpus'], c['case_id'], f['fact_id']): c
                for c in baseline['cases'] for f in c['facts']}
    if len(universe) != 260 or len(expected) != 96:
        raise ValueError(f'Unexpected baseline universe: {len(universe)} facts / {len(expected)} cases')
    overrides = dict(value.split('=', 1) for value in args.variant_path)
    pool_paths = dict(value.split('=', 1) for value in args.pool_path)
    if set(overrides) - set(VARIANTS):
        parser.error('unknown variant override')
    args.output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix='qwen-report-review-'))
    loaded = {VARIANTS[name]: load_run(Path(overrides.get(name, str(args.runs_root / name))).name,
                Path(overrides.get(name, str(args.runs_root / name))).parent) for name in args.variants}
    questions = {c['id']: c['question'] for c in read_json(BLIND / 'questions.json')['cases']}
    quotes = {f['fact_id']: f['quote'] for t in read_json(BLIND / 'oracle.json')['topics'] for f in t['facts']}
    for label, data in loaded.items():
        expected_arm = 'B' if label.startswith('B@') else 'A0'
        if any(e.get('arm') != expected_arm for e in data['events']):
            data['trace_errors'].append('trace arm mismatch')
        data['bound'], data['binding_errors'] = paired.bind(data['events'], data['run'] or {}, questions, int(label.split('@')[1]))
    rows = {identity: {k: c[k] for k in ('case_id', 'topic_id', 'split', 'lang', 'corpus')} | {'fact_id': identity[2]}
            for identity, c in sorted(universe.items())}
    report = {'schema_version': 3, 'sealed_universe': 260, 'expected_cases': 96,
              'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'temporary_pending_lead_review',
              'campaign_root': str(args.runs_root),
              'scope': 'Paired native campaign only; incomplete variants retained but excluded from comparisons.',
              'external_baseline': {'path': str(RUNS / 'recovered'), 'included': False},
              'excluded': 'Old minimal-context B and recovered A are not paired campaign observations.',
              'funnel_limitations': 'No observer: prior A acquisition rank/not_acquired unavailable. Offline exact single-row quote witnesses only; absent/split/ambiguous spans remain null, never not_acquired. Final trace rows are before host finalization; sealed delivery score is authoritative.',
              'budget_rule': 'max(o200k_tokens, ceil(utf8_bytes / 4)) <= budget',
              'metric_source': 'score.json only; no reconstructed payload wire fallback',
              'variants': {}}
    columns = ['case_id', 'topic_id', 'split', 'lang', 'corpus', 'fact_id']
    for label, data in loaded.items():
        columns += [f'{label}_stage', f'{label}_candidate_rank', f'{label}_continuation_offered', f'{label}_continuation_requested']
        columns += [f'{label}_{s}_quote_present' for s in (*paired.STAGES, 'final')]
        columns += [f'{label}_witness_decisions', f'{label}_witness_qwen_scores']
        score, run = data['score'] or {}, data['run'] or {}
        cases, records = indexed(score.get('cases', [])), indexed(run.get('records', []))
        budget = int(label.split('@')[1])
        per_case, stages = {}, Counter()
        for identity, original in expected.items():
            case, record = cases.get(identity), records.get(identity, {})
            payload = payload_or_empty(original, data['dir'])
            known = acquisition_known(case, record, score, run) if case else False
            facts = {f['fact_id']: f for f in (case or {}).get('facts', [])}
            cont = continuation(payload, record)
            for expected_fact in original['facts']:
                fid = expected_fact['fact_id']
                fact = facts.get(fid)
                stage = fact_stage(case, fact, known) if fact else ('missing_fact' if case else 'missing_case')
                stages[stage] += 1
                row = rows[(*identity, fid)]
                offline = paired.funnel(data['bound'].get(identity), quotes.get(fid))
                row.update({f'{label}_{s}_quote_present': offline[s]['present'] for s in offline})
                row[f'{label}_witness_decisions'] = json.dumps(offline['post_prune']['witness_decisions'], ensure_ascii=False)
                row[f'{label}_witness_qwen_scores'] = json.dumps(offline['post_prune']['witness_qwen_scores'], ensure_ascii=False)
                row.update({f'{label}_stage': stage,
                            f'{label}_candidate_rank': fact.get('candidate_rank') if fact and known else None,
                            f'{label}_continuation_offered': cont['offered'],
                            f'{label}_continuation_requested': cont['requested_by_client']})
            case = case or {}
            tokens, size = case.get('o200k_tokens'), case.get('utf8_bytes')
            measured = all(type(v) is int and v >= 0 for v in (tokens, size))
            cost = max(tokens, (size + 3) // 4) if measured else None
            fact_complete = (set(facts) == {f['fact_id'] for f in original['facts']}
                             and len(facts) == len(case.get('facts', []))
                             and all(type(f.get('found')) is bool for f in facts.values()))
            per_case['/'.join(identity)] = {
                'corpus': identity[0], 'case_id': identity[1], 'score_available': bool(case),
                'record_available': bool(record), 'payload_available': bool(payload),
                'fact_results_complete': fact_complete, 'acquisition_known': known,
                'facts_found': case.get('facts_found'), 'facts_total': case.get('facts_total'),
                'o200k_tokens': tokens, 'utf8_bytes': size, 'delivery_budget_cost': cost,
                'within_budget': cost <= budget if measured else None,
                'anomalies': case.get('anomalies'), 'record_error': record.get('is_error'),
                 'trace_run_ids': list({e['run_id'] for e in data['bound'].get(identity) or []}),
                 'offline_funnel': {f['fact_id']: paired.funnel(data['bound'].get(identity), quotes.get(f['fact_id'])) for f in original['facts']},
                 'q6_rule_presence': q6_diagnostic(payload), **cont}
        values = list(per_case.values())
        complete = (set(cases) == set(expected) and set(records) == set(expected)
                    and all(v['fact_results_complete'] and v['payload_available'] for v in values))
        metric_complete = all(v['within_budget'] is not None for v in values)
        anomalies = score.get('anomalies')
        unknown = sum(stages[s] for s in ('unknown', 'missing_fact', 'missing_case'))
        tokens = [v['o200k_tokens'] for v in values if v['o200k_tokens'] is not None]
        report['variants'][label] = {
            'artifact_dir': str(data['dir']), 'score_available': data['score'] is not None,
             'provenance': {k: score.get(k) for k in ('questions_sha256', 'oracle_sha256', 'scorer_sha256')},
             'run_metadata': {k: run.get(k) for k in ('started_at_utc', 'wall_seconds', 'jobs', 'observer', 'observer_oracle_sha256', 'work_root', 'reused_work', 'units', 'server_environment')},
             'source_tree': run.get('source_tree'),
            'run_available': data['run'] is not None, 'artifacts_complete': complete,
            'budget_metrics_complete': metric_complete, 'acquisition_complete': all(v['acquisition_known'] for v in values),
            'funnel_complete': unknown == 0, 'anomalies': anomalies,
            'valid_for_descriptive_reporting': complete and metric_complete and anomalies == [] and all(v['anomalies'] == [] and v['record_error'] is False and v['within_budget'] is True for v in values),
            'valid_for_comparison': False,
            'same_checked_pool_verified': False,
            'comparison_limitation': 'No frozen paired candidate-pool manifests establish identical checked inputs for A and B; descriptive completeness is not controlled selector validity.',
            'found_total': stages['delivered'] if cases else None, 'total': 260,
            'not_acquired': stages['not_acquired'] if unknown == 0 else None,
            'dropped_after_acquisition': stages['lost_after_acquisition'] if unknown == 0 else None,
            'stage_counts': dict(stages), 'slices': score.get('slices'),
            'slices_note': 'Raw scorer slices; acquisition totals may be unreliable when observer events are missing. Use stage_counts.',
            'delivery_budget_tokens': budget,
            'cases_over_budget': sum(v['within_budget'] is False for v in values),
            'cases_budget_unknown': sum(v['within_budget'] is None for v in values),
            'all_cases_within_budget': all(v['within_budget'] for v in values) if metric_complete else None,
            'o200k_tokens_median': statistics.median(tokens) if tokens else None,
            'o200k_tokens_sum': sum(tokens) if metric_complete else None,
             'utf8_bytes_sum': sum(v['utf8_bytes'] for v in values) if metric_complete else None,
             'utf8_bytes_median': statistics.median(v['utf8_bytes'] for v in values) if metric_complete else None,
            'unexpected_cases': ['/'.join(k) for k in sorted(set(cases) - set(expected))],
            'per_case': per_case}
        print(f'{label}: {len(cases)} scored cases; {dict(stages)}; complete={complete}')
    gate_a = loaded.get('A@12000', {})
    prior_path = RUNS / 'recovered' / 'A-12000' / 'score.json'
    prior = read_json(prior_path)
    def fact_slices(score):
        result = Counter()
        for c in (score or {}).get('cases', []):
            label = '/'.join(c[field] for field in ('split', 'corpus', 'lang'))
            result[label + '/facts_found'] += sum(f.get('found') is True for f in c.get('facts', []))
            result[label + '/all_found'] += bool(c.get('all_found'))
        return dict(result)
    gate_score = gate_a.get('score')
    gate_total = sum(f.get('found') is True for c in (gate_score or {}).get('cases', []) for f in c.get('facts', [])) if gate_score else None
    report['A12000_gate'] = {'prior_baseline_path': str(prior_path), 'external_not_pooled': True,
        'found_total': gate_total, 'expected_found_total': 176,
        'slice_parity': fact_slices(gate_score) == fact_slices(prior) if gate_score and prior else None,
        'scope': 'Delivered fact slices only; no-observer acquisition ranks cannot be compared.'}
    gate_pass = bool(gate_total == 176 and report['A12000_gate']['slice_parity'] is True and
        report['variants'].get('A@12000', {}).get('valid_for_descriptive_reporting'))
    report['A12000_gate']['passed'] = gate_pass
    report['paired_budgets'] = {}
    for budget in sorted({int(label.split('@')[1]) for label in loaded}, reverse=True):
        a, b = loaded.get(f'A@{budget}'), loaded.get(f'B@{budget}')
        pool_path = Path(pool_paths.get(str(budget), str(args.runs_root / f'pools-{budget}.json')))
        check = paired.pool_check((a or {}).get('bound', {}), (b or {}).get('bound', {}), read_json(pool_path))
        check['receipt_path'] = str(pool_path)
        check['complete_case_binding'] = bool(a and b and set(a['bound']) == set(expected) == set(b['bound']) and
            all(a['bound'].values()) and all(b['bound'].values()))
        clean = bool(a and b and not any(d['trace_errors'] or d['binding_errors'] for d in (a, b)))
        arun, brun = (a or {}).get('run') or {}, (b or {}).get('run') or {}
        def native_protocol(run, arm):
            env = run.get('server_environment') or {}
            return (run.get('observer') is False and run.get('observer_oracle_sha256') is None and
                    run.get('jobs') == 2 and (arm == 'A' or run.get('reused_work') is True) and
                    env.get('DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT', '0') == '0' and
                    (env.get('DOCATLAS_EXPERIMENT_PAIRED_QWEN') == '1' if arm == 'B' else env.get('DOCATLAS_EXPERIMENT_PAIRED_QWEN') != '1'))
        check['native_protocol_verified'] = native_protocol(arun, 'A') and native_protocol(brun, 'B')
        ascore, bscore = (a or {}).get('score') or {}, (b or {}).get('score') or {}
        check['scoring_provenance_equal'] = all(ascore.get(k) and ascore.get(k) == bscore.get(k) for k in ('questions_sha256', 'oracle_sha256', 'scorer_sha256'))
        check['question_provenance_equal'] = bool(ascore.get('questions_sha256') and ascore.get('questions_sha256') == arun.get('questions_sha256') == brun.get('questions_sha256'))
        acode, bcode = arun.get('source_tree', {}).get('code_sha256', {}), brun.get('source_tree', {}).get('code_sha256', {})
        check['selector_code_equal'] = all(acode.get(k) and acode.get(k) == bcode.get(k) for k in (
            'docmancer/docs/application/experimental_qwen_checked_pool.py',
            'docmancer/docs/application/joint_context_selection.py'))
        check['A12000_gate_passed'] = gate_pass
        try:
            gate_run = gate_a.get('run') or {}
            completed = datetime.fromisoformat(gate_run['started_at_utc']).timestamp() + gate_run['wall_seconds']
            check['A12000_completed_before_B'] = completed <= datetime.fromisoformat(brun['started_at_utc']).timestamp()
        except (KeyError, TypeError, ValueError):
            check['A12000_completed_before_B'] = None
        valid = check['verified'] and check['complete_case_binding'] and clean and gate_pass and check['native_protocol_verified'] and check['scoring_provenance_equal'] and check['question_provenance_equal'] and check['selector_code_equal'] and check['A12000_completed_before_B'] is True and all(
            report['variants'].get(f'{arm}@{budget}', {}).get('valid_for_descriptive_reporting') for arm in ('A', 'B'))
        check['valid_for_comparison'] = bool(valid)
        def delivered_ids(scored):
            return {(c['corpus'], c['case_id'], f['fact_id'])
                    for c in scored.get('cases', []) for f in c.get('facts', []) if f.get('found')}
        if valid:
            before, after = delivered_ids(ascore), delivered_ids(bscore)
            check['delivered_fact_changes'] = {
                'a_found': len(before), 'b_found': len(after), 'net_delta': len(after) - len(before),
                'saved_count': len(after - before), 'regressed_count': len(before - after),
                'saved_fact_cases': [list(item) for item in sorted(after - before)],
                'regressed_fact_cases': [list(item) for item in sorted(before - after)]}
        else:
            check['delivered_fact_changes'] = None
        report['paired_budgets'][str(budget)] = check
        for arm in ('A', 'B'):
            label = f'{arm}@{budget}'
            if label in loaded:
                report['variants'][label].update(same_checked_pool_verified=check['verified'] and clean,
                    valid_for_comparison=bool(valid), trace_errors=loaded[label]['trace_errors'],
                    binding_errors=loaded[label]['binding_errors'],
                    comparison_limitation='Requires both complete 96-case/260-fact variants, every budget metric/anomaly check, unambiguous trace binding and all three pool stages. Smoke is not campaign completeness.')
    report['completed_paired_budgets'] = [int(k) for k, v in report['paired_budgets'].items() if v['valid_for_comparison']]
    report['campaign_complete'] = set(report['completed_paired_budgets']) == {12000, 6000, 3000, 1500}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'funnel_by_fact_case.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: 'null' if v is None else v for k, v in row.items()} for row in rows.values())
    smoke_sources = []
    for path in args.initial_smoke_trace:
        events, errors = paired.trace(path)
        smoke_sources.append(paired.runtime({'events': events, 'trace_errors': errors, 'trace': path, 'dir': path.parent, 'run': None}))
    receipt = {'schema_version': 3, 'status': 'temporary_pending_lead_review',
               'scope': 'Persisted paired B actual receipts and direct cache counters only; no inference performed',
               'initial_smoke_sources': smoke_sources or None,
               'initial_smoke_sources_note': 'Supply --initial-smoke-trace explicitly; absence does not mean zero preparation/cache-origin cost.',
               'per_run': {label: paired.runtime(data) for label, data in loaded.items() if label.startswith('B@')}}
    for filename, content in [('facts_by_budget.json', report), ('qwen_runtime_receipt.json', receipt)]:
        (args.output_dir / filename).write_text(json.dumps(content, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'Wrote 260 funnel rows and 96 per-case entries per variant to {args.output_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
