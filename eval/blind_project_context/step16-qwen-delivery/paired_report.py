"""Offline paired-trace evidence; no production imports, scorer calls or gold injection."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

STAGES = ('raw_checked', 'post_prune', 'eligible')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def trace(path):
    events, errors = [], []
    if not path.exists():
        return events, ['trace missing']
    with path.open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError('event is not an object')
                if event.get('event') == 'pool_manifest':
                    for field in ('normalized_rows', 'normalized_snapshots'):
                        if digest(event[field]) != event[field + '_sha256']:
                            raise ValueError('manifest digest mismatch')
                    if event['row_count'] != len(event['normalized_rows']):
                        raise ValueError('row count mismatch')
                    # Full raw/snapshot evidence remains in the trace. After checking
                    # its canonical digest, reporting needs only row witnesses and hashes.
                    for field in ('raw_rows', 'raw_snapshots', 'normalized_snapshots'):
                        event.pop(field, None)
                events.append(event)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f'{number}: {exc}')
    return events, errors


def bind(events, run, questions, budget):
    """Bind only unique question+verified project identity, never occurrence guessing.

    run_id insertion order is chronological. L0 then L2 is checked per question;
    distinct worker project identities are reconstructed from recorded absolute roots.
    Empty groups lacking project identity intentionally stay unbound.
    """
    grouped = defaultdict(list)
    for event in events:
        grouped[event.get('run_id')].append(event)
    units = {u['name']: u for u in run.get('units', [])}
    records = defaultdict(list)
    for record in run.get('records', []):
        question = questions.get(record['case_id'])
        if question:
            records[question].append(record)
    bound, errors, chronology = {}, [], defaultdict(list)
    for rid, group in grouped.items():
        first = group[0]
        query = first.get('original_question')
        ids = {row['project_identity'] for e in group for row in
               e.get('normalized_rows', e.get('final_rows', [])) if row.get('project_identity')}
        matches = []
        for record in records.get(query, []):
            unit = units.get(record.get('unit'), {})
            root = unit.get('project_path')
            if not root or not Path(root).is_absolute() or unit.get('corpus') != record['corpus']:
                continue
            expected_id = 'local:' + hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
            if ids == {expected_id}:
                matches.append(record)
        if (len(matches) != 1 or not rid or
                any(e.get('original_question') != query or e.get('budget', {}).get('requested_cap') != budget for e in group)):
            errors.append({'run_id': rid, 'reason': 'ambiguous/missing record, project identity or budget'})
            continue
        record = matches[0]
        identity = (record['corpus'], record['case_id'])
        # All row paths must be relative sources under the recorded project root.
        rows = [row for e in group for row in e.get('normalized_rows', e.get('final_rows', []))]
        if any(not isinstance(r.get('path_or_url'), str) or Path(r['path_or_url']).is_absolute()
               or '..' in Path(r['path_or_url']).parts for r in rows):
            errors.append({'run_id': rid, 'reason': 'unvalidated source path'})
            continue
        if identity in bound:
            errors.append({'run_id': rid, 'reason': 'multiple calls/portions for record'})
            bound[identity] = None
        else:
            bound[identity] = group
        chronology[query].append(identity)
    for query, identities in chronology.items():
        if [i[0] for i in identities] != sorted(i[0] for i in identities):
            errors.append({'question': query, 'reason': 'not chronological L0 then L2'})
            for identity in identities:
                bound[identity] = None
    return bound, errors


def pool_check(left, right, receipt):
    checks, errors = [], []
    if not receipt:
        errors.append('pool comparison receipt missing')
    for identity in sorted(set(left) | set(right)):
        a, b = left.get(identity), right.get(identity)
        for stage in STAGES:
            x = [e for e in a or [] if e.get('event') == 'pool_manifest' and e.get('stage') == stage]
            y = [e for e in b or [] if e.get('event') == 'pool_manifest' and e.get('stage') == stage]
            equal = len(x) == len(y) == 1 and all(x[0][f] == y[0][f] for f in
                       ('normalized_rows_sha256', 'normalized_snapshots_sha256', 'row_count'))
            checks.append({'corpus': identity[0], 'case_id': identity[1], 'stage': stage, 'equal': equal})
    reported = (receipt or {}).get('comparisons', [])
    receipt_valid = (receipt or {}).get('same_checked_pools_verified') is True and bool(reported)
    receipt_valid = receipt_valid and {c.get('stage') for c in reported} == set(STAGES)
    receipt_valid = receipt_valid and all(c.get('equal') is True and c.get('pairs') and
        c.get('a_manifests') == c.get('b_manifests') == len(c['pairs']) and
        all(set(p.get('checks', {})) == {'normalized_rows_sha256', 'normalized_snapshots_sha256', 'row_count'}
            and all(v is True for v in p['checks'].values()) for p in c['pairs']) for c in reported)
    return {'verified': bool(checks) and all(c['equal'] for c in checks) and receipt_valid,
            'receipt_valid': bool(receipt_valid), 'checks': checks, 'errors': errors}


def funnel(group, quote):
    """Positive exact literal witnesses only. Absence is unknown (split spans possible)."""
    result = {}
    for stage in (*STAGES, 'final'):
        matching = [e for e in group or [] if
                    (e.get('event') == 'selection_output' if stage == 'final' else
                     e.get('event') == 'pool_manifest' and e.get('stage') == stage)]
        rows = matching[0].get('final_rows' if stage == 'final' else 'normalized_rows', []) if len(matching) == 1 else []
        witnesses = [{'path': r.get('path_or_url'), 'line_start': r.get('line_start'),
                      'line_end': r.get('line_end'), 'row_index': index}
                     for index, r in enumerate(rows) if quote and quote in r.get('snippet', '')]
        result[stage] = {'present': True if witnesses else None, 'witnesses': witnesses}
    # Decisions are bound to post-prune row indices, not to the reindexed
    # eligible manifest. Report observed witness-row decisions, not an inferred
    # exhaustive cause of fact loss when other/split witnesses may exist.
    indices = {w['row_index'] for w in result['post_prune']['witnesses']}
    result['post_prune']['witness_decisions'] = [
        {k: e.get(k) for k in ('decision', 'indices', 'group', 'priority', 'cost_bytes',
                              'selected_before', 'text_bytes', 'references_fit') if k in e}
        for e in group or [] if e.get('event') == 'selection_decision'
        and indices.intersection(e.get('indices', []))]
    scoring = [e for e in group or [] if e.get('event') == 'qwen_scoring']
    result['post_prune']['witness_qwen_scores'] = (
        {str(i): scoring[0]['row_scores'][i] for i in sorted(indices)
         if i < len(scoring[0].get('row_scores', []))} if len(scoring) == 1 else None)
    return result


def runtime(data):
    events = data['events']
    scoring = [e for e in events if e.get('event') == 'qwen_scoring']
    actual = [{'run_id': e.get('run_id'), 'receipt': e.get('actual_scorer_receipt'),
               'receipt_sha256': e.get('actual_scorer_receipt_sha256')} for e in scoring]
    errors = list(data['trace_errors'])
    for item in actual:
        if item['receipt'] is not None and digest(item['receipt']) != item['receipt_sha256']:
            errors.append('actual scorer receipt digest mismatch: ' + str(item['run_id']))
    def total(field):
        values = [e.get(field) for e in scoring]
        return sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
    run = data['run'] or {}
    fresh = [item['receipt'] for item in actual if item['receipt'] is not None]
    observed_totals = {field: sum(r.get(field, 0) for r in fresh) for field in
                       ('model_forwards', 'model_pairs', 'model_input_tokens', 'model_loads',
                        'inference_seconds', 'total_seconds', 'asset_verification_seconds')}
    observed_totals['peak_vram_allocated_bytes'] = max(
        (r.get('peak_vram_allocated_bytes', 0) for r in fresh), default=None)
    observed_totals['peak_vram_reserved_bytes'] = max(
        (r.get('peak_vram_reserved_bytes', 0) for r in fresh), default=None)
    return {'artifact_dir': str(data['dir']), 'trace': str(data['trace']),
            'observed_fresh_totals': observed_totals,
            'observed_fresh_totals_scope': 'Sum of actual fresh receipts in this trace only; cache-origin receipts excluded; summed durations are not wall time.',
            'run_manifest_available': data.get('run') is not None,
            'scope': 'Observed trace prefix only; not a completed-run aggregate unless run and score are complete',
            'trace_errors': errors, 'scoring_events': len(scoring),
            'cache_hits': total('cache_hits'), 'cache_misses': total('cache_misses'),
            'actual_scorer_receipts': actual,
            'cached_receipt_provenance': [{'run_id': e.get('run_id'),
                 'cached_scorer_receipts': e.get('cached_scorer_receipts'),
                 'row_input_sha256': e.get('row_input_sha256'),
                 'scoring_contract_sha256': e.get('scoring_contract_sha256'),
                 'adapter_recipe': e.get('adapter_recipe')} for e in scoring],
            'failures': [e for e in events if e.get('event') == 'qwen_failure'],
            'run_seconds': run.get('wall_seconds'), 'server_environment': run.get('server_environment'),
            'source_tree': run.get('source_tree'), 'cold_full_cost': None,
            'cost_complete': False,
            'note': 'Actual receipt and cache counters are read directly, never subtracted. Cached originating receipts are provenance, not additive runtime cost; initial smoke costs are separate. Cold full cost not measured.'}
