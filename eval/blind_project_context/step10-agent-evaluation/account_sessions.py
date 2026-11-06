"""Offline accounting only; never launch/poll agents or assign answer grades.

Run after an explicit completion notification. Incomplete historical attempts
can be accounted with --allow-incomplete; they never become quality baselines.
Manual per-fact/citation review remains necessary even when usage reconciles.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CASES = {'T01-en', 'T01-ru', 'T02-ru', 'T05-ru', 'T10-ru', 'T12-ru', 'T15-en', 'T19-ru'}


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def account(root, allow_incomplete=False, arm_filter=None, allowed_sessions=None):
    rows = []
    for path in sorted(root.glob('*/*/*.jsonl')):
        corpus, arm, case = path.parent.parent.name, path.parent.name, path.stem
        if arm_filter is not None and arm != arm_filter:
            continue
        if allowed_sessions is not None and (corpus,case) not in allowed_sessions:
            continue
        if corpus not in {'L0', 'L2'} or case not in CASES:
            raise ValueError(f'Unexpected non-dev session path: {path}')
        events, invalid_lines = [], []
        for number, line in enumerate(path.read_text().splitlines(), 1):
            try:
                events.append(json.loads(line))
            except ValueError:
                invalid_lines.append(number)
        receipt = read_json(path.with_suffix('.receipt.json'))
        session = read_json(path.with_suffix('.session.json'))
        state = (session or {}).get('data', {})
        steps = [e['part'] for e in events if e.get('type') == 'step_finish']
        tools = [e['part'] for e in events if e.get('type') == 'tool_use']
        text_events = [e for e in events if e.get('type') == 'text']
        usage = Counter()
        for step in steps:
            tokens = step['tokens']
            for key in ('input', 'output', 'reasoning'):
                usage[key] += tokens[key]
            for key in ('read', 'write'):
                usage['cache_'+key] += tokens['cache'][key]
        usage['input_with_cache'] = usage['input'] + usage['cache_read']
        usage['steps'] = len(steps)
        usage['top_level_tool_calls'] = len(tools)
        usage['top_level_tool_errors'] = sum(t['state'].get('status') == 'error' for t in tools)
        nested = []
        for tool in tools:
            metadata = tool['state'].get('metadata', {})
            nested.extend((metadata.get('metadata', {}) or {}).get('toolCalls', []))
        usage['reported_nested_tool_calls'] = len(nested)
        reconciled = bool(state.get('tokens'))
        if reconciled:
            expected = state['tokens']
            reconciled = all(usage[k] == expected[k] for k in ('input', 'output', 'reasoning'))
            reconciled &= all(usage['cache_'+k] == expected['cache'][k] for k in ('read', 'write'))
        step_totals = dict(usage)
        usage_source = 'reconciled_step_and_session' if reconciled else 'recorded_step_finish_events'
        # Interrupted CLI streams can omit the last step_finish while session
        # metadata already records its provider usage. Preserve both ledgers and
        # use the more complete persisted session totals rather than dropping it.
        if not reconciled and state.get('tokens') and receipt and receipt.get('censored'):
            reported = {k:state['tokens'][k] for k in ('input','output','reasoning')}
            reported.update({'cache_'+k:state['tokens']['cache'][k] for k in ('read','write')})
            if any(reported[k] < usage[k] for k in reported):
                raise ValueError(f'Conflicting censored token ledgers require inspection: {path}')
            usage.update({k:reported[k]-usage[k] for k in reported})
            usage['input_with_cache'] = usage['input'] + usage['cache_read']
            usage_source = 'persisted_session_metadata_exceeds_interrupted_event_stream'
        complete = bool(receipt and not receipt.get('censored') and receipt.get('exit') == 0
                        and state and reconciled and not invalid_lines and steps
                        and steps[-1].get('reason') == 'stop')
        if not complete and not allow_incomplete:
            raise ValueError(f'Incomplete/unreconciled session; do not grade as a completed run: {path}')
        artifact_hashes = {}
        for suffix in ('.jsonl', '.receipt.json', '.session.json', '.stderr'):
            artifact = path.with_suffix(suffix)
            if artifact.exists():
                artifact_hashes[artifact.name] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        rows.append({
            'corpus': corpus, 'arm': arm, 'case': case, 'model': state.get('model'),
            'receipt': receipt, 'session_outcome': state.get('outcome'),
            'completed_trajectory': complete, 'usage_reconciled': reconciled,
            'usage_source': usage_source, 'step_event_usage': step_totals,
            'session_reported_tokens': state.get('tokens'),
            'usage': dict(usage), 'artifact_hashes': artifact_hashes,
            'invalid_jsonl_lines': invalid_lines,
            'final_answer': text_events[-1]['part']['text'] if text_events else '',
            'commentary': [e['part']['text'] for e in text_events[:-1]],
            'tool_counts': dict(Counter(t['tool'] for t in tools)),
            'nested_tool_counts': dict(Counter(t.get('tool', 'unknown') for t in nested)),
            'tool_trace': tools,
            'step_usage': [{'reason': s.get('reason'), 'tokens': s['tokens']} for s in steps],
            'event_errors': [e for e in events if e.get('type') == 'error'],
            'grading_status': 'pending independent final-answer and source-citation review',
        })
    totals = Counter()
    for row in rows:
        totals.update(row['usage'])
    return {
        'schema_version': 1, 'source_root': str(root), 'sessions': rows,
        'summary': {'sessions': len(rows), 'completed_trajectories': sum(r['completed_trajectory'] for r in rows),
                    'usage': dict(totals)},
        'limitations': [
            'Completion/exit0/usage reconciliation does not establish answer quality or successful retrieval.',
            'Top-level and nested tool counts are separate; do not add them as independent product invocations.',
            'Censored usage uses persisted session totals when they exceed interrupted step-event totals; both ledgers are preserved. Still a lower bound for unrecorded in-flight work.',
            'Input_with_cache follows the historical analyzer: input plus cache_read; output and reasoning remain separate.',
            'This accounting helper never reads holdout questions, grades answers, launches sessions or polls completion.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-incomplete', action='store_true')
    parser.add_argument('--arm', help='Read only this arm; leave ongoing arms untouched')
    args = parser.parse_args()
    result = account(args.root, args.allow_incomplete, args.arm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
